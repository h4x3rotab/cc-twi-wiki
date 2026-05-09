---
title: "kexec_core: Accept unaccepted kexec segments' destination addresses"
date: 2025-03-07
last_reply: 2025-03-07
message_count: 1
participants: ['Kirill A. Shutemov']
---

## [1] Kirill A. Shutemov — 2025-03-07

From: Yan Zhao <yan.y.zhao@intel.com>

The UEFI Specification version 2.9 introduces the concept of memory
acceptance: some Virtual Machine platforms, such as Intel TDX or AMD
SEV-SNP, require memory to be accepted before it can be used by the
guest.

Accepting memory is expensive. The memory must be allocated by the VMM
and then brought to a known safe state: cache must be flushed, memory
must be zeroed with the guest's encryption key, and associated metadata
must be manipulated. These operations must be performed from a trusted
environment (firmware or TDX module). Switching context to and from it
also takes time.

This cost adds up. On large confidential VMs, memory acceptance alone
can take minutes. It is better to delay memory acceptance until the
memory is actually needed.

The kernel accepts memory when it is allocated from buddy allocator for
the first time. This reduces boot time and decreases memory overhead as
the VMM can allocate memory as needed.

It does not work when the guest attempts to kexec into a new kernel.

The kexec segments' destination addresses are not allocated by the buddy
allocator. Instead, they are searched from normal system RAM (top-down or
bottom-up) and exclude driver-managed memory, ACPI, persistent, and
reserved memory. Unaccepted memory is normal system RAM from kernel
point of view and kexec can place segments there.

Kexec bypasses the code path in buddy allocator where memory gets
accepted and it leads to a crash when kexec accesses segments' memory.

Accept the destination addresses during the kexec load, immediately after
they pass sanity checks. This ensures the code is located in a common place
shared by both the kexec_load and kexec_file_load system calls.

This will not conflict with the accounting in try_to_accept_memory_one()
since the accounting is set during kernel boot and decremented when pages
are moved to the freelists. There is no harm in invoking accept_memory() on
a page before making it available to the buddy allocator.

No need to worry about re-accepting memory since accept_memory() checks the
unaccepted bitmap before accepting a memory page.

Although a user may perform kexec loading without ever triggering the jump,
it doesn't impact much since kexec loading is not in a performance-critical
path. Additionally, the destination addresses are always searched and found
in the same location on a given system.

Changes to the destination address searching logic to locate only memory in
either unaccepted or accepted status are unnecessary and complicated.

Signed-off-by: Yan Zhao <yan.y.zhao@intel.com>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
[ kirill: Update the commit message ]
Acked-by: Dave Hansen <dave.hansen@linux.intel.com>
Cc: "Eric W. Biederman" <ebiederm@xmission.com>
Cc: Ashish Kalra <Ashish.Kalra@amd.com>
Cc: Baoquan He <bhe@redhat.com>
Cc: Jianxiong Gao <jxgao@google.com>
---
 v3:
   - Update the commit message and retest the patch.

 kernel/kexec_core.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/kernel/kexec_core.c b/kernel/kexec_core.c
index c0bdc1686154..9a2095216f4f 100644
--- a/kernel/kexec_core.c
+++ b/kernel/kexec_core.c
@@ -210,6 +210,16 @@ int sanity_check_segment_list(struct kimage *image)
 	}
 #endif
 
+	/*
+	 * The destination addresses are searched from system RAM rather than
+	 * being allocated from the buddy allocator, so they are not guaranteed
+	 * to be accepted by the current kernel.  Accept the destination
+	 * addresses before kexec swaps their content with the segments' source
+	 * pages to avoid accessing memory before it is accepted.
+	 */
+	for (i = 0; i < nr_segments; i++)
+		accept_memory(image->segment[i].mem, image->segment[i].memsz);
+
 	return 0;
 }

---
