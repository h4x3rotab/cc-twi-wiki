---
title: 'KVM: x86: synthesize CPUID bits only if CPU capability is set'
date: 2026-02-09
last_reply: 2026-03-05
message_count: 3
participants: ['Carlos López', 'Nikolay Borisov', 'Sean Christopherson']
---

## [1] Carlos López — 2026-02-09

KVM incorrectly synthesizes CPUID bits for KVM-only leaves, as the
following branch in kvm_cpu_cap_init() is never taken:

    if (leaf < NCAPINTS)
        kvm_cpu_caps[leaf] &= kernel_cpu_caps[leaf];

This means that bits set via SYNTHESIZED_F() for KVM-only leaves are
unconditionally set. This for example can cause issues for SEV-SNP
guests running on Family 19h CPUs, as TSA_SQ_NO and TSA_L1_NO are
always enabled by KVM in 80000021[ECX]. When userspace issues a
SNP_LAUNCH_UPDATE command to update the CPUID page for the guest, SNP
firmware will explicitly reject the command if the page sets sets these
bits on vulnerable CPUs.

To fix this, check in SYNTHESIZED_F() that the corresponding X86
capability is set before adding it to to kvm_cpu_cap_features.

Fixes: 31272abd5974 ("KVM: SVM: Advertise TSA CPUID bits to guests")
Link: https://lore.kernel.org/all/20260208164233.30405-1-clopez@suse.de/
Signed-off-by: Carlos López <clopez@suse.de>
---
v2: fix SYNTHESIZED_F() instead of using SCATTERED_F() for TSA bits
 arch/x86/kvm/cpuid.c | 5 ++++-
 1 file changed, 4 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/cpuid.c b/arch/x86/kvm/cpuid.c
index 88a5426674a1..5f41924987c7 100644
--- a/arch/x86/kvm/cpuid.c
+++ b/arch/x86/kvm/cpuid.c
@@ -770,7 +770,10 @@ do {									\
 #define SYNTHESIZED_F(name)					\
 ({								\
 	kvm_cpu_cap_synthesized |= feature_bit(name);		\
-	F(name);						\
+								\
+	BUILD_BUG_ON(X86_FEATURE_##name >= MAX_CPU_FEATURES);	\
+	if (boot_cpu_has(X86_FEATURE_##name))			\
+		F(name);					\
 })
 
 /*

---

## [2] Nikolay Borisov — 2026-02-25
*Subject: Re: [PATCH v2] KVM: x86: synthesize CPUID bits only if CPU capability
 is set*

On 9.02.26 г. 17:31 ч., Carlos López wrote:
> KVM incorrectly synthesizes CPUID bits for KVM-only leaves, as the
> following branch in kvm_cpu_cap_init() is never taken:

Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>

> ---
> v2: fix SYNTHESIZED_F() instead of using SCATTERED_F() for TSA bits

---

## [3] Sean Christopherson — 2026-03-05
*Subject: Re: [PATCH v2] KVM: x86: synthesize CPUID bits only if CPU capability
 is set*

On Mon, 09 Feb 2026 16:31:09 +0100, Carlos López wrote:
> KVM incorrectly synthesizes CPUID bits for KVM-only leaves, as the
> following branch in kvm_cpu_cap_init() is never taken:

Applied to kvm-x86 fixes, thanks!

[1/1] KVM: x86: synthesize CPUID bits only if CPU capability is set
      https://github.com/kvm-x86/linux/commit/6a5028d8f9f4

--
https://github.com/kvm-x86/linux/tree/next

---
