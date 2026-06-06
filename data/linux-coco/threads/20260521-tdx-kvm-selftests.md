---
title: 'TDX KVM selftests'
date: 2026-05-21
last_reply: 2026-06-05
message_count: 31
participants: ['Lisa Wang', 'Yosry Ahmed', 'Sean Christopherson', 'Ackerley Tng']
---

## [1] Lisa Wang — 2026-05-21

This patch series focuses on setting up a TDX VM and adding all code
necessary to run a basic lifecycle test.

Unlike standard KVM selftests can set up the VM through guest registers,
TDX module protects TDs' register state from the host. This feature of
TDX causes problems on VM boot state initialization and the ucall
implementation.

In standard KVM selftests, the host directly initializes the guest state
by manipulating Special Registers (SREGs) and General Purpose Registers
(GPRs) via IOCTLs (KVM_SET_SREGS, etc.) before the first KVM_RUN.

To bypass direct register initialization by the host, we utilize the
standard x86 reset vector as the default entry point.

The mechanism works as follows:
1. The host places register values into a specific memory region and
   inserts boot code at the VM's default starting point.
2. When the VM starts, it executes this boot code to "pull" values from
   memory and manually set up its own SREGs and GPRs.
3. Once the environment is ready, the boot code jumps to the guest code.

The standard x86 ucall() implementation uses PIO, but it does not
actually transmit data through the 4-byte PIO data. Instead, it relies
on the host reading the ucall address directly from the guest's RDI
register.

TDX selftests cannot utilize the standard x86 ucall implementation,
because the host is unable to access the guest's RDI register. Based on
this restriction, we considered these potential solutions for the TDX
ucall implementation.

1. TDCALL PIO with RCX-bits Passthrough
We first considered passing the RDI value through RCX bits to bypass the
hardware's register protection, which could be the closest approach to
the non-TDX implementation as per Sean's suggestion[1]. However, this
approach is blocked by the software-side implementation: KVM_GET_REGS
currently does not support TDX VMs and returns -EINVAL. To make this
work, the KVM ioctl would need a test-only hack.

2. TDCALL PIO with buffer indexing
To keep a PIO-based approach and unify the get_ucall implementation for
both TDX and non-TDX VMs, we considered TDCALL PIO with buffer indexing.
Since the ucall buffer is initialized prior to execution, the VM could
just pass a buffer index rather than an 8-byte ucall address to fit
within the 4-byte PIO data limit. The host, already knowing the ucall
buffer's base address, could then resolve the ucall content via this
index. We abandoned this solution because it would require changes to
the common ucall structure and impact other non-x86 architectures.

3. TDCALL MMIO (Selected solution)
We ultimately selected TDCALL with an 8-byte MMIO data. This method only
requires initializing an MMIO GPA and adding TDCALL MMIO implementation
for TDX under the original x86 ucall path. While this diverges from the
non-TDX PIO, it provides the cleanest implementation with minimal
disruption to the overall ucall architecture.

4. A note on #VE and x86 ucall simplification
It is worth noting that the use of a Virtualization Exception (#VE)
is orthogonal to the PIO vs. MMIO discussion; rather, it is a question
of how much we want to simplify the x86 ucall implementation. A #VE
handler is one option to allow VMs use PIO/MMIO identical to the
non-TDX case. Alternatively, having an MMIO_WRITE wrapper macro, as Sean
suggested[2], is another option. Either way, discussion for this is
likely a premature optimization right now, since the PIO/MMIO call is
only used under ucall_arch_do_ucall(), and standard and TDX VMs use
different ones now. We should optimize this in the future, but for now,
invoking TDCALL directly is more robust and concise.

v13 revision for TDX KVM selftests based on kvm/next and guest_memfd:
In-place conversion support[3]. For ease of testing, this series is also
available at: https://github.com/googleprodkernel/linux-cc/commits/tdx-selftests-v13

Changes from v12[4]:
1. Fixed some bugs, including typo, commit order and commit messages.
2. Inlined the TDCALL to tdx.c file.
3. Refactored the Makefile to use pattern rules for generic source
   compilation while ensuring build artifacts are directed to the target
   output directory.

Series is organized by:
1. Patches 1 - 4: Initialize the TDX VM
2. Patches 5 - 8: Add the TDX boot code
3. Patches 9 - 13: Set up the boot region
4. Patches 14 - 17: Set up the vCPU
5. Patches 18 - 19: Finalize the TDX VM
6. Patches 20 - 22: Implement the ucall and run the TDX test

[1]: https://lore.kernel.org/kvm/aQTcDH9LRezI30dm@google.com/
[2]: https://lore.kernel.org/kvm/aQTSdk3JtFu1qOMj@google.com/
[3]: https://lore.kernel.org/all/20260507-gmem-inplace-conversion-v6-0-91ab5a8b19a4@google.com/T/
[4]: https://lore.kernel.org/kvm/20251028212052.200523-1-sagis@google.com/

Signed-off-by: Lisa Wang <wyihan@google.com>
---
Ackerley Tng (2):
      KVM: selftests: Add helpers to init TDX memory and finalize VM
      KVM: selftests: Add ucall support for TDX

Erdem Aktas (2):
      KVM: selftests: Add TDX boot code
      KVM: selftests: Implement MMIO WRITE for the TDX VM

Isaku Yamahata (2):
      KVM: selftests: Update kvm_init_vm_address_properties() for TDX
      KVM: selftests: TDX: Use KVM_TDX_CAPABILITIES to validate TDs' attribute configuration

Lisa Wang (2):
      KVM: selftests: Back the first memory region with guest_memfd for TDX
      KVM: selftests: Set first memory region as shared if guest_memfd

Sagi Shahar (13):
      KVM: selftests: Initialize the TDX VM
      KVM: selftests: Expose segment definitions to assembly files
      tools: include: Add kbuild.h for assembly structure offsets
      KVM: selftests: Introduce structures for TDX guest boot parameters
      KVM: selftests: Expose functions to get default sregs values
      KVM: selftests: Set up TDX boot code region
      KVM: selftests: Set up TDX boot parameters region
      KVM: selftests: Expose function to allocate vCPU stack
      KVM: selftests: Call KVM_TDX_INIT_VCPU when creating a new TDX vcpu
      KVM: selftests: Load per-vCPU guest stack in TDX boot parameters
      KVM: selftests: Set entry point for TDX guest code
      KVM: selftests: Finalize TD memory as part of kvm_arch_vm_finalize_vcpus
      KVM: selftests: Add TDX lifecycle test

Sean Christopherson (1):
      KVM: selftests: Add macros to simplify creating VM shapes for non-default types

 tools/include/linux/kbuild.h                       |  11 +
 tools/testing/selftests/kvm/.gitignore             |   3 +-
 tools/testing/selftests/kvm/Makefile.kvm           |  33 +-
 tools/testing/selftests/kvm/include/kvm_util.h     |  13 +
 .../testing/selftests/kvm/include/x86/processor.h  |  40 +++
 .../selftests/kvm/include/x86/processor_asm.h      |  12 +
 tools/testing/selftests/kvm/include/x86/sev.h      |   2 -
 .../selftests/kvm/include/x86/tdx/td_boot.h        |  74 +++++
 .../selftests/kvm/include/x86/tdx/td_boot_asm.h    |  16 +
 tools/testing/selftests/kvm/include/x86/tdx/tdx.h  |  16 +
 .../selftests/kvm/include/x86/tdx/tdx_util.h       |  80 +++++
 tools/testing/selftests/kvm/include/x86/ucall.h    |   6 -
 tools/testing/selftests/kvm/lib/kvm_util.c         |  18 +-
 tools/testing/selftests/kvm/lib/x86/processor.c    | 107 ++++---
 tools/testing/selftests/kvm/lib/x86/sev.c          |  16 -
 tools/testing/selftests/kvm/lib/x86/tdx/td_boot.S  |  60 ++++
 .../selftests/kvm/lib/x86/tdx/td_boot_offsets.c    |  21 ++
 tools/testing/selftests/kvm/lib/x86/tdx/tdx.c      |  30 ++
 tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c | 334 +++++++++++++++++++++
 tools/testing/selftests/kvm/lib/x86/ucall.c        |  30 ++
 tools/testing/selftests/kvm/x86/sev_smoke_test.c   |  40 +--
 tools/testing/selftests/kvm/x86/tdx_vm_test.c      |  33 ++
 22 files changed, 907 insertions(+), 88 deletions(-)
---
base-commit: cd1b71113e3f70f0a1a3d61550cf89f1eed379c4
change-id: 20260508-tdx-selftests-v13-bf00ad0cb8fe

Best regards,

---

## [2] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 01/22] KVM: selftests: Add macros to simplify creating VM
 shapes for non-default types*

From: Sean Christopherson <seanjc@google.com>

Add VM_TYPE() and __VM_TYPE() macros to create a vm_shape structure given
a type (and mode), and use the macros to define VM_SHAPE_{SEV,SEV_ES,SNP}
shapes for x86's SEV family of VM shapes.  Providing common infrastructure
will avoid having to copy+paste vm_sev_create_with_one_vcpu() for TDX.

Use the new SEV+ shapes and drop vm_sev_create_with_one_vcpu().

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/include/kvm_util.h     | 13 +++++++
 .../testing/selftests/kvm/include/x86/processor.h  |  4 +++
 tools/testing/selftests/kvm/include/x86/sev.h      |  2 --
 tools/testing/selftests/kvm/lib/x86/sev.c          | 16 ---------
 tools/testing/selftests/kvm/x86/sev_smoke_test.c   | 40 +++++++++++-----------
 5 files changed, 37 insertions(+), 38 deletions(-)

diff --git a/tools/testing/selftests/kvm/include/kvm_util.h b/tools/testing/selftests/kvm/include/kvm_util.h
index dc70c6da63fa..041bdbfb93f7 100644
--- a/tools/testing/selftests/kvm/include/kvm_util.h
+++ b/tools/testing/selftests/kvm/include/kvm_util.h
@@ -233,6 +233,19 @@ kvm_static_assert(sizeof(struct vm_shape) == sizeof(u64));
 	shape;					\
 })
 
+#define __VM_TYPE(__mode, __type)		\
+({						\
+	struct vm_shape shape = {		\
+		.mode = (__mode),		\
+		.type = (__type)		\
+	};					\
+						\
+	shape;					\
+})
+
+#define VM_TYPE(__type)				\
+	__VM_TYPE(VM_MODE_DEFAULT, __type)
+
 extern enum vm_guest_mode vm_mode_default;
 
 #if defined(__aarch64__)
diff --git a/tools/testing/selftests/kvm/include/x86/processor.h b/tools/testing/selftests/kvm/include/x86/processor.h
index 77f576ee7789..0aa6eecfcbde 100644
--- a/tools/testing/selftests/kvm/include/x86/processor.h
+++ b/tools/testing/selftests/kvm/include/x86/processor.h
@@ -365,6 +365,10 @@ static inline unsigned int x86_model(unsigned int eax)
 	return ((eax >> 12) & 0xf0) | ((eax >> 4) & 0x0f);
 }
 
+#define VM_SHAPE_SEV		VM_TYPE(KVM_X86_SEV_VM)
+#define VM_SHAPE_SEV_ES		VM_TYPE(KVM_X86_SEV_ES_VM)
+#define VM_SHAPE_SNP		VM_TYPE(KVM_X86_SNP_VM)
+
 #define PHYSICAL_PAGE_MASK      GENMASK_ULL(51, 12)
 
 #define PAGE_SHIFT		12
diff --git a/tools/testing/selftests/kvm/include/x86/sev.h b/tools/testing/selftests/kvm/include/x86/sev.h
index 1af44c151d60..944c59dbe510 100644
--- a/tools/testing/selftests/kvm/include/x86/sev.h
+++ b/tools/testing/selftests/kvm/include/x86/sev.h
@@ -53,8 +53,6 @@ void snp_vm_launch_start(struct kvm_vm *vm, u64 policy);
 void snp_vm_launch_update(struct kvm_vm *vm);
 void snp_vm_launch_finish(struct kvm_vm *vm);
 
-struct kvm_vm *vm_sev_create_with_one_vcpu(u32 type, void *guest_code,
-					   struct kvm_vcpu **cpu);
 void vm_sev_launch(struct kvm_vm *vm, u64 policy, u8 *measurement);
 
 kvm_static_assert(SEV_RET_SUCCESS == 0);
diff --git a/tools/testing/selftests/kvm/lib/x86/sev.c b/tools/testing/selftests/kvm/lib/x86/sev.c
index 93f916903461..95d8520eea34 100644
--- a/tools/testing/selftests/kvm/lib/x86/sev.c
+++ b/tools/testing/selftests/kvm/lib/x86/sev.c
@@ -158,22 +158,6 @@ void snp_vm_launch_finish(struct kvm_vm *vm)
 	vm_sev_ioctl(vm, KVM_SEV_SNP_LAUNCH_FINISH, &launch_finish);
 }
 
-struct kvm_vm *vm_sev_create_with_one_vcpu(u32 type, void *guest_code,
-					   struct kvm_vcpu **cpu)
-{
-	struct vm_shape shape = {
-		.mode = VM_MODE_DEFAULT,
-		.type = type,
-	};
-	struct kvm_vm *vm;
-	struct kvm_vcpu *cpus[1];
-
-	vm = __vm_create_with_vcpus(shape, 1, 0, guest_code, cpus);
-	*cpu = cpus[0];
-
-	return vm;
-}
-
 void vm_sev_launch(struct kvm_vm *vm, u64 policy, u8 *measurement)
 {
 	if (is_sev_snp_vm(vm)) {
diff --git a/tools/testing/selftests/kvm/x86/sev_smoke_test.c b/tools/testing/selftests/kvm/x86/sev_smoke_test.c
index 1a49ee391586..fe2c438882ae 100644
--- a/tools/testing/selftests/kvm/x86/sev_smoke_test.c
+++ b/tools/testing/selftests/kvm/x86/sev_smoke_test.c
@@ -104,7 +104,7 @@ static void compare_xsave(u8 *from_host, u8 *from_guest)
 		abort();
 }
 
-static void test_sync_vmsa(u32 type, u64 policy)
+static void test_sync_vmsa(struct vm_shape shape, u64 policy)
 {
 	struct kvm_vcpu *vcpu;
 	struct kvm_vm *vm;
@@ -114,7 +114,7 @@ static void test_sync_vmsa(u32 type, u64 policy)
 	double x87val = M_PI;
 	struct kvm_xsave __attribute__((aligned(64))) xsave = { 0 };
 
-	vm = vm_sev_create_with_one_vcpu(type, guest_code_xsave, &vcpu);
+	vm = vm_create_shape_with_one_vcpu(shape, &vcpu, guest_code_xsave);
 	gva = vm_alloc_shared(vm, PAGE_SIZE, KVM_UTIL_MIN_VADDR,
 			      MEM_REGION_TEST_DATA);
 	hva = addr_gva2hva(vm, gva);
@@ -150,13 +150,13 @@ static void test_sync_vmsa(u32 type, u64 policy)
 	kvm_vm_free(vm);
 }
 
-static void test_sev(void *guest_code, u32 type, u64 policy)
+static void test_sev(void *guest_code, struct vm_shape shape, u64 policy)
 {
 	struct kvm_vcpu *vcpu;
 	struct kvm_vm *vm;
 	struct ucall uc;
 
-	vm = vm_sev_create_with_one_vcpu(type, guest_code, &vcpu);
+	vm = vm_create_shape_with_one_vcpu(shape, &vcpu, guest_code);
 
 	/* TODO: Validate the measurement is as expected. */
 	vm_sev_launch(vm, policy, NULL);
@@ -201,12 +201,12 @@ static void guest_shutdown_code(void)
 	__asm__ __volatile__("ud2");
 }
 
-static void test_sev_shutdown(u32 type, u64 policy)
+static void test_sev_shutdown(struct vm_shape shape, u64 policy)
 {
 	struct kvm_vcpu *vcpu;
 	struct kvm_vm *vm;
 
-	vm = vm_sev_create_with_one_vcpu(type, guest_shutdown_code, &vcpu);
+	vm = vm_create_shape_with_one_vcpu(shape, &vcpu, guest_shutdown_code);
 
 	vm_sev_launch(vm, policy, NULL);
 
@@ -218,28 +218,28 @@ static void test_sev_shutdown(u32 type, u64 policy)
 	kvm_vm_free(vm);
 }
 
-static void test_sev_smoke(void *guest, u32 type, u64 policy)
+static void test_sev_smoke(void *guest, struct vm_shape shape, u64 policy)
 {
 	const u64 xf_mask = XFEATURE_MASK_X87_AVX;
 
-	if (type == KVM_X86_SNP_VM)
-		test_sev(guest, type, policy | SNP_POLICY_DBG);
+	if (shape.type == KVM_X86_SNP_VM)
+		test_sev(guest, shape, policy | SNP_POLICY_DBG);
 	else
-		test_sev(guest, type, policy | SEV_POLICY_NO_DBG);
-	test_sev(guest, type, policy);
+		test_sev(guest, shape, policy | SEV_POLICY_NO_DBG);
+	test_sev(guest, shape, policy);
 
-	if (type == KVM_X86_SEV_VM)
+	if (shape.type == KVM_X86_SEV_VM)
 		return;
 
-	test_sev_shutdown(type, policy);
+	test_sev_shutdown(shape, policy);
 
 	if (kvm_has_cap(KVM_CAP_XCRS) &&
 	    (xgetbv(0) & kvm_cpu_supported_xcr0() & xf_mask) == xf_mask) {
-		test_sync_vmsa(type, policy);
-		if (type == KVM_X86_SNP_VM)
-			test_sync_vmsa(type, policy | SNP_POLICY_DBG);
+		test_sync_vmsa(shape, policy);
+		if (shape.type == KVM_X86_SNP_VM)
+			test_sync_vmsa(shape, policy | SNP_POLICY_DBG);
 		else
-			test_sync_vmsa(type, policy | SEV_POLICY_NO_DBG);
+			test_sync_vmsa(shape, policy | SEV_POLICY_NO_DBG);
 	}
 }
 
@@ -247,13 +247,13 @@ int main(int argc, char *argv[])
 {
 	TEST_REQUIRE(kvm_cpu_has(X86_FEATURE_SEV));
 
-	test_sev_smoke(guest_sev_code, KVM_X86_SEV_VM, 0);
+	test_sev_smoke(guest_sev_code, VM_SHAPE_SEV, 0);
 
 	if (kvm_cpu_has(X86_FEATURE_SEV_ES))
-		test_sev_smoke(guest_sev_es_code, KVM_X86_SEV_ES_VM, SEV_POLICY_ES);
+		test_sev_smoke(guest_sev_es_code, VM_SHAPE_SEV_ES, SEV_POLICY_ES);
 
 	if (kvm_cpu_has(X86_FEATURE_SEV_SNP))
-		test_sev_smoke(guest_snp_code, KVM_X86_SNP_VM, snp_default_policy());
+		test_sev_smoke(guest_snp_code, VM_SHAPE_SNP, snp_default_policy());
 
 	return 0;
 }

---

## [3] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 02/22] KVM: selftests: Update kvm_init_vm_address_properties()
 for TDX*

From: Isaku Yamahata <isaku.yamahata@intel.com>

Initialize the TDX S-bit and the GPA tag mask in
kvm_init_vm_address_properties() for TDX VMs, similar to how the C-bit
is initialized for SEV VMs.

The TDX S-bit is used to distinguish between shared and private guest
physical addresses. Its position is determined by the guest physical
address width, which is either 48 or 52 bits for current TDX
implementations.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Co-developed-by: Adrian Hunter <adrian.hunter@intel.com>
Signed-off-by: Adrian Hunter <adrian.hunter@intel.com>
Signed-off-by: Isaku Yamahata <isaku.yamahata@intel.com>
Co-developed-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h | 14 ++++++++++++++
 tools/testing/selftests/kvm/lib/x86/processor.c        | 12 ++++++++++--
 2 files changed, 24 insertions(+), 2 deletions(-)

diff --git a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
new file mode 100644
index 000000000000..f647e6ca6b34
--- /dev/null
+++ b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
@@ -0,0 +1,14 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef SELFTESTS_TDX_TDX_UTIL_H
+#define SELFTESTS_TDX_TDX_UTIL_H
+
+#include <stdbool.h>
+
+#include "kvm_util.h"
+
+static inline bool is_tdx_vm(struct kvm_vm *vm)
+{
+	return vm->type == KVM_X86_TDX_VM;
+}
+
+#endif /* SELFTESTS_TDX_TDX_UTIL_H */
diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index b51467d70f6e..b68ad1dc7e02 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -11,6 +11,7 @@
 #include "smm.h"
 #include "svm_util.h"
 #include "sev.h"
+#include "tdx/tdx_util.h"
 #include "vmx.h"
 
 #ifndef NUM_INTERRUPTS
@@ -1311,12 +1312,19 @@ void kvm_get_cpu_address_width(unsigned int *pa_bits, unsigned int *va_bits)
 
 void kvm_init_vm_address_properties(struct kvm_vm *vm)
 {
+	u32 gpa_bits = kvm_cpu_property(X86_PROPERTY_GUEST_MAX_PHY_ADDR);
+
+	vm->arch.sev_fd = -1;
+
 	if (is_sev_vm(vm)) {
 		vm->arch.sev_fd = open_sev_dev_path_or_exit();
 		vm->arch.c_bit = BIT_ULL(this_cpu_property(X86_PROPERTY_SEV_C_BIT));
 		vm->gpa_tag_mask = vm->arch.c_bit;
-	} else {
-		vm->arch.sev_fd = -1;
+	} else if (is_tdx_vm(vm)) {
+		TEST_ASSERT(gpa_bits == 48 || gpa_bits == 52,
+			    "TDX: bad X86_PROPERTY_GUEST_MAX_PHY_ADDR value: %u", gpa_bits);
+		vm->arch.s_bit = BIT_ULL(gpa_bits - 1);
+		vm->gpa_tag_mask = vm->arch.s_bit;
 	}
 }

---

## [4] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 03/22] KVM: selftests: Initialize the TDX VM*

From: Sagi Shahar <sagis@google.com>

Add tdx_init_vm() to handle the mandatory VM-level initialization
sequence required for Intel TDX.

For TDX, the guest's CPUID configuration must be "sealed" during
KVM_TDX_INIT_VM before any vCPUs are created. This is necessary because
the TDX hardware directly virtualizes CPUID and includes the
configuration in the guest's initial security measurement.

The helper calculates the required CPUID values by filtering the host-
supported bits (kvm_get_supported_cpuid) against the "directly
configurable" bits reported by KVM_TDX_CAPABILITIES, ensuring
compliance with the strict requirements of the TDH.MNG.INIT SEAMCALL.

Co-developed-by: Isaku Yamahata <isaku.yamahata@intel.com>
Signed-off-by: Isaku Yamahata <isaku.yamahata@intel.com>
Co-developed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 .../selftests/kvm/include/x86/tdx/tdx_util.h       |  30 +++++
 tools/testing/selftests/kvm/lib/x86/processor.c    |   3 +
 tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c | 137 +++++++++++++++++++++
 3 files changed, 170 insertions(+)

diff --git a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
index f647e6ca6b34..48d4bd36c35b 100644
--- a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
+++ b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
@@ -11,4 +11,34 @@ static inline bool is_tdx_vm(struct kvm_vm *vm)
 	return vm->type == KVM_X86_TDX_VM;
 }
 
+/*
+ * TDX ioctls
+ * Use underscores to avoid collisions with struct member names.
+ */
+#define __tdx_vm_ioctl(vm, cmd, _flags, arg)				\
+({									\
+	int r;								\
+									\
+	union {								\
+		struct kvm_tdx_cmd c;					\
+		unsigned long raw;					\
+	} tdx_cmd = { .c = {						\
+		.id = (cmd),						\
+		.flags = (u32)(_flags),				\
+		.data = (u64)(arg),				\
+	} };								\
+									\
+	r = __vm_ioctl(vm, KVM_MEMORY_ENCRYPT_OP, &tdx_cmd.raw);	\
+	r ?: tdx_cmd.c.hw_error;					\
+})
+
+#define tdx_vm_ioctl(vm, cmd, flags, arg)				\
+({									\
+	int ret = __tdx_vm_ioctl(vm, cmd, flags, arg);			\
+									\
+	__TEST_ASSERT_VM_VCPU_IOCTL(!ret, #cmd,	ret, vm);		\
+})
+
+void tdx_init_vm(struct kvm_vm *vm, u64 attributes);
+
 #endif /* SELFTESTS_TDX_TDX_UTIL_H */
diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index b68ad1dc7e02..8d06e7186df1 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -802,6 +802,9 @@ void kvm_arch_vm_post_create(struct kvm_vm *vm, unsigned int nr_vcpus)
 		vm_sev_ioctl(vm, KVM_SEV_INIT2, &init);
 	}
 
+	if (is_tdx_vm(vm))
+		tdx_init_vm(vm, 0);
+
 	r = __vm_ioctl(vm, KVM_GET_TSC_KHZ, NULL);
 	TEST_ASSERT(r > 0, "KVM_GET_TSC_KHZ did not provide a valid TSC frequency.");
 	guest_tsc_khz = r;
diff --git a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
new file mode 100644
index 000000000000..868ff62e22f2
--- /dev/null
+++ b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
@@ -0,0 +1,137 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+#include "kvm_util.h"
+#include "processor.h"
+#include "tdx/tdx_util.h"
+
+static struct kvm_tdx_capabilities *tdx_read_capabilities(struct kvm_vm *vm)
+{
+	struct kvm_tdx_capabilities *tdx_cap = NULL;
+	int nr_cpuid_configs = 4;
+	int rc = -1;
+	int i;
+
+	do {
+		nr_cpuid_configs *= 2;
+
+		tdx_cap = realloc(tdx_cap, sizeof(*tdx_cap) +
+					   sizeof(tdx_cap->cpuid) +
+					   (sizeof(struct kvm_cpuid_entry2) * nr_cpuid_configs));
+		TEST_ASSERT(tdx_cap,
+			    "Could not allocate memory for tdx capability nr_cpuid_configs %d\n",
+			    nr_cpuid_configs);
+
+		tdx_cap->cpuid.nent = nr_cpuid_configs;
+		rc = __tdx_vm_ioctl(vm, KVM_TDX_CAPABILITIES, 0, tdx_cap);
+	} while (rc < 0 && errno == E2BIG);
+
+	TEST_ASSERT(rc == 0, "KVM_TDX_CAPABILITIES failed: %d %d",
+		    rc, errno);
+
+	pr_debug("tdx_cap: supported_attrs: 0x%016llx\n"
+		 "tdx_cap: supported_xfam 0x%016llx\n",
+		 tdx_cap->supported_attrs, tdx_cap->supported_xfam);
+
+	for (i = 0; i < tdx_cap->cpuid.nent; i++) {
+		const struct kvm_cpuid_entry2 *config = &tdx_cap->cpuid.entries[i];
+
+		pr_debug("cpuid config[%d]: leaf 0x%x sub_leaf 0x%x eax 0x%08x ebx 0x%08x ecx 0x%08x edx 0x%08x\n",
+			 i, config->function, config->index,
+			 config->eax, config->ebx, config->ecx, config->edx);
+	}
+
+	return tdx_cap;
+}
+
+static struct kvm_cpuid_entry2 *tdx_find_cpuid_config(struct kvm_tdx_capabilities *cap,
+						      u32 leaf, u32 sub_leaf)
+{
+	struct kvm_cpuid_entry2 *config;
+	u32 i;
+
+	for (i = 0; i < cap->cpuid.nent; i++) {
+		config = &cap->cpuid.entries[i];
+
+		if (config->function == leaf && config->index == sub_leaf)
+			return config;
+	}
+
+	return NULL;
+}
+
+/*
+ * Filter CPUID based on TDX supported capabilities
+ *
+ * Input Args:
+ *   vm - Virtual Machine
+ *   cpuid_data - CPUID fields to filter
+ *
+ * Output Args: None
+ *
+ * Return: None
+ *
+ * For each CPUID leaf, filter out non-supported bits based on the capabilities reported
+ * by the TDX module
+ */
+static void tdx_filter_cpuid(struct kvm_vm *vm,
+			     struct kvm_cpuid2 *cpuid_data)
+{
+	struct kvm_tdx_capabilities *tdx_cap;
+	struct kvm_cpuid_entry2 *config;
+	struct kvm_cpuid_entry2 *e;
+	int i;
+
+	tdx_cap = tdx_read_capabilities(vm);
+
+	i = 0;
+	while (i < cpuid_data->nent) {
+		e = cpuid_data->entries + i;
+		config = tdx_find_cpuid_config(tdx_cap, e->function, e->index);
+
+		if (!config) {
+			int left = cpuid_data->nent - i - 1;
+
+			if (left > 0)
+				memmove(cpuid_data->entries + i,
+					cpuid_data->entries + i + 1,
+					sizeof(*cpuid_data->entries) * left);
+			cpuid_data->nent--;
+			continue;
+		}
+
+		e->eax &= config->eax;
+		e->ebx &= config->ebx;
+		e->ecx &= config->ecx;
+		e->edx &= config->edx;
+
+		i++;
+	}
+
+	free(tdx_cap);
+}
+
+void tdx_init_vm(struct kvm_vm *vm, u64 attributes)
+{
+	struct kvm_tdx_init_vm *init_vm;
+	const struct kvm_cpuid2 *tmp;
+	struct kvm_cpuid2 *cpuid;
+
+	tmp = kvm_get_supported_cpuid();
+
+	cpuid = allocate_kvm_cpuid2(tmp->nent);
+	memcpy(cpuid, tmp, kvm_cpuid2_size(tmp->nent));
+	tdx_filter_cpuid(vm, cpuid);
+
+	init_vm = calloc(1, sizeof(*init_vm) +
+			 sizeof(init_vm->cpuid.entries[0]) * cpuid->nent);
+	TEST_ASSERT(init_vm, "init_vm allocation failed");
+
+	memcpy(&init_vm->cpuid, cpuid, kvm_cpuid2_size(cpuid->nent));
+	free(cpuid);
+
+	init_vm->attributes = attributes;
+
+	tdx_vm_ioctl(vm, KVM_TDX_INIT_VM, 0, init_vm);
+
+	free(init_vm);
+}

---

## [5] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 04/22] KVM: selftests: TDX: Use KVM_TDX_CAPABILITIES to
 validate TDs' attribute configuration*

From: Isaku Yamahata <isaku.yamahata@intel.com>

Make sure that all the attributes enabled by the test are reported as
supported by both the TDX module and KVM. KVM filters out the attributes
not supported by itself.

This also exercises the KVM_TDX_CAPABILITIES ioctl.

Signed-off-by: Isaku Yamahata <isaku.yamahata@intel.com>
Co-developed-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c | 14 ++++++++++++++
 1 file changed, 14 insertions(+)

diff --git a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
index 868ff62e22f2..e5c998874a0d 100644
--- a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
+++ b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
@@ -110,6 +110,18 @@ static void tdx_filter_cpuid(struct kvm_vm *vm,
 	free(tdx_cap);
 }
 
+static void tdx_check_attributes(struct kvm_vm *vm, u64 attributes)
+{
+	struct kvm_tdx_capabilities *tdx_cap;
+
+	tdx_cap = tdx_read_capabilities(vm);
+
+	/* Make sure all the attributes are reported as supported */
+	TEST_ASSERT_EQ(attributes & tdx_cap->supported_attrs, attributes);
+
+	free(tdx_cap);
+}
+
 void tdx_init_vm(struct kvm_vm *vm, u64 attributes)
 {
 	struct kvm_tdx_init_vm *init_vm;
@@ -129,6 +141,8 @@ void tdx_init_vm(struct kvm_vm *vm, u64 attributes)
 	memcpy(&init_vm->cpuid, cpuid, kvm_cpuid2_size(cpuid->nent));
 	free(cpuid);
 
+	tdx_check_attributes(vm, attributes);
+
 	init_vm->attributes = attributes;
 
 	tdx_vm_ioctl(vm, KVM_TDX_INIT_VM, 0, init_vm);

---

## [6] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 05/22] KVM: selftests: Expose segment definitions to
 assembly files*

From: Sagi Shahar <sagis@google.com>

Move kernel segment definitions to a separate file which can be included
from assembly files.

Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/include/x86/processor_asm.h | 12 ++++++++++++
 tools/testing/selftests/kvm/lib/x86/processor.c         |  5 +----
 2 files changed, 13 insertions(+), 4 deletions(-)

diff --git a/tools/testing/selftests/kvm/include/x86/processor_asm.h b/tools/testing/selftests/kvm/include/x86/processor_asm.h
new file mode 100644
index 000000000000..713b6bc0aeb7
--- /dev/null
+++ b/tools/testing/selftests/kvm/include/x86/processor_asm.h
@@ -0,0 +1,12 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+/*
+ * Used for storing defines used by both c and assembly code.
+ */
+#ifndef SELFTEST_KVM_PROCESSOR_ASM_H
+#define SELFTEST_KVM_PROCESSOR_ASM_H
+
+#define KERNEL_CS	0x8
+#define KERNEL_DS	0x10
+#define KERNEL_TSS	0x18
+
+#endif  /* SELFTEST_KVM_PROCESSOR_ASM_H */
diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index 8d06e7186df1..62abfe27fe3a 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -8,6 +8,7 @@
 #include "kvm_util.h"
 #include "pmu.h"
 #include "processor.h"
+#include "processor_asm.h"
 #include "smm.h"
 #include "svm_util.h"
 #include "sev.h"
@@ -18,10 +19,6 @@
 #define NUM_INTERRUPTS 256
 #endif
 
-#define KERNEL_CS	0x8
-#define KERNEL_DS	0x10
-#define KERNEL_TSS	0x18
-
 gva_t exception_handlers;
 bool host_cpu_is_amd;
 bool host_cpu_is_intel;

---

## [7] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 06/22] tools: include: Add kbuild.h for assembly
 structure offsets*

From: Sagi Shahar <sagis@google.com>

Add the Kbuild macros needed to enable the filechk_offsets mechanism to
generate C header files containing structure member offset information.

Tools depending on assembly code that operate on structures have to
hardcode the offsets of structure members. The Kbuild infrastructure
can instead generate C header files with these offsets automatically,
allowing them to be included in assembly code as symbolic constants.

For example, the TDX guest boot code requires access to parameters
passed in the C structure(struct td_boot_parameters). This header
provides the macros needed to extract these offsets from C code and
expose them to assembly, ensuring the two remain synchronized.

Signed-off-by: Sagi Shahar <sagis@google.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/include/linux/kbuild.h | 11 +++++++++++
 1 file changed, 11 insertions(+)

diff --git a/tools/include/linux/kbuild.h b/tools/include/linux/kbuild.h
new file mode 100644
index 000000000000..957fd55cd159
--- /dev/null
+++ b/tools/include/linux/kbuild.h
@@ -0,0 +1,11 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#ifndef __TOOLS_LINUX_KBUILD_H
+#define __TOOLS_LINUX_KBUILD_H
+
+#define DEFINE(sym, val) \
+	asm volatile("\n.ascii \"->" #sym " %0 " #val "\"" : : "i" (val))
+
+#define OFFSET(sym, str, mem) \
+	DEFINE(sym, __builtin_offsetof(struct str, mem))
+
+#endif /* __TOOLS_LINUX_KBUILD_H */

---

## [8] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 07/22] KVM: selftests: Introduce structures for TDX guest
 boot parameters*

From: Sagi Shahar <sagis@google.com>

Introduce `td_boot_parameters` and `td_per_vcpu_parameters`, and export
their offsets to assembly via the kbuild infrastructure.

TDX guest registers are private and must be initialized by guest-side
assembly. These structures allow the assembly code to retrieve boot
parameters and index into per-vCPU data based on the vCPU ID, while
keeping host and guest definitions synchronized.

Use kbuild.h to expose the offsets into the structs from c code to
assembly code.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Co-developed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Co-developed-by: Lisa Wang <wyihan@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/.gitignore             |  3 +-
 tools/testing/selftests/kvm/Makefile.kvm           | 29 ++++++++-
 .../selftests/kvm/include/x86/tdx/td_boot.h        | 69 ++++++++++++++++++++++
 .../selftests/kvm/lib/x86/tdx/td_boot_offsets.c    | 21 +++++++
 4 files changed, 119 insertions(+), 3 deletions(-)

diff --git a/tools/testing/selftests/kvm/.gitignore b/tools/testing/selftests/kvm/.gitignore
index 1d41a046a7bf..eef6055242b2 100644
--- a/tools/testing/selftests/kvm/.gitignore
+++ b/tools/testing/selftests/kvm/.gitignore
@@ -9,4 +9,5 @@
 !config
 !settings
 !Makefile
-!Makefile.kvm
\ No newline at end of file
+!Makefile.kvm
+include/x86/**/*_offsets.h
\ No newline at end of file
diff --git a/tools/testing/selftests/kvm/Makefile.kvm b/tools/testing/selftests/kvm/Makefile.kvm
index e5769268936a..02fad7b35eac 100644
--- a/tools/testing/selftests/kvm/Makefile.kvm
+++ b/tools/testing/selftests/kvm/Makefile.kvm
@@ -19,6 +19,8 @@ LIBKVM += lib/userfaultfd_util.c
 
 LIBKVM_STRING += lib/string_override.c
 
+LIBKVM_ASM_DEFS += lib/x86/tdx/td_boot_offsets.c
+
 LIBKVM_x86 += lib/x86/apic.c
 LIBKVM_x86 += lib/x86/handlers.S
 LIBKVM_x86 += lib/x86/hyperv.c
@@ -260,6 +262,10 @@ OVERRIDE_TARGETS = 1
 include ../lib.mk
 include ../cgroup/lib/libcgroup.mk
 
+# Enable Kbuild tools.
+include $(top_srcdir)/scripts/Kbuild.include
+include $(top_srcdir)/scripts/Makefile.lib
+
 INSTALL_HDR_PATH = $(top_srcdir)/usr
 LINUX_HDR_PATH = $(INSTALL_HDR_PATH)/include/
 LINUX_TOOL_INCLUDE = $(top_srcdir)/tools/include
@@ -272,15 +278,24 @@ CFLAGS += -Wall -Wstrict-prototypes -Wuninitialized -O2 -g -std=gnu99 \
 	-fno-stack-protector -fno-PIE -fno-strict-aliasing \
 	-I$(LINUX_TOOL_INCLUDE) -I$(LINUX_TOOL_ARCH_INCLUDE) \
 	-I$(LINUX_HDR_PATH) -Iinclude -I$(<D) -Iinclude/$(ARCH) \
-	-I ../rseq -I.. $(EXTRA_CFLAGS) $(KHDR_INCLUDES)
+	-I ../rseq -I.. -I$(OUTPUT)/include/$(ARCH) $(EXTRA_CFLAGS) $(KHDR_INCLUDES)
 ifeq ($(ARCH),s390)
 	CFLAGS += -march=z10
 endif
+
 ifeq ($(ARCH),x86)
+
 ifeq ($(shell echo "void foo(void) { }" | $(CC) -march=x86-64-v2 -x c - -c -o /dev/null 2>/dev/null; echo "$$?"),0)
 	CFLAGS += -march=x86-64-v2
 endif
+
+KVM_GEN_HDRS := $(patsubst lib/x86/%.c, $(OUTPUT)/include/x86/%.h, $(filter lib/x86/%, $(LIBKVM_ASM_DEFS)))
+$(shell mkdir -p $(sort $(dir $(KVM_GEN_HDRS))))
+$(KVM_GEN_HDRS): GUARD = $(shell echo $(*F) | tr a-z A-Z | tr '.' '_')
+$(KVM_GEN_HDRS): $(OUTPUT)/include/x86/%.h: $(OUTPUT)/lib/x86/%.s FORCE
+	$(call filechk,offsets,__$(GUARD)_H__)
 endif
+
 ifeq ($(ARCH),arm64)
 tools_dir := $(top_srcdir)/tools
 arm64_tools_dir := $(tools_dir)/arch/arm64/tools/
@@ -313,6 +328,7 @@ LIBKVM_S := $(filter %.S,$(LIBKVM))
 LIBKVM_C_OBJ := $(patsubst %.c, $(OUTPUT)/%.o, $(LIBKVM_C))
 LIBKVM_S_OBJ := $(patsubst %.S, $(OUTPUT)/%.o, $(LIBKVM_S))
 LIBKVM_STRING_OBJ := $(patsubst %.c, $(OUTPUT)/%.o, $(LIBKVM_STRING))
+LIBKVM_ASM_DEFS_OBJ += $(patsubst %.c, $(OUTPUT)/%.s, $(LIBKVM_ASM_DEFS))
 LIBKVM_OBJS = $(LIBKVM_C_OBJ) $(LIBKVM_S_OBJ) $(LIBKVM_STRING_OBJ) $(LIBCGROUP_O)
 SPLIT_TEST_GEN_PROGS := $(patsubst %, $(OUTPUT)/%, $(SPLIT_TESTS))
 SPLIT_TEST_GEN_OBJ := $(patsubst %, $(OUTPUT)/$(ARCH)/%.o, $(SPLIT_TESTS))
@@ -338,7 +354,9 @@ $(SPLIT_TEST_GEN_OBJ): $(OUTPUT)/$(ARCH)/%.o: $(ARCH)/%.c
 	$(CC) $(CFLAGS) $(CPPFLAGS) $(TARGET_ARCH) -c $< -o $@
 
 EXTRA_CLEAN += $(GEN_HDRS) \
+	       $(KVM_GEN_HDRS) \
 	       $(LIBKVM_OBJS) \
+	       $(LIBKVM_ASM_DEFS_OBJ) \
 	       $(SPLIT_TEST_GEN_OBJ) \
 	       $(TEST_DEP_FILES) \
 	       $(TEST_GEN_OBJ) \
@@ -350,6 +368,9 @@ $(LIBKVM_C_OBJ): $(OUTPUT)/%.o: %.c $(GEN_HDRS)
 $(LIBKVM_S_OBJ): $(OUTPUT)/%.o: %.S $(GEN_HDRS)
 	$(CC) $(CFLAGS) $(CPPFLAGS) $(TARGET_ARCH) -c $< -o $@
 
+$(LIBKVM_ASM_DEFS_OBJ): $(OUTPUT)/%.s: %.c FORCE
+	$(CC) $(CFLAGS) $(CPPFLAGS) $(TARGET_ARCH) -S $< -o $@
+
 # Compile the string overrides as freestanding to prevent the compiler from
 # generating self-referential code, e.g. without "freestanding" the compiler may
 # "optimize" memcmp() by invoking memcmp(), thus causing infinite recursion.
@@ -358,11 +379,15 @@ $(LIBKVM_STRING_OBJ): $(OUTPUT)/%.o: %.c
 
 $(shell mkdir -p $(sort $(dir $(TEST_GEN_PROGS))))
 $(SPLIT_TEST_GEN_OBJ): $(GEN_HDRS)
+$(LIBKVM_OBJS): $(KVM_GEN_HDRS)
 $(TEST_GEN_PROGS): $(LIBKVM_OBJS)
 $(TEST_GEN_PROGS_EXTENDED): $(LIBKVM_OBJS)
 $(TEST_GEN_OBJ): $(GEN_HDRS)
 
-cscope: include_paths = $(LINUX_TOOL_INCLUDE) $(LINUX_HDR_PATH) include lib ..
+FORCE:
+
+cscope: include_paths = $(LINUX_TOOL_INCLUDE) $(LINUX_HDR_PATH) include lib .. \
+			$(wildcard $(sort $(dir $(KVM_GEN_HDRS))))
 cscope:
 	$(RM) cscope.*
 	(find $(include_paths) -name '*.h' \
diff --git a/tools/testing/selftests/kvm/include/x86/tdx/td_boot.h b/tools/testing/selftests/kvm/include/x86/tdx/td_boot.h
new file mode 100644
index 000000000000..af4474dee387
--- /dev/null
+++ b/tools/testing/selftests/kvm/include/x86/tdx/td_boot.h
@@ -0,0 +1,69 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef SELFTEST_TDX_TD_BOOT_H
+#define SELFTEST_TDX_TD_BOOT_H
+
+#include <stdint.h>
+
+#include <linux/compiler.h>
+#include <linux/sizes.h>
+
+/*
+ * Layout for boot section (not to scale)
+ *
+ *                                   GPA
+ * _________________________________ 0x1_0000_0000 (4GB)
+ * |   Boot code trampoline    |
+ * |___________________________|____ 0x0_ffff_fff0: Reset vector (16B below 4GB)
+ * |   Boot code               |
+ * |___________________________|____ td_boot will be copied here, so that the
+ * |                           |     jmp to td_boot is exactly at the reset vector
+ * |   Empty space             |
+ * |                           |
+ * |───────────────────────────|
+ * |                           |
+ * |                           |
+ * |   Boot parameters         |
+ * |                           |
+ * |                           |
+ * |___________________________|____ 0x0_ffff_0000: TD_BOOT_PARAMETERS_GPA
+ */
+#define FOUR_GIGABYTES_GPA (SZ_4G)
+
+/*
+ * The exact memory layout for LGDT or LIDT instructions.
+ */
+struct __packed td_boot_parameters_dtr {
+	u16 limit;
+	u32 base;
+};
+
+/*
+ * Allows each vCPU to be initialized with different rip and esp.
+ */
+struct td_per_vcpu_parameters {
+	u32 esp_gva;
+	u64 guest_code;
+};
+
+/*
+ * Boot parameters for the TD.
+ *
+ * Unlike a regular VM, KVM cannot set registers such as esp, eip, etc
+ * before boot, so to run selftests, these registers' values have to be
+ * initialized by the TD.
+ *
+ * This struct is loaded in TD private memory at TD_BOOT_PARAMETERS_GPA.
+ *
+ * The TD boot code will read off parameters from this struct and set up the
+ * vCPU for executing selftests.
+ */
+struct td_boot_parameters {
+	u32 cr0;
+	u32 cr3;
+	u32 cr4;
+	struct td_boot_parameters_dtr gdtr;
+	struct td_boot_parameters_dtr idtr;
+	struct td_per_vcpu_parameters per_vcpu[];
+};
+
+#endif /* SELFTEST_TDX_TD_BOOT_H */
diff --git a/tools/testing/selftests/kvm/lib/x86/tdx/td_boot_offsets.c b/tools/testing/selftests/kvm/lib/x86/tdx/td_boot_offsets.c
new file mode 100644
index 000000000000..7f76a3585b99
--- /dev/null
+++ b/tools/testing/selftests/kvm/lib/x86/tdx/td_boot_offsets.c
@@ -0,0 +1,21 @@
+// SPDX-License-Identifier: GPL-2.0
+#define COMPILE_OFFSETS
+
+#include <linux/kbuild.h>
+
+#include "tdx/td_boot.h"
+
+static void __attribute__((used)) common(void)
+{
+	OFFSET(TD_BOOT_PARAMETERS_CR0, td_boot_parameters, cr0);
+	OFFSET(TD_BOOT_PARAMETERS_CR3, td_boot_parameters, cr3);
+	OFFSET(TD_BOOT_PARAMETERS_CR4, td_boot_parameters, cr4);
+	OFFSET(TD_BOOT_PARAMETERS_GDT, td_boot_parameters, gdtr);
+	OFFSET(TD_BOOT_PARAMETERS_IDT, td_boot_parameters, idtr);
+	OFFSET(TD_BOOT_PARAMETERS_PER_VCPU, td_boot_parameters, per_vcpu);
+	OFFSET(TD_PER_VCPU_PARAMETERS_ESP_GVA, td_per_vcpu_parameters, esp_gva);
+	OFFSET(TD_PER_VCPU_PARAMETERS_GUEST_CODE, td_per_vcpu_parameters,
+	       guest_code);
+	DEFINE(SIZEOF_TD_PER_VCPU_PARAMETERS,
+	       sizeof(struct td_per_vcpu_parameters));
+}

---

## [9] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 08/22] KVM: selftests: Add TDX boot code*

From: Erdem Aktas <erdemaktas@google.com>

Add code to boot a TDX test VM. Since TDX registers are inaccessible to
KVM, the boot code loads the relevant values from memory into the
registers before jumping to the guest code.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Erdem Aktas <erdemaktas@google.com>
Co-developed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
Co-developed-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/Makefile.kvm           |  1 +
 .../selftests/kvm/include/x86/tdx/td_boot.h        |  5 ++
 .../selftests/kvm/include/x86/tdx/td_boot_asm.h    | 16 ++++++
 tools/testing/selftests/kvm/lib/x86/tdx/td_boot.S  | 60 ++++++++++++++++++++++
 4 files changed, 82 insertions(+)

diff --git a/tools/testing/selftests/kvm/Makefile.kvm b/tools/testing/selftests/kvm/Makefile.kvm
index 02fad7b35eac..929965ca4b75 100644
--- a/tools/testing/selftests/kvm/Makefile.kvm
+++ b/tools/testing/selftests/kvm/Makefile.kvm
@@ -31,6 +31,7 @@ LIBKVM_x86 += lib/x86/sev.c
 LIBKVM_x86 += lib/x86/svm.c
 LIBKVM_x86 += lib/x86/ucall.c
 LIBKVM_x86 += lib/x86/vmx.c
+LIBKVM_x86 += lib/x86/tdx/td_boot.S
 
 LIBKVM_arm64 += lib/arm64/gic.c
 LIBKVM_arm64 += lib/arm64/gic_v3.c
diff --git a/tools/testing/selftests/kvm/include/x86/tdx/td_boot.h b/tools/testing/selftests/kvm/include/x86/tdx/td_boot.h
index af4474dee387..e5d54a20ed72 100644
--- a/tools/testing/selftests/kvm/include/x86/tdx/td_boot.h
+++ b/tools/testing/selftests/kvm/include/x86/tdx/td_boot.h
@@ -66,4 +66,9 @@ struct td_boot_parameters {
 	struct td_per_vcpu_parameters per_vcpu[];
 };
 
+void td_boot(void);
+void td_boot_code_end(void);
+
+#define TD_BOOT_CODE_SIZE (td_boot_code_end - td_boot)
+
 #endif /* SELFTEST_TDX_TD_BOOT_H */
diff --git a/tools/testing/selftests/kvm/include/x86/tdx/td_boot_asm.h b/tools/testing/selftests/kvm/include/x86/tdx/td_boot_asm.h
new file mode 100644
index 000000000000..10b4b527595c
--- /dev/null
+++ b/tools/testing/selftests/kvm/include/x86/tdx/td_boot_asm.h
@@ -0,0 +1,16 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef SELFTEST_TDX_TD_BOOT_ASM_H
+#define SELFTEST_TDX_TD_BOOT_ASM_H
+
+/*
+ * GPA where TD boot parameters will be loaded.
+ *
+ * TD_BOOT_PARAMETERS_GPA is arbitrarily chosen to
+ *
+ * + be within the 4GB address space
+ * + provide enough contiguous memory for the struct td_boot_parameters such
+ *   that there is one struct td_per_vcpu_parameters for KVM_MAX_VCPUS
+ */
+#define TD_BOOT_PARAMETERS_GPA 0xffff0000
+
+#endif  // SELFTEST_TDX_TD_BOOT_ASM_H
diff --git a/tools/testing/selftests/kvm/lib/x86/tdx/td_boot.S b/tools/testing/selftests/kvm/lib/x86/tdx/td_boot.S
new file mode 100644
index 000000000000..7aa33caa9a78
--- /dev/null
+++ b/tools/testing/selftests/kvm/lib/x86/tdx/td_boot.S
@@ -0,0 +1,60 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+
+#include "tdx/td_boot_asm.h"
+#include "tdx/td_boot_offsets.h"
+#include "processor_asm.h"
+
+.code32
+
+.globl td_boot
+td_boot:
+	/* In this procedure, edi is used as a temporary register. */
+	cli
+
+	/* Paging is off. */
+
+	movl $TD_BOOT_PARAMETERS_GPA, %ebx
+
+	/*
+	 * Find the address of struct td_per_vcpu_parameters for this
+	 * vCPU based on esi (TDX spec: initialized with vCPU id). Put
+	 * struct address into register for indirect addressing.
+	 */
+	movl $SIZEOF_TD_PER_VCPU_PARAMETERS, %eax
+	mul %esi
+	leal TD_BOOT_PARAMETERS_PER_VCPU(%ebx), %edi
+	addl %edi, %eax
+
+	/* Setup stack. */
+	movl TD_PER_VCPU_PARAMETERS_ESP_GVA(%eax), %esp
+
+	/* Setup GDT. */
+	leal TD_BOOT_PARAMETERS_GDT(%ebx), %edi
+	lgdt (%edi)
+
+	/* Setup IDT. */
+	leal TD_BOOT_PARAMETERS_IDT(%ebx), %edi
+	lidt (%edi)
+
+	/*
+	 * Set up control registers (There are no instructions to mov from
+	 * memory to control registers, hence use edi as a scratch register).
+	 */
+	movl TD_BOOT_PARAMETERS_CR4(%ebx), %edi
+	movl %edi, %cr4
+	movl TD_BOOT_PARAMETERS_CR3(%ebx), %edi
+	movl %edi, %cr3
+	movl TD_BOOT_PARAMETERS_CR0(%ebx), %edi
+	movl %edi, %cr0
+
+	/* Switching to 64bit mode after ljmp and then jump to guest code */
+	ljmp $(KERNEL_CS),$1f
+1:
+	jmp *TD_PER_VCPU_PARAMETERS_GUEST_CODE(%eax)
+
+/* Leave marker so size of td_boot code can be computed. */
+.globl td_boot_code_end
+td_boot_code_end:
+
+/* Disable executable stack. */
+.section .note.GNU-stack,"",%progbits

---

## [10] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 09/22] KVM: selftests: Expose functions to get default
 sregs values*

From: Sagi Shahar <sagis@google.com>

TDX can't set sregs values directly using KVM_SET_SREGS. Expose the
default values of certain sregs used by TDX VMs so they can be set
manually.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 .../testing/selftests/kvm/include/x86/processor.h  | 33 ++++++++++++++++++++++
 tools/testing/selftests/kvm/lib/x86/processor.c    | 18 ++++--------
 2 files changed, 38 insertions(+), 13 deletions(-)

diff --git a/tools/testing/selftests/kvm/include/x86/processor.h b/tools/testing/selftests/kvm/include/x86/processor.h
index 0aa6eecfcbde..1ebf161ec5d0 100644
--- a/tools/testing/selftests/kvm/include/x86/processor.h
+++ b/tools/testing/selftests/kvm/include/x86/processor.h
@@ -29,6 +29,10 @@ extern u64 guest_tsc_khz;
 #define MAX_NR_CPUID_ENTRIES 100
 #endif
 
+#ifndef NUM_INTERRUPTS
+#define NUM_INTERRUPTS 256
+#endif
+
 #define NONCANONICAL 0xaaaaaaaaaaaaaaaaull
 
 /* Forced emulation prefix, used to invoke the emulator unconditionally. */
@@ -1562,4 +1566,33 @@ u64 *tdp_get_pte(struct kvm_vm *vm, u64 l2_gpa);
 
 bool sys_clocksource_is_based_on_tsc(void);
 
+static inline u16 kvm_get_default_idt_limit(void)
+{
+	return NUM_INTERRUPTS * sizeof(struct idt_entry) - 1;
+}
+
+static inline u16 kvm_get_default_gdt_limit(void)
+{
+	return getpagesize() - 1;
+}
+
+static inline u64 kvm_get_default_cr0(void)
+{
+	return X86_CR0_PE | X86_CR0_NE | X86_CR0_PG;
+}
+
+static inline u64 kvm_get_default_cr4(void)
+{
+	u64 cr4 = X86_CR4_PAE | X86_CR4_OSFXSR;
+
+	if (kvm_cpu_has(X86_FEATURE_XSAVE))
+		cr4 |= X86_CR4_OSXSAVE;
+	return cr4;
+}
+
+static inline u64 kvm_get_default_efer(void)
+{
+	return EFER_LME | EFER_LMA | EFER_NX;
+}
+
 #endif /* SELFTEST_KVM_PROCESSOR_H */
diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index 62abfe27fe3a..5027411665bf 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -15,10 +15,6 @@
 #include "tdx/tdx_util.h"
 #include "vmx.h"
 
-#ifndef NUM_INTERRUPTS
-#define NUM_INTERRUPTS 256
-#endif
-
 gva_t exception_handlers;
 bool host_cpu_is_amd;
 bool host_cpu_is_intel;
@@ -647,16 +643,12 @@ static void vcpu_init_sregs(struct kvm_vm *vm, struct kvm_vcpu *vcpu)
 	vcpu_sregs_get(vcpu, &sregs);
 
 	sregs.idt.base = vm->arch.idt;
-	sregs.idt.limit = NUM_INTERRUPTS * sizeof(struct idt_entry) - 1;
+	sregs.idt.limit = kvm_get_default_idt_limit();
 	sregs.gdt.base = vm->arch.gdt;
-	sregs.gdt.limit = getpagesize() - 1;
-
-	sregs.cr0 = X86_CR0_PE | X86_CR0_NE | X86_CR0_PG;
-	sregs.cr4 |= X86_CR4_PAE | X86_CR4_OSFXSR;
-	if (kvm_cpu_has(X86_FEATURE_XSAVE))
-		sregs.cr4 |= X86_CR4_OSXSAVE;
-	if (vm->mmu.pgtable_levels == 5)
-		sregs.cr4 |= X86_CR4_LA57;
+	sregs.gdt.limit = kvm_get_default_gdt_limit();
+
+	sregs.cr0 = kvm_get_default_cr0();
+	sregs.cr4 |= kvm_get_default_cr4();
 	sregs.efer |= (EFER_LME | EFER_LMA | EFER_NX);
 
 	kvm_seg_set_unusable(&sregs.ldt);

---

## [11] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 10/22] KVM: selftests: Set up TDX boot code region*

From: Sagi Shahar <sagis@google.com>

Add memory for TDX boot code in a separate memslot.

Use virt_map() to get identity map in this memory region to allow for
seamless transition from paging disabled to paging enabled code.

Copy the boot code into the memory region and set up the reset vector
at this point. While it's possible to separate the memory allocation and
boot code initialization into separate functions, having all the
calculations for memory size and offsets in one place simplifies the
code and avoids duplications.

Handcode the reset vector as suggested by Sean Christopherson.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Suggested-by: Sean Christopherson <seanjc@google.com>
Co-developed-by: Erdem Aktas <erdemaktas@google.com>
Signed-off-by: Erdem Aktas <erdemaktas@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/Makefile.kvm           |  1 +
 .../selftests/kvm/include/x86/tdx/tdx_util.h       |  1 +
 tools/testing/selftests/kvm/lib/x86/processor.c    |  4 +-
 tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c | 47 ++++++++++++++++++++++
 4 files changed, 52 insertions(+), 1 deletion(-)

diff --git a/tools/testing/selftests/kvm/Makefile.kvm b/tools/testing/selftests/kvm/Makefile.kvm
index 929965ca4b75..a651a876c522 100644
--- a/tools/testing/selftests/kvm/Makefile.kvm
+++ b/tools/testing/selftests/kvm/Makefile.kvm
@@ -31,6 +31,7 @@ LIBKVM_x86 += lib/x86/sev.c
 LIBKVM_x86 += lib/x86/svm.c
 LIBKVM_x86 += lib/x86/ucall.c
 LIBKVM_x86 += lib/x86/vmx.c
+LIBKVM_x86 += lib/x86/tdx/tdx_util.c
 LIBKVM_x86 += lib/x86/tdx/td_boot.S
 
 LIBKVM_arm64 += lib/arm64/gic.c
diff --git a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
index 48d4bd36c35b..d66ea7bc85f9 100644
--- a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
+++ b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
@@ -40,5 +40,6 @@ static inline bool is_tdx_vm(struct kvm_vm *vm)
 })
 
 void tdx_init_vm(struct kvm_vm *vm, u64 attributes);
+void tdx_vm_setup_boot_code_region(struct kvm_vm *vm);
 
 #endif /* SELFTESTS_TDX_TDX_UTIL_H */
diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index 5027411665bf..dfabdfd17976 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -791,8 +791,10 @@ void kvm_arch_vm_post_create(struct kvm_vm *vm, unsigned int nr_vcpus)
 		vm_sev_ioctl(vm, KVM_SEV_INIT2, &init);
 	}
 
-	if (is_tdx_vm(vm))
+	if (is_tdx_vm(vm)) {
 		tdx_init_vm(vm, 0);
+		tdx_vm_setup_boot_code_region(vm);
+	}
 
 	r = __vm_ioctl(vm, KVM_GET_TSC_KHZ, NULL);
 	TEST_ASSERT(r > 0, "KVM_GET_TSC_KHZ did not provide a valid TSC frequency.");
diff --git a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
index e5c998874a0d..bbfaa9af9c60 100644
--- a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
+++ b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
@@ -2,8 +2,55 @@
 
 #include "kvm_util.h"
 #include "processor.h"
+#include "tdx/td_boot.h"
 #include "tdx/tdx_util.h"
 
+/* Arbitrarily selected to avoid overlaps with anything else */
+#define TD_BOOT_CODE_SLOT	20
+
+#define X86_RESET_VECTOR	0xfffffff0ul
+#define X86_RESET_VECTOR_SIZE	16
+
+void tdx_vm_setup_boot_code_region(struct kvm_vm *vm)
+{
+	size_t total_code_size = TD_BOOT_CODE_SIZE + X86_RESET_VECTOR_SIZE;
+	gpa_t boot_code_gpa = X86_RESET_VECTOR - TD_BOOT_CODE_SIZE;
+	gpa_t alloc_gpa = round_down(boot_code_gpa, PAGE_SIZE);
+	size_t nr_pages = DIV_ROUND_UP(total_code_size, PAGE_SIZE);
+	gpa_t gpa;
+	u8 *hva;
+
+	vm_userspace_mem_region_add(vm, VM_MEM_SRC_ANONYMOUS,
+				    alloc_gpa,
+				    TD_BOOT_CODE_SLOT, nr_pages,
+				    KVM_MEM_GUEST_MEMFD);
+
+	gpa = vm_phy_pages_alloc(vm, nr_pages, alloc_gpa, TD_BOOT_CODE_SLOT);
+	TEST_ASSERT(gpa == alloc_gpa, "Failed vm_phy_pages_alloc\n");
+
+	virt_map(vm, alloc_gpa, alloc_gpa, nr_pages);
+	hva = addr_gpa2hva(vm, boot_code_gpa);
+	memcpy(hva, td_boot, TD_BOOT_CODE_SIZE);
+
+	hva += TD_BOOT_CODE_SIZE;
+	TEST_ASSERT(hva == addr_gpa2hva(vm, X86_RESET_VECTOR),
+		    "Expected RESET vector at hva 0x%lx, got %lx",
+		    (unsigned long)addr_gpa2hva(vm, X86_RESET_VECTOR), (unsigned long)hva);
+
+	/*
+	 * Handcode "JMP rel8" at the RESET vector to jump back to the TD boot
+	 * code, as there are only 16 bytes at the RESET vector before RIP will
+	 * wrap back to zero.  Insert a trailing int3 so that the vCPU crashes
+	 * in case the JMP somehow falls through.  Note!  The target address is
+	 * relative to the end of the instruction!
+	 */
+	TEST_ASSERT(TD_BOOT_CODE_SIZE + 2 <= 128,
+		    "TD boot code not addressable by 'JMP rel8'");
+	hva[0] = 0xeb;
+	hva[1] = 256 - 2 - TD_BOOT_CODE_SIZE;
+	hva[2] = 0xcc;
+}
+
 static struct kvm_tdx_capabilities *tdx_read_capabilities(struct kvm_vm *vm)
 {
 	struct kvm_tdx_capabilities *tdx_cap = NULL;

---

## [12] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 11/22] KVM: selftests: Set up TDX boot parameters region*

From: Sagi Shahar <sagis@google.com>

Allocate memory for TDX boot parameters and define the utility functions
necessary to fill this memory with the boot parameters.

Co-developed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 .../selftests/kvm/include/x86/tdx/tdx_util.h       |  2 +
 tools/testing/selftests/kvm/lib/x86/processor.c    |  2 +
 tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c | 56 ++++++++++++++++++++++
 3 files changed, 60 insertions(+)

diff --git a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
index d66ea7bc85f9..9660ea9d2f31 100644
--- a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
+++ b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
@@ -41,5 +41,7 @@ static inline bool is_tdx_vm(struct kvm_vm *vm)
 
 void tdx_init_vm(struct kvm_vm *vm, u64 attributes);
 void tdx_vm_setup_boot_code_region(struct kvm_vm *vm);
+void tdx_vm_setup_boot_parameters_region(struct kvm_vm *vm, u32 nr_runnable_vcpus);
+void tdx_vm_load_common_boot_parameters(struct kvm_vm *vm);
 
 #endif /* SELFTESTS_TDX_TDX_UTIL_H */
diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index dfabdfd17976..c7c4a37b3170 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -794,6 +794,8 @@ void kvm_arch_vm_post_create(struct kvm_vm *vm, unsigned int nr_vcpus)
 	if (is_tdx_vm(vm)) {
 		tdx_init_vm(vm, 0);
 		tdx_vm_setup_boot_code_region(vm);
+		tdx_vm_setup_boot_parameters_region(vm, nr_vcpus);
+		tdx_vm_load_common_boot_parameters(vm);
 	}
 
 	r = __vm_ioctl(vm, KVM_GET_TSC_KHZ, NULL);
diff --git a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
index bbfaa9af9c60..b16bf24f3ef1 100644
--- a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
+++ b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
@@ -3,10 +3,12 @@
 #include "kvm_util.h"
 #include "processor.h"
 #include "tdx/td_boot.h"
+#include "tdx/td_boot_asm.h"
 #include "tdx/tdx_util.h"
 
 /* Arbitrarily selected to avoid overlaps with anything else */
 #define TD_BOOT_CODE_SLOT	20
+#define TD_BOOT_PARAMETERS_SLOT	21
 
 #define X86_RESET_VECTOR	0xfffffff0ul
 #define X86_RESET_VECTOR_SIZE	16
@@ -51,6 +53,60 @@ void tdx_vm_setup_boot_code_region(struct kvm_vm *vm)
 	hva[2] = 0xcc;
 }
 
+void tdx_vm_setup_boot_parameters_region(struct kvm_vm *vm, u32 nr_runnable_vcpus)
+{
+	size_t boot_params_size =
+		sizeof(struct td_boot_parameters) +
+		nr_runnable_vcpus * sizeof(struct td_per_vcpu_parameters);
+	int npages = DIV_ROUND_UP(boot_params_size, PAGE_SIZE);
+	gpa_t gpa;
+
+	vm_userspace_mem_region_add(vm, VM_MEM_SRC_ANONYMOUS,
+				    TD_BOOT_PARAMETERS_GPA,
+				    TD_BOOT_PARAMETERS_SLOT, npages,
+				    KVM_MEM_GUEST_MEMFD);
+	gpa = vm_phy_pages_alloc(vm, npages, TD_BOOT_PARAMETERS_GPA, TD_BOOT_PARAMETERS_SLOT);
+	TEST_ASSERT(gpa == TD_BOOT_PARAMETERS_GPA, "Failed vm_phy_pages_alloc\n");
+
+	virt_map(vm, TD_BOOT_PARAMETERS_GPA, TD_BOOT_PARAMETERS_GPA, npages);
+}
+
+void tdx_vm_load_common_boot_parameters(struct kvm_vm *vm)
+{
+	struct td_boot_parameters *params =
+		addr_gpa2hva(vm, TD_BOOT_PARAMETERS_GPA);
+	u32 cr4;
+
+	TEST_ASSERT_EQ(vm->mode, VM_MODE_PXXVYY_4K);
+
+	cr4 = kvm_get_default_cr4();
+	if (vm->mmu.pgtable_levels == 5)
+		cr4 |= X86_CR4_LA57;
+
+	/* TDX spec 11.6.2: CR4 bit MCE is fixed to 1 */
+	cr4 |= X86_CR4_MCE;
+
+	/* TDX spec 11.6.2: CR4 bit VMXE and SMXE are fixed to 0 */
+	cr4 &= ~(X86_CR4_VMXE | X86_CR4_SMXE);
+
+	/* Set parameters! */
+	params->cr0 = kvm_get_default_cr0();
+	TEST_ASSERT(vm->mmu.pgd < (1ULL << 32),
+		    "PGD must be within 32-bit address space for 32-bit boot code");
+	params->cr3 = vm->mmu.pgd;
+	params->cr4 = cr4;
+	params->idtr.base = vm->arch.idt;
+	params->idtr.limit = kvm_get_default_idt_limit();
+	params->gdtr.base = vm->arch.gdt;
+	params->gdtr.limit = kvm_get_default_gdt_limit();
+
+	TEST_ASSERT(params->cr0 != 0, "cr0 should not be 0");
+	TEST_ASSERT(params->cr3 != 0, "cr3 should not be 0");
+	TEST_ASSERT(params->cr4 != 0, "cr4 should not be 0");
+	TEST_ASSERT(params->gdtr.base != 0, "gdt base address should not be 0");
+	TEST_ASSERT(params->idtr.base != 0, "idt base address should not be 0");
+}
+
 static struct kvm_tdx_capabilities *tdx_read_capabilities(struct kvm_vm *vm)
 {
 	struct kvm_tdx_capabilities *tdx_cap = NULL;

---

## [13] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 12/22] KVM: selftests: Back the first memory region with
 guest_memfd for TDX*

Force GUEST_MEMFD for the primary memory region of TDX VMs.

TDX must use guest_memfd for private pages as there is no alternative
mechanism supported by the TDX architecture.

Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/lib/kvm_util.c | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/tools/testing/selftests/kvm/lib/kvm_util.c b/tools/testing/selftests/kvm/lib/kvm_util.c
index d1befa3f4b30..9a29540fff40 100644
--- a/tools/testing/selftests/kvm/lib/kvm_util.c
+++ b/tools/testing/selftests/kvm/lib/kvm_util.c
@@ -472,7 +472,7 @@ void kvm_set_files_rlimit(u32 nr_vcpus)
 static bool is_guest_memfd_required(struct vm_shape shape)
 {
 #ifdef __x86_64__
-	return shape.type == KVM_X86_SNP_VM;
+	return (shape.type == KVM_X86_SNP_VM || shape.type == KVM_X86_TDX_VM);
 #else
 	return false;
 #endif

---

## [14] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 13/22] KVM: selftests: Set first memory region as shared
 if guest_memfd*

Set the initial state of the first memory region as shared if it is
backed by guest_memfd, so that the KVM selftest framework functions can
populate mmap()-ed guest_memfd memory the same way memory from other
memory providers are populated.

For CoCo VMs, pages that need to be private are explicitly set to
private before executing the VM.

Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/lib/kvm_util.c | 16 ++++++++++------
 1 file changed, 10 insertions(+), 6 deletions(-)

diff --git a/tools/testing/selftests/kvm/lib/kvm_util.c b/tools/testing/selftests/kvm/lib/kvm_util.c
index 9a29540fff40..1bab7d76a59c 100644
--- a/tools/testing/selftests/kvm/lib/kvm_util.c
+++ b/tools/testing/selftests/kvm/lib/kvm_util.c
@@ -484,8 +484,10 @@ struct kvm_vm *__vm_create(struct vm_shape shape, u32 nr_runnable_vcpus,
 	u64 nr_pages = vm_nr_pages_required(shape.mode, nr_runnable_vcpus,
 						 nr_extra_pages);
 	struct userspace_mem_region *slot0;
+	u64 gmem_flags = 0;
 	struct kvm_vm *vm;
-	int i, flags;
+	int flags = 0;
+	int i;
 
 	kvm_set_files_rlimit(nr_runnable_vcpus);
 
@@ -495,14 +497,16 @@ struct kvm_vm *__vm_create(struct vm_shape shape, u32 nr_runnable_vcpus,
 	vm = ____vm_create(shape);
 
 	/*
-	 * Force GUEST_MEMFD for the primary memory region if necessary, e.g.
-	 * for CoCo VMs that require GUEST_MEMFD backed private memory.
+	 * Force GUEST_MEMFD for the primary memory region if necessary, and
+	 * initialize it as shared so the selftest framework can populate it
+	 * exactly like other memory providers.
 	 */
-	flags = 0;
-	if (is_guest_memfd_required(shape))
+	if (is_guest_memfd_required(shape)) {
 		flags |= KVM_MEM_GUEST_MEMFD;
+		gmem_flags |= GUEST_MEMFD_FLAG_INIT_SHARED;
+	}
 
-	vm_userspace_mem_region_add(vm, VM_MEM_SRC_ANONYMOUS, 0, 0, nr_pages, flags);
+	vm_mem_add(vm, VM_MEM_SRC_ANONYMOUS, 0, 0, nr_pages, flags, -1, 0, gmem_flags);
 	for (i = 0; i < NR_MEM_REGIONS; i++)
 		vm->memslots[i] = 0;

---

## [15] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 14/22] KVM: selftests: Expose function to allocate vCPU stack*

From: Sagi Shahar <sagis@google.com>

Introduce kvm_allocate_vcpu_stack() to allocate a vCPU's stack
in preparation for TDX to allocate a vCPU's stack and initialize
its stack pointer.

TDX VMs' registers are protected state and cannot be initialized
using the KVM_SET_REGS ioctl() that is used for normal VMs. A TDX
vCPU's stack address will be a property of the TDX specific boot code
that initializes the vCPUs' stack pointers at boot.

Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/include/x86/processor.h |  2 ++
 tools/testing/selftests/kvm/lib/x86/processor.c     | 16 +++++++++++-----
 2 files changed, 13 insertions(+), 5 deletions(-)

diff --git a/tools/testing/selftests/kvm/include/x86/processor.h b/tools/testing/selftests/kvm/include/x86/processor.h
index 1ebf161ec5d0..ed9c031b77b8 100644
--- a/tools/testing/selftests/kvm/include/x86/processor.h
+++ b/tools/testing/selftests/kvm/include/x86/processor.h
@@ -1142,6 +1142,8 @@ static inline void vcpu_clear_cpuid_feature(struct kvm_vcpu *vcpu,
 	vcpu_set_or_clear_cpuid_feature(vcpu, feature, false);
 }
 
+gva_t kvm_allocate_vcpu_stack(struct kvm_vm *vm);
+
 u64 vcpu_get_msr(struct kvm_vcpu *vcpu, u64 msr_index);
 int _vcpu_set_msr(struct kvm_vcpu *vcpu, u64 msr_index, u64 msr_value);
 
diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index c7c4a37b3170..8b0aa64384a1 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -813,12 +813,9 @@ void vcpu_arch_set_entry_point(struct kvm_vcpu *vcpu, void *guest_code)
 	vcpu_regs_set(vcpu, &regs);
 }
 
-struct kvm_vcpu *vm_arch_vcpu_add(struct kvm_vm *vm, u32 vcpu_id)
+gva_t kvm_allocate_vcpu_stack(struct kvm_vm *vm)
 {
-	struct kvm_mp_state mp_state;
-	struct kvm_regs regs;
 	gva_t stack_gva;
-	struct kvm_vcpu *vcpu;
 
 	stack_gva = __vm_alloc(vm, DEFAULT_STACK_PGS * getpagesize(),
 			       DEFAULT_GUEST_STACK_VADDR_MIN, MEM_REGION_DATA);
@@ -838,6 +835,15 @@ struct kvm_vcpu *vm_arch_vcpu_add(struct kvm_vm *vm, u32 vcpu_id)
 		    "__vm_alloc() did not provide a page-aligned address");
 	stack_gva -= 8;
 
+	return stack_gva;
+}
+
+struct kvm_vcpu *vm_arch_vcpu_add(struct kvm_vm *vm, u32 vcpu_id)
+{
+	struct kvm_mp_state mp_state;
+	struct kvm_vcpu *vcpu;
+	struct kvm_regs regs;
+
 	vcpu = __vm_vcpu_add(vm, vcpu_id);
 	vcpu_init_cpuid(vcpu, kvm_get_supported_cpuid());
 	vcpu_init_sregs(vm, vcpu);
@@ -846,7 +852,7 @@ struct kvm_vcpu *vm_arch_vcpu_add(struct kvm_vm *vm, u32 vcpu_id)
 	/* Setup guest general purpose registers */
 	vcpu_regs_get(vcpu, &regs);
 	regs.rflags = regs.rflags | 0x2;
-	regs.rsp = stack_gva;
+	regs.rsp = kvm_allocate_vcpu_stack(vm);
 	vcpu_regs_set(vcpu, &regs);
 
 	/* Setup the MP state */

---

## [16] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 15/22] KVM: selftests: Call KVM_TDX_INIT_VCPU when
 creating a new TDX vcpu*

From: Sagi Shahar <sagis@google.com>

TDX VMs need to issue the KVM_TDX_INIT_VCPU ioctl for each vcpu after
vcpu creation.

Since the cpuids for TD are managed by the TDX module, read the values
virtualized for the TD using KVM_TDX_GET_CPUID and set them in kvm using
KVM_SET_CPUID2 so that kvm has an accurate view of the VM cpuid values.

Signed-off-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 .../selftests/kvm/include/x86/tdx/tdx_util.h       | 24 ++++++++++++++++
 tools/testing/selftests/kvm/lib/x86/processor.c    | 33 ++++++++++++++++------
 2 files changed, 49 insertions(+), 8 deletions(-)

diff --git a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
index 9660ea9d2f31..4d01f806b37d 100644
--- a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
+++ b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
@@ -39,6 +39,30 @@ static inline bool is_tdx_vm(struct kvm_vm *vm)
 	__TEST_ASSERT_VM_VCPU_IOCTL(!ret, #cmd,	ret, vm);		\
 })
 
+#define __tdx_vcpu_ioctl(vcpu, cmd, _flags, arg)			\
+({									\
+	int r;								\
+									\
+	union {								\
+		struct kvm_tdx_cmd c;					\
+		unsigned long raw;					\
+	} tdx_cmd = { .c = {						\
+		.id = (cmd),						\
+		.flags = (u32)(_flags),				\
+		.data = (u64)(arg),				\
+	} };								\
+									\
+	r = __vcpu_ioctl(vcpu, KVM_MEMORY_ENCRYPT_OP, &tdx_cmd.raw);	\
+	r ?: tdx_cmd.c.hw_error;					\
+})
+
+#define tdx_vcpu_ioctl(vcpu, cmd, flags, arg)				\
+({									\
+	int ret = __tdx_vcpu_ioctl(vcpu, cmd, flags, arg);		\
+									\
+	__TEST_ASSERT_VM_VCPU_IOCTL(!ret, #cmd,	ret, (vcpu)->vm);	\
+})
+
 void tdx_init_vm(struct kvm_vm *vm, u64 attributes);
 void tdx_vm_setup_boot_code_region(struct kvm_vm *vm);
 void tdx_vm_setup_boot_parameters_region(struct kvm_vm *vm, u32 nr_runnable_vcpus);
diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index 8b0aa64384a1..757da2295ba0 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -838,6 +838,17 @@ gva_t kvm_allocate_vcpu_stack(struct kvm_vm *vm)
 	return stack_gva;
 }
 
+static void tdx_vcpu_init(struct kvm_vm *vm, struct kvm_vcpu *vcpu)
+{
+	struct kvm_cpuid2 *cpuid;
+
+	cpuid = allocate_kvm_cpuid2(MAX_NR_CPUID_ENTRIES);
+	tdx_vcpu_ioctl(vcpu, KVM_TDX_GET_CPUID, 0, cpuid);
+	vcpu_init_cpuid(vcpu, cpuid);
+	free(cpuid);
+	tdx_vcpu_ioctl(vcpu, KVM_TDX_INIT_VCPU, 0, NULL);
+}
+
 struct kvm_vcpu *vm_arch_vcpu_add(struct kvm_vm *vm, u32 vcpu_id)
 {
 	struct kvm_mp_state mp_state;
@@ -845,15 +856,21 @@ struct kvm_vcpu *vm_arch_vcpu_add(struct kvm_vm *vm, u32 vcpu_id)
 	struct kvm_regs regs;
 
 	vcpu = __vm_vcpu_add(vm, vcpu_id);
-	vcpu_init_cpuid(vcpu, kvm_get_supported_cpuid());
-	vcpu_init_sregs(vm, vcpu);
-	vcpu_init_xcrs(vm, vcpu);
 
-	/* Setup guest general purpose registers */
-	vcpu_regs_get(vcpu, &regs);
-	regs.rflags = regs.rflags | 0x2;
-	regs.rsp = kvm_allocate_vcpu_stack(vm);
-	vcpu_regs_set(vcpu, &regs);
+	if (is_tdx_vm(vm)) {
+		tdx_vcpu_init(vm, vcpu);
+	} else {
+		vcpu_init_cpuid(vcpu, kvm_get_supported_cpuid());
+
+		vcpu_init_sregs(vm, vcpu);
+		vcpu_init_xcrs(vm, vcpu);
+
+		/* Setup guest general purpose registers */
+		vcpu_regs_get(vcpu, &regs);
+		regs.rflags = regs.rflags | 0x2;
+		regs.rsp = kvm_allocate_vcpu_stack(vm);
+		vcpu_regs_set(vcpu, &regs);
+	}
 
 	/* Setup the MP state */
 	mp_state.mp_state = 0;

---

## [17] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 16/22] KVM: selftests: Load per-vCPU guest stack in TDX
 boot parameters*

From: Sagi Shahar <sagis@google.com>

Allocate a guest stack for each vCPU and record the GVA in the TDX boot
parameters region to allow proper vCPU initialization.

Co-developed-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Ackerley Tng <ackerleytng@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h |  1 +
 tools/testing/selftests/kvm/lib/x86/processor.c        |  2 ++
 tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c     | 11 +++++++++++
 3 files changed, 14 insertions(+)

diff --git a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
index 4d01f806b37d..644de6bbec17 100644
--- a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
+++ b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
@@ -67,5 +67,6 @@ void tdx_init_vm(struct kvm_vm *vm, u64 attributes);
 void tdx_vm_setup_boot_code_region(struct kvm_vm *vm);
 void tdx_vm_setup_boot_parameters_region(struct kvm_vm *vm, u32 nr_runnable_vcpus);
 void tdx_vm_load_common_boot_parameters(struct kvm_vm *vm);
+void tdx_vcpu_load_boot_parameters(struct kvm_vm *vm, struct kvm_vcpu *vcpu);
 
 #endif /* SELFTESTS_TDX_TDX_UTIL_H */
diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index 757da2295ba0..ba332f279f03 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -847,6 +847,8 @@ static void tdx_vcpu_init(struct kvm_vm *vm, struct kvm_vcpu *vcpu)
 	vcpu_init_cpuid(vcpu, cpuid);
 	free(cpuid);
 	tdx_vcpu_ioctl(vcpu, KVM_TDX_INIT_VCPU, 0, NULL);
+
+	tdx_vcpu_load_boot_parameters(vm, vcpu);
 }
 
 struct kvm_vcpu *vm_arch_vcpu_add(struct kvm_vm *vm, u32 vcpu_id)
diff --git a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
index b16bf24f3ef1..f26d602501b8 100644
--- a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
+++ b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
@@ -107,6 +107,17 @@ void tdx_vm_load_common_boot_parameters(struct kvm_vm *vm)
 	TEST_ASSERT(params->idtr.base != 0, "idt base address should not be 0");
 }
 
+void tdx_vcpu_load_boot_parameters(struct kvm_vm *vm, struct kvm_vcpu *vcpu)
+{
+	struct td_boot_parameters *params =
+		addr_gpa2hva(vm, TD_BOOT_PARAMETERS_GPA);
+	struct td_per_vcpu_parameters *vcpu_params =
+		&params->per_vcpu[vcpu->id];
+
+	vcpu_params->esp_gva = kvm_allocate_vcpu_stack(vm);
+}
+
+
 static struct kvm_tdx_capabilities *tdx_read_capabilities(struct kvm_vm *vm)
 {
 	struct kvm_tdx_capabilities *tdx_cap = NULL;

---

## [18] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 17/22] KVM: selftests: Set entry point for TDX guest code*

From: Sagi Shahar <sagis@google.com>

Since the rip register is inaccessible for TDX VMs, we need a different
way to set the guest entry point for TDX VMs. This is done by writing
the guest code address to a predefined location in the guest memory and
loading it into rip as part of the TDX boot code.

Signed-off-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h |  1 +
 tools/testing/selftests/kvm/lib/x86/processor.c        | 10 +++++++---
 tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c     | 10 ++++++++++
 3 files changed, 18 insertions(+), 3 deletions(-)

diff --git a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
index 644de6bbec17..efa4c7f7b1c1 100644
--- a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
+++ b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
@@ -68,5 +68,6 @@ void tdx_vm_setup_boot_code_region(struct kvm_vm *vm);
 void tdx_vm_setup_boot_parameters_region(struct kvm_vm *vm, u32 nr_runnable_vcpus);
 void tdx_vm_load_common_boot_parameters(struct kvm_vm *vm);
 void tdx_vcpu_load_boot_parameters(struct kvm_vm *vm, struct kvm_vcpu *vcpu);
+void tdx_vcpu_set_entry_point(struct kvm_vcpu *vcpu, void *guest_code);
 
 #endif /* SELFTESTS_TDX_TDX_UTIL_H */
diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index ba332f279f03..d84c629a1945 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -808,9 +808,13 @@ void vcpu_arch_set_entry_point(struct kvm_vcpu *vcpu, void *guest_code)
 {
 	struct kvm_regs regs;
 
-	vcpu_regs_get(vcpu, &regs);
-	regs.rip = (unsigned long) guest_code;
-	vcpu_regs_set(vcpu, &regs);
+	if (is_tdx_vm(vcpu->vm)) {
+		tdx_vcpu_set_entry_point(vcpu, guest_code);
+	} else {
+		vcpu_regs_get(vcpu, &regs);
+		regs.rip = (unsigned long)guest_code;
+		vcpu_regs_set(vcpu, &regs);
+	}
 }
 
 gva_t kvm_allocate_vcpu_stack(struct kvm_vm *vm)
diff --git a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
index f26d602501b8..158cba1b95e3 100644
--- a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
+++ b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
@@ -117,6 +117,16 @@ void tdx_vcpu_load_boot_parameters(struct kvm_vm *vm, struct kvm_vcpu *vcpu)
 	vcpu_params->esp_gva = kvm_allocate_vcpu_stack(vm);
 }
 
+void tdx_vcpu_set_entry_point(struct kvm_vcpu *vcpu, void *guest_code)
+{
+	struct td_boot_parameters *params =
+		addr_gpa2hva(vcpu->vm, TD_BOOT_PARAMETERS_GPA);
+	struct td_per_vcpu_parameters *vcpu_params =
+		&params->per_vcpu[vcpu->id];
+
+	vcpu_params->guest_code = (u64)guest_code;
+}
+
 
 static struct kvm_tdx_capabilities *tdx_read_capabilities(struct kvm_vm *vm)
 {

---

## [19] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 18/22] KVM: selftests: Add helpers to init TDX memory and
 finalize VM*

From: Ackerley Tng <ackerleytng@google.com>

TDX protected memory needs to be measured and encrypted before it can be
used by the guest. Traverse the VM's memory regions and initialize all
the protected ranges by calling KVM_TDX_INIT_MEM_REGION.

Once all the memory is initialized, the VM can be finalized by calling
KVM_TDX_FINALIZE_VM.

Signed-off-by: Ackerley Tng <ackerleytng@google.com>
Co-developed-by: Erdem Aktas <erdemaktas@google.com>
Signed-off-by: Erdem Aktas <erdemaktas@google.com>
Co-developed-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Reviewed-by: Binbin Wu <binbin.wu@linux.intel.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 .../selftests/kvm/include/x86/tdx/tdx_util.h       |  2 +
 tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c | 59 ++++++++++++++++++++++
 2 files changed, 61 insertions(+)

diff --git a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
index efa4c7f7b1c1..8276622c50d2 100644
--- a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
+++ b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
@@ -70,4 +70,6 @@ void tdx_vm_load_common_boot_parameters(struct kvm_vm *vm);
 void tdx_vcpu_load_boot_parameters(struct kvm_vm *vm, struct kvm_vcpu *vcpu);
 void tdx_vcpu_set_entry_point(struct kvm_vcpu *vcpu, void *guest_code);
 
+void tdx_vm_finalize(struct kvm_vm *vm);
+
 #endif /* SELFTESTS_TDX_TDX_UTIL_H */
diff --git a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
index 158cba1b95e3..584e6600b588 100644
--- a/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
+++ b/tools/testing/selftests/kvm/lib/x86/tdx/tdx_util.c
@@ -1,5 +1,7 @@
 // SPDX-License-Identifier: GPL-2.0-only
 
+#include <linux/align.h>
+
 #include "kvm_util.h"
 #include "processor.h"
 #include "tdx/td_boot.h"
@@ -273,3 +275,60 @@ void tdx_init_vm(struct kvm_vm *vm, u64 attributes)
 
 	free(init_vm);
 }
+
+static void tdx_init_mem_region(struct kvm_vm *vm, void *source_pages,
+				u64 gpa, u64 size)
+{
+	u32 flags = KVM_TDX_MEASURE_MEMORY_REGION;
+	struct kvm_tdx_init_mem_region mem_region = {
+		.source_addr = (u64)source_pages,
+		.gpa = gpa,
+		.nr_pages = size / PAGE_SIZE,
+	};
+	struct kvm_vcpu *vcpu;
+
+	vcpu = list_first_entry_or_null(&vm->vcpus, struct kvm_vcpu, list);
+
+	TEST_ASSERT(size && IS_ALIGNED(size, PAGE_SIZE),
+		"Cannot add partial pages to the guest memory.\n");
+	TEST_ASSERT(IS_ALIGNED((u64)source_pages, PAGE_SIZE),
+		"Source memory buffer is not page aligned\n");
+	tdx_vcpu_ioctl(vcpu, KVM_TDX_INIT_MEM_REGION, flags, &mem_region);
+}
+
+static void tdx_load_private_memory(struct kvm_vm *vm)
+{
+	struct userspace_mem_region *region;
+	int ctr;
+
+	hash_for_each(vm->regions.slot_hash, ctr, region, slot_node) {
+		const struct sparsebit *protected_pages = region->protected_phy_pages;
+		const gpa_t gpa_base = region->region.guest_phys_addr;
+		const u64 hva_base = region->region.userspace_addr;
+		const sparsebit_idx_t lowest_page_in_region = gpa_base >> vm->page_shift;
+		sparsebit_idx_t i, j;
+
+		if (!sparsebit_any_set(protected_pages))
+			continue;
+
+		TEST_ASSERT(region->region.guest_memfd != -1,
+			    "TD private memory must be backed by guest_memfd");
+
+		sparsebit_for_each_set_range(protected_pages, i, j) {
+			const u64 size_to_load = (j - i + 1) * vm->page_size;
+			const u64 offset =
+				(i - lowest_page_in_region) * vm->page_size;
+			const u64 hva = hva_base + offset;
+			const u64 gpa = gpa_base + offset;
+
+			vm_mem_set_private(vm, gpa, size_to_load);
+			tdx_init_mem_region(vm, (void *)hva, gpa, size_to_load);
+		}
+	}
+}
+
+void tdx_vm_finalize(struct kvm_vm *vm)
+{
+	tdx_load_private_memory(vm);
+	tdx_vm_ioctl(vm, KVM_TDX_FINALIZE_VM, 0, NULL);
+}

---

## [20] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 19/22] KVM: selftests: Finalize TD memory as part of kvm_arch_vm_finalize_vcpus*

From: Sagi Shahar <sagis@google.com>

Finalize TDX VM after creation to make it runnable.

Signed-off-by: Sagi Shahar <sagis@google.com>
Reviewed-by: Ira Weiny <ira.weiny@intel.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/lib/x86/processor.c | 6 ++++++
 1 file changed, 6 insertions(+)

diff --git a/tools/testing/selftests/kvm/lib/x86/processor.c b/tools/testing/selftests/kvm/lib/x86/processor.c
index d84c629a1945..842cac168e99 100644
--- a/tools/testing/selftests/kvm/lib/x86/processor.c
+++ b/tools/testing/selftests/kvm/lib/x86/processor.c
@@ -1479,6 +1479,12 @@ bool kvm_arch_has_default_irqchip(void)
 	return true;
 }
 
+void kvm_arch_vm_finalize_vcpus(struct kvm_vm *vm)
+{
+	if (is_tdx_vm(vm))
+		tdx_vm_finalize(vm);
+}
+
 void setup_smram(struct kvm_vm *vm, struct kvm_vcpu *vcpu, u64 smram_gpa,
 		 const void *smi_handler, size_t handler_size)
 {

---

## [21] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 20/22] KVM: selftests: Implement MMIO WRITE for the TDX VM*

From: Erdem Aktas <erdemaktas@google.com>

Implement the tdx_mmio_write() to allow TDX VMs to request MMIO
emulation.

Follow the Intel Guest-Hypervisor Communication Interface (GHCI) spec
to the minimum extent that a spec-abiding TDX module will pass the
request to KVM. Skip implementing the #VE handler as described in the
GHCI spec so selftests will not take a dependency on having a working

To perform emulated I/O, VMs use the TDG.VP.VMCALL instruction to
request MMIO.

Signed-off-by: Erdem Aktas <erdemaktas@google.com>
Co-developed-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Co-developed-by: Lisa Wang <wyihan@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/Makefile.kvm          |  1 +
 tools/testing/selftests/kvm/include/x86/tdx/tdx.h | 16 ++++++++++++
 tools/testing/selftests/kvm/lib/x86/tdx/tdx.c     | 30 +++++++++++++++++++++++
 3 files changed, 47 insertions(+)

diff --git a/tools/testing/selftests/kvm/Makefile.kvm b/tools/testing/selftests/kvm/Makefile.kvm
index a651a876c522..489324cecf83 100644
--- a/tools/testing/selftests/kvm/Makefile.kvm
+++ b/tools/testing/selftests/kvm/Makefile.kvm
@@ -33,6 +33,7 @@ LIBKVM_x86 += lib/x86/ucall.c
 LIBKVM_x86 += lib/x86/vmx.c
 LIBKVM_x86 += lib/x86/tdx/tdx_util.c
 LIBKVM_x86 += lib/x86/tdx/td_boot.S
+LIBKVM_x86 += lib/x86/tdx/tdx.c
 
 LIBKVM_arm64 += lib/arm64/gic.c
 LIBKVM_arm64 += lib/arm64/gic_v3.c
diff --git a/tools/testing/selftests/kvm/include/x86/tdx/tdx.h b/tools/testing/selftests/kvm/include/x86/tdx/tdx.h
new file mode 100644
index 000000000000..810ca7423c84
--- /dev/null
+++ b/tools/testing/selftests/kvm/include/x86/tdx/tdx.h
@@ -0,0 +1,16 @@
+/* SPDX-License-Identifier: GPL-2.0-only */
+#ifndef SELFTESTS_TDX_TDX_H
+#define SELFTESTS_TDX_TDX_H
+
+#include <linux/types.h>
+
+enum mmio_size {
+	MMIO_SIZE_1B = 1,
+	MMIO_SIZE_2B = 2,
+	MMIO_SIZE_4B = 4,
+	MMIO_SIZE_8B = 8
+};
+
+u64 tdx_mmio_write(u64 address, enum mmio_size size, u64 data_in);
+
+#endif // SELFTESTS_TDX_TDX_H
diff --git a/tools/testing/selftests/kvm/lib/x86/tdx/tdx.c b/tools/testing/selftests/kvm/lib/x86/tdx/tdx.c
new file mode 100644
index 000000000000..f19be79fe11f
--- /dev/null
+++ b/tools/testing/selftests/kvm/lib/x86/tdx/tdx.c
@@ -0,0 +1,30 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+#include "tdx/tdx.h"
+
+#define TDG_VP_VMCALL 0
+#define TDG_VP_VMCALL_VE_REQUEST_MMIO    48
+#define TDVMCALL_MMIO_WRITE		  1
+#define TDVMCALL_EXPOSE_REGS_MASK    0xFC00
+
+u64 tdx_mmio_write(u64 address, enum mmio_size size, u64 data_in)
+{
+	register u64 r10_reg asm("r10") = TDG_VP_VMCALL;
+	register u64 r11_reg asm("r11") = TDG_VP_VMCALL_VE_REQUEST_MMIO;
+	register u64 r12_reg asm("r12") = size;
+	register u64 r13_reg asm("r13") = TDVMCALL_MMIO_WRITE;
+	register u64 r14_reg asm("r14") = address;
+	register u64 r15_reg asm("r15") = data_in;
+	register u64 rax_reg asm("rax") = TDG_VP_VMCALL;
+	register u64 rcx_reg asm("rcx") = TDVMCALL_EXPOSE_REGS_MASK;
+
+	asm volatile(
+	 ".byte 0x66,0x0f,0x01,0xcc" /* tdcall */
+	 : "+r" (r10_reg), "+r" (r11_reg)
+	 : "r" (r12_reg), "r" (r13_reg), "r" (r14_reg), "r" (r15_reg),
+	   "r" (rax_reg), "r" (rcx_reg)
+	 : "cc", "memory"
+	);
+
+	return r10_reg;
+}

---

## [22] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 21/22] KVM: selftests: Add ucall support for TDX*

From: Ackerley Tng <ackerleytng@google.com>

Implement TDX ucall using TDCALL-based MMIO to pass the ucall address
from the VM to the host.

In standard KVM selftests, ucall uses a PIO instruction as a trigger
to exit to the host, which then retrieves the ucall address by reading
the guest's RDI register. This approach is incompatible with TDX
because the host cannot access guest registers.

Furthermore, PIO exits only expose 4 bytes of immediate data, which
is insufficient for a 8-byte ucall address. By using TDCALL-based MMIO,
the VM can share the full 8-byte address in a single exit without
refactoring the common ucall framework and other non-x86 architectures.

Signed-off-by: Ackerley Tng <ackerleytng@google.com>
Co-developed-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Sagi Shahar <sagis@google.com>
Co-developed-by: Lisa Wang <wyihan@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/include/x86/ucall.h |  6 -----
 tools/testing/selftests/kvm/lib/x86/ucall.c     | 30 +++++++++++++++++++++++++
 2 files changed, 30 insertions(+), 6 deletions(-)

diff --git a/tools/testing/selftests/kvm/include/x86/ucall.h b/tools/testing/selftests/kvm/include/x86/ucall.h
index 0e4950041e3e..7e54ec2c1a45 100644
--- a/tools/testing/selftests/kvm/include/x86/ucall.h
+++ b/tools/testing/selftests/kvm/include/x86/ucall.h
@@ -2,12 +2,6 @@
 #ifndef SELFTEST_KVM_UCALL_H
 #define SELFTEST_KVM_UCALL_H
 
-#include "kvm_util.h"
-
 #define UCALL_EXIT_REASON       KVM_EXIT_IO
 
-static inline void ucall_arch_init(struct kvm_vm *vm, gpa_t mmio_gpa)
-{
-}
-
 #endif
diff --git a/tools/testing/selftests/kvm/lib/x86/ucall.c b/tools/testing/selftests/kvm/lib/x86/ucall.c
index e7dd5791959b..c8e3418d53af 100644
--- a/tools/testing/selftests/kvm/lib/x86/ucall.c
+++ b/tools/testing/selftests/kvm/lib/x86/ucall.c
@@ -5,11 +5,34 @@
  * Copyright (C) 2018, Red Hat, Inc.
  */
 #include "kvm_util.h"
+#include "tdx/tdx.h"
+#include "tdx/tdx_util.h"
 
 #define UCALL_PIO_PORT ((u16)0x1000)
 
+static u8 vm_type;
+static gpa_t host_ucall_mmio_gpa;
+static gpa_t ucall_mmio_gpa;
+
+void ucall_arch_init(struct kvm_vm *vm, gpa_t mmio_gpa)
+{
+	vm_type = vm->type;
+	sync_global_to_guest(vm, vm_type);
+
+	if (is_tdx_vm(vm)) {
+		host_ucall_mmio_gpa = ucall_mmio_gpa = mmio_gpa;
+		ucall_mmio_gpa |= vm->arch.s_bit;
+		sync_global_to_guest(vm, ucall_mmio_gpa);
+	}
+}
+
 void ucall_arch_do_ucall(gva_t uc)
 {
+	if (vm_type == KVM_X86_TDX_VM) {
+		tdx_mmio_write(ucall_mmio_gpa, MMIO_SIZE_8B, uc);
+		return;
+	}
+
 	/*
 	 * FIXME: Revert this hack (the entire commit that added it) once nVMX
 	 * preserves L2 GPRs across a nested VM-Exit.  If a ucall from L2, e.g.
@@ -46,6 +69,13 @@ void *ucall_arch_get_ucall(struct kvm_vcpu *vcpu)
 {
 	struct kvm_run *run = vcpu->run;
 
+	if (vm_type == KVM_X86_TDX_VM) {
+		if (run->exit_reason == KVM_EXIT_MMIO &&
+		    run->mmio.phys_addr == host_ucall_mmio_gpa &&
+		    run->mmio.len == MMIO_SIZE_8B && run->mmio.is_write)
+			return (void *)(*((u64 *)run->mmio.data));
+	}
+
 	if (run->exit_reason == KVM_EXIT_IO && run->io.port == UCALL_PIO_PORT) {
 		struct kvm_regs regs;

---

## [23] Lisa Wang — 2026-05-21
*Subject: [PATCH  v13 22/22] KVM: selftests: Add TDX lifecycle test*

From: Sagi Shahar <sagis@google.com>

Adding a test to verify TDX lifecycle by creating a simple TDX VM.

Signed-off-by: Sagi Shahar <sagis@google.com>
Signed-off-by: Lisa Wang <wyihan@google.com>
---
 tools/testing/selftests/kvm/Makefile.kvm           |  1 +
 .../testing/selftests/kvm/include/x86/processor.h  |  1 +
 .../selftests/kvm/include/x86/tdx/tdx_util.h       |  5 ++++
 tools/testing/selftests/kvm/x86/tdx_vm_test.c      | 33 ++++++++++++++++++++++
 4 files changed, 40 insertions(+)

diff --git a/tools/testing/selftests/kvm/Makefile.kvm b/tools/testing/selftests/kvm/Makefile.kvm
index 489324cecf83..14db8eb2bf0d 100644
--- a/tools/testing/selftests/kvm/Makefile.kvm
+++ b/tools/testing/selftests/kvm/Makefile.kvm
@@ -167,6 +167,7 @@ TEST_GEN_PROGS_x86 += rseq_test
 TEST_GEN_PROGS_x86 += steal_time
 TEST_GEN_PROGS_x86 += system_counter_offset_test
 TEST_GEN_PROGS_x86 += pre_fault_memory_test
+TEST_GEN_PROGS_x86 += x86/tdx_vm_test
 
 # Compiled outputs used by test targets
 TEST_GEN_PROGS_EXTENDED_x86 += x86/nx_huge_pages_test
diff --git a/tools/testing/selftests/kvm/include/x86/processor.h b/tools/testing/selftests/kvm/include/x86/processor.h
index ed9c031b77b8..f65755482a97 100644
--- a/tools/testing/selftests/kvm/include/x86/processor.h
+++ b/tools/testing/selftests/kvm/include/x86/processor.h
@@ -372,6 +372,7 @@ static inline unsigned int x86_model(unsigned int eax)
 #define VM_SHAPE_SEV		VM_TYPE(KVM_X86_SEV_VM)
 #define VM_SHAPE_SEV_ES		VM_TYPE(KVM_X86_SEV_ES_VM)
 #define VM_SHAPE_SNP		VM_TYPE(KVM_X86_SNP_VM)
+#define VM_SHAPE_TDX		VM_TYPE(KVM_X86_TDX_VM)
 
 #define PHYSICAL_PAGE_MASK      GENMASK_ULL(51, 12)
 
diff --git a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
index 8276622c50d2..56538b1286f3 100644
--- a/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
+++ b/tools/testing/selftests/kvm/include/x86/tdx/tdx_util.h
@@ -11,6 +11,11 @@ static inline bool is_tdx_vm(struct kvm_vm *vm)
 	return vm->type == KVM_X86_TDX_VM;
 }
 
+static inline bool is_tdx_supported(void)
+{
+	return !!(kvm_check_cap(KVM_CAP_VM_TYPES) & BIT(KVM_X86_TDX_VM));
+}
+
 /*
  * TDX ioctls
  * Use underscores to avoid collisions with struct member names.
diff --git a/tools/testing/selftests/kvm/x86/tdx_vm_test.c b/tools/testing/selftests/kvm/x86/tdx_vm_test.c
new file mode 100644
index 000000000000..7cdcaf33b585
--- /dev/null
+++ b/tools/testing/selftests/kvm/x86/tdx_vm_test.c
@@ -0,0 +1,33 @@
+// SPDX-License-Identifier: GPL-2.0-only
+
+#include "processor.h"
+#include "kvm_util.h"
+#include "tdx/tdx_util.h"
+#include "ucall_common.h"
+#include "kselftest_harness.h"
+
+static void guest_code_lifecycle(void)
+{
+	GUEST_DONE();
+}
+
+TEST(verify_td_lifecycle)
+{
+	struct kvm_vcpu *vcpu;
+	struct kvm_vm *vm;
+	struct ucall uc;
+
+	vm = vm_create_shape_with_one_vcpu(VM_SHAPE_TDX, &vcpu,
+					   guest_code_lifecycle);
+
+	vcpu_run(vcpu);
+	TEST_ASSERT_EQ(get_ucall(vcpu, &uc), UCALL_DONE);
+
+	kvm_vm_free(vm);
+}
+
+int main(int argc, char **argv)
+{
+	TEST_REQUIRE(is_tdx_supported());
+	return test_harness_run(argc, argv);
+}

---

## [24] Yosry Ahmed — 2026-05-22
*Subject: Re: [PATCH v13 07/22] KVM: selftests: Introduce structures for TDX
 guest boot parameters*

> +static void __attribute__((used)) common(void)
> +{

This is neat.

Sean, is this the preferred way to expose offsets to asm files (or asm
code blocks) -- as opposed to say using .equ [*]?

If yes, I can rework my nVMX GPR fixes to use the same approach for
register offsets. I wonder if the non-TDX part of this patch (i.e.
Makefile stuff) can be split, then patch 6 and the Makefile stuff can
land independently and allow development on top.

I can also split them out and include them in the next version of my
series, then whichever series lands first will land the offsets
support.

WDYT?

[*]https://lore.kernel.org/kvm/20260518202514.2037078-2-yosry@kernel.org/

---

## [25] Sean Christopherson — 2026-05-22
*Subject: Re: [PATCH v13 07/22] KVM: selftests: Introduce structures for TDX
 guest boot parameters*

On Fri, May 22, 2026, Yosry Ahmed wrote:
> > +static void __attribute__((used)) common(void)
> > +{

For actual .S assembly, yes.  For inline asm, maybe?  If it looks prettier, go
for it.  

> If yes, I can rework my nVMX GPR fixes to use the same approach for
> register offsets. I wonder if the non-TDX part of this patch (i.e.

Hmm, I'd say keep your series as-is for now.  The OFFSET() infrastructure really
shines for proper assembly.  For what you're doing, AFAICT it's only marginally
better.  So I don't think it's worth juggling dependencies to use it right away,
we can always convert if/when the TDX series lands the fancy stuff.

---

## [26] Yosry Ahmed — 2026-05-22
*Subject: Re: [PATCH v13 07/22] KVM: selftests: Introduce structures for TDX
 guest boot parameters*

> > Sean, is this the preferred way to expose offsets to asm files (or asm
> > code blocks) -- as opposed to say using .equ [*]?

Ack. We can do the switch later like you say.

---

## [27] Yosry Ahmed — 2026-05-28
*Subject: Re: [PATCH v13 07/22] KVM: selftests: Introduce structures for TDX
 guest boot parameters*

On Fri, May 22, 2026 at 04:50:07PM -0700, Yosry Ahmed wrote:
> > > Sean, is this the preferred way to expose offsets to asm files (or asm
> > > code blocks) -- as opposed to say using .equ [*]?

I take this back. My series builds with the internal toolchain, but not
when I just use make with LLVM. Probably different compiler versions or
build options, but the fact the .equ thing doesn't always work means I
can't use it.

I would paste the error here, but the compiler literally spits out
incomprehensible garbage.

Lisa, if you will send a new version of this series for other reasons,
do you mind splitting out the non-TDX parts of this patch? Ideally we'd
have 1-2 patches that introduce the OFFSET() infrastructure without any
TDX parts, which should make it easier to pick up separately or include
with other series.

If a new version won't be needed anyway, I will just wait for this to
land before refreshing my series on top.

---

## [28] Ackerley Tng — 2026-06-05
*Subject: Re: [PATCH v13 19/22] KVM: selftests: Finalize TD memory as part of kvm_arch_vm_finalize_vcpus*

Lisa Wang <wyihan@google.com> writes:

> From: Sagi Shahar <sagis@google.com>
>

This doesn't necessarily block this series, we could (re)move this
later: I'm not sure if kvm_arch_vm_finalize_vcpus() is the correct place
to be finalizing the VM.

Was kvm_arch_vm_finalize_vcpus() supposed to be for finalizing vCPUs
instead?

The awkward part is that kvm_arch_vm_finalize_vcpus() is called from
__vm_create_with_vcpus().

While building this POC to test conversions [1] I only wanted to create
the vm and vcpus and didn't want to finalize yet, since I still needed
to do more mappings in the guest (and I needed the vm pointer to do
mappings in the guest).

Would calling tdx_vm_finalize() from within vcpu_run(), just once, be
too magical?

It's also possible to have some kvm_vm_finalize() call that can be
explicitly and manually invoked from selftests just for CoCo selftests.

[1] https://lore.kernel.org/all/20260605134153.204152-1-ackerleytng@google.com/

>  void setup_smram(struct kvm_vm *vm, struct kvm_vcpu *vcpu, u64 smram_gpa,
>  		 const void *smi_handler, size_t handler_size)

---

## [29] Sean Christopherson — 2026-06-05
*Subject: Re: [PATCH v13 19/22] KVM: selftests: Finalize TD memory as part of kvm_arch_vm_finalize_vcpus*

On Fri, Jun 05, 2026, Ackerley Tng wrote:
> Lisa Wang <wyihan@google.com> writes:
> 

Hmm, I would argue this is a flaw in the selftests infrastructure.  IMO, as a
developer, it's quite surprising that the current value of a global variable
doesn't show up in the VM automagically.  I totally understand why selftests
work that way, but it's certainly odd and annoying.  If _that_ were solved, then
the kludginess of what you're doing goes away.

The other way this could be solved is by adding support for annotating globals
with a __shared flag, a la the kernel's __bss_decrypted, so that loading memory
into the VM can automatically mark the associated globals' pages as shared.

> Would calling tdx_vm_finalize() from within vcpu_run(), just once, be
> too magical?

Yes.

> It's also possible to have some kvm_vm_finalize() call that can be
> explicitly and manually invoked from selftests just for CoCo selftests.

Why bother?  It's obviously possible to all kvm_arch_vm_finalize_vcpus() directly.

---

## [30] Ackerley Tng — 2026-06-05
*Subject: Re: [PATCH v13 19/22] KVM: selftests: Finalize TD memory as part of kvm_arch_vm_finalize_vcpus*

Sean Christopherson <seanjc@google.com> writes:

>
> [...snip...]

More generally, is your opinion that tests should not have to add extra
memslots?

If I wanted a shared page, would I have to do

  static __shared test_page[4096] = {0};

and then rely on ELF loading to put that in the guest for me? Are there
some compiler flags/how will I require that test_page be page aligned?

If I mark 10 globals as __shared, would the compiler automatically
consolidate the shared memory together?

I think it's a bit constraining to require that all guest memory be set
up statically. It's nice to have but I'd like another option...

Many tests use vm_userspace_mem_region_add(), CoCo tests that require
finalizing shouldn't be disallowed that option.

>> Would calling tdx_vm_finalize() from within vcpu_run(), just once, be
>> too magical?

Works for me to call directly. Do you mean kvm_arch_vm_finalize_vcpus()
is the right function where the TD is finalized?

For tests that need to do more setup after creating a vm, is the only
way out to call __vm_create() then vm_vcpu_add() to avoid premature
finalization in __vm_create_with_vcpus() when
kvm_arch_vm_finalize_vcpus() is called?

---

## [31] Sean Christopherson — 2026-06-05
*Subject: Re: [PATCH v13 19/22] KVM: selftests: Finalize TD memory as part of kvm_arch_vm_finalize_vcpus*

On Fri, Jun 05, 2026, Ackerley Tng wrote:
> Sean Christopherson <seanjc@google.com> writes:
> 

I don't care?  What I care about is making it as easy and intuitive as possible
for people to write tests, and to minimize maintenance costs.

> If I wanted a shared page, would I have to do
> 

Compilere and linker shenanigans.

> If I mark 10 globals as __shared, would the compiler automatically
> consolidate the shared memory together?

Yes, follow the __bss_decrypted breadcrumbs.

  #define __bss_decrypted __section(".bss..decrypted")

> I think it's a bit constraining to require that all guest memory be set
> up statically. It's nice to have but I'd like another option...

You do have options, they just require more work.

> Many tests use vm_userspace_mem_region_add(), CoCo tests that require
> finalizing shouldn't be disallowed that option.

What does that have to do with finalizing the VM?

> >> It's also possible to have some kvm_vm_finalize() call that can be
> >> explicitly and manually invoked from selftests just for CoCo selftests.

Depends on what you're doing.  Sometimes, the answer will be yes.  That's why
there are "low level" APIs, so that some tests can do fancy things, while most
tests can leave the details to the infrastructure.

If there's a recurring problem, or we anticipate one, then we can and should
figure out how to minimize the pain so that tests don't have to deal with the
same boilerplate issues over and over.  Hence the __shared idea.

---
