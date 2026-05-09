---
title: '[PATCH v10 08/16] KVM: guest_memfd: Allow host to map guest_memfd\n pages'
date: 2025-06-02
last_reply: 2025-06-02
message_count: 2
participants: ['Shivank Garg', 'Fuad Tabba']
---

## [1] Shivank Garg — 2025-06-02

On 5/27/2025 11:32 PM, Fuad Tabba wrote:
> This patch enables support for shared memory in guest_memfd, including
> mapping that memory at the host userspace. This support is gated by the


I've been testing this patch-series. I did not saw failure with guest_memfd selftests but encountered a regression on my system with KVM_X86_DEFAULT_VM.

I'm getting below error in QEMU:
Issue #1 - QEMU fails to start with KVM_X86_DEFAULT_VM, showing:

qemu-system-x86_64: kvm_set_user_memory_region: KVM_SET_USER_MEMORY_REGION2 failed, slot=65536, start=0x0, size=0x80000000, flags=0x0, guest_memfd=-1, guest_memfd_offset=0x0: Invalid argument
kvm_set_phys_mem: error registering slot: Invalid argument

I did some digging to find out,
In kvm_set_memory_region as_id >= kvm_arch_nr_memslot_as_ids(kvm) now returns true.
(as_id:1 kvm_arch_nr_memslot_as_ids(kvm):1 id:0 KVM_MEM_SLOTS_NUM:32767)

/* SMM is currently unsupported for guests with guest_memfd (esp private) memory. */
# define kvm_arch_nr_memslot_as_ids(kvm) (kvm_arch_supports_gmem(kvm) ? 1 : 2)
evaluates to be 1

I'm still debugging to find answer to these question
Why slot=65536 and (as_id = mem->slot >> 16 = 1) is requested for KVM_X86_DEFAULT_VM case
which is making it fail for above check.
Was this change intentional for KVM_X86_DEFAULT_VM? Should this be considered as KVM regression or QEMU[1] compatibility issue?

---
Issue #2: Testing challenges with QEMU changes[2] and mmap Implementation:
Currently, QEMU only enables guest_memfd for SEV_SNP_GUEST (KVM_X86_SNP_VM) by setting require_guest_memfd=true. However, the new mmap implementation doesn't support SNP guests per kvm_arch_supports_gmem_shared_mem().

static void
sev_snp_guest_instance_init(Object *obj)
{
    ConfidentialGuestSupport *cgs = CONFIDENTIAL_GUEST_SUPPORT(obj);
    SevSnpGuestState *sev_snp_guest = SEV_SNP_GUEST(obj);

    cgs->require_guest_memfd = true;


To bypass this, I did two things and failed:
1. Enabling guest_memfd for KVM_X86_DEFAULT_VM in QEMU: Hits Issue #1 above
2. Adding KVM_X86_SNP_VM to kvm_arch_supports_gmem_shared_mem(): mmap() succeeds but QEMU stuck during boot.



My NUMA policy support for guest-memfd patch[3] depends on mmap() support and extends
kvm_gmem_vm_ops with get_policy/set_policy operations.
Since NUMA policy applies to both shared and private memory scenarios, what checks should
be included in the mmap() implementation, and what's the recommended approach for
integrating with your shared memory restrictions?


[1] https://github.com/qemu/qemu
[2] Snippet to QEMU changes to add mmap

+                new_block->guest_memfd = kvm_create_guest_memfd(
+                                           new_block->max_length, /*0 */GUEST_MEMFD_FLAG_SUPPORT_SHARED, errp);
+                if (new_block->guest_memfd < 0) {
+                        qemu_mutex_unlock_ramlist();
+                        goto out_free;
+                }
+                new_block->ptr_memfd = mmap(NULL, new_block->max_length,
+                                            PROT_READ | PROT_WRITE,
+                                            MAP_SHARED,
+                                            new_block->guest_memfd, 0);
+                if (new_block->ptr_memfd == MAP_FAILED) {
+                    error_report("Failed to mmap guest_memfd");
+                    qemu_mutex_unlock_ramlist();
+                    goto out_free;
+                }
+                printf("mmap successful\n");
+            }
[3] https://lore.kernel.org/linux-mm/20250408112402.181574-1-shivankg@amd.com



>  	/* Decided by the vendor code for other VM types.  */
>  	kvm->arch.pre_fault_allowed =

---

## [2] Fuad Tabba — 2025-06-02
*Subject: Re: [PATCH v10 08/16] KVM: guest_memfd: Allow host to map guest_memfd pages*

Hi Shivank,

On Mon, 2 Jun 2025 at 11:44, Shivank Garg <shivankg@amd.com> wrote:
>
>

Yes, this was intentional. We talked about this during the guest_memfd
biweekly sync on May 15 [*]. We came to the conclusion that we cannot
support SMM with private memory. KVM_X86_DEFAULT_VM cannot have
private memory, but guest_memfd with shared memory.

[*] https://docs.google.com/document/d/1M6766BzdY1Lhk7LiR5IqVR8B8mG3cr-cxTxOrAosPOk/edit?tab=t.0#heading=h.b4x45fcfgzvo

> ---
> Issue #2: Testing challenges with QEMU changes[2] and mmap Implementation:

KVM_X86_SNP_VM doesn't support in-place shared memory yet, so I think
this is to be expected for now.

Thanks,
/fuad

>
> [1] https://github.com/qemu/qemu

---
