---
title: 'KVM: SEV: Track SNP launch state and disallow invalid\n userspace interactions'
date: 2026-01-19
last_reply: 2026-03-06
message_count: 8
participants: ['Jethro Beekman', 'Sean Christopherson']
---

## [1] Jethro Beekman — 2026-01-19

Calling any of the SNP_LAUNCH_ ioctls after SNP_LAUNCH_FINISH results in a
kernel page fault due to RMP violation. Track SNP launch state and exit early.

vCPUs created after SNP_LAUNCH_FINISH won't have a guest VMSA automatically
created during SNP_LAUNCH_FINISH by converting the kernel-allocated VMSA. Don't
allocate a VMSA page, so that the vCPU is in a state similar to what it would
be after SNP AP destroy. This ensures pre_sev_run() prevents the vCPU from
running even if userspace makes the vCPU runnable.

Signed-off-by: Jethro Beekman <jethro@fortanix.com>
---
 arch/x86/kvm/svm/sev.c | 43 ++++++++++++++++++++++++++----------------
 arch/x86/kvm/svm/svm.h |  1 +
 2 files changed, 28 insertions(+), 16 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index f59c65abe3cf..cdaca10b8773 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2205,6 +2205,9 @@ static int snp_launch_start(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	if (!sev_snp_guest(kvm))
 		return -ENOTTY;
 
+	if (sev->snp_finished)
+		return -EINVAL;
+
 	if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
 		return -EFAULT;
 
@@ -2369,7 +2372,7 @@ static int snp_launch_update(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	void __user *src;
 	int ret = 0;
 
-	if (!sev_snp_guest(kvm) || !sev->snp_context)
+	if (!sev_snp_guest(kvm) || !sev->snp_context || sev->snp_finished)
 		return -EINVAL;
 
 	if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
@@ -2502,7 +2505,7 @@ static int snp_launch_finish(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	if (!sev_snp_guest(kvm))
 		return -ENOTTY;
 
-	if (!sev->snp_context)
+	if (!sev->snp_context || sev->snp_finished)
 		return -EINVAL;
 
 	if (copy_from_user(&params, u64_to_user_ptr(argp->data), sizeof(params)))
@@ -2548,13 +2551,15 @@ static int snp_launch_finish(struct kvm *kvm, struct kvm_sev_cmd *argp)
 	data->gctx_paddr = __psp_pa(sev->snp_context);
 	ret = sev_issue_cmd(kvm, SEV_CMD_SNP_LAUNCH_FINISH, data, &argp->error);
 
-	/*
-	 * Now that there will be no more SNP_LAUNCH_UPDATE ioctls, private pages
-	 * can be given to the guest simply by marking the RMP entry as private.
-	 * This can happen on first access and also with KVM_PRE_FAULT_MEMORY.
-	 */
-	if (!ret)
+	if (!ret) {
+		sev->snp_finished = true;
+		/*
+		 * Now that there will be no more SNP_LAUNCH_UPDATE ioctls, private pages
+		 * can be given to the guest simply by marking the RMP entry as private.
+		 * This can happen on first access and also with KVM_PRE_FAULT_MEMORY.
+		 */
 		kvm->arch.pre_fault_allowed = true;
+	}
 
 	kfree(id_auth);
 
@@ -3253,6 +3258,9 @@ void sev_free_vcpu(struct kvm_vcpu *vcpu)
 
 	svm = to_svm(vcpu);
 
+	if (!svm->sev_es.vmsa)
+		goto skip_vmsa_free;
+
 	/*
 	 * If it's an SNP guest, then the VMSA was marked in the RMP table as
 	 * a guest-owned page. Transition the page to hypervisor state before
@@ -4653,6 +4661,7 @@ void sev_init_vmcb(struct vcpu_svm *svm, bool init_event)
 
 int sev_vcpu_create(struct kvm_vcpu *vcpu)
 {
+	struct kvm_sev_info *sev = to_kvm_sev_info(vcpu->kvm);
 	struct vcpu_svm *svm = to_svm(vcpu);
 	struct page *vmsa_page;
 
@@ -4661,15 +4670,17 @@ int sev_vcpu_create(struct kvm_vcpu *vcpu)
 	if (!sev_es_guest(vcpu->kvm))
 		return 0;
 
-	/*
-	 * SEV-ES guests require a separate (from the VMCB) VMSA page used to
-	 * contain the encrypted register state of the guest.
-	 */
-	vmsa_page = snp_safe_alloc_page();
-	if (!vmsa_page)
-		return -ENOMEM;
+	if (!sev->snp_finished) {
+		/*
+		 * SEV-ES guests require a separate (from the VMCB) VMSA page used to
+		 * contain the encrypted register state of the guest.
+		 */
+		vmsa_page = snp_safe_alloc_page();
+		if (!vmsa_page)
+			return -ENOMEM;
 
-	svm->sev_es.vmsa = page_address(vmsa_page);
+		svm->sev_es.vmsa = page_address(vmsa_page);
+	}
 
 	vcpu->arch.guest_tsc_protected = snp_is_secure_tsc_enabled(vcpu->kvm);
 
diff --git a/arch/x86/kvm/svm/svm.h b/arch/x86/kvm/svm/svm.h
index 01be93a53d07..59c328c13b2a 100644
--- a/arch/x86/kvm/svm/svm.h
+++ b/arch/x86/kvm/svm/svm.h
@@ -96,6 +96,7 @@ struct kvm_sev_info {
 	bool active;		/* SEV enabled guest */
 	bool es_active;		/* SEV-ES enabled guest */
 	bool need_init;		/* waiting for SEV_INIT2 */
+	bool snp_finished;	/* SNP guest measurement has been finalized */
 	unsigned int asid;	/* ASID used for this guest */
 	unsigned int handle;	/* SEV firmware handle */
 	int fd;			/* SEV device fd */

---

## [2] Jethro Beekman — 2026-01-19
*Subject: Re: [PATCH] KVM: SEV: Track SNP launch state and disallow invalid
 userspace interactions*

On 2026-01-19 20:06, Jethro Beekman wrote:
> Calling any of the SNP_LAUNCH_ ioctls after SNP_LAUNCH_FINISH results in a
> kernel page fault due to RMP violation. Track SNP launch state and exit early.

I think there may be a race between this creation of a vCPU and the kvm_for_each_vcpu() loop in snp_launch_update_vmsa(). What should happen is that every vCPU that wasn't considered in snp_launch_update_vmsa() must not have a VMSA allocated here. If there is a race, I'm not sure what the best way is to prevent it.

>  
>  	vcpu->arch.guest_tsc_protected = snp_is_secure_tsc_enabled(vcpu->kvm);

---

## [3] Sean Christopherson — 2026-02-25
*Subject: Re: [PATCH] KVM: SEV: Track SNP launch state and disallow invalid
 userspace interactions*

On Mon, Jan 19, 2026, Jethro Beekman wrote:
> Calling any of the SNP_LAUNCH_ ioctls after SNP_LAUNCH_FINISH results in a
> kernel page fault due to RMP violation. Track SNP launch state and exit early.

What exactly trips the RMP #PF?  A backtrace would be especially helpful for
posterity.

I ask because it's basically impossible to determine if this approach is optimal
without knowing exactly what's going wrong.  Semantically it sounds reasonable,
but ideally KVM would naturally handle userspace stupidity (without exploding).

---

## [4] Jethro Beekman — 2026-02-25
*Subject: Re: [PATCH] KVM: SEV: Track SNP launch state and disallow invalid
 userspace interactions*

On 2026-02-25 12:05, Sean Christopherson wrote:
> On Mon, Jan 19, 2026, Jethro Beekman wrote:
>> Calling any of the SNP_LAUNCH_ ioctls after SNP_LAUNCH_FINISH results in a

Here's a backtrace for calling ioctl(KVM_SEV_SNP_LAUNCH_FINISH) twice. Note this is with a modified version of QEMU.

BUG: unable to handle page fault for address: ff1276cbfdf36000
#PF: supervisor write access in kernel mode
#PF: error_code(0x80000003) - RMP violation
PGD 5a31801067 P4D 5a31802067 PUD 40ccfb5063 PMD 40e5954063 PTE 80000040fdf36163
SEV-SNP: PFN 0x40fdf36, RMP entry: [0x6010fffffffff001 - 0x000000000000001f]
Oops: Oops: 0003 [#1] SMP NOPTI
CPU: 33 UID: 0 PID: 996180 Comm: qemu-system-x86 Tainted: G           OE       6.18.0-8-generic #8-Ubuntu PREEMPT(voluntary) 
Tainted: [O]=OOT_MODULE, [E]=UNSIGNED_MODULE
Hardware name: Dell Inc. PowerEdge R7625/0H1TJT, BIOS 1.5.8 07/21/2023
RIP: 0010:sev_es_sync_vmsa+0x54/0x4c0 [kvm_amd]
Code: 89 f8 48 8d b2 00 04 00 00 48 89 e5 41 56 41 54 53 48 83 ec 30 48 8b 9f 18 1c 00 00 48 8b 8a 00 04 00 00 4c 8b 07 48 8d 7b 08 <48> 89 0b 48 89 d9 48 8b 92 e0 06 00 00 48 83 e7 f8 48 29 f9 48 89
RSP: 0018:ff42462db15fb8b8 EFLAGS: 00010286
RAX: ff1276d253008000 RBX: ff1276cbfdf36000 RCX: 0000ffff00930000
RDX: ff1276cb899e6000 RSI: ff1276cb899e6400 RDI: ff1276cbfdf36008
RBP: ff42462db15fb900 R08: ff1276cbfb1f2000 R09: 0000000000000000
R10: 0000000000000000 R11: 0000000000000000 R12: ff1276cbfb1f2000
R13: 00007fffffffdc10 R14: ff1276cbfb1f3188 R15: ff42462db15fba70
FS:  00007ffff6846f40(0000) GS:ff1276cacfaf0000(0000) knlGS:0000000000000000
CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
CR2: ff1276cbfdf36000 CR3: 0000004628e03004 CR4: 0000000000f71ef0
PKRU: 55555554
Call Trace:
 <TASK>
 snp_launch_update_vmsa+0x19d/0x290 [kvm_amd]
 snp_launch_finish+0xb6/0x380 [kvm_amd]
 sev_mem_enc_ioctl+0x14e/0x720 [kvm_amd]
 kvm_arch_vm_ioctl+0x837/0xcf0 [kvm]
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? hook_file_ioctl+0x10/0x20
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? __x64_sys_ioctl+0xbd/0x100
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? kvm_vm_ioctl+0x3fd/0xcc0 [kvm]
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? __x64_sys_ioctl+0xbd/0x100
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? arch_exit_to_user_mode_prepare.isra.0+0xd/0xe0
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? rseq_get_rseq_cs.isra.0+0x16/0x240
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? kvm_vm_ioctl+0x3fd/0xcc0 [kvm]
 ? srso_alias_return_thunk+0x5/0xfbef5
 kvm_vm_ioctl+0x3fd/0xcc0 [kvm]
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? arch_exit_to_user_mode_prepare.isra.0+0xc5/0xe0
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? do_syscall_64+0xb9/0x10f0
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? __rseq_handle_notify_resume+0xbb/0x1c0
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? hook_file_ioctl+0x10/0x20
 ? srso_alias_return_thunk+0x5/0xfbef5
 __x64_sys_ioctl+0xa3/0x100
 ? arch_exit_to_user_mode_prepare.isra.0+0xc5/0xe0
 x64_sys_call+0xfe0/0x2350
 do_syscall_64+0x81/0x10f0
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? arch_exit_to_user_mode_prepare.isra.0+0xd/0x100
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? irqentry_exit_to_user_mode+0x2d/0x1d0
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? irqentry_exit+0x43/0x50
 ? srso_alias_return_thunk+0x5/0xfbef5
 ? exc_page_fault+0x90/0x1b0
 entry_SYSCALL_64_after_hwframe+0x76/0x7e
RIP: 0033:0x7ffff673287d
Code: 04 25 28 00 00 00 48 89 45 c8 31 c0 48 8d 45 10 c7 45 b0 10 00 00 00 48 89 45 b8 48 8d 45 d0 48 89 45 c0 b8 10 00 00 00 0f 05 <89> c2 3d 00 f0 ff ff 77 1a 48 8b 45 c8 64 48 2b 04 25 28 00 00 00
RSP: 002b:00007fffffffda80 EFLAGS: 00000246 ORIG_RAX: 0000000000000010
RAX: ffffffffffffffda RBX: 00000000c008aeba RCX: 00007ffff673287d
RDX: 00007fffffffdc10 RSI: 00000000c008aeba RDI: 0000000000000008
RBP: 00007fffffffdad0 R08: 0000000000811000 R09: 00005555562737f0
R10: 00005555576631b0 R11: 0000000000000246 R12: 00007fffffffdc10
R13: 0000555557695f80 R14: 0000000000001000 R15: 00007fff73c75000
 </TASK>
Modules linked in: kvm_amd nf_conntrack_netlink veth ecdsa_generic vfio_pci vfio_pci_core vfio_iommu_type1 vfio iommufd amd_atl intel_rapl_msr intel_rapl_common amd64_edac edac_mce_amd xfrm_user xfrm_algo xt_set ip_set bonding cfg80211 nft_chain_nat xt_MASQUERADE nf_nat binfmt_misc xt_addrtype xt_conntrack nf_conntrack nf_defrag_ipv6 nf_defrag_ipv4 nft_compat nf_tables xfs nls_iso8859_1 ipmi_ssif platform_profile dell_wmi video spd5118 sparse_keymap kvm irqbypass dell_smbios dax_hmem dcdbas cxl_acpi rapl cxl_port dell_wmi_descriptor wmi_bmof mgag200 i2c_algo_bit acpi_power_meter cxl_core i2c_piix4 einj ipmi_si acpi_ipmi k10temp ccp i2c_smbus ipmi_devintf mlx5_fwctl joydev input_leds fwctl ipmi_msghandler mac_hid nfsd auth_rpcgss nfs_acl lockd grace sch_fq_codel sunrpc br_netfilter bridge stp llc overlay efi_pstore dm_multipath nfnetlink dmi_sysfs ip_tables x_tables autofs4 btrfs blake2b_generic raid10 raid456 async_raid6_recov async_memcpy async_pq async_xor async_tx xor raid6_pq raid1 linear mlx5_ib
 ib_uverbs macsec ib_core raid0 hid_generic usbhid hid mlx5_core nvme mlxfw nvme_core psample polyval_clmulni ghash_clmulni_intel nvme_keyring tls ahci nvme_auth megaraid_sas libahci pci_hyperv_intf hkdf wmi aesni_intel [last unloaded: kvm_amd(OE)]
CR2: ff1276cbfdf36000
---[ end trace 0000000000000000 ]---
pstore: backend (erst) writing error (-22)
RIP: 0010:sev_es_sync_vmsa+0x54/0x4c0 [kvm_amd]
Code: 89 f8 48 8d b2 00 04 00 00 48 89 e5 41 56 41 54 53 48 83 ec 30 48 8b 9f 18 1c 00 00 48 8b 8a 00 04 00 00 4c 8b 07 48 8d 7b 08 <48> 89 0b 48 89 d9 48 8b 92 e0 06 00 00 48 83 e7 f8 48 29 f9 48 89
RSP: 0018:ff42462db15fb8b8 EFLAGS: 00010286
RAX: ff1276d253008000 RBX: ff1276cbfdf36000 RCX: 0000ffff00930000
RDX: ff1276cb899e6000 RSI: ff1276cb899e6400 RDI: ff1276cbfdf36008
RBP: ff42462db15fb900 R08: ff1276cbfb1f2000 R09: 0000000000000000
R10: 0000000000000000 R11: 0000000000000000 R12: ff1276cbfb1f2000
R13: 00007fffffffdc10 R14: ff1276cbfb1f3188 R15: ff42462db15fba70
FS:  00007ffff6846f40(0000) GS:ff1276cacfaf0000(0000) knlGS:0000000000000000
CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
CR2: ff1276cbfdf36000 CR3: 0000004628e03004 CR4: 0000000000f71ef0
PKRU: 55555554
note: qemu-system-x86[996180] exited with irqs disabled

--
Jethro Beekman | CTO | Fortanix

---

## [5] Sean Christopherson — 2026-02-25
*Subject: Re: [PATCH] KVM: SEV: Track SNP launch state and disallow invalid
 userspace interactions*

On Wed, Feb 25, 2026, Jethro Beekman wrote:
> On 2026-02-25 12:05, Sean Christopherson wrote:
> > On Mon, Jan 19, 2026, Jethro Beekman wrote:

> RIP: 0010:sev_es_sync_vmsa+0x54/0x4c0 [kvm_amd]
>  snp_launch_update_vmsa+0x19d/0x290 [kvm_amd]

Ah, it's the VMSA that's being accessed.  Can't we just do?

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index 723f4452302a..1e40ae592c93 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -882,6 +882,9 @@ static int sev_es_sync_vmsa(struct vcpu_svm *svm)
        u8 *d;
        int i;
 
+       if (vcpu->arch.guest_state_protected)
+               return -EINVAL;
+
        /* Check some debug related fields before encrypting the VMSA */
        if (svm->vcpu.guest_debug || (svm->vmcb->save.dr7 & ~DR7_FIXED_1))
                return -EINVAL;

---

## [6] Jethro Beekman — 2026-02-25
*Subject: Re: [PATCH] KVM: SEV: Track SNP launch state and disallow invalid
 userspace interactions*

On 2026-02-25 12:21, Sean Christopherson wrote:
> On Wed, Feb 25, 2026, Jethro Beekman wrote:
>> On 2026-02-25 12:05, Sean Christopherson wrote:

I tried relying on guest_state_protected instead of creating new state but I don't think it's sufficient. In particular, your proposal may fix snp_launch_finish() but I don't believe this addresses the issues in snp_launch_update() and sev_vcpu_create().

---

## [7] Sean Christopherson — 2026-02-26
*Subject: Re: [PATCH] KVM: SEV: Track SNP launch state and disallow invalid
 userspace interactions*

On Wed, Feb 25, 2026, Jethro Beekman wrote:
> On 2026-02-25 12:21, Sean Christopherson wrote:
> > On Wed, Feb 25, 2026, Jethro Beekman wrote:

But it does fix that case, correct?  I don't want to complicate one fix just
because there are other bugs that are similar but yet distinct.

> but I don't believe this addresses the issues in snp_launch_update() and

Do you mean snp_launch_update_vmsa() here?  Or am I missing an interaction with
vCPUs in snp_launch_update()?

> sev_vcpu_create().

There are a pile of SEV lifecycle and locking issues, i.e. this is just one of
several flaws.  Fixing the locking has been on my todo list for a few months (we
found some "fun" bugs with an internal run of syzkaller), and I'm finally getting
to it.  Hopefully I'll post a series early next week.

Somewhat off the cuff, but I think the easiest way to close the race between
KVM_CREATE_VCPU and KVM_SEV_SNP_LAUNCH_FINISH is to reject KVM_SEV_SNP_LAUNCH_FINISH
if a vCPU is being created.  Or did I misunderstand the race you're pointing out?

Though unless there's a strong reason not to, I'd prefer to get greedy and block
all of sev_mem_enc_ioctl(), e.g.

11:23:23 ✔ ~/go/src/kernel.org/linux $ gdd
diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index ea515cf41168..2b1033c0ec54 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -2047,8 +2047,8 @@ static int sev_check_source_vcpus(struct kvm *dst, struct kvm *src)
        struct kvm_vcpu *src_vcpu;
        unsigned long i;
 
-       if (src->created_vcpus != atomic_read(&src->online_vcpus) ||
-           dst->created_vcpus != atomic_read(&dst->online_vcpus))
+       if (kvm_is_vcpu_creation_in_progress(src) ||
+           kvm_is_vcpu_creation_in_progress(dst))
                return -EBUSY;
 
        if (!sev_es_guest(src))
@@ -2596,6 +2596,11 @@ int sev_mem_enc_ioctl(struct kvm *kvm, void __user *argp)
                goto out;
        }
 
+       if (kvm_is_vcpu_creation_in_progress(kvm)) {
+               r = -EBUSY;
+               goto out;
+       }
+
        /*
         * Once KVM_SEV_INIT2 initializes a KVM instance as an SNP guest, only
         * allow the use of SNP-specific commands.
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 2c7d76262898..60ca5222e1e5 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -1032,6 +1032,13 @@ static inline struct kvm_vcpu *kvm_get_vcpu_by_id(struct kvm *kvm, int id)
        return NULL;
 }
 
+static inline bool kvm_is_vcpu_creation_in_progress(struct kvm *kvm)
+{
+       lockdep_assert_held(&kvm->lock);
+
+       return kvm->created_vcpus != atomic_read(&kvm->online_vcpus);
+}
+
 void kvm_destroy_vcpus(struct kvm *kvm);
 
 int kvm_trylock_all_vcpus(struct kvm *kvm);

---

## [8] Sean Christopherson — 2026-03-06
*Subject: Re: [PATCH] KVM: SEV: Track SNP launch state and disallow invalid
 userspace interactions*

On Thu, Feb 26, 2026, Sean Christopherson wrote:
> On Wed, Feb 25, 2026, Jethro Beekman wrote:
> > On 2026-02-25 12:21, Sean Christopherson wrote:

Circling back to this (writing changelogs), I don't think there's actually a
novel bug with respect to KVM_SEV_SNP_LAUNCH_FINISH racing with KVM_CREATE_VCPU.

kvm_for_each_vcpu() operates on online_vcpus, LAUNCH_FINISH (all SEV+ sub-ioctls)
holds kvm->mutex, and fully onlining a vCPU in kvm_vm_ioctl_create_vcpu() is done
under kvm->mutex.  So AFAICT, there's no difference between an in-progress vCPU
and a vCPU that is created entirely after LAUNCH_FINISH.

It's probably worth preventing as a hardening measure, but I don't think there's
an actual bug to be fixed.

---
