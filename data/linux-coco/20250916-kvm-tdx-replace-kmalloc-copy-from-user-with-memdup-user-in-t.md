---
title: 'KVM: TDX: Replace kmalloc + copy_from_user with memdup_user in tdx_td_init'
date: 2025-09-16
last_reply: 2025-10-15
message_count: 4
participants: ['Thorsten Blum', 'Sean Christopherson']
---

## [1] Thorsten Blum — 2025-09-16

Use get_user() to retrieve the number of entries instead of allocating
memory for 'init_vm' with the maximum size, copying 'cmd->data' to it,
only to then read the actual entry count 'cpuid.nent' from the copy.

Return -E2BIG early if 'nr_user_entries' exceeds KVM_MAX_CPUID_ENTRIES.

Use memdup_user() to allocate just enough memory to fit all entries and
to copy 'cmd->data' from userspace. Use struct_size() instead of
manually calculating the number of bytes to allocate and copy.

No functional changes intended.

Signed-off-by: Thorsten Blum <thorsten.blum@linux.dev>
---
Compile-tested only.
---
 arch/x86/kvm/vmx/tdx.c | 32 ++++++++++++--------------------
 1 file changed, 12 insertions(+), 20 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 66744f5768c8..87510541d2a2 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -2742,8 +2742,10 @@ static int tdx_read_cpuid(struct kvm_vcpu *vcpu, u32 leaf, u32 sub_leaf,
 static int tdx_td_init(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 {
 	struct kvm_tdx *kvm_tdx = to_kvm_tdx(kvm);
+	struct kvm_tdx_init_vm __user *user_init_vm;
 	struct kvm_tdx_init_vm *init_vm;
 	struct td_params *td_params = NULL;
+	u32 nr_user_entries;
 	int ret;
 
 	BUILD_BUG_ON(sizeof(*init_vm) != 256 + sizeof_field(struct kvm_tdx_init_vm, cpuid));
@@ -2755,28 +2757,18 @@ static int tdx_td_init(struct kvm *kvm, struct kvm_tdx_cmd *cmd)
 	if (cmd->flags)
 		return -EINVAL;
 
-	init_vm = kmalloc(sizeof(*init_vm) +
-			  sizeof(init_vm->cpuid.entries[0]) * KVM_MAX_CPUID_ENTRIES,
-			  GFP_KERNEL);
-	if (!init_vm)
-		return -ENOMEM;
-
-	if (copy_from_user(init_vm, u64_to_user_ptr(cmd->data), sizeof(*init_vm))) {
-		ret = -EFAULT;
-		goto out;
-	}
+	user_init_vm = u64_to_user_ptr(cmd->data);
+	ret = get_user(nr_user_entries, &user_init_vm->cpuid.nent);
+	if (ret)
+		return ret;
 
-	if (init_vm->cpuid.nent > KVM_MAX_CPUID_ENTRIES) {
-		ret = -E2BIG;
-		goto out;
-	}
+	if (nr_user_entries > KVM_MAX_CPUID_ENTRIES)
+		return -E2BIG;
 
-	if (copy_from_user(init_vm->cpuid.entries,
-			   u64_to_user_ptr(cmd->data) + sizeof(*init_vm),
-			   flex_array_size(init_vm, cpuid.entries, init_vm->cpuid.nent))) {
-		ret = -EFAULT;
-		goto out;
-	}
+	init_vm = memdup_user(user_init_vm,
+			      struct_size(user_init_vm, cpuid.entries, nr_user_entries));
+	if (IS_ERR(init_vm))
+		return PTR_ERR(init_vm);
 
 	if (memchr_inv(init_vm->reserved, 0, sizeof(init_vm->reserved))) {
 		ret = -EINVAL;

---

## [2] Sean Christopherson — 2025-10-13
*Subject: Re: [PATCH] KVM: TDX: Replace kmalloc + copy_from_user with
 memdup_user in tdx_td_init*

On Tue, Sep 16, 2025, Thorsten Blum wrote:
> Use get_user() to retrieve the number of entries instead of allocating
> memory for 'init_vm' with the maximum size, copying 'cmd->data' to it,

I think I'll drop this line from the changelog.  At first glance I thought you
were calling out a change in behavior, and my hackles went up.  :-)

> Use memdup_user() to allocate just enough memory to fit all entries and
> to copy 'cmd->data' from userspace. Use struct_size() instead of

Any objection to calling this user_data instead of user_init_vm?  I keep reading
user_init_vm as a flag or command, e.g. "user initialized VM" or something, not
as a pointer to user data.

No need for a v2, I'll fixup to whatever we settle on (assuming no one jumps in
with a crazy idea).

---

## [3] Thorsten Blum — 2025-10-14
*Subject: Re: [PATCH] KVM: TDX: Replace kmalloc + copy_from_user with
 memdup_user in tdx_td_init*

On 14. Oct 2025, at 00:15, Sean Christopherson wrote:
> On Tue, Sep 16, 2025, Thorsten Blum wrote:
>> Use get_user() to retrieve the number of entries instead of allocating

No objection.

> No need for a v2, I'll fixup to whatever we settle on (assuming no one jumps in
> with a crazy idea).

Ok thanks!

---

## [4] Sean Christopherson — 2025-10-15
*Subject: Re: [PATCH] KVM: TDX: Replace kmalloc + copy_from_user with
 memdup_user in tdx_td_init*

On Tue, 16 Sep 2025 23:31:29 +0200, Thorsten Blum wrote:
> Use get_user() to retrieve the number of entries instead of allocating
> memory for 'init_vm' with the maximum size, copying 'cmd->data' to it,

Applied to kvm-x86 vmx, with the aforementioned tweaks.  Thanks!

[1/1] KVM: TDX: Replace kmalloc + copy_from_user with memdup_user in tdx_td_init
      https://github.com/kvm-x86/linux/commit/0bd0a4a1428b

--
https://github.com/kvm-x86/linux/tree/next

---
