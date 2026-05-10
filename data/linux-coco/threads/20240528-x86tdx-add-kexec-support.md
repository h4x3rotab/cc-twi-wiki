---
title: 'x86/tdx: Add kexec support'
date: 2024-05-28
last_reply: 2024-06-21
message_count: 115
participants: ['Kirill A. Shutemov', 'Rafael J. Wysocki', 'Huang, Kai', 'Borislav Petkov', 'Nikolay Borisov', 'Andrew Cooper', 'Ashish Kalra', 'Alexander Kuleshov', 'Mike Rapoport', 'H. Peter Anvin', 'Dave Young', 'Dave Hansen', 'Ard Biesheuvel', 'Tom Lendacky']
---

## [1] Kirill A. Shutemov — 2024-05-28

The patchset adds bits and pieces to get kexec (and crashkernel) work on
TDX guest.

The last patch implements CPU offlining according to the approved ACPI
spec change poposal[1]. It unlocks kexec with all CPUs visible in the target
kernel. It requires BIOS-side enabling. If it missing we fallback to booting
2nd kernel with single CPU.

Please review. I would be glad for any feedback.

[1] https://lore.kernel.org/all/13356251.uLZWGnKmhe@kreacher

v11:
  - Rebased onto current tip/master;
  - Rename CONFIG_X86_ACPI_MADT_WAKEUP to CONFIG_ACPI_MADT_WAKEUP;
  - Drop CC_ATTR_GUEST_MEM_ENCRYPT checks around x86_platform.guest.enc_kexec_*
    callbacks;
  - Rename x86_platform.guest.enc_kexec_* callbacks;
  - Report error code in case of vmm call fail in __set_memory_enc_pgtable();
  - Update commit messages and comments;
  - Add Reviewed-bys;
v10:
  - Rebased to current tip/master;
  - Preserve CR4.MCE instead of setting it unconditionally;
  - Fix build error in Hyper-V code after rebase;
  - Include Ashish's patch for real;
v9:
  - Rebased;
  - Keep page tables that maps E820_TYPE_ACPI (Ashish);
  - Ack/Reviewed/Tested-bys from Sathya, Kai, Tao;
  - Minor printk() message adjustments;
v8:
  - Rework serialization of around conversion memory back to private;
  - Print ACPI_MADT_TYPE_MULTIPROC_WAKEUP in acpi_table_print_madt_entry();
  - Drop debugfs interface to dump info on shared memory;
  - Adjust comments and commit messages;
  - Reviewed-bys by Baoquan, Dave and Thomas;
v7:
  - Call enc_kexec_stop_conversion() and enc_kexec_unshare_mem() after shutting
    down IO-APIC, lapic and hpet. It meets AMD requirements.
  - Minor style changes;
  - Add Acked/Reviewed-bys;
v6:
  - Rebased to v6.8-rc1;
  - Provide default noop callbacks from .enc_kexec_stop_conversion and
    .enc_kexec_unshare_mem;
  - Split off patch that introduces .enc_kexec_* callbacks;
  - asm_acpi_mp_play_dead(): program CR3 directly from RSI, no MOV to RAX
    required;
  - Restructure how smp_ops.stop_this_cpu() hooked up in crash_nmi_callback();
  - kvmclock patch got merged via KVM tree;
v5:
  - Rename smp_ops.crash_play_dead to smp_ops.stop_this_cpu and use it in
    stop_this_cpu();
  - Split off enc_kexec_stop_conversion() from enc_kexec_unshare_mem();
  - Introduce kernel_ident_mapping_free();
  - Add explicit include for alternatives and stringify.
  - Add barrier() after setting conversion_allowed to false;
  - Mark cpu_hotplug_offline_disabled __ro_after_init;
  - Print error if failed to hand over CPU to BIOS;
  - Update comments and commit messages;
v4:
  - Fix build for !KEXEC_CORE;
  - Cleaner ATLERNATIVE use;
  - Update commit messages and comments;
  - Add Reviewed-bys;
v3:
  - Rework acpi_mp_crash_stop_other_cpus() to avoid invoking hotplug state
    machine;
  - Free page tables if reset vector setup failed;
  - Change asm_acpi_mp_play_dead() to pass reset vector and PGD as arguments;
  - Mark acpi_mp_* variables as static and __ro_after_init;
  - Use u32 for apicid;
  - Disable CPU offlining if reset vector setup failed;
  - Rename madt.S -> madt_playdead.S;
  - Mark tdx_kexec_unshare_mem() as static;
  - Rebase onto up-to-date tip/master;
  - Whitespace fixes;
  - Reorder patches;
  - Add Reviewed-bys;
  - Update comments and commit messages;
v2:
  - Rework how unsharing hook ups into kexec codepath;
  - Rework kvmclock_disable() fix based on Sean's;
  - s/cpu_hotplug_not_supported()/cpu_hotplug_disable_offlining()/;
  - use play_dead_common() to implement acpi_mp_play_dead();
  - cond_resched() in tdx_shared_memory_show();
  - s/target kernel/second kernel/;
  - Update commit messages and comments;

Ashish Kalra (1):
  x86/mm: Do not zap page table entries mapping unaccepted memory table
    during kdump.

Borislav Petkov (1):
  x86/relocate_kernel: Use named labels for less confusion

Kirill A. Shutemov (17):
  x86/acpi: Extract ACPI MADT wakeup code into a separate file
  x86/apic: Mark acpi_mp_wake_* variables as __ro_after_init
  cpu/hotplug: Add support for declaring CPU offlining not supported
  cpu/hotplug, x86/acpi: Disable CPU offlining for ACPI MADT wakeup
  x86/kexec: Keep CR4.MCE set during kexec for TDX guest
  x86/mm: Make x86_platform.guest.enc_status_change_*() return errno
  x86/mm: Return correct level from lookup_address() if pte is none
  x86/tdx: Account shared memory
  x86/mm: Add callbacks to prepare encrypted memory for kexec
  x86/tdx: Convert shared memory back to private on kexec
  x86/mm: Make e820__end_ram_pfn() cover E820_TYPE_ACPI ranges
  x86/acpi: Rename fields in acpi_madt_multiproc_wakeup structure
  x86/acpi: Do not attempt to bring up secondary CPUs in kexec case
  x86/smp: Add smp_ops.stop_this_cpu() callback
  x86/mm: Introduce kernel_ident_mapping_free()
  x86/acpi: Add support for CPU offlining for ACPI MADT wakeup method
  ACPI: tables: Print MULTIPROC_WAKEUP when MADT is parsed

 arch/x86/Kconfig                     |   7 +
 arch/x86/coco/core.c                 |   1 -
 arch/x86/coco/tdx/tdx.c              |  96 ++++++++-
 arch/x86/hyperv/ivm.c                |  22 +-
 arch/x86/include/asm/acpi.h          |   7 +
 arch/x86/include/asm/init.h          |   3 +
 arch/x86/include/asm/pgtable.h       |   5 +
 arch/x86/include/asm/pgtable_types.h |   1 +
 arch/x86/include/asm/set_memory.h    |   3 +
 arch/x86/include/asm/smp.h           |   1 +
 arch/x86/include/asm/x86_init.h      |  13 +-
 arch/x86/kernel/acpi/Makefile        |   1 +
 arch/x86/kernel/acpi/boot.c          |  86 +-------
 arch/x86/kernel/acpi/madt_playdead.S |  28 +++
 arch/x86/kernel/acpi/madt_wakeup.c   | 292 +++++++++++++++++++++++++++
 arch/x86/kernel/crash.c              |  12 ++
 arch/x86/kernel/e820.c               |   9 +-
 arch/x86/kernel/process.c            |   7 +
 arch/x86/kernel/reboot.c             |  18 ++
 arch/x86/kernel/relocate_kernel_64.S |  25 ++-
 arch/x86/kernel/x86_init.c           |   8 +-
 arch/x86/mm/ident_map.c              |  73 +++++++
 arch/x86/mm/init_64.c                |  16 +-
 arch/x86/mm/mem_encrypt_amd.c        |   8 +-
 arch/x86/mm/pat/set_memory.c         |  74 +++++--
 drivers/acpi/tables.c                |  14 ++
 include/acpi/actbl2.h                |  19 +-
 include/linux/cc_platform.h          |  10 -
 include/linux/cpu.h                  |   2 +
 kernel/cpu.c                         |  12 +-
 30 files changed, 707 insertions(+), 166 deletions(-)
 create mode 100644 arch/x86/kernel/acpi/madt_playdead.S
 create mode 100644 arch/x86/kernel/acpi/madt_wakeup.c

---

## [2] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 01/19] x86/acpi: Extract ACPI MADT wakeup code into a separate file*

In order to prepare for the expansion of support for the ACPI MADT
wakeup method, move the relevant code into a separate file.

Introduce a new configuration option to clearly indicate dependencies
without the use of ifdefs.

There have been no functional changes.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Baoquan He <bhe@redhat.com>
Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/Kconfig                   |  7 +++
 arch/x86/include/asm/acpi.h        |  5 ++
 arch/x86/kernel/acpi/Makefile      |  1 +
 arch/x86/kernel/acpi/boot.c        | 86 +-----------------------------
 arch/x86/kernel/acpi/madt_wakeup.c | 82 ++++++++++++++++++++++++++++
 5 files changed, 96 insertions(+), 85 deletions(-)
 create mode 100644 arch/x86/kernel/acpi/madt_wakeup.c

diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index e8837116704c..e30ea4129d2c 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -1118,6 +1118,13 @@ config X86_LOCAL_APIC
 	depends on X86_64 || SMP || X86_32_NON_STANDARD || X86_UP_APIC || PCI_MSI
 	select IRQ_DOMAIN_HIERARCHY
 
+config ACPI_MADT_WAKEUP
+	def_bool y
+	depends on X86_64
+	depends on ACPI
+	depends on SMP
+	depends on X86_LOCAL_APIC
+
 config X86_IO_APIC
 	def_bool y
 	depends on X86_LOCAL_APIC || X86_UP_IOAPIC
diff --git a/arch/x86/include/asm/acpi.h b/arch/x86/include/asm/acpi.h
index 5af926c050f0..ceacac2b335d 100644
--- a/arch/x86/include/asm/acpi.h
+++ b/arch/x86/include/asm/acpi.h
@@ -78,6 +78,11 @@ static inline bool acpi_skip_set_wakeup_address(void)
 
 #define acpi_skip_set_wakeup_address acpi_skip_set_wakeup_address
 
+union acpi_subtable_headers;
+
+int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
+			      const unsigned long end);
+
 /*
  * Check if the CPU can handle C2 and deeper
  */
diff --git a/arch/x86/kernel/acpi/Makefile b/arch/x86/kernel/acpi/Makefile
index fc17b3f136fe..2feba7257665 100644
--- a/arch/x86/kernel/acpi/Makefile
+++ b/arch/x86/kernel/acpi/Makefile
@@ -4,6 +4,7 @@ obj-$(CONFIG_ACPI)		+= boot.o
 obj-$(CONFIG_ACPI_SLEEP)	+= sleep.o wakeup_$(BITS).o
 obj-$(CONFIG_ACPI_APEI)		+= apei.o
 obj-$(CONFIG_ACPI_CPPC_LIB)	+= cppc.o
+obj-$(CONFIG_ACPI_MADT_WAKEUP)	+= madt_wakeup.o
 
 ifneq ($(CONFIG_ACPI_PROCESSOR),)
 obj-y				+= cstate.o
diff --git a/arch/x86/kernel/acpi/boot.c b/arch/x86/kernel/acpi/boot.c
index 4bf82dbd2a6b..9f4618dcd704 100644
--- a/arch/x86/kernel/acpi/boot.c
+++ b/arch/x86/kernel/acpi/boot.c
@@ -67,13 +67,6 @@ static bool has_lapic_cpus __initdata;
 static bool acpi_support_online_capable;
 #endif
 
-#ifdef CONFIG_X86_64
-/* Physical address of the Multiprocessor Wakeup Structure mailbox */
-static u64 acpi_mp_wake_mailbox_paddr;
-/* Virtual address of the Multiprocessor Wakeup Structure mailbox */
-static struct acpi_madt_multiproc_wakeup_mailbox *acpi_mp_wake_mailbox;
-#endif
-
 #ifdef CONFIG_X86_IO_APIC
 /*
  * Locks related to IOAPIC hotplug
@@ -341,60 +334,6 @@ acpi_parse_lapic_nmi(union acpi_subtable_headers * header, const unsigned long e
 
 	return 0;
 }
-
-#ifdef CONFIG_X86_64
-static int acpi_wakeup_cpu(u32 apicid, unsigned long start_ip)
-{
-	/*
-	 * Remap mailbox memory only for the first call to acpi_wakeup_cpu().
-	 *
-	 * Wakeup of secondary CPUs is fully serialized in the core code.
-	 * No need to protect acpi_mp_wake_mailbox from concurrent accesses.
-	 */
-	if (!acpi_mp_wake_mailbox) {
-		acpi_mp_wake_mailbox = memremap(acpi_mp_wake_mailbox_paddr,
-						sizeof(*acpi_mp_wake_mailbox),
-						MEMREMAP_WB);
-	}
-
-	/*
-	 * Mailbox memory is shared between the firmware and OS. Firmware will
-	 * listen on mailbox command address, and once it receives the wakeup
-	 * command, the CPU associated with the given apicid will be booted.
-	 *
-	 * The value of 'apic_id' and 'wakeup_vector' must be visible to the
-	 * firmware before the wakeup command is visible.  smp_store_release()
-	 * ensures ordering and visibility.
-	 */
-	acpi_mp_wake_mailbox->apic_id	    = apicid;
-	acpi_mp_wake_mailbox->wakeup_vector = start_ip;
-	smp_store_release(&acpi_mp_wake_mailbox->command,
-			  ACPI_MP_WAKE_COMMAND_WAKEUP);
-
-	/*
-	 * Wait for the CPU to wake up.
-	 *
-	 * The CPU being woken up is essentially in a spin loop waiting to be
-	 * woken up. It should not take long for it wake up and acknowledge by
-	 * zeroing out ->command.
-	 *
-	 * ACPI specification doesn't provide any guidance on how long kernel
-	 * has to wait for a wake up acknowledgement. It also doesn't provide
-	 * a way to cancel a wake up request if it takes too long.
-	 *
-	 * In TDX environment, the VMM has control over how long it takes to
-	 * wake up secondary. It can postpone scheduling secondary vCPU
-	 * indefinitely. Giving up on wake up request and reporting error opens
-	 * possible attack vector for VMM: it can wake up a secondary CPU when
-	 * kernel doesn't expect it. Wait until positive result of the wake up
-	 * request.
-	 */
-	while (READ_ONCE(acpi_mp_wake_mailbox->command))
-		cpu_relax();
-
-	return 0;
-}
-#endif /* CONFIG_X86_64 */
 #endif /* CONFIG_X86_LOCAL_APIC */
 
 #ifdef CONFIG_X86_IO_APIC
@@ -1124,29 +1063,6 @@ static int __init acpi_parse_madt_lapic_entries(void)
 	}
 	return 0;
 }
-
-#ifdef CONFIG_X86_64
-static int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
-				     const unsigned long end)
-{
-	struct acpi_madt_multiproc_wakeup *mp_wake;
-
-	if (!IS_ENABLED(CONFIG_SMP))
-		return -ENODEV;
-
-	mp_wake = (struct acpi_madt_multiproc_wakeup *)header;
-	if (BAD_MADT_ENTRY(mp_wake, end))
-		return -EINVAL;
-
-	acpi_table_print_madt_entry(&header->common);
-
-	acpi_mp_wake_mailbox_paddr = mp_wake->base_address;
-
-	apic_update_callback(wakeup_secondary_cpu_64, acpi_wakeup_cpu);
-
-	return 0;
-}
-#endif				/* CONFIG_X86_64 */
 #endif				/* CONFIG_X86_LOCAL_APIC */
 
 #ifdef	CONFIG_X86_IO_APIC
@@ -1343,7 +1259,7 @@ static void __init acpi_process_madt(void)
 				smp_found_config = 1;
 			}
 
-#ifdef CONFIG_X86_64
+#ifdef CONFIG_ACPI_MADT_WAKEUP
 			/*
 			 * Parse MADT MP Wake entry.
 			 */
diff --git a/arch/x86/kernel/acpi/madt_wakeup.c b/arch/x86/kernel/acpi/madt_wakeup.c
new file mode 100644
index 000000000000..7f164d38bd0b
--- /dev/null
+++ b/arch/x86/kernel/acpi/madt_wakeup.c
@@ -0,0 +1,82 @@
+// SPDX-License-Identifier: GPL-2.0-or-later
+#include <linux/acpi.h>
+#include <linux/io.h>
+#include <asm/apic.h>
+#include <asm/barrier.h>
+#include <asm/processor.h>
+
+/* Physical address of the Multiprocessor Wakeup Structure mailbox */
+static u64 acpi_mp_wake_mailbox_paddr;
+
+/* Virtual address of the Multiprocessor Wakeup Structure mailbox */
+static struct acpi_madt_multiproc_wakeup_mailbox *acpi_mp_wake_mailbox;
+
+static int acpi_wakeup_cpu(u32 apicid, unsigned long start_ip)
+{
+	/*
+	 * Remap mailbox memory only for the first call to acpi_wakeup_cpu().
+	 *
+	 * Wakeup of secondary CPUs is fully serialized in the core code.
+	 * No need to protect acpi_mp_wake_mailbox from concurrent accesses.
+	 */
+	if (!acpi_mp_wake_mailbox) {
+		acpi_mp_wake_mailbox = memremap(acpi_mp_wake_mailbox_paddr,
+						sizeof(*acpi_mp_wake_mailbox),
+						MEMREMAP_WB);
+	}
+
+	/*
+	 * Mailbox memory is shared between the firmware and OS. Firmware will
+	 * listen on mailbox command address, and once it receives the wakeup
+	 * command, the CPU associated with the given apicid will be booted.
+	 *
+	 * The value of 'apic_id' and 'wakeup_vector' must be visible to the
+	 * firmware before the wakeup command is visible.  smp_store_release()
+	 * ensures ordering and visibility.
+	 */
+	acpi_mp_wake_mailbox->apic_id	    = apicid;
+	acpi_mp_wake_mailbox->wakeup_vector = start_ip;
+	smp_store_release(&acpi_mp_wake_mailbox->command,
+			  ACPI_MP_WAKE_COMMAND_WAKEUP);
+
+	/*
+	 * Wait for the CPU to wake up.
+	 *
+	 * The CPU being woken up is essentially in a spin loop waiting to be
+	 * woken up. It should not take long for it wake up and acknowledge by
+	 * zeroing out ->command.
+	 *
+	 * ACPI specification doesn't provide any guidance on how long kernel
+	 * has to wait for a wake up acknowledgment. It also doesn't provide
+	 * a way to cancel a wake up request if it takes too long.
+	 *
+	 * In TDX environment, the VMM has control over how long it takes to
+	 * wake up secondary. It can postpone scheduling secondary vCPU
+	 * indefinitely. Giving up on wake up request and reporting error opens
+	 * possible attack vector for VMM: it can wake up a secondary CPU when
+	 * kernel doesn't expect it. Wait until positive result of the wake up
+	 * request.
+	 */
+	while (READ_ONCE(acpi_mp_wake_mailbox->command))
+		cpu_relax();
+
+	return 0;
+}
+
+int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
+			      const unsigned long end)
+{
+	struct acpi_madt_multiproc_wakeup *mp_wake;
+
+	mp_wake = (struct acpi_madt_multiproc_wakeup *)header;
+	if (BAD_MADT_ENTRY(mp_wake, end))
+		return -EINVAL;
+
+	acpi_table_print_madt_entry(&header->common);
+
+	acpi_mp_wake_mailbox_paddr = mp_wake->base_address;
+
+	apic_update_callback(wakeup_secondary_cpu_64, acpi_wakeup_cpu);
+
+	return 0;
+}

---

## [3] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 02/19] x86/apic: Mark acpi_mp_wake_* variables as __ro_after_init*

acpi_mp_wake_mailbox_paddr and acpi_mp_wake_mailbox initialized once
during ACPI MADT init and never changed.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Baoquan He <bhe@redhat.com>
Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/kernel/acpi/madt_wakeup.c | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kernel/acpi/madt_wakeup.c b/arch/x86/kernel/acpi/madt_wakeup.c
index 7f164d38bd0b..cf79ea6f3007 100644
--- a/arch/x86/kernel/acpi/madt_wakeup.c
+++ b/arch/x86/kernel/acpi/madt_wakeup.c
@@ -6,10 +6,10 @@
 #include <asm/processor.h>
 
 /* Physical address of the Multiprocessor Wakeup Structure mailbox */
-static u64 acpi_mp_wake_mailbox_paddr;
+static u64 acpi_mp_wake_mailbox_paddr __ro_after_init;
 
 /* Virtual address of the Multiprocessor Wakeup Structure mailbox */
-static struct acpi_madt_multiproc_wakeup_mailbox *acpi_mp_wake_mailbox;
+static struct acpi_madt_multiproc_wakeup_mailbox *acpi_mp_wake_mailbox __ro_after_init;
 
 static int acpi_wakeup_cpu(u32 apicid, unsigned long start_ip)
 {

---

## [4] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 03/19] cpu/hotplug: Add support for declaring CPU offlining not supported*

The ACPI MADT mailbox wakeup method doesn't allow to offline CPU after
it got woke up.

Currently offlining hotplug is prevented based on the confidential
computing attribute which is set for Intel TDX. But TDX is not
the only possible user of the wake up method. The MADT wakeup can be
implemented outside of a confidential computing environment. Offline
support is a property of the wakeup method, not the CoCo implementation.

Introduce cpu_hotplug_disable_offlining() that can be called to indicate
that CPU offlining should be disabled.

This function is going to replace CC_ATTR_HOTPLUG_DISABLED for ACPI
MADT wakeup method.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Tested-by: Tao Liu <ltao@redhat.com>
---
 include/linux/cpu.h |  2 ++
 kernel/cpu.c        | 13 ++++++++++++-
 2 files changed, 14 insertions(+), 1 deletion(-)

diff --git a/include/linux/cpu.h b/include/linux/cpu.h
index 861c3bfc5f17..6e265b085f95 100644
--- a/include/linux/cpu.h
+++ b/include/linux/cpu.h
@@ -141,6 +141,7 @@ extern void cpus_read_lock(void);
 extern void cpus_read_unlock(void);
 extern int  cpus_read_trylock(void);
 extern void lockdep_assert_cpus_held(void);
+extern void cpu_hotplug_disable_offlining(void);
 extern void cpu_hotplug_disable(void);
 extern void cpu_hotplug_enable(void);
 void clear_tasks_mm_cpumask(int cpu);
@@ -156,6 +157,7 @@ static inline void cpus_read_lock(void) { }
 static inline void cpus_read_unlock(void) { }
 static inline int  cpus_read_trylock(void) { return true; }
 static inline void lockdep_assert_cpus_held(void) { }
+static inline void cpu_hotplug_disable_offlining(void) { }
 static inline void cpu_hotplug_disable(void) { }
 static inline void cpu_hotplug_enable(void) { }
 static inline int remove_cpu(unsigned int cpu) { return -EPERM; }
diff --git a/kernel/cpu.c b/kernel/cpu.c
index 563877d6c28b..4c15b478e2bc 100644
--- a/kernel/cpu.c
+++ b/kernel/cpu.c
@@ -483,6 +483,8 @@ static int cpu_hotplug_disabled;
 
 DEFINE_STATIC_PERCPU_RWSEM(cpu_hotplug_lock);
 
+static bool cpu_hotplug_offline_disabled __ro_after_init;
+
 void cpus_read_lock(void)
 {
 	percpu_down_read(&cpu_hotplug_lock);
@@ -542,6 +544,14 @@ static void lockdep_release_cpus_lock(void)
 	rwsem_release(&cpu_hotplug_lock.dep_map, _THIS_IP_);
 }
 
+/* Declare CPU offlining not supported */
+void cpu_hotplug_disable_offlining(void)
+{
+	cpu_maps_update_begin();
+	cpu_hotplug_offline_disabled = true;
+	cpu_maps_update_done();
+}
+
 /*
  * Wait for currently running CPU hotplug operations to complete (if any) and
  * disable future CPU hotplug (from sysfs). The 'cpu_add_remove_lock' protects
@@ -1471,7 +1481,8 @@ static int cpu_down_maps_locked(unsigned int cpu, enum cpuhp_state target)
 	 * If the platform does not support hotplug, report it explicitly to
 	 * differentiate it from a transient offlining failure.
 	 */
-	if (cc_platform_has(CC_ATTR_HOTPLUG_DISABLED))
+	if (cc_platform_has(CC_ATTR_HOTPLUG_DISABLED) ||
+	    cpu_hotplug_offline_disabled)
 		return -EOPNOTSUPP;
 	if (cpu_hotplug_disabled)
 		return -EBUSY;

---

## [5] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 04/19] cpu/hotplug, x86/acpi: Disable CPU offlining for ACPI MADT wakeup*

ACPI MADT doesn't allow to offline CPU after it got woke up.

Currently CPU hotplug is prevented based on the confidential computing
attribute which is set for Intel TDX. But TDX is not the only possible
user of the wake up method. Any platform that uses ACPI MADT wakeup
method cannot offline CPU.

Disable CPU offlining on ACPI MADT wakeup enumeration.

The change has no visible effects for users: currently, TDX guest is the
only platform that uses the ACPI MADT wakeup method.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/coco/core.c               |  1 -
 arch/x86/kernel/acpi/madt_wakeup.c |  3 +++
 include/linux/cc_platform.h        | 10 ----------
 kernel/cpu.c                       |  3 +--
 4 files changed, 4 insertions(+), 13 deletions(-)

diff --git a/arch/x86/coco/core.c b/arch/x86/coco/core.c
index b31ef2424d19..0f81f70aca82 100644
--- a/arch/x86/coco/core.c
+++ b/arch/x86/coco/core.c
@@ -29,7 +29,6 @@ static bool noinstr intel_cc_platform_has(enum cc_attr attr)
 {
 	switch (attr) {
 	case CC_ATTR_GUEST_UNROLL_STRING_IO:
-	case CC_ATTR_HOTPLUG_DISABLED:
 	case CC_ATTR_GUEST_MEM_ENCRYPT:
 	case CC_ATTR_MEM_ENCRYPT:
 		return true;
diff --git a/arch/x86/kernel/acpi/madt_wakeup.c b/arch/x86/kernel/acpi/madt_wakeup.c
index cf79ea6f3007..d222be8d7a07 100644
--- a/arch/x86/kernel/acpi/madt_wakeup.c
+++ b/arch/x86/kernel/acpi/madt_wakeup.c
@@ -1,5 +1,6 @@
 // SPDX-License-Identifier: GPL-2.0-or-later
 #include <linux/acpi.h>
+#include <linux/cpu.h>
 #include <linux/io.h>
 #include <asm/apic.h>
 #include <asm/barrier.h>
@@ -76,6 +77,8 @@ int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
 
 	acpi_mp_wake_mailbox_paddr = mp_wake->base_address;
 
+	cpu_hotplug_disable_offlining();
+
 	apic_update_callback(wakeup_secondary_cpu_64, acpi_wakeup_cpu);
 
 	return 0;
diff --git a/include/linux/cc_platform.h b/include/linux/cc_platform.h
index 60693a145894..caa4b4430634 100644
--- a/include/linux/cc_platform.h
+++ b/include/linux/cc_platform.h
@@ -81,16 +81,6 @@ enum cc_attr {
 	 */
 	CC_ATTR_GUEST_SEV_SNP,
 
-	/**
-	 * @CC_ATTR_HOTPLUG_DISABLED: Hotplug is not supported or disabled.
-	 *
-	 * The platform/OS is running as a guest/virtual machine does not
-	 * support CPU hotplug feature.
-	 *
-	 * Examples include TDX Guest.
-	 */
-	CC_ATTR_HOTPLUG_DISABLED,
-
 	/**
 	 * @CC_ATTR_HOST_SEV_SNP: AMD SNP enabled on the host.
 	 *
diff --git a/kernel/cpu.c b/kernel/cpu.c
index 4c15b478e2bc..a609385c7f99 100644
--- a/kernel/cpu.c
+++ b/kernel/cpu.c
@@ -1481,8 +1481,7 @@ static int cpu_down_maps_locked(unsigned int cpu, enum cpuhp_state target)
 	 * If the platform does not support hotplug, report it explicitly to
 	 * differentiate it from a transient offlining failure.
 	 */
-	if (cc_platform_has(CC_ATTR_HOTPLUG_DISABLED) ||
-	    cpu_hotplug_offline_disabled)
+	if (cpu_hotplug_offline_disabled)
 		return -EOPNOTSUPP;
 	if (cpu_hotplug_disabled)
 		return -EBUSY;

---

## [6] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less confusion*

From: Borislav Petkov <bp@alien8.de>

That identity_mapped() functions was loving that "1" label to the point
of completely confusing its readers.

Use named labels in each place for clarity.

No functional changes.

Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/kernel/relocate_kernel_64.S | 13 +++++++------
 1 file changed, 7 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kernel/relocate_kernel_64.S b/arch/x86/kernel/relocate_kernel_64.S
index 56cab1bb25f5..085eef5c3904 100644
--- a/arch/x86/kernel/relocate_kernel_64.S
+++ b/arch/x86/kernel/relocate_kernel_64.S
@@ -148,9 +148,10 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
 	 */
 	movl	$X86_CR4_PAE, %eax
 	testq	$X86_CR4_LA57, %r13
-	jz	1f
+	jz	.Lno_la57
 	orl	$X86_CR4_LA57, %eax
-1:
+.Lno_la57:
+
 	movq	%rax, %cr4
 
 	jmp 1f
@@ -165,9 +166,9 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
 	 * used by kexec. Flush the caches before copying the kernel.
 	 */
 	testq	%r12, %r12
-	jz 1f
+	jz .Lsme_off
 	wbinvd
-1:
+.Lsme_off:
 
 	movq	%rcx, %r11
 	call	swap_pages
@@ -187,7 +188,7 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
 	 */
 
 	testq	%r11, %r11
-	jnz 1f
+	jnz .Lrelocate
 	xorl	%eax, %eax
 	xorl	%ebx, %ebx
 	xorl    %ecx, %ecx
@@ -208,7 +209,7 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
 	ret
 	int3
 
-1:
+.Lrelocate:
 	popq	%rdx
 	leaq	PAGE_SIZE(%r10), %rsp
 	ANNOTATE_RETPOLINE_SAFE

---

## [7] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 06/19] x86/kexec: Keep CR4.MCE set during kexec for TDX guest*

TDX guests run with MCA enabled (CR4.MCE=1b) from the very start. If
that bit is cleared during CR4 register reprogramming during boot or
kexec flows, a #VE exception will be raised which the guest kernel
cannot handle it.

Therefore, make sure the CR4.MCE setting is preserved over kexec too and
avoid raising any #VEs.

The change doesn't affect non-TDX-guest environments.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/kernel/relocate_kernel_64.S | 16 ++++++++++------
 1 file changed, 10 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kernel/relocate_kernel_64.S b/arch/x86/kernel/relocate_kernel_64.S
index 085eef5c3904..b668a6be4f6f 100644
--- a/arch/x86/kernel/relocate_kernel_64.S
+++ b/arch/x86/kernel/relocate_kernel_64.S
@@ -5,6 +5,8 @@
  */
 
 #include <linux/linkage.h>
+#include <linux/stringify.h>
+#include <asm/alternative.h>
 #include <asm/page_types.h>
 #include <asm/kexec.h>
 #include <asm/processor-flags.h>
@@ -143,15 +145,17 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
 
 	/*
 	 * Set cr4 to a known state:
-	 *  - physical address extension enabled
 	 *  - 5-level paging, if it was enabled before
+	 *  - Machine check exception on TDX guest, if it was enabled before.
+	 *    Clearing MCE might not be allowed in TDX guests, depending on setup.
+	 *  - physical address extension enabled
 	 */
-	movl	$X86_CR4_PAE, %eax
-	testq	$X86_CR4_LA57, %r13
-	jz	.Lno_la57
-	orl	$X86_CR4_LA57, %eax
-.Lno_la57:
+	movl	$X86_CR4_LA57, %eax
+	ALTERNATIVE "", __stringify(orl $X86_CR4_MCE, %eax), X86_FEATURE_TDX_GUEST
 
+	/* R13 contains the original CR4 value, read in relocate_kernel() */
+	andl	%r13d, %eax
+	orl	$X86_CR4_PAE, %eax
 	movq	%rax, %cr4
 
 	jmp 1f

---

## [8] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 07/19] x86/mm: Make x86_platform.guest.enc_status_change_*() return errno*

TDX is going to have more than one reason to fail
enc_status_change_prepare().

Change the callback to return errno instead of assuming -EIO;
enc_status_change_finish() changed too to keep the interface symmetric.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Dave Hansen <dave.hansen@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
Reviewed-by: Michael Kelley <mhklinux@outlook.com>
---
 arch/x86/coco/tdx/tdx.c         | 20 +++++++++++---------
 arch/x86/hyperv/ivm.c           | 22 ++++++++++------------
 arch/x86/include/asm/x86_init.h |  4 ++--
 arch/x86/kernel/x86_init.c      |  4 ++--
 arch/x86/mm/mem_encrypt_amd.c   |  8 ++++----
 arch/x86/mm/pat/set_memory.c    | 12 +++++++-----
 6 files changed, 36 insertions(+), 34 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index c1cb90369915..26fa47db5782 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -798,28 +798,30 @@ static bool tdx_enc_status_changed(unsigned long vaddr, int numpages, bool enc)
 	return true;
 }
 
-static bool tdx_enc_status_change_prepare(unsigned long vaddr, int numpages,
-					  bool enc)
+static int tdx_enc_status_change_prepare(unsigned long vaddr, int numpages,
+					 bool enc)
 {
 	/*
 	 * Only handle shared->private conversion here.
 	 * See the comment in tdx_early_init().
 	 */
-	if (enc)
-		return tdx_enc_status_changed(vaddr, numpages, enc);
-	return true;
+	if (enc && !tdx_enc_status_changed(vaddr, numpages, enc))
+		return -EIO;
+
+	return 0;
 }
 
-static bool tdx_enc_status_change_finish(unsigned long vaddr, int numpages,
+static int tdx_enc_status_change_finish(unsigned long vaddr, int numpages,
 					 bool enc)
 {
 	/*
 	 * Only handle private->shared conversion here.
 	 * See the comment in tdx_early_init().
 	 */
-	if (!enc)
-		return tdx_enc_status_changed(vaddr, numpages, enc);
-	return true;
+	if (!enc && !tdx_enc_status_changed(vaddr, numpages, enc))
+		return -EIO;
+
+	return 0;
 }
 
 void __init tdx_early_init(void)
diff --git a/arch/x86/hyperv/ivm.c b/arch/x86/hyperv/ivm.c
index 768d73de0d09..b4a851d27c7c 100644
--- a/arch/x86/hyperv/ivm.c
+++ b/arch/x86/hyperv/ivm.c
@@ -523,9 +523,9 @@ static int hv_mark_gpa_visibility(u16 count, const u64 pfn[],
  * transition is complete, hv_vtom_set_host_visibility() marks the pages
  * as "present" again.
  */
-static bool hv_vtom_clear_present(unsigned long kbuffer, int pagecount, bool enc)
+static int hv_vtom_clear_present(unsigned long kbuffer, int pagecount, bool enc)
 {
-	return !set_memory_np(kbuffer, pagecount);
+	return set_memory_np(kbuffer, pagecount);
 }
 
 /*
@@ -536,20 +536,19 @@ static bool hv_vtom_clear_present(unsigned long kbuffer, int pagecount, bool enc
  * with host. This function works as wrap of hv_mark_gpa_visibility()
  * with memory base and size.
  */
-static bool hv_vtom_set_host_visibility(unsigned long kbuffer, int pagecount, bool enc)
+static int hv_vtom_set_host_visibility(unsigned long kbuffer, int pagecount, bool enc)
 {
 	enum hv_mem_host_visibility visibility = enc ?
 			VMBUS_PAGE_NOT_VISIBLE : VMBUS_PAGE_VISIBLE_READ_WRITE;
 	u64 *pfn_array;
 	phys_addr_t paddr;
+	int i, pfn, err;
 	void *vaddr;
 	int ret = 0;
-	bool result = true;
-	int i, pfn;
 
 	pfn_array = kmalloc(HV_HYP_PAGE_SIZE, GFP_KERNEL);
 	if (!pfn_array) {
-		result = false;
+		ret = -ENOMEM;
 		goto err_set_memory_p;
 	}
 
@@ -568,10 +567,8 @@ static bool hv_vtom_set_host_visibility(unsigned long kbuffer, int pagecount, bo
 		if (pfn == HV_MAX_MODIFY_GPA_REP_COUNT || i == pagecount - 1) {
 			ret = hv_mark_gpa_visibility(pfn, pfn_array,
 						     visibility);
-			if (ret) {
-				result = false;
+			if (ret)
 				goto err_free_pfn_array;
-			}
 			pfn = 0;
 		}
 	}
@@ -586,10 +583,11 @@ static bool hv_vtom_set_host_visibility(unsigned long kbuffer, int pagecount, bo
 	 * order to avoid leaving the memory range in a "broken" state. Setting
 	 * the PRESENT bits shouldn't fail, but return an error if it does.
 	 */
-	if (set_memory_p(kbuffer, pagecount))
-		result = false;
+	err = set_memory_p(kbuffer, pagecount);
+	if (err && !ret)
+		ret = err;
 
-	return result;
+	return ret;
 }
 
 static bool hv_vtom_tlb_flush_required(bool private)
diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 6149eabe200f..28ac3cb9b987 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -151,8 +151,8 @@ struct x86_init_acpi {
  * @enc_cache_flush_required	Returns true if a cache flush is needed before changing page encryption status
  */
 struct x86_guest {
-	bool (*enc_status_change_prepare)(unsigned long vaddr, int npages, bool enc);
-	bool (*enc_status_change_finish)(unsigned long vaddr, int npages, bool enc);
+	int (*enc_status_change_prepare)(unsigned long vaddr, int npages, bool enc);
+	int (*enc_status_change_finish)(unsigned long vaddr, int npages, bool enc);
 	bool (*enc_tlb_flush_required)(bool enc);
 	bool (*enc_cache_flush_required)(void);
 };
diff --git a/arch/x86/kernel/x86_init.c b/arch/x86/kernel/x86_init.c
index d5dc5a92635a..a7143bb7dd93 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -134,8 +134,8 @@ struct x86_cpuinit_ops x86_cpuinit = {
 
 static void default_nmi_init(void) { };
 
-static bool enc_status_change_prepare_noop(unsigned long vaddr, int npages, bool enc) { return true; }
-static bool enc_status_change_finish_noop(unsigned long vaddr, int npages, bool enc) { return true; }
+static int enc_status_change_prepare_noop(unsigned long vaddr, int npages, bool enc) { return 0; }
+static int enc_status_change_finish_noop(unsigned long vaddr, int npages, bool enc) { return 0; }
 static bool enc_tlb_flush_required_noop(bool enc) { return false; }
 static bool enc_cache_flush_required_noop(void) { return false; }
 static bool is_private_mmio_noop(u64 addr) {return false; }
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 422602f6039b..e7b67519ddb5 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -283,7 +283,7 @@ static void enc_dec_hypercall(unsigned long vaddr, unsigned long size, bool enc)
 #endif
 }
 
-static bool amd_enc_status_change_prepare(unsigned long vaddr, int npages, bool enc)
+static int amd_enc_status_change_prepare(unsigned long vaddr, int npages, bool enc)
 {
 	/*
 	 * To maintain the security guarantees of SEV-SNP guests, make sure
@@ -292,11 +292,11 @@ static bool amd_enc_status_change_prepare(unsigned long vaddr, int npages, bool
 	if (cc_platform_has(CC_ATTR_GUEST_SEV_SNP) && !enc)
 		snp_set_memory_shared(vaddr, npages);
 
-	return true;
+	return 0;
 }
 
 /* Return true unconditionally: return value doesn't matter for the SEV side */
-static bool amd_enc_status_change_finish(unsigned long vaddr, int npages, bool enc)
+static int amd_enc_status_change_finish(unsigned long vaddr, int npages, bool enc)
 {
 	/*
 	 * After memory is mapped encrypted in the page table, validate it
@@ -308,7 +308,7 @@ static bool amd_enc_status_change_finish(unsigned long vaddr, int npages, bool e
 	if (!cc_platform_has(CC_ATTR_HOST_MEM_ENCRYPT))
 		enc_dec_hypercall(vaddr, npages << PAGE_SHIFT, enc);
 
-	return true;
+	return 0;
 }
 
 static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
index 19fdfbb171ed..498812f067cd 100644
--- a/arch/x86/mm/pat/set_memory.c
+++ b/arch/x86/mm/pat/set_memory.c
@@ -2196,7 +2196,8 @@ static int __set_memory_enc_pgtable(unsigned long addr, int numpages, bool enc)
 		cpa_flush(&cpa, x86_platform.guest.enc_cache_flush_required());
 
 	/* Notify hypervisor that we are about to set/clr encryption attribute. */
-	if (!x86_platform.guest.enc_status_change_prepare(addr, numpages, enc))
+	ret = x86_platform.guest.enc_status_change_prepare(addr, numpages, enc);
+	if (ret)
 		goto vmm_fail;
 
 	ret = __change_page_attr_set_clr(&cpa, 1);
@@ -2214,16 +2215,17 @@ static int __set_memory_enc_pgtable(unsigned long addr, int numpages, bool enc)
 		return ret;
 
 	/* Notify hypervisor that we have successfully set/clr encryption attribute. */
-	if (!x86_platform.guest.enc_status_change_finish(addr, numpages, enc))
+	ret = x86_platform.guest.enc_status_change_finish(addr, numpages, enc);
+	if (ret)
 		goto vmm_fail;
 
 	return 0;
 
 vmm_fail:
-	WARN_ONCE(1, "CPA VMM failure to convert memory (addr=%p, numpages=%d) to %s.\n",
-		  (void *)addr, numpages, enc ? "private" : "shared");
+	WARN_ONCE(1, "CPA VMM failure to convert memory (addr=%p, numpages=%d) to %s: %d\n",
+		  (void *)addr, numpages, enc ? "private" : "shared", ret);
 
-	return -EIO;
+	return ret;
 }
 
 static int __set_memory_enc_dec(unsigned long addr, int numpages, bool enc)

---

## [9] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 08/19] x86/mm: Return correct level from lookup_address() if pte is none*

Currently, lookup_address() returns two things:
  1. A "pte_t" (which might be a p[g4um]d_t)
  2. The 'level' of the page tables where the "pte_t" was found
     (returned via a pointer)

If no pte_t is found, 'level' is essentially garbage.

Always fill out the level.  For NULL "pte_t"s, fill in the level where
the p*d_none() entry was found mirroring the "found" behavior.

Always filling out the level allows using lookup_address() to precisely
skip over holes when walking kernel page tables.

Add one more entry into enum pg_level to indicate the size of the VA
covered by one PGD entry in 5-level paging mode.

Update comments for lookup_address() and lookup_address_in_pgd() to
reflect changes in the interface.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Baoquan He <bhe@redhat.com>
Reviewed-by: Dave Hansen <dave.hansen@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/include/asm/pgtable_types.h |  1 +
 arch/x86/mm/pat/set_memory.c         | 21 ++++++++++-----------
 2 files changed, 11 insertions(+), 11 deletions(-)

diff --git a/arch/x86/include/asm/pgtable_types.h b/arch/x86/include/asm/pgtable_types.h
index b78644962626..2f321137736c 100644
--- a/arch/x86/include/asm/pgtable_types.h
+++ b/arch/x86/include/asm/pgtable_types.h
@@ -549,6 +549,7 @@ enum pg_level {
 	PG_LEVEL_2M,
 	PG_LEVEL_1G,
 	PG_LEVEL_512G,
+	PG_LEVEL_256T,
 	PG_LEVEL_NUM
 };
 
diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
index 498812f067cd..a7a7a6c6a3fb 100644
--- a/arch/x86/mm/pat/set_memory.c
+++ b/arch/x86/mm/pat/set_memory.c
@@ -662,8 +662,9 @@ static inline pgprot_t verify_rwx(pgprot_t old, pgprot_t new, unsigned long star
 
 /*
  * Lookup the page table entry for a virtual address in a specific pgd.
- * Return a pointer to the entry, the level of the mapping, and the effective
- * NX and RW bits of all page table levels.
+ * Return a pointer to the entry (or NULL if the entry does not exist),
+ * the level of the entry, and the effective NX and RW bits of all
+ * page table levels.
  */
 pte_t *lookup_address_in_pgd_attr(pgd_t *pgd, unsigned long address,
 				  unsigned int *level, bool *nx, bool *rw)
@@ -672,13 +673,14 @@ pte_t *lookup_address_in_pgd_attr(pgd_t *pgd, unsigned long address,
 	pud_t *pud;
 	pmd_t *pmd;
 
-	*level = PG_LEVEL_NONE;
+	*level = PG_LEVEL_256T;
 	*nx = false;
 	*rw = true;
 
 	if (pgd_none(*pgd))
 		return NULL;
 
+	*level = PG_LEVEL_512G;
 	*nx |= pgd_flags(*pgd) & _PAGE_NX;
 	*rw &= pgd_flags(*pgd) & _PAGE_RW;
 
@@ -686,10 +688,10 @@ pte_t *lookup_address_in_pgd_attr(pgd_t *pgd, unsigned long address,
 	if (p4d_none(*p4d))
 		return NULL;
 
-	*level = PG_LEVEL_512G;
 	if (p4d_leaf(*p4d) || !p4d_present(*p4d))
 		return (pte_t *)p4d;
 
+	*level = PG_LEVEL_1G;
 	*nx |= p4d_flags(*p4d) & _PAGE_NX;
 	*rw &= p4d_flags(*p4d) & _PAGE_RW;
 
@@ -697,10 +699,10 @@ pte_t *lookup_address_in_pgd_attr(pgd_t *pgd, unsigned long address,
 	if (pud_none(*pud))
 		return NULL;
 
-	*level = PG_LEVEL_1G;
 	if (pud_leaf(*pud) || !pud_present(*pud))
 		return (pte_t *)pud;
 
+	*level = PG_LEVEL_2M;
 	*nx |= pud_flags(*pud) & _PAGE_NX;
 	*rw &= pud_flags(*pud) & _PAGE_RW;
 
@@ -708,15 +710,13 @@ pte_t *lookup_address_in_pgd_attr(pgd_t *pgd, unsigned long address,
 	if (pmd_none(*pmd))
 		return NULL;
 
-	*level = PG_LEVEL_2M;
 	if (pmd_leaf(*pmd) || !pmd_present(*pmd))
 		return (pte_t *)pmd;
 
+	*level = PG_LEVEL_4K;
 	*nx |= pmd_flags(*pmd) & _PAGE_NX;
 	*rw &= pmd_flags(*pmd) & _PAGE_RW;
 
-	*level = PG_LEVEL_4K;
-
 	return pte_offset_kernel(pmd, address);
 }
 
@@ -736,9 +736,8 @@ pte_t *lookup_address_in_pgd(pgd_t *pgd, unsigned long address,
  * Lookup the page table entry for a virtual address. Return a pointer
  * to the entry and the level of the mapping.
  *
- * Note: We return pud and pmd either when the entry is marked large
- * or when the present bit is not set. Otherwise we would return a
- * pointer to a nonexisting mapping.
+ * Note: the function returns p4d, pud or pmd either when the entry is marked
+ * large or when the present bit is not set. Otherwise it returns NULL.
  */
 pte_t *lookup_address(unsigned long address, unsigned int *level)
 {

---

## [10] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 09/19] x86/tdx: Account shared memory*

The kernel will convert all shared memory back to private during kexec.
The direct mapping page tables will provide information on which memory
is shared.

It is extremely important to convert all shared memory. If a page is
missed, it will cause the second kernel to crash when it accesses it.

Keep track of the number of shared pages. This will allow for
cross-checking against the shared information in the direct mapping and
reporting if the shared bit is lost.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/coco/tdx/tdx.c | 7 +++++++
 1 file changed, 7 insertions(+)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 26fa47db5782..979891e97d83 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -38,6 +38,8 @@
 
 #define TDREPORT_SUBTYPE_0	0
 
+static atomic_long_t nr_shared;
+
 /* Called from __tdx_hypercall() for unrecoverable failure */
 noinstr void __noreturn __tdx_hypercall_failed(void)
 {
@@ -821,6 +823,11 @@ static int tdx_enc_status_change_finish(unsigned long vaddr, int numpages,
 	if (!enc && !tdx_enc_status_changed(vaddr, numpages, enc))
 		return -EIO;
 
+	if (enc)
+		atomic_long_sub(numpages, &nr_shared);
+	else
+		atomic_long_add(numpages, &nr_shared);
+
 	return 0;
 }

---

## [11] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 10/19] x86/mm: Add callbacks to prepare encrypted memory for kexec*

AMD SEV and Intel TDX guests allocate shared buffers for performing I/O.
This is done by allocating pages normally from the buddy allocator and
then converting them to shared using set_memory_decrypted().

On kexec, the second kernel is unaware of which memory has been
converted in this manner. It only sees E820_TYPE_RAM. Accessing shared
memory as private is fatal.

Therefore, the memory state must be reset to its original state before
starting the new kernel with kexec.

The process of converting shared memory back to private occurs in two
steps:

- enc_kexec_begin() stops new conversions.

- enc_kexec_finish() unshares all existing shared memory, reverting it
  back to private.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/include/asm/x86_init.h |  9 +++++++++
 arch/x86/kernel/crash.c         | 12 ++++++++++++
 arch/x86/kernel/reboot.c        | 12 ++++++++++++
 arch/x86/kernel/x86_init.c      |  4 ++++
 4 files changed, 37 insertions(+)

diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 28ac3cb9b987..6cade48811cc 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -149,12 +149,21 @@ struct x86_init_acpi {
  * @enc_status_change_finish	Notify HV after the encryption status of a range is changed
  * @enc_tlb_flush_required	Returns true if a TLB flush is needed before changing page encryption status
  * @enc_cache_flush_required	Returns true if a cache flush is needed before changing page encryption status
+ * @enc_kexec_begin		Begin the two-step process of conversion shared memory back
+ *				to private. It stops the new conversions from being started
+ *				and waits in-flight conversions to finish, if possible.
+ * @enc_kexec_finish		Finish the two-step process of conversion shared memory to
+ *				private. All memory is private after the call.
+ *				It called with all CPUs but one shutdown and interrupts
+ *				disabled.
  */
 struct x86_guest {
 	int (*enc_status_change_prepare)(unsigned long vaddr, int npages, bool enc);
 	int (*enc_status_change_finish)(unsigned long vaddr, int npages, bool enc);
 	bool (*enc_tlb_flush_required)(bool enc);
 	bool (*enc_cache_flush_required)(void);
+	void (*enc_kexec_begin)(bool crash);
+	void (*enc_kexec_finish)(void);
 };
 
 /**
diff --git a/arch/x86/kernel/crash.c b/arch/x86/kernel/crash.c
index f06501445cd9..74f6305eb9ec 100644
--- a/arch/x86/kernel/crash.c
+++ b/arch/x86/kernel/crash.c
@@ -128,6 +128,18 @@ void native_machine_crash_shutdown(struct pt_regs *regs)
 #ifdef CONFIG_HPET_TIMER
 	hpet_disable();
 #endif
+
+	/*
+	 * Non-crash kexec calls enc_kexec_begin() while scheduling is still
+	 * active. This allows the callback to wait until all in-flight
+	 * shared<->private conversions are complete. In a crash scenario,
+	 * enc_kexec_begin() get call after all but one CPU has been shut down
+	 * and interrupts have been disabled. This only allows the callback to
+	 * detect a race with the conversion and report it.
+	 */
+	x86_platform.guest.enc_kexec_begin(true);
+	x86_platform.guest.enc_kexec_finish();
+
 	crash_save_cpu(regs, safe_smp_processor_id());
 }
 
diff --git a/arch/x86/kernel/reboot.c b/arch/x86/kernel/reboot.c
index f3130f762784..097313147ad3 100644
--- a/arch/x86/kernel/reboot.c
+++ b/arch/x86/kernel/reboot.c
@@ -12,6 +12,7 @@
 #include <linux/delay.h>
 #include <linux/objtool.h>
 #include <linux/pgtable.h>
+#include <linux/kexec.h>
 #include <acpi/reboot.h>
 #include <asm/io.h>
 #include <asm/apic.h>
@@ -716,6 +717,14 @@ static void native_machine_emergency_restart(void)
 
 void native_machine_shutdown(void)
 {
+	/*
+	 * Call enc_kexec_begin() while all CPUs are still active and
+	 * interrupts are enabled. This will allow all in-flight memory
+	 * conversions to finish cleanly.
+	 */
+	if (kexec_in_progress)
+		x86_platform.guest.enc_kexec_begin(false);
+
 	/* Stop the cpus and apics */
 #ifdef CONFIG_X86_IO_APIC
 	/*
@@ -752,6 +761,9 @@ void native_machine_shutdown(void)
 #ifdef CONFIG_X86_64
 	x86_platform.iommu_shutdown();
 #endif
+
+	if (kexec_in_progress)
+		x86_platform.guest.enc_kexec_finish();
 }
 
 static void __machine_emergency_restart(int emergency)
diff --git a/arch/x86/kernel/x86_init.c b/arch/x86/kernel/x86_init.c
index a7143bb7dd93..8a79fb505303 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -138,6 +138,8 @@ static int enc_status_change_prepare_noop(unsigned long vaddr, int npages, bool
 static int enc_status_change_finish_noop(unsigned long vaddr, int npages, bool enc) { return 0; }
 static bool enc_tlb_flush_required_noop(bool enc) { return false; }
 static bool enc_cache_flush_required_noop(void) { return false; }
+static void enc_kexec_begin_noop(bool crash) {}
+static void enc_kexec_finish_noop(void) {}
 static bool is_private_mmio_noop(u64 addr) {return false; }
 
 struct x86_platform_ops x86_platform __ro_after_init = {
@@ -161,6 +163,8 @@ struct x86_platform_ops x86_platform __ro_after_init = {
 		.enc_status_change_finish  = enc_status_change_finish_noop,
 		.enc_tlb_flush_required	   = enc_tlb_flush_required_noop,
 		.enc_cache_flush_required  = enc_cache_flush_required_noop,
+		.enc_kexec_begin	   = enc_kexec_begin_noop,
+		.enc_kexec_finish	   = enc_kexec_finish_noop,
 	},
 };

---

## [12] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 11/19] x86/tdx: Convert shared memory back to private on kexec*

TDX guests allocate shared buffers to perform I/O. It is done by
allocating pages normally from the buddy allocator and converting them
to shared with set_memory_decrypted().

The second, kexec-ed kernel has no idea what memory is converted this
way. It only sees E820_TYPE_RAM.

Accessing shared memory via private mapping is fatal. It leads to
unrecoverable TD exit.

On kexec walk direct mapping and convert all shared memory back to
private. It makes all RAM private again and second kernel may use it
normally.

The conversion occurs in two steps: stopping new conversions and
unsharing all memory. In the case of normal kexec, the stopping of
conversions takes place while scheduling is still functioning. This
allows for waiting until any ongoing conversions are finished. The
second step is carried out when all CPUs except one are inactive and
interrupts are disabled. This prevents any conflicts with code that may
access shared memory.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/coco/tdx/tdx.c           | 69 +++++++++++++++++++++++++++++++
 arch/x86/include/asm/pgtable.h    |  5 +++
 arch/x86/include/asm/set_memory.h |  3 ++
 arch/x86/mm/pat/set_memory.c      | 41 ++++++++++++++++--
 4 files changed, 115 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 979891e97d83..c0a651fa8963 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -7,6 +7,7 @@
 #include <linux/cpufeature.h>
 #include <linux/export.h>
 #include <linux/io.h>
+#include <linux/kexec.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -14,6 +15,7 @@
 #include <asm/insn.h>
 #include <asm/insn-eval.h>
 #include <asm/pgtable.h>
+#include <asm/set_memory.h>
 
 /* MMIO direction */
 #define EPT_READ	0
@@ -831,6 +833,70 @@ static int tdx_enc_status_change_finish(unsigned long vaddr, int numpages,
 	return 0;
 }
 
+/* Stop new private<->shared conversions */
+static void tdx_kexec_begin(bool crash)
+{
+	/*
+	 * Crash kernel reaches here with interrupts disabled: can't wait for
+	 * conversions to finish.
+	 *
+	 * If race happened, just report and proceed.
+	 */
+	if (!set_memory_enc_stop_conversion(!crash))
+		pr_warn("Failed to stop shared<->private conversions\n");
+}
+
+/* Walk direct mapping and convert all shared memory back to private */
+static void tdx_kexec_finish(void)
+{
+	unsigned long addr, end;
+	long found = 0, shared;
+
+	lockdep_assert_irqs_disabled();
+
+	addr = PAGE_OFFSET;
+	end  = PAGE_OFFSET + get_max_mapped();
+
+	while (addr < end) {
+		unsigned long size;
+		unsigned int level;
+		pte_t *pte;
+
+		pte = lookup_address(addr, &level);
+		size = page_level_size(level);
+
+		if (pte && pte_decrypted(*pte)) {
+			int pages = size / PAGE_SIZE;
+
+			/*
+			 * Touching memory with shared bit set triggers implicit
+			 * conversion to shared.
+			 *
+			 * Make sure nobody touches the shared range from
+			 * now on.
+			 */
+			set_pte(pte, __pte(0));
+
+			if (!tdx_enc_status_changed(addr, pages, true)) {
+				pr_err("Failed to unshare range %#lx-%#lx\n",
+				       addr, addr + size);
+			}
+
+			found += pages;
+		}
+
+		addr += size;
+	}
+
+	__flush_tlb_all();
+
+	shared = atomic_long_read(&nr_shared);
+	if (shared != found) {
+		pr_err("shared page accounting is off\n");
+		pr_err("nr_shared = %ld, nr_found = %ld\n", shared, found);
+	}
+}
+
 void __init tdx_early_init(void)
 {
 	struct tdx_module_args args = {
@@ -890,6 +956,9 @@ void __init tdx_early_init(void)
 	x86_platform.guest.enc_cache_flush_required  = tdx_cache_flush_required;
 	x86_platform.guest.enc_tlb_flush_required    = tdx_tlb_flush_required;
 
+	x86_platform.guest.enc_kexec_begin	     = tdx_kexec_begin;
+	x86_platform.guest.enc_kexec_finish	     = tdx_kexec_finish;
+
 	/*
 	 * TDX intercepts the RDMSR to read the X2APIC ID in the parallel
 	 * bringup low level code. That raises #VE which cannot be handled
diff --git a/arch/x86/include/asm/pgtable.h b/arch/x86/include/asm/pgtable.h
index 65b8e5bb902c..e39311a89bf4 100644
--- a/arch/x86/include/asm/pgtable.h
+++ b/arch/x86/include/asm/pgtable.h
@@ -140,6 +140,11 @@ static inline int pte_young(pte_t pte)
 	return pte_flags(pte) & _PAGE_ACCESSED;
 }
 
+static inline bool pte_decrypted(pte_t pte)
+{
+	return cc_mkdec(pte_val(pte)) == pte_val(pte);
+}
+
 #define pmd_dirty pmd_dirty
 static inline bool pmd_dirty(pmd_t pmd)
 {
diff --git a/arch/x86/include/asm/set_memory.h b/arch/x86/include/asm/set_memory.h
index 9aee31862b4a..d490db38db9e 100644
--- a/arch/x86/include/asm/set_memory.h
+++ b/arch/x86/include/asm/set_memory.h
@@ -49,8 +49,11 @@ int set_memory_wb(unsigned long addr, int numpages);
 int set_memory_np(unsigned long addr, int numpages);
 int set_memory_p(unsigned long addr, int numpages);
 int set_memory_4k(unsigned long addr, int numpages);
+
+bool set_memory_enc_stop_conversion(bool wait);
 int set_memory_encrypted(unsigned long addr, int numpages);
 int set_memory_decrypted(unsigned long addr, int numpages);
+
 int set_memory_np_noalias(unsigned long addr, int numpages);
 int set_memory_nonglobal(unsigned long addr, int numpages);
 int set_memory_global(unsigned long addr, int numpages);
diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
index a7a7a6c6a3fb..2a548b65ef5f 100644
--- a/arch/x86/mm/pat/set_memory.c
+++ b/arch/x86/mm/pat/set_memory.c
@@ -2227,12 +2227,47 @@ static int __set_memory_enc_pgtable(unsigned long addr, int numpages, bool enc)
 	return ret;
 }
 
+/*
+ * The lock serializes conversions between private and shared memory.
+ *
+ * It is taken for read on conversion. A write lock guarantees that no
+ * concurrent conversions are in progress.
+ */
+static DECLARE_RWSEM(mem_enc_lock);
+
+/*
+ * Stop new private<->shared conversions.
+ *
+ * Taking the exclusive mem_enc_lock waits for in-flight conversions to complete.
+ * The lock is not released to prevent new conversions from being started.
+ *
+ * If sleep is not allowed, as in a crash scenario, try to take the lock.
+ * Failure indicates that there is a race with the conversion.
+ */
+bool set_memory_enc_stop_conversion(bool wait)
+{
+	if (!wait)
+		return down_write_trylock(&mem_enc_lock);
+
+	down_write(&mem_enc_lock);
+
+	return true;
+}
+
 static int __set_memory_enc_dec(unsigned long addr, int numpages, bool enc)
 {
-	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
-		return __set_memory_enc_pgtable(addr, numpages, enc);
+	int ret = 0;
 
-	return 0;
+	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT)) {
+		if (!down_read_trylock(&mem_enc_lock))
+			return -EBUSY;
+
+		ret = __set_memory_enc_pgtable(addr, numpages, enc);
+
+		up_read(&mem_enc_lock);
+	}
+
+	return ret;
 }
 
 int set_memory_encrypted(unsigned long addr, int numpages)

---

## [13] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 12/19] x86/mm: Make e820__end_ram_pfn() cover E820_TYPE_ACPI ranges*

e820__end_of_ram_pfn() is used to calculate max_pfn which, among other
things, guides where direct mapping ends. Any memory above max_pfn is
not going to be present in the direct mapping.

e820__end_of_ram_pfn() finds the end of the RAM based on the highest
E820_TYPE_RAM range. But it doesn't includes E820_TYPE_ACPI ranges into
calculation.

Despite the name, E820_TYPE_ACPI covers not only ACPI data, but also EFI
tables and might be required by kernel to function properly.

Usually the problem is hidden because there is some E820_TYPE_RAM memory
above E820_TYPE_ACPI. But crashkernel only presents pre-allocated crash
memory as E820_TYPE_RAM on boot. If the preallocated range is small, it
can fit under the last E820_TYPE_ACPI range.

Modify e820__end_of_ram_pfn() and e820__end_of_low_ram_pfn() to cover
E820_TYPE_ACPI memory.

The problem was discovered during debugging kexec for TDX guest. TDX
guest uses E820_TYPE_ACPI to store the unaccepted memory bitmap and pass
it between the kernels on kexec.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Dave Hansen <dave.hansen@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/kernel/e820.c | 9 +++++----
 1 file changed, 5 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kernel/e820.c b/arch/x86/kernel/e820.c
index 68b09f718f10..4893d30ce438 100644
--- a/arch/x86/kernel/e820.c
+++ b/arch/x86/kernel/e820.c
@@ -828,7 +828,7 @@ u64 __init e820__memblock_alloc_reserved(u64 size, u64 align)
 /*
  * Find the highest page frame number we have available
  */
-static unsigned long __init e820_end_pfn(unsigned long limit_pfn, enum e820_type type)
+static unsigned long __init e820__end_ram_pfn(unsigned long limit_pfn)
 {
 	int i;
 	unsigned long last_pfn = 0;
@@ -839,7 +839,8 @@ static unsigned long __init e820_end_pfn(unsigned long limit_pfn, enum e820_type
 		unsigned long start_pfn;
 		unsigned long end_pfn;
 
-		if (entry->type != type)
+		if (entry->type != E820_TYPE_RAM &&
+		    entry->type != E820_TYPE_ACPI)
 			continue;
 
 		start_pfn = entry->addr >> PAGE_SHIFT;
@@ -865,12 +866,12 @@ static unsigned long __init e820_end_pfn(unsigned long limit_pfn, enum e820_type
 
 unsigned long __init e820__end_of_ram_pfn(void)
 {
-	return e820_end_pfn(MAX_ARCH_PFN, E820_TYPE_RAM);
+	return e820__end_ram_pfn(MAX_ARCH_PFN);
 }
 
 unsigned long __init e820__end_of_low_ram_pfn(void)
 {
-	return e820_end_pfn(1UL << (32 - PAGE_SHIFT), E820_TYPE_RAM);
+	return e820__end_ram_pfn(1UL << (32 - PAGE_SHIFT));
 }
 
 static void __init early_panic(char *msg)

---

## [14] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 13/19] x86/mm: Do not zap page table entries mapping unaccepted memory table during kdump.*

From: Ashish Kalra <ashish.kalra@amd.com>

During crashkernel boot only pre-allocated crash memory is presented as
E820_TYPE_RAM. This can cause page table entries mapping unaccepted memory
table to be zapped during phys_pte_init(), phys_pmd_init(), phys_pud_init()
and phys_p4d_init() as SNP/TDX guest use E820_TYPE_ACPI to store the
unaccepted memory table and pass it between the kernels on
kexec/kdump.

E820_TYPE_ACPI covers not only ACPI data, but also EFI tables and might
be required by kernel to function properly.

The problem was discovered during debugging kdump for SNP guest. The
unaccepted memory table stored with E820_TYPE_ACPI and passed between
the kernels on kdump was getting zapped as the PMD entry mapping this
is above the E820_TYPE_RAM range for the reserved crashkernel memory.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/mm/init_64.c | 16 ++++++++++++----
 1 file changed, 12 insertions(+), 4 deletions(-)

diff --git a/arch/x86/mm/init_64.c b/arch/x86/mm/init_64.c
index 7e177856ee4f..28002cc7a37d 100644
--- a/arch/x86/mm/init_64.c
+++ b/arch/x86/mm/init_64.c
@@ -469,7 +469,9 @@ phys_pte_init(pte_t *pte_page, unsigned long paddr, unsigned long paddr_end,
 			    !e820__mapped_any(paddr & PAGE_MASK, paddr_next,
 					     E820_TYPE_RAM) &&
 			    !e820__mapped_any(paddr & PAGE_MASK, paddr_next,
-					     E820_TYPE_RESERVED_KERN))
+					     E820_TYPE_RESERVED_KERN) &&
+			    !e820__mapped_any(paddr & PAGE_MASK, paddr_next,
+					     E820_TYPE_ACPI))
 				set_pte_init(pte, __pte(0), init);
 			continue;
 		}
@@ -524,7 +526,9 @@ phys_pmd_init(pmd_t *pmd_page, unsigned long paddr, unsigned long paddr_end,
 			    !e820__mapped_any(paddr & PMD_MASK, paddr_next,
 					     E820_TYPE_RAM) &&
 			    !e820__mapped_any(paddr & PMD_MASK, paddr_next,
-					     E820_TYPE_RESERVED_KERN))
+					     E820_TYPE_RESERVED_KERN) &&
+			    !e820__mapped_any(paddr & PMD_MASK, paddr_next,
+					     E820_TYPE_ACPI))
 				set_pmd_init(pmd, __pmd(0), init);
 			continue;
 		}
@@ -611,7 +615,9 @@ phys_pud_init(pud_t *pud_page, unsigned long paddr, unsigned long paddr_end,
 			    !e820__mapped_any(paddr & PUD_MASK, paddr_next,
 					     E820_TYPE_RAM) &&
 			    !e820__mapped_any(paddr & PUD_MASK, paddr_next,
-					     E820_TYPE_RESERVED_KERN))
+					     E820_TYPE_RESERVED_KERN) &&
+			    !e820__mapped_any(paddr & PUD_MASK, paddr_next,
+					     E820_TYPE_ACPI))
 				set_pud_init(pud, __pud(0), init);
 			continue;
 		}
@@ -698,7 +704,9 @@ phys_p4d_init(p4d_t *p4d_page, unsigned long paddr, unsigned long paddr_end,
 			    !e820__mapped_any(paddr & P4D_MASK, paddr_next,
 					     E820_TYPE_RAM) &&
 			    !e820__mapped_any(paddr & P4D_MASK, paddr_next,
-					     E820_TYPE_RESERVED_KERN))
+					     E820_TYPE_RESERVED_KERN) &&
+			    !e820__mapped_any(paddr & P4D_MASK, paddr_next,
+					     E820_TYPE_ACPI))
 				set_p4d_init(p4d, __p4d(0), init);
 			continue;
 		}

---

## [15] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 14/19] x86/acpi: Rename fields in acpi_madt_multiproc_wakeup structure*

In order to support MADT wakeup structure version 1, provide more
appropriate names for the fields in the structure.

Rename 'mailbox_version' to 'version'. This field signifies the version
of the structure and the related protocols, rather than the version of
the mailbox. This field has not been utilized in the code thus far.

Rename 'base_address' to 'mailbox_address' to clarify the kind of
address it represents. In version 1, the structure includes the reset
vector address. Clear and distinct naming helps to prevent any
confusion.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/kernel/acpi/madt_wakeup.c | 2 +-
 include/acpi/actbl2.h              | 4 ++--
 2 files changed, 3 insertions(+), 3 deletions(-)

diff --git a/arch/x86/kernel/acpi/madt_wakeup.c b/arch/x86/kernel/acpi/madt_wakeup.c
index d222be8d7a07..004801b9b151 100644
--- a/arch/x86/kernel/acpi/madt_wakeup.c
+++ b/arch/x86/kernel/acpi/madt_wakeup.c
@@ -75,7 +75,7 @@ int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
 
 	acpi_table_print_madt_entry(&header->common);
 
-	acpi_mp_wake_mailbox_paddr = mp_wake->base_address;
+	acpi_mp_wake_mailbox_paddr = mp_wake->mailbox_address;
 
 	cpu_hotplug_disable_offlining();
 
diff --git a/include/acpi/actbl2.h b/include/acpi/actbl2.h
index ae747c89d92c..fa63362469aa 100644
--- a/include/acpi/actbl2.h
+++ b/include/acpi/actbl2.h
@@ -1194,9 +1194,9 @@ struct acpi_madt_generic_translator {
 
 struct acpi_madt_multiproc_wakeup {
 	struct acpi_subtable_header header;
-	u16 mailbox_version;
+	u16 version;
 	u32 reserved;		/* reserved - must be zero */
-	u64 base_address;
+	u64 mailbox_address;
 };
 
 #define ACPI_MULTIPROC_WAKEUP_MB_OS_SIZE        2032

---

## [16] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 15/19] x86/acpi: Do not attempt to bring up secondary CPUs in kexec case*

ACPI MADT doesn't allow to offline a CPU after it was onlined. This
limits kexec: the second kernel won't be able to use more than one CPU.

To prevent a kexec kernel from onlining secondary CPUs invalidate the
mailbox address in the ACPI MADT wakeup structure which prevents a
kexec kernel to use it.

This is safe as the booting kernel has the mailbox address cached
already and acpi_wakeup_cpu() uses the cached value to bring up the
secondary CPUs.

Note: This is a Linux specific convention and not covered by the
      ACPI specification.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/kernel/acpi/madt_wakeup.c | 29 ++++++++++++++++++++++++++++-
 1 file changed, 28 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kernel/acpi/madt_wakeup.c b/arch/x86/kernel/acpi/madt_wakeup.c
index 004801b9b151..30820f9de5af 100644
--- a/arch/x86/kernel/acpi/madt_wakeup.c
+++ b/arch/x86/kernel/acpi/madt_wakeup.c
@@ -14,6 +14,11 @@ static struct acpi_madt_multiproc_wakeup_mailbox *acpi_mp_wake_mailbox __ro_afte
 
 static int acpi_wakeup_cpu(u32 apicid, unsigned long start_ip)
 {
+	if (!acpi_mp_wake_mailbox_paddr) {
+		pr_warn_once("No MADT mailbox: cannot bringup secondary CPUs. Booting with kexec?\n");
+		return -EOPNOTSUPP;
+	}
+
 	/*
 	 * Remap mailbox memory only for the first call to acpi_wakeup_cpu().
 	 *
@@ -64,6 +69,28 @@ static int acpi_wakeup_cpu(u32 apicid, unsigned long start_ip)
 	return 0;
 }
 
+static void acpi_mp_disable_offlining(struct acpi_madt_multiproc_wakeup *mp_wake)
+{
+	cpu_hotplug_disable_offlining();
+
+	/*
+	 * ACPI MADT doesn't allow to offline a CPU after it was onlined. This
+	 * limits kexec: the second kernel won't be able to use more than one CPU.
+	 *
+	 * To prevent a kexec kernel from onlining secondary CPUs invalidate the
+	 * mailbox address in the ACPI MADT wakeup structure which prevents a
+	 * kexec kernel to use it.
+	 *
+	 * This is safe as the booting kernel has the mailbox address cached
+	 * already and acpi_wakeup_cpu() uses the cached value to bring up the
+	 * secondary CPUs.
+	 *
+	 * Note: This is a Linux specific convention and not covered by the
+	 *       ACPI specification.
+	 */
+	mp_wake->mailbox_address = 0;
+}
+
 int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
 			      const unsigned long end)
 {
@@ -77,7 +104,7 @@ int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
 
 	acpi_mp_wake_mailbox_paddr = mp_wake->mailbox_address;
 
-	cpu_hotplug_disable_offlining();
+	acpi_mp_disable_offlining(mp_wake);
 
 	apic_update_callback(wakeup_secondary_cpu_64, acpi_wakeup_cpu);

---

## [17] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 16/19] x86/smp: Add smp_ops.stop_this_cpu() callback*

If the helper is defined, it is called instead of halt() to stop the CPU
at the end of stop_this_cpu() and on crash CPU shutdown.

ACPI MADT will use it to hand over the CPU to BIOS in order to be able
to wake it up again after kexec.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/include/asm/smp.h | 1 +
 arch/x86/kernel/process.c  | 7 +++++++
 arch/x86/kernel/reboot.c   | 6 ++++++
 3 files changed, 14 insertions(+)

diff --git a/arch/x86/include/asm/smp.h b/arch/x86/include/asm/smp.h
index a35936b512fe..ca073f40698f 100644
--- a/arch/x86/include/asm/smp.h
+++ b/arch/x86/include/asm/smp.h
@@ -35,6 +35,7 @@ struct smp_ops {
 	int (*cpu_disable)(void);
 	void (*cpu_die)(unsigned int cpu);
 	void (*play_dead)(void);
+	void (*stop_this_cpu)(void);
 
 	void (*send_call_func_ipi)(const struct cpumask *mask);
 	void (*send_call_func_single_ipi)(int cpu);
diff --git a/arch/x86/kernel/process.c b/arch/x86/kernel/process.c
index b8441147eb5e..f63f8fd00a91 100644
--- a/arch/x86/kernel/process.c
+++ b/arch/x86/kernel/process.c
@@ -835,6 +835,13 @@ void __noreturn stop_this_cpu(void *dummy)
 	 */
 	cpumask_clear_cpu(cpu, &cpus_stop_mask);
 
+#ifdef CONFIG_SMP
+	if (smp_ops.stop_this_cpu) {
+		smp_ops.stop_this_cpu();
+		unreachable();
+	}
+#endif
+
 	for (;;) {
 		/*
 		 * Use native_halt() so that memory contents don't change
diff --git a/arch/x86/kernel/reboot.c b/arch/x86/kernel/reboot.c
index 097313147ad3..513809b5b27c 100644
--- a/arch/x86/kernel/reboot.c
+++ b/arch/x86/kernel/reboot.c
@@ -880,6 +880,12 @@ static int crash_nmi_callback(unsigned int val, struct pt_regs *regs)
 	cpu_emergency_disable_virtualization();
 
 	atomic_dec(&waiting_for_crash_ipi);
+
+	if (smp_ops.stop_this_cpu) {
+		smp_ops.stop_this_cpu();
+		unreachable();
+	}
+
 	/* Assume hlt works */
 	halt();
 	for (;;)

---

## [18] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 17/19] x86/mm: Introduce kernel_ident_mapping_free()*

The helper complements kernel_ident_mapping_init(): it frees the
identity mapping that was previously allocated. It will be used in the
error path to free a partially allocated mapping or if the mapping is no
longer needed.

The caller provides a struct x86_mapping_info with the free_pgd_page()
callback hooked up and the pgd_t to free.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/include/asm/init.h |  3 ++
 arch/x86/mm/ident_map.c     | 73 +++++++++++++++++++++++++++++++++++++
 2 files changed, 76 insertions(+)

diff --git a/arch/x86/include/asm/init.h b/arch/x86/include/asm/init.h
index cc9ccf61b6bd..14d72727d7ee 100644
--- a/arch/x86/include/asm/init.h
+++ b/arch/x86/include/asm/init.h
@@ -6,6 +6,7 @@
 
 struct x86_mapping_info {
 	void *(*alloc_pgt_page)(void *); /* allocate buf for page table */
+	void (*free_pgt_page)(void *, void *); /* free buf for page table */
 	void *context;			 /* context for alloc_pgt_page */
 	unsigned long page_flag;	 /* page flag for PMD or PUD entry */
 	unsigned long offset;		 /* ident mapping offset */
@@ -16,4 +17,6 @@ struct x86_mapping_info {
 int kernel_ident_mapping_init(struct x86_mapping_info *info, pgd_t *pgd_page,
 				unsigned long pstart, unsigned long pend);
 
+void kernel_ident_mapping_free(struct x86_mapping_info *info, pgd_t *pgd);
+
 #endif /* _ASM_X86_INIT_H */
diff --git a/arch/x86/mm/ident_map.c b/arch/x86/mm/ident_map.c
index 968d7005f4a7..3996af7b4abf 100644
--- a/arch/x86/mm/ident_map.c
+++ b/arch/x86/mm/ident_map.c
@@ -4,6 +4,79 @@
  * included by both the compressed kernel and the regular kernel.
  */
 
+static void free_pte(struct x86_mapping_info *info, pmd_t *pmd)
+{
+	pte_t *pte = pte_offset_kernel(pmd, 0);
+
+	info->free_pgt_page(pte, info->context);
+}
+
+static void free_pmd(struct x86_mapping_info *info, pud_t *pud)
+{
+	pmd_t *pmd = pmd_offset(pud, 0);
+	int i;
+
+	for (i = 0; i < PTRS_PER_PMD; i++) {
+		if (!pmd_present(pmd[i]))
+			continue;
+
+		if (pmd_leaf(pmd[i]))
+			continue;
+
+		free_pte(info, &pmd[i]);
+	}
+
+	info->free_pgt_page(pmd, info->context);
+}
+
+static void free_pud(struct x86_mapping_info *info, p4d_t *p4d)
+{
+	pud_t *pud = pud_offset(p4d, 0);
+	int i;
+
+	for (i = 0; i < PTRS_PER_PUD; i++) {
+		if (!pud_present(pud[i]))
+			continue;
+
+		if (pud_leaf(pud[i]))
+			continue;
+
+		free_pmd(info, &pud[i]);
+	}
+
+	info->free_pgt_page(pud, info->context);
+}
+
+static void free_p4d(struct x86_mapping_info *info, pgd_t *pgd)
+{
+	p4d_t *p4d = p4d_offset(pgd, 0);
+	int i;
+
+	for (i = 0; i < PTRS_PER_P4D; i++) {
+		if (!p4d_present(p4d[i]))
+			continue;
+
+		free_pud(info, &p4d[i]);
+	}
+
+	if (pgtable_l5_enabled())
+		info->free_pgt_page(pgd, info->context);
+}
+
+void kernel_ident_mapping_free(struct x86_mapping_info *info, pgd_t *pgd)
+{
+	int i;
+
+	for (i = 0; i < PTRS_PER_PGD; i++) {
+		if (!pgd_present(pgd[i]))
+			continue;
+
+		free_p4d(info, &pgd[i]);
+	}
+
+	info->free_pgt_page(pgd, info->context);
+}
+
 static void ident_pmd_init(struct x86_mapping_info *info, pmd_t *pmd_page,
 			   unsigned long addr, unsigned long end)
 {

---

## [19] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for ACPI MADT wakeup method*

MADT Multiprocessor Wakeup structure version 1 brings support of CPU
offlining: BIOS provides a reset vector where the CPU has to jump to
for offlining itself. The new TEST mailbox command can be used to test
whether the CPU offlined itself which means the BIOS has control over
the CPU and can online it again via the ACPI MADT wakeup method.

Add CPU offling support for the ACPI MADT wakeup method by implementing
custom cpu_die(), play_dead() and stop_this_cpu() SMP operations.

CPU offlining makes is possible to hand over secondary CPUs over kexec,
not limiting the second kernel to a single CPU.

The change conforms to the approved ACPI spec change proposal. See the
Link.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Link: https://lore.kernel.org/all/13356251.uLZWGnKmhe@kreacher
Acked-by: Kai Huang <kai.huang@intel.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Thomas Gleixner <tglx@linutronix.de>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/include/asm/acpi.h          |   2 +
 arch/x86/kernel/acpi/Makefile        |   2 +-
 arch/x86/kernel/acpi/madt_playdead.S |  28 ++++
 arch/x86/kernel/acpi/madt_wakeup.c   | 184 ++++++++++++++++++++++++++-
 include/acpi/actbl2.h                |  15 ++-
 5 files changed, 227 insertions(+), 4 deletions(-)
 create mode 100644 arch/x86/kernel/acpi/madt_playdead.S

diff --git a/arch/x86/include/asm/acpi.h b/arch/x86/include/asm/acpi.h
index ceacac2b335d..21bc53f5ed0c 100644
--- a/arch/x86/include/asm/acpi.h
+++ b/arch/x86/include/asm/acpi.h
@@ -83,6 +83,8 @@ union acpi_subtable_headers;
 int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
 			      const unsigned long end);
 
+void asm_acpi_mp_play_dead(u64 reset_vector, u64 pgd_pa);
+
 /*
  * Check if the CPU can handle C2 and deeper
  */
diff --git a/arch/x86/kernel/acpi/Makefile b/arch/x86/kernel/acpi/Makefile
index 2feba7257665..842a5f449404 100644
--- a/arch/x86/kernel/acpi/Makefile
+++ b/arch/x86/kernel/acpi/Makefile
@@ -4,7 +4,7 @@ obj-$(CONFIG_ACPI)		+= boot.o
 obj-$(CONFIG_ACPI_SLEEP)	+= sleep.o wakeup_$(BITS).o
 obj-$(CONFIG_ACPI_APEI)		+= apei.o
 obj-$(CONFIG_ACPI_CPPC_LIB)	+= cppc.o
-obj-$(CONFIG_ACPI_MADT_WAKEUP)	+= madt_wakeup.o
+obj-$(CONFIG_ACPI_MADT_WAKEUP)	+= madt_wakeup.o madt_playdead.o
 
 ifneq ($(CONFIG_ACPI_PROCESSOR),)
 obj-y				+= cstate.o
diff --git a/arch/x86/kernel/acpi/madt_playdead.S b/arch/x86/kernel/acpi/madt_playdead.S
new file mode 100644
index 000000000000..4e498d28cdc8
--- /dev/null
+++ b/arch/x86/kernel/acpi/madt_playdead.S
@@ -0,0 +1,28 @@
+/* SPDX-License-Identifier: GPL-2.0 */
+#include <linux/linkage.h>
+#include <asm/nospec-branch.h>
+#include <asm/page_types.h>
+#include <asm/processor-flags.h>
+
+	.text
+	.align PAGE_SIZE
+
+/*
+ * asm_acpi_mp_play_dead() - Hand over control of the CPU to the BIOS
+ *
+ * rdi: Address of the ACPI MADT MPWK ResetVector
+ * rsi: PGD of the identity mapping
+ */
+SYM_FUNC_START(asm_acpi_mp_play_dead)
+	/* Turn off global entries. Following CR3 write will flush them. */
+	movq	%cr4, %rdx
+	andq	$~(X86_CR4_PGE), %rdx
+	movq	%rdx, %cr4
+
+	/* Switch to identity mapping */
+	movq	%rsi, %cr3
+
+	/* Jump to reset vector */
+	ANNOTATE_RETPOLINE_SAFE
+	jmp	*%rdi
+SYM_FUNC_END(asm_acpi_mp_play_dead)
diff --git a/arch/x86/kernel/acpi/madt_wakeup.c b/arch/x86/kernel/acpi/madt_wakeup.c
index 30820f9de5af..6cfe762be28b 100644
--- a/arch/x86/kernel/acpi/madt_wakeup.c
+++ b/arch/x86/kernel/acpi/madt_wakeup.c
@@ -1,10 +1,19 @@
 // SPDX-License-Identifier: GPL-2.0-or-later
 #include <linux/acpi.h>
 #include <linux/cpu.h>
+#include <linux/delay.h>
 #include <linux/io.h>
+#include <linux/kexec.h>
+#include <linux/memblock.h>
+#include <linux/pgtable.h>
+#include <linux/sched/hotplug.h>
 #include <asm/apic.h>
 #include <asm/barrier.h>
+#include <asm/init.h>
+#include <asm/intel_pt.h>
+#include <asm/nmi.h>
 #include <asm/processor.h>
+#include <asm/reboot.h>
 
 /* Physical address of the Multiprocessor Wakeup Structure mailbox */
 static u64 acpi_mp_wake_mailbox_paddr __ro_after_init;
@@ -12,6 +21,154 @@ static u64 acpi_mp_wake_mailbox_paddr __ro_after_init;
 /* Virtual address of the Multiprocessor Wakeup Structure mailbox */
 static struct acpi_madt_multiproc_wakeup_mailbox *acpi_mp_wake_mailbox __ro_after_init;
 
+static u64 acpi_mp_pgd __ro_after_init;
+static u64 acpi_mp_reset_vector_paddr __ro_after_init;
+
+static void acpi_mp_stop_this_cpu(void)
+{
+	asm_acpi_mp_play_dead(acpi_mp_reset_vector_paddr, acpi_mp_pgd);
+}
+
+static void acpi_mp_play_dead(void)
+{
+	play_dead_common();
+	asm_acpi_mp_play_dead(acpi_mp_reset_vector_paddr, acpi_mp_pgd);
+}
+
+static void acpi_mp_cpu_die(unsigned int cpu)
+{
+	u32 apicid = per_cpu(x86_cpu_to_apicid, cpu);
+	unsigned long timeout;
+
+	/*
+	 * Use TEST mailbox command to prove that BIOS got control over
+	 * the CPU before declaring it dead.
+	 *
+	 * BIOS has to clear 'command' field of the mailbox.
+	 */
+	acpi_mp_wake_mailbox->apic_id = apicid;
+	smp_store_release(&acpi_mp_wake_mailbox->command,
+			  ACPI_MP_WAKE_COMMAND_TEST);
+
+	/* Don't wait longer than a second. */
+	timeout = USEC_PER_SEC;
+	while (READ_ONCE(acpi_mp_wake_mailbox->command) && --timeout)
+		udelay(1);
+
+	if (!timeout)
+		pr_err("Failed to hand over CPU %d to BIOS\n", cpu);
+}
+
+/* The argument is required to match type of x86_mapping_info::alloc_pgt_page */
+static void __init *alloc_pgt_page(void *dummy)
+{
+	return memblock_alloc(PAGE_SIZE, PAGE_SIZE);
+}
+
+static void __init free_pgt_page(void *pgt, void *dummy)
+{
+	return memblock_free(pgt, PAGE_SIZE);
+}
+
+/*
+ * Make sure asm_acpi_mp_play_dead() is present in the identity mapping at
+ * the same place as in the kernel page tables. asm_acpi_mp_play_dead() switches
+ * to the identity mapping and the function has be present at the same spot in
+ * the virtual address space before and after switching page tables.
+ */
+static int __init init_transition_pgtable(pgd_t *pgd)
+{
+	pgprot_t prot = PAGE_KERNEL_EXEC_NOENC;
+	unsigned long vaddr, paddr;
+	p4d_t *p4d;
+	pud_t *pud;
+	pmd_t *pmd;
+	pte_t *pte;
+
+	vaddr = (unsigned long)asm_acpi_mp_play_dead;
+	pgd += pgd_index(vaddr);
+	if (!pgd_present(*pgd)) {
+		p4d = (p4d_t *)alloc_pgt_page(NULL);
+		if (!p4d)
+			return -ENOMEM;
+		set_pgd(pgd, __pgd(__pa(p4d) | _KERNPG_TABLE));
+	}
+	p4d = p4d_offset(pgd, vaddr);
+	if (!p4d_present(*p4d)) {
+		pud = (pud_t *)alloc_pgt_page(NULL);
+		if (!pud)
+			return -ENOMEM;
+		set_p4d(p4d, __p4d(__pa(pud) | _KERNPG_TABLE));
+	}
+	pud = pud_offset(p4d, vaddr);
+	if (!pud_present(*pud)) {
+		pmd = (pmd_t *)alloc_pgt_page(NULL);
+		if (!pmd)
+			return -ENOMEM;
+		set_pud(pud, __pud(__pa(pmd) | _KERNPG_TABLE));
+	}
+	pmd = pmd_offset(pud, vaddr);
+	if (!pmd_present(*pmd)) {
+		pte = (pte_t *)alloc_pgt_page(NULL);
+		if (!pte)
+			return -ENOMEM;
+		set_pmd(pmd, __pmd(__pa(pte) | _KERNPG_TABLE));
+	}
+	pte = pte_offset_kernel(pmd, vaddr);
+
+	paddr = __pa(vaddr);
+	set_pte(pte, pfn_pte(paddr >> PAGE_SHIFT, prot));
+
+	return 0;
+}
+
+static int __init acpi_mp_setup_reset(u64 reset_vector)
+{
+	struct x86_mapping_info info = {
+		.alloc_pgt_page = alloc_pgt_page,
+		.free_pgt_page	= free_pgt_page,
+		.page_flag      = __PAGE_KERNEL_LARGE_EXEC,
+		.kernpg_flag    = _KERNPG_TABLE_NOENC,
+	};
+	pgd_t *pgd;
+
+	pgd = alloc_pgt_page(NULL);
+	if (!pgd)
+		return -ENOMEM;
+
+	for (int i = 0; i < nr_pfn_mapped; i++) {
+		unsigned long mstart, mend;
+
+		mstart = pfn_mapped[i].start << PAGE_SHIFT;
+		mend   = pfn_mapped[i].end << PAGE_SHIFT;
+		if (kernel_ident_mapping_init(&info, pgd, mstart, mend)) {
+			kernel_ident_mapping_free(&info, pgd);
+			return -ENOMEM;
+		}
+	}
+
+	if (kernel_ident_mapping_init(&info, pgd,
+				      PAGE_ALIGN_DOWN(reset_vector),
+				      PAGE_ALIGN(reset_vector + 1))) {
+		kernel_ident_mapping_free(&info, pgd);
+		return -ENOMEM;
+	}
+
+	if (init_transition_pgtable(pgd)) {
+		kernel_ident_mapping_free(&info, pgd);
+		return -ENOMEM;
+	}
+
+	smp_ops.play_dead = acpi_mp_play_dead;
+	smp_ops.stop_this_cpu = acpi_mp_stop_this_cpu;
+	smp_ops.cpu_die = acpi_mp_cpu_die;
+
+	acpi_mp_reset_vector_paddr = reset_vector;
+	acpi_mp_pgd = __pa(pgd);
+
+	return 0;
+}
+
 static int acpi_wakeup_cpu(u32 apicid, unsigned long start_ip)
 {
 	if (!acpi_mp_wake_mailbox_paddr) {
@@ -97,14 +254,37 @@ int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
 	struct acpi_madt_multiproc_wakeup *mp_wake;
 
 	mp_wake = (struct acpi_madt_multiproc_wakeup *)header;
-	if (BAD_MADT_ENTRY(mp_wake, end))
+
+	/*
+	 * Cannot use the standard BAD_MADT_ENTRY() to sanity check the @mp_wake
+	 * entry.  'sizeof (struct acpi_madt_multiproc_wakeup)' can be larger
+	 * than the actual size of the MP wakeup entry in ACPI table because the
+	 * 'reset_vector' is only available in the V1 MP wakeup structure.
+	 */
+	if (!mp_wake)
+		return -EINVAL;
+	if (end - (unsigned long)mp_wake < ACPI_MADT_MP_WAKEUP_SIZE_V0)
+		return -EINVAL;
+	if (mp_wake->header.length < ACPI_MADT_MP_WAKEUP_SIZE_V0)
 		return -EINVAL;
 
 	acpi_table_print_madt_entry(&header->common);
 
 	acpi_mp_wake_mailbox_paddr = mp_wake->mailbox_address;
 
-	acpi_mp_disable_offlining(mp_wake);
+	if (mp_wake->version >= ACPI_MADT_MP_WAKEUP_VERSION_V1 &&
+	    mp_wake->header.length >= ACPI_MADT_MP_WAKEUP_SIZE_V1) {
+		if (acpi_mp_setup_reset(mp_wake->reset_vector)) {
+			pr_warn("Failed to setup MADT reset vector\n");
+			acpi_mp_disable_offlining(mp_wake);
+		}
+	} else {
+		/*
+		 * CPU offlining requires version 1 of the ACPI MADT wakeup
+		 * structure.
+		 */
+		acpi_mp_disable_offlining(mp_wake);
+	}
 
 	apic_update_callback(wakeup_secondary_cpu_64, acpi_wakeup_cpu);
 
diff --git a/include/acpi/actbl2.h b/include/acpi/actbl2.h
index fa63362469aa..e27958ef8264 100644
--- a/include/acpi/actbl2.h
+++ b/include/acpi/actbl2.h
@@ -1197,8 +1197,20 @@ struct acpi_madt_multiproc_wakeup {
 	u16 version;
 	u32 reserved;		/* reserved - must be zero */
 	u64 mailbox_address;
+	u64 reset_vector;
 };
 
+/* Values for Version field above */
+
+enum acpi_madt_multiproc_wakeup_version {
+	ACPI_MADT_MP_WAKEUP_VERSION_NONE = 0,
+	ACPI_MADT_MP_WAKEUP_VERSION_V1 = 1,
+	ACPI_MADT_MP_WAKEUP_VERSION_RESERVED = 2, /* 2 and greater are reserved */
+};
+
+#define ACPI_MADT_MP_WAKEUP_SIZE_V0	16
+#define ACPI_MADT_MP_WAKEUP_SIZE_V1	24
+
 #define ACPI_MULTIPROC_WAKEUP_MB_OS_SIZE        2032
 #define ACPI_MULTIPROC_WAKEUP_MB_FIRMWARE_SIZE  2048
 
@@ -1211,7 +1223,8 @@ struct acpi_madt_multiproc_wakeup_mailbox {
 	u8 reserved_firmware[ACPI_MULTIPROC_WAKEUP_MB_FIRMWARE_SIZE];	/* reserved for firmware use */
 };
 
-#define ACPI_MP_WAKE_COMMAND_WAKEUP    1
+#define ACPI_MP_WAKE_COMMAND_WAKEUP	1
+#define ACPI_MP_WAKE_COMMAND_TEST	2
 
 /* 17: CPU Core Interrupt Controller (ACPI 6.5) */

---

## [20] Kirill A. Shutemov — 2024-05-28
*Subject: [PATCHv11 19/19] ACPI: tables: Print MULTIPROC_WAKEUP when MADT is parsed*

When MADT is parsed, print MULTIPROC_WAKEUP information:

ACPI: MP Wakeup (version[1], mailbox[0x7fffd000], reset[0x7fffe068])

This debug information will be very helpful during bring up.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Baoquan He <bhe@redhat.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
---
 drivers/acpi/tables.c | 14 ++++++++++++++
 1 file changed, 14 insertions(+)

diff --git a/drivers/acpi/tables.c b/drivers/acpi/tables.c
index b976e5fc3fbc..9e1b01c35070 100644
--- a/drivers/acpi/tables.c
+++ b/drivers/acpi/tables.c
@@ -198,6 +198,20 @@ void acpi_table_print_madt_entry(struct acpi_subtable_header *header)
 		}
 		break;
 
+	case ACPI_MADT_TYPE_MULTIPROC_WAKEUP:
+		{
+			struct acpi_madt_multiproc_wakeup *p =
+				(struct acpi_madt_multiproc_wakeup *)header;
+			u64 reset_vector = 0;
+
+			if (p->version >= ACPI_MADT_MP_WAKEUP_VERSION_V1)
+				reset_vector = p->reset_vector;
+
+			pr_debug("MP Wakeup (version[%d], mailbox[%#llx], reset[%#llx])\n",
+				 p->version, p->mailbox_address, reset_vector);
+		}
+		break;
+
 	case ACPI_MADT_TYPE_CORE_PIC:
 		{
 			struct acpi_madt_core_pic *p = (struct acpi_madt_core_pic *)header;

---

## [21] Rafael J. Wysocki — 2024-05-28
*Subject: Re: [PATCHv11 00/19] x86/tdx: Add kexec support*

On Tue, May 28, 2024 at 11:55 AM Kirill A. Shutemov
<kirill.shutemov@linux.intel.com> wrote:
>
> The patchset adds bits and pieces to get kexec (and crashkernel) work on

For the ACPI-related changes in the series

Acked-by: Rafael J. Wysocki <rafael.j.wysocki@intel.com>

---

## [22] Huang, Kai — 2024-05-28
*Subject: Re: [PATCHv11 06/19] x86/kexec: Keep CR4.MCE set during kexec for TDX
 guest*

On Tue, 2024-05-28 at 12:55 +0300, Kirill A. Shutemov wrote:
> TDX guests run with MCA enabled (CR4.MCE=1b) from the very start. If
> that bit is cleared during CR4 register reprogramming during boot or

Nit: the ending "it" isn't needed.

> 
> Therefore, make sure the CR4.MCE setting is preserved over kexec too and

Reviewed-by: Kai Huang <kai.huang@intel.com>

> ---
>  arch/x86/kernel/relocate_kernel_64.S | 16 ++++++++++------

---

## [23] Borislav Petkov — 2024-05-28
*Subject: Re: [PATCHv11 01/19] x86/acpi: Extract ACPI MADT wakeup code into a
 separate file*

On Tue, May 28, 2024 at 12:55:04PM +0300, Kirill A. Shutemov wrote:
> In order to prepare for the expansion of support for the ACPI MADT
> wakeup method, move the relevant code into a separate file.

Acked-by: Borislav Petkov (AMD) <bp@alien8.de>

---

## [24] Borislav Petkov — 2024-05-29
*Subject: Re: [PATCHv11 10/19] x86/mm: Add callbacks to prepare encrypted
 memory for kexec*

On Tue, May 28, 2024 at 12:55:13PM +0300, Kirill A. Shutemov wrote:
> diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
> index 28ac3cb9b987..6cade48811cc 100644

s/conversion/converting/

> + *				to private. It stops the new conversions from being started
> + *				and waits in-flight conversions to finish, if possible.

Good.

Now add "The @crash parameter denotes whether the function is being
called in the crash shutdown path."

> + * @enc_kexec_finish		Finish the two-step process of conversion shared memory to

s/conversion/converting/

> + *				private. All memory is private after the call.

"... when the function returns."

> + *				It called with all CPUs but one shutdown and interrupts
> + *				disabled.

"It is called on only one CPU while the others are shut down and with
interrupts disabled."

>   */
>  struct x86_guest {

"gets called" ... "have been shut down"

> +	 * and interrupts have been disabled. This only allows the callback to

only?

> +	 * detect a race with the conversion and report it.
> +	 */

...

---

## [25] Nikolay Borisov — 2024-05-29
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On 28.05.24 г. 12:55 ч., Kirill A. Shutemov wrote:
> From: Borislav Petkov <bp@alien8.de>
> 

That jmp 1f becomes redundant now as it simply jumps 1 line below.

> @@ -165,9 +166,9 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
>   	 * used by kexec. Flush the caches before copying the kernel.

---

## [26] Kirill A. Shutemov — 2024-05-29
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On Wed, May 29, 2024 at 01:47:50PM +0300, Nikolay Borisov wrote:
> 
> 

Nothing changed wrt this jump. It dates back to initial kexec
implementation.

See 5234f5eb04ab ("[PATCH] kexec: x86_64 kexec implementation").

But I don't see functional need in it.

Anyway, it is outside of the scope of the patch.

---

## [27] Borislav Petkov — 2024-05-29
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On Wed, May 29, 2024 at 02:17:29PM +0300, Kirill A. Shutemov wrote:
> > That jmp 1f becomes redundant now as it simply jumps 1 line below.
> > 

Yap, Kirill did what Nikolay should've done - git archeology. Please
don't forget to do that next time.

And back in the day they didn't comment non-obvious things because
commenting is for losers. :-\

So that unconditional forward jump either flushes branch prediction on
some old uarch or something else weird, uarch-special.

I doubt we can remove it just like that.

Lemme add Andy - he should know.

---

## [28] Nikolay Borisov — 2024-05-29
*Subject: Re: [PATCHv11 06/19] x86/kexec: Keep CR4.MCE set during kexec for TDX
 guest*

On 28.05.24 г. 12:55 ч., Kirill A. Shutemov wrote:
> TDX guests run with MCA enabled (CR4.MCE=1b) from the very start. If
> that bit is cleared during CR4 register reprogramming during boot or

Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>

---

## [29] Andrew Cooper — 2024-05-29
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On 29/05/2024 12:28 pm, Borislav Petkov wrote:
> On Wed, May 29, 2024 at 02:17:29PM +0300, Kirill A. Shutemov wrote:
>>> That jmp 1f becomes redundant now as it simply jumps 1 line below.

Seems I've gained a reputation...

jmp 1f dates back to ye olde 8086, which started the whole trend of the
instruction pointer just being a figment of the ISA's imagination[1].

Hardware maintains the pointer to the next byte to fetch (the prefetch
queue was up to 6 bytes), and there was a micro-op to subtract the
current length of the prefetch queue from the accumulator.

In those days, the prefetch queue was not coherent with main memory, and
jumps (being a discontinuity in the instruction stream) simply flushed
the prefetch queue.

This was necessary after modifying executable code, because otherwise
you could end up executing stale bytes from the prefetch queue and then
non-stale bytes thereafter.  (Otherwise known as the way to distinguish
the 8086 from the 8088 because the latter only had a 4 byte prefetch queue.)

Anyway.  It's how you used to spell "serialising operation" before that
term ever entered the architecture.  Linux still supports CPUs prior to
the Pentium, so still needs to care about prefetch queues in the 486.

However, this example appears to be in 64bit code and following a write
to CR4 which will be fully serialising, so it's probably copy&paste from
32bit code where it would be necessary in principle.

~Andrew

[1]
https://www.righto.com/2023/01/inside-8086-processors-instruction.html#fn:pc

In fact, anyone who hasn't should read the entire series on the 8086,
https://www.righto.com/p/index.html

---

## [30] Borislav Petkov — 2024-05-29
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On Wed, May 29, 2024 at 01:33:35PM +0100, Andrew Cooper wrote:
> Seems I've gained a reputation...

Yes you have. You have this weird interest in very deep uarch details
that I can't share. Not at that detail. :-P

> jmp 1f dates back to ye olde 8086, which started the whole trend of the
> instruction pointer just being a figment of the ISA's imagination[1].

Thanks - that certainly wakes up a long-asleep neuron in the back of my
mind...

> Anyway.  It's how you used to spell "serialising operation" before that
> term ever entered the architecture.  Linux still supports CPUs prior to

Yap, fully agreed. We could try to remove it and see what complains.

Nikolay, wanna do a patch which properly explains the situation?

> https://www.righto.com/2023/01/inside-8086-processors-instruction.html#fn:pc
> 

Oh yeah, already bookmarked.

Thanks Andy!

---

## [31] Ashish Kalra — 2024-05-30
*Subject: [PATCH v7 0/3] x86/snp: Add kexec support*

From: Ashish Kalra <ashish.kalra@amd.com>

The patchset adds bits and pieces to get kexec (and crashkernel) work on
SNP guest.

The series is based off of and tested against Kirill Shutemov's tree:
  https://github.com/intel/tdx.git guest-kexec

----

v7:
- Rebased onto current tip/master;
- Moved back to checking the md attribute instead of checking the
  efi_setup for detecting if running under kexec kernel as 
  suggested in upstream review feedback.

v6:
- Updated and restructured the commit message for patch 1/3 to
  explain the issue in detail.
- Updated inline comments in patch 1/3 to explain the issue in 
  detail.
- Moved back to checking efi_setup for detecting if running
  under kexec kernel.

v5:
- Removed sev_es_enabled() function and using sev_status directly to
  check for SEV-ES/SEV-SNP guest.
- used --base option to generate patches to specify Kirill's TDX guest
  kexec patches as prerequisite patches to fix kernel test robot
  build errors.

v4:
- Rebased to current tip/master.
- Reviewed-bys from Sathya.
- Remove snp_kexec_unprep_rom_memory() as it is not needed any more as 
  SEV-SNP code is not validating the ROM range in probe_roms() anymore.
- Fix kernel test robot build error/warnings.

v3:
- Rebased;
- moved Keep page tables that maps E820_TYPE_ACPI patch to Kirill's tdx
  guest kexec patch series.
- checking the md attribute instead of checking the efi_setup for
  detecting if running under kexec kernel.
- added new sev_es_enabled() function.
- skip video memory access in decompressor for SEV-ES/SNP systems to 
  prevent guest termination as boot stage2 #VC handler does not handle
  MMIO.

v2:
- address zeroing of unaccepted memory table mappings at all page table levels
  adding phys_pte_init(), phys_pud_init() and phys_p4d_init().
- include skip efi_arch_mem_reserve() in case of kexec as part of this 
  patch set.
- rename last_address_shd_kexec to a more appropriate 
  kexec_last_address_to_make_private.
- remove duplicate code shared with TDX and use common interfaces
  defined for SNP and TDX for kexec/kdump.
- remove set_pte_enc() dependency on pg_level_to_pfn() and make the 
  function simpler.
- rename unshare_pte() to make_pte_private().
- clarify and make the comment for using kexec_last_address_to_make_private  
  more understandable.
- general cleanup. 

Ashish Kalra (3):
  efi/x86: Fix EFI memory map corruption with kexec
  x86/boot/compressed: Skip Video Memory access in Decompressor for
    SEV-ES/SNP.
  x86/snp: Convert shared memory back to private on kexec

 arch/x86/boot/compressed/misc.c |   6 +-
 arch/x86/include/asm/sev.h      |   4 +
 arch/x86/kernel/sev.c           | 162 ++++++++++++++++++++++++++++++++
 arch/x86/mm/mem_encrypt_amd.c   |   3 +
 arch/x86/platform/efi/quirks.c  |  30 +++++-
 5 files changed, 200 insertions(+), 5 deletions(-)


base-commit: f8441cd55885e43eb0d4e8eedc6c5ab15d2dabf1
prerequisite-patch-id: a911f230c2524bd791c47f62f17f0a93cbf726b6
prerequisite-patch-id: bfe2fa046349978ac1825275eb205acecfbc22f3
prerequisite-patch-id: 5e60d292457c7cd98fd3e45c23127e9463b56a69
prerequisite-patch-id: 1f97d0a2edb7509dd58276f628d1a4bda62c154c
prerequisite-patch-id: 6e07f4d4ac95ad1d2c7750ebd3e87483fb9fd48f
prerequisite-patch-id: 24ec385d6a89cf2c8553c6d29515cc513643a68a
prerequisite-patch-id: 6a8bda2b3cf9bfab8177acdcfc8dd0408ed129fa
prerequisite-patch-id: 99382c42348b9a076ba930eca0dfc9d000ec951d
prerequisite-patch-id: 469a0a3c78b0eca82527cd85e2205fb8fb89d645
prerequisite-patch-id: 2be870cdf58bdc6a10ca3c18bf874e5c6cfb7e42
prerequisite-patch-id: 7fc62697fb6bdade0bab66ba2b45a19759008f9e
prerequisite-patch-id: 95356474298029468750a9c1bc2224fb09a86eed
prerequisite-patch-id: d4966ae63e86d24b0bf578da4dae871cd9002b12
prerequisite-patch-id: fccde6f1fa385b5af0195f81fcb95acd71822428
prerequisite-patch-id: 16048ee15e392b0b9217b8923939b0059311abd2
prerequisite-patch-id: 5c9ae9aa294f72f63ae2c3551507dfbd92525803
prerequisite-patch-id: 758bdb686290c018cbd5b7d005354019f9d15248
prerequisite-patch-id: c85fd0bb6d183a40da73720eaa607481b1d51daf
prerequisite-patch-id: 60760e0c98ab7ccd2ca22ae3e9f20ff5a94c6e91

---

## [32] Ashish Kalra — 2024-05-30
*Subject: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

From: Ashish Kalra <ashish.kalra@amd.com>

With SNP guest kexec observe the following efi memmap corruption :

[    0.000000] efi: EFI v2.7 by EDK II
[    0.000000] efi: SMBIOS=0x7e33f000 SMBIOS 3.0=0x7e33d000 ACPI=0x7e57e000 ACPI 2.0=0x7e57e014 MEMATTR=0x7cc3c018 Unaccepted=0x7c09e018
[    0.000000] efi: [Firmware Bug]: Invalid EFI memory map entries:
[    0.000000] efi: mem03: [type=269370880|attr=0x0e42100e42180e41] range=[0x0486200e41038c18-0x200e898a0eee713ac17] (invalid)
[    0.000000] efi: mem04: [type=12336|attr=0x0e410686300e4105] range=[0x100e420000000176-0x8c290f26248d200e175] (invalid)
[    0.000000] efi: mem06: [type=1124304408|attr=0x000030b400000028] range=[0x0e51300e45280e77-0xb44ed2142f460c1e76] (invalid)
[    0.000000] efi: mem08: [type=68|attr=0x300e540583280e41] range=[0x0000011affff3cd8-0x486200e54b38c0bcd7] (invalid)
[    0.000000] efi: mem10: [type=1107529240|attr=0x0e42280e41300e41] range=[0x300e41058c280e42-0x38010ae54c5c328ee41] (invalid)
[    0.000000] efi: mem11: [type=189335566|attr=0x048d200e42038e18] range=[0x0000318c00000048-0xe42029228ce4200047] (invalid)
[    0.000000] efi: mem12: [type=239142534|attr=0x0000002400000b4b] range=[0x0e41380e0a7d700e-0x80f26238f22bfe500d] (invalid)
[    0.000000] efi: mem14: [type=239207055|attr=0x0e41300e43380e0a] range=[0x8c280e42048d200e-0xc70b028f2f27cc0a00d] (invalid)
[    0.000000] efi: mem15: [type=239210510|attr=0x00080e660b47080e] range=[0x0000324c0000001c-0xa78028634ce490001b] (invalid)
[    0.000000] efi: mem16: [type=4294848528|attr=0x0000329400000014] range=[0x0e410286100e4100-0x80f252036a218f20ff] (invalid)
[    0.000000] efi: mem19: [type=2250772033|attr=0x42180e42200e4328] range=[0x41280e0ab9020683-0xe0e538c28b39e62682] (invalid)
[    0.000000] efi: mem20: [type=16|   |  |  |  |  |  |  |  |  |   |WB|  |WC|  ] range=[0x00000008ffff4438-0xffff44340090333c437] (invalid)
[    0.000000] efi: mem22: [Reserved    |attr=0x000000c1ffff4420] range=[0xffff442400003398-0x1033a04240003f397] (invalid)
[    0.000000] efi: mem23: [type=1141080856|attr=0x080e41100e43180e] range=[0x280e66300e4b280e-0x440dc5ee7141f4c080d] (invalid)
[    0.000000] efi: mem25: [Reserved    |attr=0x0000000affff44a0] range=[0xffff44a400003428-0x1034304a400013427] (invalid)
[    0.000000] efi: mem28: [type=16|   |  |  |  |  |  |  |  |  |   |WB|  |WC|  ] range=[0x0000000affff4488-0xffff448400b034bc487] (invalid)
[    0.000000] efi: mem30: [Reserved    |attr=0x0000000affff4470] range=[0xffff447400003518-0x10352047400013517] (invalid)
[    0.000000] efi: mem33: [type=16|   |  |  |  |  |  |  |  |  |   |WB|  |WC|  ] range=[0x0000000affff4458-0xffff445400b035ac457] (invalid)
[    0.000000] efi: mem35: [type=269372416|attr=0x0e42100e42180e41] range=[0x0486200e44038c18-0x200e8b8a0eee823ac17] (invalid)
[    0.000000] efi: mem37: [type=2351435330|attr=0x0e42100e42180e42] range=[0x470783380e410686-0x2002b2a041c2141e685] (invalid)
[    0.000000] efi: mem38: [type=1093668417|attr=0x100e420000000270] range=[0x42100e42180e4220-0xfff366a4e421b78c21f] (invalid)
[    0.000000] efi: mem39: [type=76357646|attr=0x180e42200e42280e] range=[0x0e410686300e4105-0x4130f251a0710ae5104] (invalid)
[    0.000000] efi: mem40: [type=940444268|attr=0x0e42200e42280e41] range=[0x180e42200e42280e-0x300fc71c300b4f2480d] (invalid)
[    0.000000] efi: mem41: [MMIO        |attr=0x8c280e42048d200e] range=[0xffff479400003728-0x42138e0c87820292727] (invalid)
[    0.000000] efi: mem42: [type=1191674680|attr=0x0000004c0000000b] range=[0x300e41380e0a0246-0x470b0f26238f22b8245] (invalid)
[    0.000000] efi: mem43: [type=2010|attr=0x0301f00e4d078338] range=[0x45038e180e42028f-0xe4556bf118f282528e] (invalid)
[    0.000000] efi: mem44: [type=1109921345|attr=0x300e44000000006c] range=[0x44080e42100e4218-0xfff39254e42138ac217] (invalid)
...

This EFI memap corruption is happening with efi_arch_mem_reserve() invocation in case of kexec boot.

( efi_arch_mem_reserve() is invoked with the following call-stack: )

[    0.310010]  efi_arch_mem_reserve+0xb1/0x220
[    0.311382]  efi_mem_reserve+0x36/0x60
[    0.311973]  efi_bgrt_init+0x17d/0x1a0
[    0.313265]  acpi_parse_bgrt+0x12/0x20
[    0.313858]  acpi_table_parse+0x77/0xd0
[    0.314463]  acpi_boot_init+0x362/0x630
[    0.315069]  setup_arch+0xa88/0xf80
[    0.315629]  start_kernel+0x68/0xa90
[    0.316194]  x86_64_start_reservations+0x1c/0x30
[    0.316921]  x86_64_start_kernel+0xbf/0x110
[    0.317582]  common_startup_64+0x13e/0x141

efi_arch_mem_reserve() calls efi_memmap_alloc() to allocate memory for
EFI memory map and due to early allocation it uses memblock allocation.

Later during boot, efi_enter_virtual_mode() calls kexec_enter_virtual_mode()
in case of a kexec-ed kernel boot.

This function kexec_enter_virtual_mode() installs the new EFI memory map by
calling efi_memmap_init_late() which remaps the efi_memmap physically allocated
in efi_arch_mem_reserve(), but this remapping is still using memblock allocation.

Subsequently, when memblock is freed later in boot flow, this remapped
efi_memmap will have random corruption (similar to a use-after-free scenario).

The corrupted EFI memory map is then passed to the next kexec-ed kernel
which causes a panic when trying to use the corrupted EFI memory map.

Fix this EFI memory map corruption by skipping efi_arch_mem_reserve() for kexec.

Additionally, efi_mem_reserve() is used to reserve boot service memory
eg. bgrt, but it is not necessary for kexec boot, as there are no
boot services in kexec reboot at all after the first kernel ExitBootServices().

The UEFI memmap passed to kexec kernel includes not only the runtime
service memory map but also the boot service memory ranges which were
reserved by the first kernel with efi_mem_reserve, and those boot service
memory ranges have already been marked "EFI_MEMORY_RUNTIME" attribute.

This is the additional reason why efi_mem_reserve can be skipped
for kexec booting and by checking the set EFI_MEMORY_RUNTIME attribute.

Suggested-by: Dave Young <dyoung@redhat.com>
[Dave Young: checking the md attribute instead of checking the efi_setup]
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/platform/efi/quirks.c | 30 +++++++++++++++++++++++++++---
 1 file changed, 27 insertions(+), 3 deletions(-)

diff --git a/arch/x86/platform/efi/quirks.c b/arch/x86/platform/efi/quirks.c
index f0cc00032751..6f398c59278a 100644
--- a/arch/x86/platform/efi/quirks.c
+++ b/arch/x86/platform/efi/quirks.c
@@ -255,15 +255,39 @@ void __init efi_arch_mem_reserve(phys_addr_t addr, u64 size)
 	struct efi_memory_map_data data = { 0 };
 	struct efi_mem_range mr;
 	efi_memory_desc_t md;
-	int num_entries;
+	int num_entries, ret;
 	void *new;
 
-	if (efi_mem_desc_lookup(addr, &md) ||
-	    md.type != EFI_BOOT_SERVICES_DATA) {
+	/*
+	 * efi_mem_reserve() is used to reserve boot service memory, eg. bgrt,
+	 * but it is not neccasery for kexec, as there are no boot services in
+	 * kexec reboot at all after the first kernel's ExitBootServices().
+	 *
+	 * Additionally kexec_enter_virtual_mode() during late init will remap
+	 * the efi_memmap physical pages allocated here via memblock & then
+	 * subsequently cause random EFI memmap corruption once memblock is freed.
+	 *
+	 * Therefore, skip efi_mem_reserve for kexec booting by checking the
+	 * EFI_MEMORY_RUNTIME attribute which indicates boot service memory
+	 * ranges reserved by the first kernel using efi_mem_reserve and marked
+	 * with EFI_MEMORY_RUNTIME attribute.
+	 */
+
+	ret = efi_mem_desc_lookup(addr, &md);
+	if (ret) {
 		pr_err("Failed to lookup EFI memory descriptor for %pa\n", &addr);
 		return;
 	}
 
+	if (md.type != EFI_BOOT_SERVICES_DATA) {
+		pr_err("Skip reserving non EFI Boot Service Data memory for %pa\n", &addr);
+		return;
+	}
+
+	/* Kexec copied the efi memmap from the first kernel, thus skip the case */
+	if (md.attribute & EFI_MEMORY_RUNTIME)
+		return;
+
 	if (addr + size > md.phys_addr + (md.num_pages << EFI_PAGE_SHIFT)) {
 		pr_err("Region spans EFI memory descriptors, %pa\n", &addr);
 		return;

---

## [33] Ashish Kalra — 2024-05-30
*Subject: [PATCH v7 2/3] x86/boot/compressed: Skip Video Memory access in Decompressor for SEV-ES/SNP.*

From: Ashish Kalra <ashish.kalra@amd.com>

Accessing guest video memory/RAM during kernel decompressor
causes guest termination as boot stage2 #VC handler for
SEV-ES/SNP systems does not support MMIO handling.

This issue is observed with SEV-ES/SNP guest kexec as
kexec -c adds screen_info to the boot parameters
passed to the kexec kernel, which causes console output to
be dumped to both video and serial.

As the decompressor output gets cleared really fast, it is
preferable to get the console output only on serial, hence,
skip accessing video RAM during decompressor stage to
prevent guest termination.

Serial console output during decompressor stage works as
boot stage2 #VC handler already supports handling port I/O.

Suggested-by: Thomas Lendacy <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
---
 arch/x86/boot/compressed/misc.c | 6 ++++--
 1 file changed, 4 insertions(+), 2 deletions(-)

diff --git a/arch/x86/boot/compressed/misc.c b/arch/x86/boot/compressed/misc.c
index b70e4a21c15f..3b9f96b3dbcc 100644
--- a/arch/x86/boot/compressed/misc.c
+++ b/arch/x86/boot/compressed/misc.c
@@ -427,8 +427,10 @@ asmlinkage __visible void *extract_kernel(void *rmode, unsigned char *output)
 		vidport = 0x3d4;
 	}
 
-	lines = boot_params_ptr->screen_info.orig_video_lines;
-	cols = boot_params_ptr->screen_info.orig_video_cols;
+	if (!(sev_status & MSR_AMD64_SEV_ES_ENABLED)) {
+		lines = boot_params_ptr->screen_info.orig_video_lines;
+		cols = boot_params_ptr->screen_info.orig_video_cols;
+	}
 
 	init_default_io_ops();

---

## [34] Ashish Kalra — 2024-05-30
*Subject: [PATCH v7 3/3] x86/snp: Convert shared memory back to private on kexec*

From: Ashish Kalra <ashish.kalra@amd.com>

SNP guests allocate shared buffers to perform I/O. It is done by
allocating pages normally from the buddy allocator and converting them
to shared with set_memory_decrypted().

The second kernel has no idea what memory is converted this way. It only
sees E820_TYPE_RAM.

Accessing shared memory via private mapping will cause unrecoverable RMP
page-faults.

On kexec walk direct mapping and convert all shared memory back to
private. It makes all RAM private again and second kernel may use it
normally. Additionally for SNP guests convert all bss decrypted section
pages back to private.

The conversion occurs in two steps: stopping new conversions and
unsharing all memory. In the case of normal kexec, the stopping of
conversions takes place while scheduling is still functioning. This
allows for waiting until any ongoing conversions are finished. The
second step is carried out when all CPUs except one are inactive and
interrupts are disabled. This prevents any conflicts with code that may
access shared memory.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/sev.h    |   4 +
 arch/x86/kernel/sev.c         | 162 ++++++++++++++++++++++++++++++++++
 arch/x86/mm/mem_encrypt_amd.c |   3 +
 3 files changed, 169 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ca20cc4e5826..f9b0a4eb1980 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -229,6 +229,8 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end);
 u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
+void snp_kexec_finish(void);
+void snp_kexec_begin(bool crash);
 #else
 static inline void sev_es_ist_enter(struct pt_regs *regs) { }
 static inline void sev_es_ist_exit(void) { }
@@ -258,6 +260,8 @@ static inline void snp_accept_memory(phys_addr_t start, phys_addr_t end) { }
 static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
+static inline void snp_kexec_finish(void) { }
+static inline void snp_kexec_begin(bool crash) { }
 #endif
 
 #ifdef CONFIG_KVM_AMD_SEV
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 3342ed58e168..941f3996a9b6 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/kernel/sev.c
@@ -42,6 +42,8 @@
 #include <asm/apic.h>
 #include <asm/cpuid.h>
 #include <asm/cmdline.h>
+#include <asm/pgtable.h>
+#include <asm/set_memory.h>
 
 #define DR7_RESET_VALUE        0x400
 
@@ -92,6 +94,9 @@ static struct ghcb *boot_ghcb __section(".data");
 /* Bitmap of SEV features supported by the hypervisor */
 static u64 sev_hv_features __ro_after_init;
 
+/* Last address to be switched to private during kexec */
+static unsigned long kexec_last_addr_to_make_private;
+
 /* #VC handler runtime per-CPU data */
 struct sev_es_runtime_data {
 	struct ghcb ghcb_page;
@@ -913,6 +918,163 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE);
 }
 
+static bool set_pte_enc(pte_t *kpte, int level, void *va)
+{
+	pte_t new_pte;
+
+	if (pte_none(*kpte))
+		return false;
+
+	/*
+	 * Change the physical page attribute from C=0 to C=1. Flush the
+	 * caches to ensure that data gets accessed with the correct C-bit.
+	 */
+	if (pte_present(*kpte))
+		clflush_cache_range(va, page_level_size(level));
+
+	new_pte = __pte(cc_mkenc(pte_val(*kpte)));
+	set_pte_atomic(kpte, new_pte);
+
+	return true;
+}
+
+static bool make_pte_private(pte_t *pte, unsigned long addr, int pages, int level)
+{
+	struct sev_es_runtime_data *data;
+	struct ghcb *ghcb;
+
+	data = this_cpu_read(runtime_data);
+	ghcb = &data->ghcb_page;
+
+	/* Check for GHCB for being part of a PMD range. */
+	if ((unsigned long)ghcb >= addr &&
+	    (unsigned long)ghcb <= (addr + (pages * PAGE_SIZE))) {
+		/*
+		 * Ensure that the current cpu's GHCB is made private
+		 * at the end of unshared loop so that we continue to use the
+		 * optimized GHCB protocol and not force the switch to
+		 * MSR protocol till the very end.
+		 */
+		pr_debug("setting boot_ghcb to NULL for this cpu ghcb\n");
+		kexec_last_addr_to_make_private = addr;
+		return true;
+	}
+
+	if (!set_pte_enc(pte, level, (void *)addr))
+		return false;
+
+	snp_set_memory_private(addr, pages);
+
+	return true;
+}
+
+static void unshare_all_memory(void)
+{
+	unsigned long addr, end;
+
+	/*
+	 * Walk direct mapping and convert all shared memory back to private,
+	 */
+
+	addr = PAGE_OFFSET;
+	end  = PAGE_OFFSET + get_max_mapped();
+
+	while (addr < end) {
+		unsigned long size;
+		unsigned int level;
+		pte_t *pte;
+
+		pte = lookup_address(addr, &level);
+		size = page_level_size(level);
+
+		/*
+		 * pte_none() check is required to skip physical memory holes in direct mapped.
+		 */
+		if (pte && pte_decrypted(*pte) && !pte_none(*pte)) {
+			int pages = size / PAGE_SIZE;
+
+			if (!make_pte_private(pte, addr, pages, level)) {
+				pr_err("Failed to unshare range %#lx-%#lx\n",
+				       addr, addr + size);
+			}
+
+		}
+
+		addr += size;
+	}
+	__flush_tlb_all();
+
+}
+
+static void unshare_all_bss_decrypted_memory(void)
+{
+	unsigned long vaddr, vaddr_end;
+	unsigned int level;
+	unsigned int npages;
+	pte_t *pte;
+
+	vaddr = (unsigned long)__start_bss_decrypted;
+	vaddr_end = (unsigned long)__start_bss_decrypted_unused;
+	npages = (vaddr_end - vaddr) >> PAGE_SHIFT;
+	for (; vaddr < vaddr_end; vaddr += PAGE_SIZE) {
+		pte = lookup_address(vaddr, &level);
+		if (!pte || !pte_decrypted(*pte) || pte_none(*pte))
+			continue;
+
+		set_pte_enc(pte, level, (void *)vaddr);
+	}
+	vaddr = (unsigned long)__start_bss_decrypted;
+	snp_set_memory_private(vaddr, npages);
+}
+
+/* Stop new private<->shared conversions */
+void snp_kexec_begin(bool crash)
+{
+	/*
+	 * Crash kernel reaches here with interrupts disabled: can't wait for
+	 * conversions to finish.
+	 *
+	 * If race happened, just report and proceed.
+	 */
+	bool wait_for_lock = !crash;
+
+	if (!set_memory_enc_stop_conversion(wait_for_lock))
+		pr_warn("Failed to stop shared<->private conversions\n");
+}
+
+/* Walk direct mapping and convert all shared memory back to private */
+void snp_kexec_finish(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	unshare_all_memory();
+
+	unshare_all_bss_decrypted_memory();
+
+	if (kexec_last_addr_to_make_private) {
+		unsigned long size;
+		unsigned int level;
+		pte_t *pte;
+
+		/*
+		 * Switch to using the MSR protocol to change this cpu's
+		 * GHCB to private.
+		 * All the per-cpu GHCBs have been switched back to private,
+		 * so can't do any more GHCB calls to the hypervisor beyond
+		 * this point till the kexec kernel starts running.
+		 */
+		boot_ghcb = NULL;
+		sev_cfg.ghcbs_initialized = false;
+
+		pr_debug("boot ghcb 0x%lx\n", kexec_last_addr_to_make_private);
+		pte = lookup_address(kexec_last_addr_to_make_private, &level);
+		size = page_level_size(level);
+		set_pte_enc(pte, level, (void *)kexec_last_addr_to_make_private);
+		snp_set_memory_private(kexec_last_addr_to_make_private, (size / PAGE_SIZE));
+	}
+}
+
 static int snp_set_vmsa(void *va, bool vmsa)
 {
 	u64 attrs;
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index e7b67519ddb5..3ba792cd28ef 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -468,6 +468,9 @@ void __init sme_early_init(void)
 	x86_platform.guest.enc_tlb_flush_required    = amd_enc_tlb_flush_required;
 	x86_platform.guest.enc_cache_flush_required  = amd_enc_cache_flush_required;
 
+	x86_platform.guest.enc_kexec_begin	     = snp_kexec_begin;
+	x86_platform.guest.enc_kexec_finish	     = snp_kexec_finish;
+
 	/*
 	 * AMD-SEV-ES intercepts the RDMSR to read the X2APIC ID in the
 	 * parallel bringup low level code. That raises #VC which cannot be

---

## [35] Alexander Kuleshov — 2024-05-31
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On 30.05.2024 23:36, Ashish Kalra wrote:
>From: Ashish Kalra <ashish.kalra@amd.com>
>+	 * but it is not neccasery for kexec, as there are no boot services in

A typo in necessary

---

## [36] Borislav Petkov — 2024-05-31
*Subject: Re: [PATCHv11 11/19] x86/tdx: Convert shared memory back to private
 on kexec*

On Tue, May 28, 2024 at 12:55:14PM +0300, Kirill A. Shutemov wrote:
> +static void tdx_kexec_finish(void)
> +{

Format the below into a comment here:

/* 

The only thing one can do at this point on failure is panic. It is
reasonable to proceed, especially for the crash case because the
kexec-ed kernel is using a different page table so there won't be
a mismatch between shared/private marking of the page so it doesn't
matter.

Also, even if the failure is real and the page cannot be touched as
private, the kdump kernel will boot fine as it uses pre-reserved memory.
What happens next depends on what the dumping process does and there's
a reasonable chance to produce useful dump on crash.

Regardless, the print leaves a trace in the log to give a clue for
debug.

One possible reason for the failure is if kdump raced with memory
conversion. In this case shared bit in page table got set (or not
cleared form shared->private conversion), but the page is actually
private. So this failure is not going to affect the kexec'ed kernel.

*/

<---

> +			if (!tdx_enc_status_changed(addr, pages, true)) {
> +				pr_err("Failed to unshare range %#lx-%#lx\n",

...

>  static int __set_memory_enc_dec(unsigned long addr, int numpages, bool enc)
>  {

So CC_ATTR_MEM_ENCRYPT is set for SEV* guests too. You need to change
that code here to take the lock only on TDX, where you want it, not on
the others.

Thx.

---

## [37] Kalra, Ashish — 2024-05-31
*Subject: Re: [PATCHv11 11/19] x86/tdx: Convert shared memory back to private
 on kexec*

Hello Boris,

On 5/31/2024 10:14 AM, Borislav Petkov wrote:
>>   static int __set_memory_enc_dec(unsigned long addr, int numpages, bool enc)
>>   {

SNP guest kexec patches are based on top of this patch-series and SNP 
guests also need this exclusive mem_enc_lock protection, so 
CC_ATTR_MEM_ENCRYPT makes sense to be used here.

Thanks, Ashish

---

## [38] Borislav Petkov — 2024-05-31
*Subject: Re: [PATCHv11 11/19] x86/tdx: Convert shared memory back to private
 on kexec*

On Fri, May 31, 2024 at 12:34:49PM -0500, Kalra, Ashish wrote:
> SNP guest kexec patches are based on top of this patch-series and SNP guests
> also need this exclusive mem_enc_lock protection, so CC_ATTR_MEM_ENCRYPT

Well, for the future, I'd encourage you to always send an Acked-by: you
or Reviewed-by: you as a reply to such patches so that it is clear that
such a change is desired.

Thx.

---

## [39] Kirill A. Shutemov — 2024-06-02
*Subject: [PATCHv11.1 10/19] x86/mm: Add callbacks to prepare encrypted memory for kexec*

AMD SEV and Intel TDX guests allocate shared buffers for performing I/O.
This is done by allocating pages normally from the buddy allocator and
then converting them to shared using set_memory_decrypted().

On kexec, the second kernel is unaware of which memory has been
converted in this manner. It only sees E820_TYPE_RAM. Accessing shared
memory as private is fatal.

Therefore, the memory state must be reset to its original state before
starting the new kernel with kexec.

The process of converting shared memory back to private occurs in two
steps:

- enc_kexec_begin() stops new conversions.

- enc_kexec_finish() unshares all existing shared memory, reverting it
  back to private.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/include/asm/x86_init.h |  9 +++++++++
 arch/x86/kernel/crash.c         | 12 ++++++++++++
 arch/x86/kernel/reboot.c        | 12 ++++++++++++
 arch/x86/kernel/x86_init.c      |  4 ++++
 4 files changed, 37 insertions(+)

diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 28ac3cb9b987..6cade48811cc 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -149,12 +149,21 @@ struct x86_init_acpi {
  * @enc_status_change_finish	Notify HV after the encryption status of a range is changed
  * @enc_tlb_flush_required	Returns true if a TLB flush is needed before changing page encryption status
  * @enc_cache_flush_required	Returns true if a cache flush is needed before changing page encryption status
+ * @enc_kexec_begin		Begin the two-step process of conversion shared memory back
+ *				to private. It stops the new conversions from being started
+ *				and waits in-flight conversions to finish, if possible.
+ * @enc_kexec_finish		Finish the two-step process of conversion shared memory to
+ *				private. All memory is private after the call.
+ *				It called with all CPUs but one shutdown and interrupts
+ *				disabled.
  */
 struct x86_guest {
 	int (*enc_status_change_prepare)(unsigned long vaddr, int npages, bool enc);
 	int (*enc_status_change_finish)(unsigned long vaddr, int npages, bool enc);
 	bool (*enc_tlb_flush_required)(bool enc);
 	bool (*enc_cache_flush_required)(void);
+	void (*enc_kexec_begin)(bool crash);
+	void (*enc_kexec_finish)(void);
 };
 
 /**
diff --git a/arch/x86/kernel/crash.c b/arch/x86/kernel/crash.c
index f06501445cd9..74f6305eb9ec 100644
--- a/arch/x86/kernel/crash.c
+++ b/arch/x86/kernel/crash.c
@@ -128,6 +128,18 @@ void native_machine_crash_shutdown(struct pt_regs *regs)
 #ifdef CONFIG_HPET_TIMER
 	hpet_disable();
 #endif
+
+	/*
+	 * Non-crash kexec calls enc_kexec_begin() while scheduling is still
+	 * active. This allows the callback to wait until all in-flight
+	 * shared<->private conversions are complete. In a crash scenario,
+	 * enc_kexec_begin() get call after all but one CPU has been shut down
+	 * and interrupts have been disabled. This only allows the callback to
+	 * detect a race with the conversion and report it.
+	 */
+	x86_platform.guest.enc_kexec_begin(true);
+	x86_platform.guest.enc_kexec_finish();
+
 	crash_save_cpu(regs, safe_smp_processor_id());
 }
 
diff --git a/arch/x86/kernel/reboot.c b/arch/x86/kernel/reboot.c
index f3130f762784..097313147ad3 100644
--- a/arch/x86/kernel/reboot.c
+++ b/arch/x86/kernel/reboot.c
@@ -12,6 +12,7 @@
 #include <linux/delay.h>
 #include <linux/objtool.h>
 #include <linux/pgtable.h>
+#include <linux/kexec.h>
 #include <acpi/reboot.h>
 #include <asm/io.h>
 #include <asm/apic.h>
@@ -716,6 +717,14 @@ static void native_machine_emergency_restart(void)
 
 void native_machine_shutdown(void)
 {
+	/*
+	 * Call enc_kexec_begin() while all CPUs are still active and
+	 * interrupts are enabled. This will allow all in-flight memory
+	 * conversions to finish cleanly.
+	 */
+	if (kexec_in_progress)
+		x86_platform.guest.enc_kexec_begin(false);
+
 	/* Stop the cpus and apics */
 #ifdef CONFIG_X86_IO_APIC
 	/*
@@ -752,6 +761,9 @@ void native_machine_shutdown(void)
 #ifdef CONFIG_X86_64
 	x86_platform.iommu_shutdown();
 #endif
+
+	if (kexec_in_progress)
+		x86_platform.guest.enc_kexec_finish();
 }
 
 static void __machine_emergency_restart(int emergency)
diff --git a/arch/x86/kernel/x86_init.c b/arch/x86/kernel/x86_init.c
index a7143bb7dd93..8a79fb505303 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -138,6 +138,8 @@ static int enc_status_change_prepare_noop(unsigned long vaddr, int npages, bool
 static int enc_status_change_finish_noop(unsigned long vaddr, int npages, bool enc) { return 0; }
 static bool enc_tlb_flush_required_noop(bool enc) { return false; }
 static bool enc_cache_flush_required_noop(void) { return false; }
+static void enc_kexec_begin_noop(bool crash) {}
+static void enc_kexec_finish_noop(void) {}
 static bool is_private_mmio_noop(u64 addr) {return false; }
 
 struct x86_platform_ops x86_platform __ro_after_init = {
@@ -161,6 +163,8 @@ struct x86_platform_ops x86_platform __ro_after_init = {
 		.enc_status_change_finish  = enc_status_change_finish_noop,
 		.enc_tlb_flush_required	   = enc_tlb_flush_required_noop,
 		.enc_cache_flush_required  = enc_cache_flush_required_noop,
+		.enc_kexec_begin	   = enc_kexec_begin_noop,
+		.enc_kexec_finish	   = enc_kexec_finish_noop,
 	},
 };

---

## [40] Kirill A. Shutemov — 2024-06-02
*Subject: Re: [PATCHv11.1 10/19] x86/mm: Add callbacks to prepare encrypted
 memory for kexec*

Please disregard this. I failed to fold changes :/

---

## [41] Kirill A. Shutemov — 2024-06-02
*Subject: [PATCHv11.2 10/19] x86/mm: Add callbacks to prepare encrypted memory for kexec*

AMD SEV and Intel TDX guests allocate shared buffers for performing I/O.
This is done by allocating pages normally from the buddy allocator and
then converting them to shared using set_memory_decrypted().

On kexec, the second kernel is unaware of which memory has been
converted in this manner. It only sees E820_TYPE_RAM. Accessing shared
memory as private is fatal.

Therefore, the memory state must be reset to its original state before
starting the new kernel with kexec.

The process of converting shared memory back to private occurs in two
steps:

- enc_kexec_begin() stops new conversions.

- enc_kexec_finish() unshares all existing shared memory, reverting it
  back to private.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Nikolay Borisov <nik.borisov@suse.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/include/asm/x86_init.h | 12 ++++++++++++
 arch/x86/kernel/crash.c         | 12 ++++++++++++
 arch/x86/kernel/reboot.c        | 12 ++++++++++++
 arch/x86/kernel/x86_init.c      |  4 ++++
 4 files changed, 40 insertions(+)

diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 28ac3cb9b987..b0f313278967 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -149,12 +149,24 @@ struct x86_init_acpi {
  * @enc_status_change_finish	Notify HV after the encryption status of a range is changed
  * @enc_tlb_flush_required	Returns true if a TLB flush is needed before changing page encryption status
  * @enc_cache_flush_required	Returns true if a cache flush is needed before changing page encryption status
+ * @enc_kexec_begin		Begin the two-step process of converting shared memory back
+ *				to private. It stops the new conversions from being started
+ *				and waits in-flight conversions to finish, if possible.
+ *				The @crash parameter denotes whether the function is being
+ *				called in the crash shutdown path.
+ * @enc_kexec_finish		Finish the two-step process of converting shared memory to
+ *				private. All memory is private after the call when
+ *				the function returns.
+ *				It is called on only one CPU while the others are shut down
+ *				and with interrupts disabled.
  */
 struct x86_guest {
 	int (*enc_status_change_prepare)(unsigned long vaddr, int npages, bool enc);
 	int (*enc_status_change_finish)(unsigned long vaddr, int npages, bool enc);
 	bool (*enc_tlb_flush_required)(bool enc);
 	bool (*enc_cache_flush_required)(void);
+	void (*enc_kexec_begin)(bool crash);
+	void (*enc_kexec_finish)(void);
 };
 
 /**
diff --git a/arch/x86/kernel/crash.c b/arch/x86/kernel/crash.c
index f06501445cd9..fc52ea80cdc8 100644
--- a/arch/x86/kernel/crash.c
+++ b/arch/x86/kernel/crash.c
@@ -128,6 +128,18 @@ void native_machine_crash_shutdown(struct pt_regs *regs)
 #ifdef CONFIG_HPET_TIMER
 	hpet_disable();
 #endif
+
+	/*
+	 * Non-crash kexec calls enc_kexec_begin() while scheduling is still
+	 * active. This allows the callback to wait until all in-flight
+	 * shared<->private conversions are complete. In a crash scenario,
+	 * enc_kexec_begin() gets called after all but one CPU have been shut
+	 * down and interrupts have been disabled. This allows the callback to
+	 * detect a race with the conversion and report it.
+	 */
+	x86_platform.guest.enc_kexec_begin(true);
+	x86_platform.guest.enc_kexec_finish();
+
 	crash_save_cpu(regs, safe_smp_processor_id());
 }
 
diff --git a/arch/x86/kernel/reboot.c b/arch/x86/kernel/reboot.c
index f3130f762784..097313147ad3 100644
--- a/arch/x86/kernel/reboot.c
+++ b/arch/x86/kernel/reboot.c
@@ -12,6 +12,7 @@
 #include <linux/delay.h>
 #include <linux/objtool.h>
 #include <linux/pgtable.h>
+#include <linux/kexec.h>
 #include <acpi/reboot.h>
 #include <asm/io.h>
 #include <asm/apic.h>
@@ -716,6 +717,14 @@ static void native_machine_emergency_restart(void)
 
 void native_machine_shutdown(void)
 {
+	/*
+	 * Call enc_kexec_begin() while all CPUs are still active and
+	 * interrupts are enabled. This will allow all in-flight memory
+	 * conversions to finish cleanly.
+	 */
+	if (kexec_in_progress)
+		x86_platform.guest.enc_kexec_begin(false);
+
 	/* Stop the cpus and apics */
 #ifdef CONFIG_X86_IO_APIC
 	/*
@@ -752,6 +761,9 @@ void native_machine_shutdown(void)
 #ifdef CONFIG_X86_64
 	x86_platform.iommu_shutdown();
 #endif
+
+	if (kexec_in_progress)
+		x86_platform.guest.enc_kexec_finish();
 }
 
 static void __machine_emergency_restart(int emergency)
diff --git a/arch/x86/kernel/x86_init.c b/arch/x86/kernel/x86_init.c
index a7143bb7dd93..8a79fb505303 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -138,6 +138,8 @@ static int enc_status_change_prepare_noop(unsigned long vaddr, int npages, bool
 static int enc_status_change_finish_noop(unsigned long vaddr, int npages, bool enc) { return 0; }
 static bool enc_tlb_flush_required_noop(bool enc) { return false; }
 static bool enc_cache_flush_required_noop(void) { return false; }
+static void enc_kexec_begin_noop(bool crash) {}
+static void enc_kexec_finish_noop(void) {}
 static bool is_private_mmio_noop(u64 addr) {return false; }
 
 struct x86_platform_ops x86_platform __ro_after_init = {
@@ -161,6 +163,8 @@ struct x86_platform_ops x86_platform __ro_after_init = {
 		.enc_status_change_finish  = enc_status_change_finish_noop,
 		.enc_tlb_flush_required	   = enc_tlb_flush_required_noop,
 		.enc_cache_flush_required  = enc_cache_flush_required_noop,
+		.enc_kexec_begin	   = enc_kexec_begin_noop,
+		.enc_kexec_finish	   = enc_kexec_finish_noop,
 	},
 };

---

## [42] Kirill A. Shutemov — 2024-06-02
*Subject: Re: [PATCHv11 11/19] x86/tdx: Convert shared memory back to private
 on kexec*

On Fri, May 31, 2024 at 05:14:42PM +0200, Borislav Petkov wrote:
> On Tue, May 28, 2024 at 12:55:14PM +0300, Kirill A. Shutemov wrote:
> > +static void tdx_kexec_finish(void)

Page tables would not make a difference here. We will switch to identity
mappings soon. And kexec-ed kernel will build new page tables from
scratch.

I will drop the part after "It is reasonable to proceed".

---

## [43] Kirill A. Shutemov — 2024-06-02
*Subject: [PATCHv11.1 11/19] x86/tdx: Convert shared memory back to private on kexec*

TDX guests allocate shared buffers to perform I/O. It is done by
allocating pages normally from the buddy allocator and converting them
to shared with set_memory_decrypted().

The second, kexec-ed kernel has no idea what memory is converted this
way. It only sees E820_TYPE_RAM.

Accessing shared memory via private mapping is fatal. It leads to
unrecoverable TD exit.

On kexec walk direct mapping and convert all shared memory back to
private. It makes all RAM private again and second kernel may use it
normally.

The conversion occurs in two steps: stopping new conversions and
unsharing all memory. In the case of normal kexec, the stopping of
conversions takes place while scheduling is still functioning. This
allows for waiting until any ongoing conversions are finished. The
second step is carried out when all CPUs except one are inactive and
interrupts are disabled. This prevents any conflicts with code that may
access shared memory.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Reviewed-by: Rick Edgecombe <rick.p.edgecombe@intel.com>
Reviewed-by: Kai Huang <kai.huang@intel.com>
Tested-by: Tao Liu <ltao@redhat.com>
---
 arch/x86/coco/tdx/tdx.c           | 90 +++++++++++++++++++++++++++++++
 arch/x86/include/asm/pgtable.h    |  5 ++
 arch/x86/include/asm/set_memory.h |  3 ++
 arch/x86/mm/pat/set_memory.c      | 41 ++++++++++++--
 4 files changed, 136 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 979891e97d83..afd71bc6eb02 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -7,6 +7,7 @@
 #include <linux/cpufeature.h>
 #include <linux/export.h>
 #include <linux/io.h>
+#include <linux/kexec.h>
 #include <asm/coco.h>
 #include <asm/tdx.h>
 #include <asm/vmx.h>
@@ -14,6 +15,7 @@
 #include <asm/insn.h>
 #include <asm/insn-eval.h>
 #include <asm/pgtable.h>
+#include <asm/set_memory.h>
 
 /* MMIO direction */
 #define EPT_READ	0
@@ -831,6 +833,91 @@ static int tdx_enc_status_change_finish(unsigned long vaddr, int numpages,
 	return 0;
 }
 
+/* Stop new private<->shared conversions */
+static void tdx_kexec_begin(bool crash)
+{
+	/*
+	 * Crash kernel reaches here with interrupts disabled: can't wait for
+	 * conversions to finish.
+	 *
+	 * If race happened, just report and proceed.
+	 */
+	if (!set_memory_enc_stop_conversion(!crash))
+		pr_warn("Failed to stop shared<->private conversions\n");
+}
+
+/* Walk direct mapping and convert all shared memory back to private */
+static void tdx_kexec_finish(void)
+{
+	unsigned long addr, end;
+	long found = 0, shared;
+
+	lockdep_assert_irqs_disabled();
+
+	addr = PAGE_OFFSET;
+	end  = PAGE_OFFSET + get_max_mapped();
+
+	while (addr < end) {
+		unsigned long size;
+		unsigned int level;
+		pte_t *pte;
+
+		pte = lookup_address(addr, &level);
+		size = page_level_size(level);
+
+		if (pte && pte_decrypted(*pte)) {
+			int pages = size / PAGE_SIZE;
+
+			/*
+			 * Touching memory with shared bit set triggers implicit
+			 * conversion to shared.
+			 *
+			 * Make sure nobody touches the shared range from
+			 * now on.
+			 */
+			set_pte(pte, __pte(0));
+
+			/*
+			 * The only thing one can do at this point on failure
+			 * is panic. It is reasonable to proceed.
+			 *
+			 * Also, even if the failure is real and the page cannot
+			 * be touched as private, the kdump kernel will boot
+			 * fine as it uses pre-reserved memory. What happens
+			 * next depends on what the dumping process does and
+			 * there's a reasonable chance to produce useful dump
+			 * on crash.
+			 *
+			 * Regardless, the print leaves a trace in the log to
+			 * give a clue for debug.
+			 *
+			 * One possible reason for the failure is if kdump raced
+			 * with memory conversion. In this case shared bit in
+			 * page table got set (or not cleared) during
+			 * shared<->private conversion, but the page is actually
+			 * private. So this failure is not going to affect the
+			 * kexec'ed kernel.
+			 */
+			if (!tdx_enc_status_changed(addr, pages, true)) {
+				pr_err("Failed to unshare range %#lx-%#lx\n",
+				       addr, addr + size);
+			}
+
+			found += pages;
+		}
+
+		addr += size;
+	}
+
+	__flush_tlb_all();
+
+	shared = atomic_long_read(&nr_shared);
+	if (shared != found) {
+		pr_err("shared page accounting is off\n");
+		pr_err("nr_shared = %ld, nr_found = %ld\n", shared, found);
+	}
+}
+
 void __init tdx_early_init(void)
 {
 	struct tdx_module_args args = {
@@ -890,6 +977,9 @@ void __init tdx_early_init(void)
 	x86_platform.guest.enc_cache_flush_required  = tdx_cache_flush_required;
 	x86_platform.guest.enc_tlb_flush_required    = tdx_tlb_flush_required;
 
+	x86_platform.guest.enc_kexec_begin	     = tdx_kexec_begin;
+	x86_platform.guest.enc_kexec_finish	     = tdx_kexec_finish;
+
 	/*
 	 * TDX intercepts the RDMSR to read the X2APIC ID in the parallel
 	 * bringup low level code. That raises #VE which cannot be handled
diff --git a/arch/x86/include/asm/pgtable.h b/arch/x86/include/asm/pgtable.h
index 65b8e5bb902c..e39311a89bf4 100644
--- a/arch/x86/include/asm/pgtable.h
+++ b/arch/x86/include/asm/pgtable.h
@@ -140,6 +140,11 @@ static inline int pte_young(pte_t pte)
 	return pte_flags(pte) & _PAGE_ACCESSED;
 }
 
+static inline bool pte_decrypted(pte_t pte)
+{
+	return cc_mkdec(pte_val(pte)) == pte_val(pte);
+}
+
 #define pmd_dirty pmd_dirty
 static inline bool pmd_dirty(pmd_t pmd)
 {
diff --git a/arch/x86/include/asm/set_memory.h b/arch/x86/include/asm/set_memory.h
index 9aee31862b4a..d490db38db9e 100644
--- a/arch/x86/include/asm/set_memory.h
+++ b/arch/x86/include/asm/set_memory.h
@@ -49,8 +49,11 @@ int set_memory_wb(unsigned long addr, int numpages);
 int set_memory_np(unsigned long addr, int numpages);
 int set_memory_p(unsigned long addr, int numpages);
 int set_memory_4k(unsigned long addr, int numpages);
+
+bool set_memory_enc_stop_conversion(bool wait);
 int set_memory_encrypted(unsigned long addr, int numpages);
 int set_memory_decrypted(unsigned long addr, int numpages);
+
 int set_memory_np_noalias(unsigned long addr, int numpages);
 int set_memory_nonglobal(unsigned long addr, int numpages);
 int set_memory_global(unsigned long addr, int numpages);
diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
index a7a7a6c6a3fb..2a548b65ef5f 100644
--- a/arch/x86/mm/pat/set_memory.c
+++ b/arch/x86/mm/pat/set_memory.c
@@ -2227,12 +2227,47 @@ static int __set_memory_enc_pgtable(unsigned long addr, int numpages, bool enc)
 	return ret;
 }
 
+/*
+ * The lock serializes conversions between private and shared memory.
+ *
+ * It is taken for read on conversion. A write lock guarantees that no
+ * concurrent conversions are in progress.
+ */
+static DECLARE_RWSEM(mem_enc_lock);
+
+/*
+ * Stop new private<->shared conversions.
+ *
+ * Taking the exclusive mem_enc_lock waits for in-flight conversions to complete.
+ * The lock is not released to prevent new conversions from being started.
+ *
+ * If sleep is not allowed, as in a crash scenario, try to take the lock.
+ * Failure indicates that there is a race with the conversion.
+ */
+bool set_memory_enc_stop_conversion(bool wait)
+{
+	if (!wait)
+		return down_write_trylock(&mem_enc_lock);
+
+	down_write(&mem_enc_lock);
+
+	return true;
+}
+
 static int __set_memory_enc_dec(unsigned long addr, int numpages, bool enc)
 {
-	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT))
-		return __set_memory_enc_pgtable(addr, numpages, enc);
+	int ret = 0;
 
-	return 0;
+	if (cc_platform_has(CC_ATTR_MEM_ENCRYPT)) {
+		if (!down_read_trylock(&mem_enc_lock))
+			return -EBUSY;
+
+		ret = __set_memory_enc_pgtable(addr, numpages, enc);
+
+		up_read(&mem_enc_lock);
+	}
+
+	return ret;
 }
 
 int set_memory_encrypted(unsigned long addr, int numpages)

---

## [44] Borislav Petkov — 2024-06-03
*Subject: Re: [PATCHv11.1 11/19] x86/tdx: Convert shared memory back to
 private on kexec*

On Sun, Jun 02, 2024 at 05:23:03PM +0300, Kirill A. Shutemov wrote:
> +			/*
> +			 * The only thing one can do at this point on failure

It makes even less sense now: panic() means "all stops and we die" and
you say it is reasonable to proceed.

I'm confused.

---

## [45] Borislav Petkov — 2024-06-03
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Tue, May 28, 2024 at 12:55:21PM +0300, Kirill A. Shutemov wrote:
> MADT Multiprocessor Wakeup structure version 1 brings support of CPU

s/of /for /

> offlining: BIOS provides a reset vector where the CPU has to jump to
> for offlining itself. The new TEST mailbox command can be used to test

Unknown word [offling] in commit message.

Please introduce a spellchecker into your patch creation workflow.

> custom cpu_die(), play_dead() and stop_this_cpu() SMP operations.
> 

s/is /it /

> not limiting the second kernel to a single CPU.

...

> +/*
> + * Make sure asm_acpi_mp_play_dead() is present in the identity mapping at

This looks like a generic helper which should be in set_memory.c. And
looking at that file, there's populate_pgd() which does pretty much the
same thing, if I squint real hard.

Let's tone down the duplication.

> +{
> +	pgprot_t prot = PAGE_KERNEL_EXEC_NOENC;

---

## [46] Borislav Petkov — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Thu, May 30, 2024 at 11:36:55PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

This sounds fishy: memblock allocated memory is not freed later in the
boot - it remains reserved. Only free memory is freed from memblock to
the buddy allocator.

Or is the problem that memblock-allocated memory cannot be memremapped
because *raisins*?

Mike?

---

## [47] Kalra, Ashish — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On 6/3/2024 3:56 AM, Borislav Petkov wrote

>> EFI memory map and due to early allocation it uses memblock allocation.
>>

This is what seems to be happening:

efi_arch_mem_reserve() calls efi_memmap_alloc() to allocate memory for
EFI memory map and due to early allocation it uses memblock allocation.

And later efi_enter_virtual_mode() calls kexec_enter_virtual_mode()
in case of a kexec-ed kernel boot.

This function kexec_enter_virtual_mode() installs the new EFI memory map by
calling efi_memmap_init_late() which does memremap() on memblock-allocated memory.

Thanks, Ashish

>
> Mike?

---

## [48] Mike Rapoport — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Mon, Jun 03, 2024 at 08:06:56AM -0500, Kalra, Ashish wrote:
> On 6/3/2024 3:56 AM, Borislav Petkov wrote
> 

Does the issue happen only with SNP?

I didn't really dig, but my theory would be that it has something to do
with arch_memremap_can_ram_remap() in arch/x86/mm/ioremap.c
 
> Thanks, Ashish

---

## [49] Kalra, Ashish — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On 6/3/2024 8:39 AM, Mike Rapoport wrote:

> On Mon, Jun 03, 2024 at 08:06:56AM -0500, Kalra, Ashish wrote:
>> On 6/3/2024 3:56 AM, Borislav Petkov wrote

This is observed under SNP as efi_arch_mem_reserve() is only being 
called with SNP enabled and then efi_arch_mem_reserve() allocates EFI 
memory map using memblock.

If we skip efi_arch_mem_reserve() (which should probably be anyway 
skipped for kexec case), then for kexec boot, EFI memmap is memremapped 
in the same virtual address as the first kernel and not the allocated 
memblock address.

Thanks, Ashish

>
> I didn't really dig, but my theory would be that it has something to do

---

## [50] H. Peter Anvin — 2024-06-03
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On 5/29/24 03:47, Nikolay Borisov wrote:
>>
>> diff --git a/arch/x86/kernel/relocate_kernel_64.S 

Uh... am I the only person to notice that ALL that is needed here is:

	andl $(X86_CR4_PAE|X86_CR4_LA57), %r13d
	movq %r13, %rax

... since %r13 is dead afterwards, and PAE *will* have been set in %r13 
already?

I don't believe that this specific jmp is actually needed -- there are 
several more synchronizing jumps later -- but it doesn't hurt.

However, if the effort is for improving the readability, it might be 
worthwhile to encapsulate the "jmp 1f; 1:" as a macro, e.g. "SYNC_CODE".

	-hpa

---

## [51] Borislav Petkov — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Mon, Jun 03, 2024 at 09:01:49AM -0500, Kalra, Ashish wrote:
> If we skip efi_arch_mem_reserve() (which should probably be anyway skipped
> for kexec case), then for kexec boot, EFI memmap is memremapped in the same

Are you saying that we should simply do

diff --git a/drivers/firmware/efi/efi.c b/drivers/firmware/efi/efi.c
index fdf07dd6f459..410cb0743289 100644
--- a/drivers/firmware/efi/efi.c
+++ b/drivers/firmware/efi/efi.c
@@ -577,6 +577,9 @@ void __init efi_mem_reserve(phys_addr_t addr, u64 size)
 	if (WARN_ON_ONCE(efi_enabled(EFI_PARAVIRT)))
 		return;
 
+	if (kexec_in_progress)
+		return;
+
 	if (!memblock_is_region_reserved(addr, size))
 		memblock_reserve(addr, size);
 
and skip that whole call?

---

## [52] Mike Rapoport — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Mon, Jun 03, 2024 at 09:01:49AM -0500, Kalra, Ashish wrote:
> On 6/3/2024 8:39 AM, Mike Rapoport wrote:
> 

I don't see how efi_arch_mem_reserve() is only called with SNP. What did I
miss?
 
> If we skip efi_arch_mem_reserve() (which should probably be anyway skipped
> for kexec case), then for kexec boot, EFI memmap is memremapped in the same

Maybe we should skip efi_arch_mem_reserve() for kexec case, but I think we
still need to understand what's causing memory corruption.

> Thanks, Ashish
>

---

## [53] Mike Rapoport — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Mon, Jun 03, 2024 at 04:46:39PM +0200, Borislav Petkov wrote:
> On Mon, Jun 03, 2024 at 09:01:49AM -0500, Kalra, Ashish wrote:
> > If we skip efi_arch_mem_reserve() (which should probably be anyway skipped

I think Ashish suggested rather 

diff --git a/drivers/firmware/efi/efi.c b/drivers/firmware/efi/efi.c
index fdf07dd6f459..eccc10ab15a4 100644
--- a/drivers/firmware/efi/efi.c
+++ b/drivers/firmware/efi/efi.c
@@ -580,6 +580,9 @@ void __init efi_mem_reserve(phys_addr_t addr, u64 size)
 	if (!memblock_is_region_reserved(addr, size))
 		memblock_reserve(addr, size);
 
+	if (kexec_in_progress)
+		return;
+
 	/*
 	 * Some architectures (x86) reserve all boot services ranges
 	 * until efi_free_boot_services() because of buggy firmware
 
> -- 
> Regards/Gruss,

---

## [54] Kalra, Ashish — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On 6/3/2024 10:31 AM, Mike Rapoport wrote:

> On Mon, Jun 03, 2024 at 04:46:39PM +0200, Borislav Petkov wrote:
>> On Mon, Jun 03, 2024 at 09:01:49AM -0500, Kalra, Ashish wrote:
Yes, something similar as above, as efi_mem_reserve() is used to reserve 
boot service memory and is not necessary for kexec boot.

So, Dave Young (dyoung@redhat.com) had suggested that we skip 
efi_arch_mem_reserve() for kexec by checking the set EFI_MEMORY_RUNTIME 
attribute as below:

diff 
<https://lore.kernel.org/lkml/Zl3HfiQ6oHdTdOdA@kernel.org/T/#iZ2e.:..:f4be03b8488665f56a1e5c6e6459f447352dfcf5.1717111180.git.ashish.kalra::40amd.com:1arch:x86:platform:efi:quirks.c> 
--git a/arch/x86/platform/efi/quirks.c b/arch/x86/platform/efi/quirks.c 
index f0cc00032751..6f398c59278a 100644 --- 
a/arch/x86/platform/efi/quirks.c +++ b/arch/x86/platform/efi/quirks.c @@ 
-255,15 +255,39 @@ void __init efi_arch_mem_reserve(phys_addr_t addr, 
u64 size)   	struct efi_memory_map_data data = { 0 };
  	struct efi_mem_range mr;
  	efi_memory_desc_t md;
- int num_entries; + int num_entries, ret;   	void *new;
  
- if (efi_mem_desc_lookup(addr, &md) || - md.type != 
EFI_BOOT_SERVICES_DATA) { + /* + * efi_mem_reserve() is used to reserve 
boot service memory, eg. bgrt, + * but it is not neccasery for kexec, as 
there are no boot services in + * kexec reboot at all after the first 
kernel's ExitBootServices(). + * + * Therefore, skip efi_mem_reserve for 
kexec booting by checking the + * EFI_MEMORY_RUNTIME attribute which 
indicates boot service memory + * ranges reserved by the first kernel 
using efi_mem_reserve and marked + * with EFI_MEMORY_RUNTIME attribute. 
+ */ + + ret = efi_mem_desc_lookup(addr, &md); + if (ret) {   		pr_err("Failed to lookup EFI memory descriptor for %pa\n", &addr);
  		return;
  	}
  
+ if (md.type != EFI_BOOT_SERVICES_DATA) { + pr_err("Skip reserving non 
EFI Boot Service Data memory for %pa\n", &addr); + return; + } + + /* 
Kexec copied the efi memmap from the first kernel, thus skip the case */ 
+ if (md.attribute & EFI_MEMORY_RUNTIME) + return; +   	if (addr + size > md.phys_addr + (md.num_pages << EFI_PAGE_SHIFT)) {
  		pr_err("Region spans EFI memory descriptors, %pa\n", &addr);
  		return;

---

## [55] Kalra, Ashish — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On 6/3/2024 10:29 AM, Mike Rapoport wrote:

> On Mon, Jun 03, 2024 at 09:01:49AM -0500, Kalra, Ashish wrote:
>> On 6/3/2024 8:39 AM, Mike Rapoport wrote:

This is the call stack for efi_arch_mem_reserve():

[    0.310010]  efi_arch_mem_reserve+0xb1/0x220
[    0.311382]  efi_mem_reserve+0x36/0x60
[    0.311973]  efi_bgrt_init+0x17d/0x1a0
[    0.313265]  acpi_parse_bgrt+0x12/0x20
[    0.313858]  acpi_table_parse+0x77/0xd0
[    0.314463]  acpi_boot_init+0x362/0x630
[    0.315069]  setup_arch+0xa88/0xf80
[    0.315629]  start_kernel+0x68/0xa90
[    0.316194]  x86_64_start_reservations+0x1c/0x30
[    0.316921]  x86_64_start_kernel+0xbf/0x110
[    0.317582]  common_startup_64+0x13e/0x141

So, probably it is being invoked specifically for AMD platform ?

>> If we skip efi_arch_mem_reserve() (which should probably be anyway skipped
>> for kexec case), then for kexec boot, EFI memmap is memremapped in the same

When, efi_arch_mem_reserve() allocates memory for EFI memory map using 
memblock and then later in boot, kexec_enter_virtual_mode() does 
memremap on this memblock allocated memory, subsequently after this i 
see EFI memory map corruption, so are there are any issues doing 
memremap on memblock-allocated memory ?

Thanks, Ashish

>>> I didn't really dig, but my theory would be that it has something to do
>>> with arch_memremap_can_ram_remap() in arch/x86/mm/ioremap.c

---

## [56] Borislav Petkov — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Mon, Jun 03, 2024 at 11:48:03AM -0500, Kalra, Ashish wrote:
> Yes, something similar as above, as efi_mem_reserve() is used to reserve
> boot service memory and is not necessary for kexec boot.

efi_arch_mem_reserve() or efi_mem_reserve() altogether?

Btw, that below got really gibberished by your mail client. Snipped.

---

## [57] Kalra, Ashish — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

Re-sending this, last response got garbled.

On 6/3/2024 11:48 AM, Kalra, Ashish wrote:
> On 6/3/2024 10:31 AM, Mike Rapoport wrote:
>
diff --git a/arch/x86/platform/efi/quirks.c b/arch/x86/platform/efi/quirks.c
index f0cc00032751..6f398c59278a 100644
--- a/arch/x86/platform/efi/quirks.c
+++ b/arch/x86/platform/efi/quirks.c
@@ -255,15 +255,39 @@ void __init efi_arch_mem_reserve(phys_addr_t addr, 
u64 size)
         struct efi_memory_map_data data = { 0 };
         struct efi_mem_range mr;
         efi_memory_desc_t md;
-       int num_entries;
+       int num_entries, ret;
         void *new;

-       if (efi_mem_desc_lookup(addr, &md) ||
-           md.type != EFI_BOOT_SERVICES_DATA) {
+       /*
+        * efi_mem_reserve() is used to reserve boot service memory, eg. 
bgrt,
+        * but it is not neccasery for kexec, as there are no boot 
services in
+        * kexec reboot at all after the first kernel's ExitBootServices().
+        *
+        * Therefore, skip efi_mem_reserve for kexec booting by checking the
+        * EFI_MEMORY_RUNTIME attribute which indicates boot service memory
+        * ranges reserved by the first kernel using efi_mem_reserve and 
marked
+        * with EFI_MEMORY_RUNTIME attribute.
+        */
+
+       ret = efi_mem_desc_lookup(addr, &md);

+       if (ret) {

                 pr_err("Failed to lookup EFI memory descriptor for 
%pa\n", &addr);
                 return;
         }

+       if (md.type != EFI_BOOT_SERVICES_DATA) {
+               pr_err("Skip reserving non EFI Boot Service Data memory 
for %pa\n", &addr);
+               return;
+       }
+
+       /* Kexec copied the efi memmap from the first kernel, thus skip 
the case */
+       if (md.attribute & EFI_MEMORY_RUNTIME)
+               return;
+
         if (addr + size > md.phys_addr + (md.num_pages << 
EFI_PAGE_SHIFT)) {
                 pr_err("Region spans EFI memory descriptors, %pa\n", 
&addr);
                 return;

Thanks, Ashish

---

## [58] Kalra, Ashish — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On 6/3/2024 11:57 AM, Borislav Petkov wrote:

> On Mon, Jun 03, 2024 at 11:48:03AM -0500, Kalra, Ashish wrote:
>> Yes, something similar as above, as efi_mem_reserve() is used to reserve

efi_arch_mem_reserve().

Thanks, Ashish

>
> Btw, that below got really gibberished by your mail client. Snipped.

---

## [59] Borislav Petkov — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Mon, Jun 03, 2024 at 12:05:45PM -0500, Kalra, Ashish wrote:
> Re-sending this, last response got garbled.

And this got linewrapped.

Thunderbird section in Documentation/process/email-clients.rst.

> index f0cc00032751..6f398c59278a 100644
> --- a/arch/x86/platform/efi/quirks.c

^^^

>         struct efi_memory_map_data data = { 0 };
>         struct efi_mem_range mr;

^^^

---

## [60] Borislav Petkov — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Mon, Jun 03, 2024 at 12:08:48PM -0500, Kalra, Ashish wrote:
> efi_arch_mem_reserve().

Now it only remains for you to explain why...

---

## [61] Mike Rapoport — 2024-06-03
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Mon, Jun 03, 2024 at 11:56:01AM -0500, Kalra, Ashish wrote:
> On 6/3/2024 10:29 AM, Mike Rapoport wrote:
> 

AFAIU, efi_bgrt_init() can be called for any x86 platform, with or without
encryption. 
So if my understating is correct, efi_arch_mem_reserve() will be called with SNP
disabled as well. And if kexec works ok without SNP but fails with SNP this
may give as a clue to the root cause of the failure.
 
> > > If we skip efi_arch_mem_reserve() (which should probably be anyway skipped
> > > for kexec case), then for kexec boot, EFI memmap is memremapped in the same

memblock-allocated memory is just RAM, so my take is that memremap() cannot
figure out the encryption bits properly.

You can check if there are issues with memrmapp()ing memblock-allocated
memory by sticking memblock_phys_alloc() somewhere, filling that memory with a
pattern and then calling memremap(addr, size, MEMREMAP_WB) and checking if
the pattern is still there.
 
> Thanks, Ashish
>

---

## [62] H. Peter Anvin — 2024-06-03
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On 5/29/24 03:47, Nikolay Borisov wrote:
>>
>> diff --git a/arch/x86/kernel/relocate_kernel_64.S 

Sorry if this is a duplicate; something strange happened with my email.

If you are cleaning up this code anyway...

this whole piece of code can be simplified to:

	and $(X86_CR4_PAE | X86_CR4_LA57), %r13d
	mov %r13, %cr4

The PAE bit in %r13 is guaranteed to be set, and %r13 is dead after this.

	-hpa

---

## [63] H. Peter Anvin — 2024-06-03
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

Trying one more time; sorry (again) if someone receives this in duplicate.

>>>
>>> diff --git a/arch/x86/kernel/relocate_kernel_64.S b/arch/x86/kernel/relocate_kernel_64.S

If we are cleaning up this code... the above can simply be:

	andl $(X86_CR4_PAE | X86_CR4_LA54), %r13
	movq %r13, %cr4

%r13 is dead afterwards, and the PAE bit *will* be set in %r13 anyway.

	-hpa

---

## [64] Dave Young — 2024-06-04
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Mon, 3 Jun 2024 at 23:33, Mike Rapoport <rppt@kernel.org> wrote:
>
> On Mon, Jun 03, 2024 at 04:46:39PM +0200, Borislav Petkov wrote:

kexec_in_progress is only for checking if this is in a reboot (kexec) code path.
But eif_mem_reserve is only called during the boot time so checking
kexec_in_progress is meaningless here.
current_kernel_is_booted_via_kexec != is_rebooting_with_kexec

The code change below in the patch looks good to me, but I'm not sure
what caused the memory corruption, it indeed worth some more digging,
maybe SEV/SNP related.
+       if (md.attribute & EFI_MEMORY_RUNTIME)
+               return;

Thanks
Dave

---

## [65] Borislav Petkov — 2024-06-04
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On Mon, Jun 03, 2024 at 05:24:00PM -0700, H. Peter Anvin wrote:
> Trying one more time; sorry (again) if someone receives this in duplicate.
> 

Yeah, with a proper comment. The testing of bits is not really needed.

Thx.

---

## [66] Borislav Petkov — 2024-06-04
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Tue, Jun 04, 2024 at 09:23:58AM +0800, Dave Young wrote:
> kexec_in_progress is only for checking if this is in a reboot (kexec) code path.
> But eif_mem_reserve is only called during the boot time so checking

That's exactly what I wanna check: whether this is a kexec-ed kernel. Or
is there a better helper for that?

---

## [67] Dave Young — 2024-06-04
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Tue, 4 Jun 2024 at 17:44, Borislav Petkov <bp@alien8.de> wrote:
>
> On Tue, Jun 04, 2024 at 09:23:58AM +0800, Dave Young wrote:

No general way to check if it is a kexec-ed kernel or not,  for x86
one can check the efi_setup as Ashish's original patch did, as the
kexec booted kernel (efi boot) will have efi setup_data passed in.

Otherwise there is a type_of_loader field for x86 boot protocol,
kexec-tools is 0x0D, the kexec_file_load also uses this.  But adding
the type_of_loader was only added in kexec-tools code when Yinghai
worked on the kexec-tools bzImage64 load, so older kexec-tools will
not set this field.  Anyway the in-kernel kexec_file_load code for x86
added 0x0D as loader type from the beginning.

Anyway there is not such a helper for all cases.

>
> --

---

## [68] Kirill A. Shutemov — 2024-06-04
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On Tue, Jun 04, 2024 at 11:15:03AM +0200, Borislav Petkov wrote:
> On Mon, Jun 03, 2024 at 05:24:00PM -0700, H. Peter Anvin wrote:
> > Trying one more time; sorry (again) if someone receives this in duplicate.

I think it is better fit the next patch.

What about this?

From b45fe48092abad2612c2bafbb199e4de80c99545 Mon Sep 17 00:00:00 2001
From: "Kirill A. Shutemov" <kirill.shutemov@linux.intel.com>
Date: Fri, 10 Feb 2023 12:53:11 +0300
Subject: [PATCHv11.1 06/19] x86/kexec: Keep CR4.MCE set during kexec for TDX guest

TDX guests run with MCA enabled (CR4.MCE=1b) from the very start. If
that bit is cleared during CR4 register reprogramming during boot or
kexec flows, a #VE exception will be raised which the guest kernel
cannot handle it.

Therefore, make sure the CR4.MCE setting is preserved over kexec too and
avoid raising any #VEs.

The change doesn't affect non-TDX-guest environments.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/kernel/relocate_kernel_64.S | 17 ++++++++++-------
 1 file changed, 10 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kernel/relocate_kernel_64.S b/arch/x86/kernel/relocate_kernel_64.S
index 085eef5c3904..9c2cf70c5f54 100644
--- a/arch/x86/kernel/relocate_kernel_64.S
+++ b/arch/x86/kernel/relocate_kernel_64.S
@@ -5,6 +5,8 @@
  */
 
 #include <linux/linkage.h>
+#include <linux/stringify.h>
+#include <asm/alternative.h>
 #include <asm/page_types.h>
 #include <asm/kexec.h>
 #include <asm/processor-flags.h>
@@ -145,14 +147,15 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
 	 * Set cr4 to a known state:
 	 *  - physical address extension enabled
 	 *  - 5-level paging, if it was enabled before
+	 *  - Machine check exception on TDX guest, if it was enabled before.
+	 *    Clearing MCE might not be allowed in TDX guests, depending on setup.
+	 *
+	 * Use R13 that contains the original CR4 value, read in relocate_kernel().
+	 * PAE is always set in the original CR4.
 	 */
-	movl	$X86_CR4_PAE, %eax
-	testq	$X86_CR4_LA57, %r13
-	jz	.Lno_la57
-	orl	$X86_CR4_LA57, %eax
-.Lno_la57:
-
-	movq	%rax, %cr4
+	andl	$(X86_CR4_PAE | X86_CR4_LA57), %r13d
+	ALTERNATIVE "", __stringify(orl $X86_CR4_MCE, %r13d), X86_FEATURE_TDX_GUEST
+	movq	%r13, %cr4
 
 	jmp 1f
 1:

---

## [69] Kirill A. Shutemov — 2024-06-04
*Subject: Re: [PATCHv11.1 11/19] x86/tdx: Convert shared memory back to
 private on kexec*

On Mon, Jun 03, 2024 at 10:37:54AM +0200, Borislav Petkov wrote:
> On Sun, Jun 02, 2024 at 05:23:03PM +0300, Kirill A. Shutemov wrote:
> > +			/*

Right.

What about the comment below?

			/*
			 * One possible reason for the failure is if kexec raced
			 * with memory conversion. In this case shared bit in
			 * page table got set (or not cleared) during
			 * shared<->private conversion, but the page is actually
			 * private. So this failure is not going to affect the
			 * kexec'ed kernel.
			 *
			 * The only thing one can do at this point on failure
			 * at this point is panic. In absence of better options,
			 * it is reasonable to proceed, hoping the failure is a
			 * benign shared bit mismatch due to the race.
			 *
			 * Also, even if the failure is real and the page cannot
			 * be touched as private, the kdump kernel will boot
			 * fine as it uses pre-reserved memory. What happens
			 * next depends on what the dumping process does and
			 * there's a reasonable chance to produce useful dump
			 * on crash.
			 *
			 * Regardless, the print leaves a trace in the log to
			 * give a clue for debug.
			 */

---

## [70] Dave Hansen — 2024-06-04
*Subject: Re: [PATCHv11.1 11/19] x86/tdx: Convert shared memory back to private
 on kexec*

On 6/4/24 08:32, Kirill A. Shutemov wrote:
> What about the comment below?
> 

It's rambling too much for my taste.

Let's boil this down to what matters:

 1. Failures to change encryption status here can lead a future kernel
    to touch shared memory with a private mapping
 2. That causes an immediate unrecoverable guest shutdown (right?)
 3. kdump kernels should not be affected since they have their own
    memory ranges and its encryption status is not being tweawked here
 4. The pr_err() may help make some sense out of #2 when it happens

I'm not sure the reason behind the failed conversion is important here.

I wouldn't mention panic().

We don't need to opine about what the next kernel might or might not do.

---

## [71] Dave Hansen — 2024-06-04
*Subject: Re: [PATCHv11 09/19] x86/tdx: Account shared memory*

On 5/28/24 02:55, Kirill A. Shutemov wrote:
> Keep track of the number of shared pages. This will allow for 
> cross-checking against the shared information in the direct mapping

It's probably also worth mentioning that conversions are slow and
relatively rare and even though a global atomic isn't really scalable,
it also isn't worth doing anything fancier.
> diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
> index 26fa47db5782..979891e97d83 100644

Doesn't this technically need to be:

	static atomic_long_t nr_shared = ATOMIC_LONG_INIT(0);

?  I thought we had some architectures where the 0 logical value wasn't
actually all 0's.

---

## [72] Kirill A. Shutemov — 2024-06-04
*Subject: Re: [PATCHv11.1 11/19] x86/tdx: Convert shared memory back to
 private on kexec*

On Tue, Jun 04, 2024 at 08:47:22AM -0700, Dave Hansen wrote:
> On 6/4/24 08:32, Kirill A. Shutemov wrote:
> > What about the comment below?

Right.

>  3. kdump kernels should not be affected since they have their own
>     memory ranges and its encryption status is not being tweawked here

The important part is that failure can be benign. It explains "can" in #1.
But okay.

> I wouldn't mention panic().
> 

Is this any better?

			/*
			 * If tdx_enc_status_changed() fails, it leaves memory
			 * in an unknown state. If the memory remains shared,
			 * it can result in an unrecoverable guest shutdown on
			 * the first accessed through a private mapping.
			 *
			 * The kdump kernel boot is not impacted as it uses
			 * a pre-reserved memory range that is always private.
			 * However, gathering crash information could lead to
			 * a crash if it accesses unconverted memory through
			 * a private mapping.
			 *
			 * pr_err() may assist in understanding such crashes.
			 */

---

## [73] Dave Hansen — 2024-06-04
*Subject: Re: [PATCHv11 10/19] x86/mm: Add callbacks to prepare encrypted
 memory for kexec*

On 5/28/24 02:55, Kirill A. Shutemov wrote:
> +	x86_platform.guest.enc_kexec_begin(true);
> +	x86_platform.guest.enc_kexec_finish();

I really despise the random, unlabeled true/false/0/1 arguments to
functions like this.

I'll bring it up in the non-noop patch though.

---

## [74] Kirill A. Shutemov — 2024-06-04
*Subject: Re: [PATCHv11 09/19] x86/tdx: Account shared memory*

On Tue, Jun 04, 2024 at 09:08:25AM -0700, Dave Hansen wrote:
> On 5/28/24 02:55, Kirill A. Shutemov wrote:
> > Keep track of the number of shared pages. This will allow for 

Okay, will do.

> > diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
> > index 26fa47db5782..979891e97d83 100644

Hm. I am not aware of such requirement. I see plenty uninitilized
atomic_long_t in generic code. For instance, invalid_kread_bytes.

And I doubt TDX will ever be built for non-x86 :P

---

## [75] Dave Hansen — 2024-06-04
*Subject: Re: [PATCHv11 11/19] x86/tdx: Convert shared memory back to private
 on kexec*

On 5/28/24 02:55, Kirill A. Shutemov wrote:
> +/* Stop new private<->shared conversions */
> +static void tdx_kexec_begin(bool crash)

I don't like having to pass 'crash' in here.

If interrupts are the problem we have ways of testing for those directly.

If it's being in an oops that's a problem, we have 'oops_in_progress'
for that.

In other words, I'd much rather this function (or better yet
set_memory_enc_stop_conversion() itself) use some existing API to change
its behavior in a crash rather than have the context be passed down and
twiddled through several levels of function calls.

There are a ton of these in the console code:

	if (oops_in_progress)
		foo_trylock();
	else
		foo_lock();

To me, that's a billion times more clear than a 'wait' argument that
gets derives from who-knows-what that I have to trace through ten levels
of function calls.

---

## [76] Borislav Petkov — 2024-06-04
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On Tue, Jun 04, 2024 at 06:21:27PM +0300, Kirill A. Shutemov wrote:
> What about this?

Yeah, LGTM.

Thx.

---

## [77] Borislav Petkov — 2024-06-04
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Tue, Jun 04, 2024 at 07:09:56PM +0800, Dave Young wrote:
> Anyway there is not such a helper for all cases.

But maybe there should be...

This is not the first case where the need arises to be able to say:

	if (am I a kexeced kernel)

in code.

Perhaps we should have a global var kexeced or so which gets incremented
on each kexec-ed kernel, somewhere in very early boot of the kexec-ed
kernel we do

	kexeced++;

and then other code can query it and know whether this is a kexec-ed
kernel and how many times it got kexec-ed...

---

## [78] Borislav Petkov — 2024-06-04
*Subject: Re: [PATCHv11.1 11/19] x86/tdx: Convert shared memory back to
 private on kexec*

On Tue, Jun 04, 2024 at 07:14:00PM +0300, Kirill A. Shutemov wrote:
> 			/*
> 			 * If tdx_enc_status_changed() fails, it leaves memory

"access"

So this sentence above can go too, right?

Because that comment is in tdx_kexec_finish() and we're basically going
off to kexec. So can a guest even access it through a private mapping?
We're shutting down so nothing is running anymore...

> 			 * The kdump kernel boot is not impacted as it uses
> 			 * a pre-reserved memory range that is always private.

When does the kexec kernel even get such a private mapping? It is not
even up yet...

> 			 * pr_err() may assist in understanding such crashes.

"Print error info in order to leave bread crumbs for debugging." is what
I'd say.

Thx.

---

## [79] Kalra, Ashish — 2024-06-04
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On 6/3/2024 12:12 PM, Borislav Petkov wrote:

> On Mon, Jun 03, 2024 at 12:08:48PM -0500, Kalra, Ashish wrote:
>> efi_arch_mem_reserve().

Here is a detailed explanation of what is causing the EFI memory map corruption, with added debug logs and memblock debugging enabled:

Initially at boot, efi_memblock_x86_reserve_range() does early_memremap() of the EFI memory map passed as part of setup_data, as the following logs show:

...

[ 0.000000] efi: in efi_memblock_x86_reserve_range, phys map 0x27fff9110 [ 0.000000] memblock_reserve: [0x000000027fff9110-0x000000027fffa12f] efi_memblock_x86_reserve_range+0x168/0x2a0

...

Later, efi_arch_mem_reserve() is invoked, which calls efi_memmap_alloc() which does memblock_phys_alloc() to insert new EFI memory descriptor into efi.memap:

...

[ 0.733263] memblock_reserve: [0x000000027ffcaf80-0x000000027ffcbfff] memblock_alloc_range_nid+0xf1/0x1b0 [ 0.734787] efi: efi_arch_mem_reserve, efi phys map 0x27ffcaf80

...

Finally, at the end of boot, kexec_enter_virtual_mode() is called.

It does mapping of efi regions which were passed via setup_data.

So it unregisters the early mem-remapped EFI memmap and installs the new EFI memory map as below:

( Because of efi_arch_mem_reserve() getting invoked, the new EFI memmap phys base being remapped now is the memblock allocation done in efi_arch_mem_reserve()).

[ 4.042160] efi: efi memmap phys map 0x27ffcaf80

So, kexec_enter_virtual_mode() does the following :

if (efi_memmap_init_late(efi.memmap.phys_map, <---- refers to the new EFI memmap phys base allocated via memblock in efi_arch_mem_reserve(). efi.memmap.desc_size * efi.memmap.nr_map)) { ...

This late init, does a memremap() on this memblock-allocated memory, but then immediately frees it :

drivers/firmware/efi/memmap.c:

*/ int __init __efi_memmap_init(struct efi_memory_map_data *data) {

..

phys_map = data->phys_map; <----------------------- refers to the new EFI memmap phys base allocated via memblock in efi_arch_mem_reserve().

if (data->flags & EFI_MEMMAP_LATE) map.map = memremap(phys_map, data->size, MEMREMAP_WB); ... ... if (efi.memmap.flags & (EFI_MEMMAP_MEMBLOCK | EFI_MEMMAP_SLAB)) { __efi_memmap_free(efi.memmap.phys_map, efi.memmap.desc_size * efi.memmap.nr_map, efi.memmap.flags); }

map.phys_map = data->phys_map;

...

efi.memmap = map;

...

This happens as kexec_enter_virtual_mode() can only handle the early mapped EFI memmap and not the one which is memblock allocated by efi_arch_mem_reserve(). As seen above this memblock allocated (EFI_MEMMAP_MEMBLOCK tagged) memory gets freed.

This is confirmed by memblock debugging:

[ 4.044057] memblock_free_late: [0x000000027ffcaf80-0x000000027ffcbfff] __efi_memmap_free+0x66/0x80

So while this memory is memremapped, it has also been freed and then it gets into a use-after-free condition and subsequently gets corrupted.

This corruption is seen just before kexec-ing into the new kernel:

...

[ 11.045522] PEFILE: Unsigned PE binary^M [ 11.060801] kexec-bzImage64: efi memmap phys map 0x27ffcaf80 ... [ 11.061220] kexec-bzImage64: mmap entry, type = 11, va = 0xfffffffeffc00000, pa = 0xffc00000, np = 0x400, attr = 0x8000000000000001^M [ 11.061225] kexec-bzImage64: mmap entry, type = 6, va = 0xfffffffeffb04000, pa = 0x7f704000, np = 0x84, attr = 0x800000000000000f^M [ 11.061228] kexec-bzImage64: mmap entry, type = 4, va = 0xfffffffeff700000, pa = 0x7f100000, np = 0x300, attr = 0x0^M [ 11.061231] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M <---------------- CORRUPTED!!! [ 11.061234] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061236] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061239] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061241] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0,
attr = 0x0^M [ 11.061243] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061245] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061248] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061250] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061252] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061255] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061257] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061259] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061262] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061264] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061266]
kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061268] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061271] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061273] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061275] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061278] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061280] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061282] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061284] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061287] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061289] kexec-bzImage64: mmap entry, type = 0,
va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061291] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061294] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061296] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061298] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061301] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061303] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061305] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061307] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061310] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M [ 11.061312] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr =
0x0^M [ 11.061314] kexec-bzImage64: mmap entry, type = 14080, va = 0x14f29, pa = 0x36c0, np = 0x0, attr = 0x0^M [ 11.061317] kexec-bzImage64: mmap entry, type = 85808, va = 0x0, pa = 0x0, np = 0x72, attr = 0x14f40

...

This EFI memmapphys map address 0x27ffcaf80 being mem-remapped and also getting freed and then in use after free condition (while setting up the EFI memory map for the next kernel with kexec -s) in the above logs confirm the use-after-free case.

Looking at the above code flow, it makes sense to skip efi_arch_mem_reserve() to fix this issue, as it anyway needs to be skipped for kexec case.

Thanks, Ashish

---

## [80] Kalra, Ashish — 2024-06-04
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

Re-sending as the earlier response got line-wrapped.

On 6/3/2024 12:12 PM, Borislav Petkov wrote:
> On Mon, Jun 03, 2024 at 12:08:48PM -0500, Kalra, Ashish wrote:
>> efi_arch_mem_reserve().

Here is a detailed explanation of what is causing the EFI memory map corruption, with added debug logs and memblock debugging enabled:

Initially at boot, efi_memblock_x86_reserve_range() does early_memremap() of the EFI memory map passed as part of setup_data, as the following logs show:

...

[ 0.000000] efi: in efi_memblock_x86_reserve_range, phys map 0x27fff9110 
[ 0.000000] memblock_reserve: [0x000000027fff9110-0x000000027fffa12f] efi_memblock_x86_reserve_range+0x168/0x2a0

...

Later, efi_arch_mem_reserve() is invoked, which calls efi_memmap_alloc() which does memblock_phys_alloc() to insert new EFI memory descriptor into efi.memap:

...

[ 0.733263] memblock_reserve: [0x000000027ffcaf80-0x000000027ffcbfff] memblock_alloc_range_nid+0xf1/0x1b0 
[ 0.734787] efi: efi_arch_mem_reserve, efi phys map 0x27ffcaf80

...

Finally, at the end of boot, kexec_enter_virtual_mode() is called.

It does mapping of efi regions which were passed via setup_data.

So it unregisters the early mem-remapped EFI memmap and installs the new EFI memory map as below:

( Because of efi_arch_mem_reserve() getting invoked, the new EFI memmap phys base being remapped now is the memblock allocation done in efi_arch_mem_reserve()).

[ 4.042160] efi: efi memmap phys map 0x27ffcaf80

So, kexec_enter_virtual_mode() does the following :

	if (efi_memmap_init_late(efi.memmap.phys_map, <- refers to the new EFI memmap phys base allocated via memblock in efi_arch_mem_reserve().
	 	efi.memmap.desc_size * efi.memmap.nr_map)) { ...

This late init, does a memremap() on this memblock-allocated memory, but then immediately frees it :

drivers/firmware/efi/memmap.c:

int __init __efi_memmap_init(struct efi_memory_map_data *data) 
{

	..

	phys_map = data->phys_map; <- refers to the new EFI memmap phys base allocated via memblock in efi_arch_mem_reserve().

	if (data->flags & EFI_MEMMAP_LATE) 
		map.map = memremap(phys_map, data->size, MEMREMAP_WB);
	... 
	... 
	if (efi.memmap.flags & (EFI_MEMMAP_MEMBLOCK | EFI_MEMMAP_SLAB)) { 
		__efi_memmap_free(efi.memmap.phys_map, 
				efi.memmap.desc_size * efi.memmap.nr_map, efi.memmap.flags); 
	}

	...
	map.phys_map = data->phys_map;

	...

	efi.memmap = map;

	...

This happens as kexec_enter_virtual_mode() can only handle the early mapped EFI memmap and not the one which is memblock allocated by efi_arch_mem_reserve(). As seen above this memblock allocated (EFI_MEMMAP_MEMBLOCK tagged) memory gets freed.

This is confirmed by memblock debugging:

[ 4.044057] memblock_free_late: [0x000000027ffcaf80-0x000000027ffcbfff] __efi_memmap_free+0x66/0x80

So while this memory is memremapped, it has also been freed and then it gets into a use-after-free condition and subsequently gets corrupted.

This corruption is seen just before kexec-ing into the new kernel:

...
[   11.045522] PEFILE: Unsigned PE binary^M
[   11.060801] kexec-bzImage64: efi memmap phys map 0x27ffcaf80^M
...
[   11.061220] kexec-bzImage64: mmap entry, type = 11, va = 0xfffffffeffc00000, pa = 0xffc00000, np = 0x400, attr = 0x8000000000000001^M
[   11.061225] kexec-bzImage64: mmap entry, type = 6, va = 0xfffffffeffb04000, pa = 0x7f704000, np = 0x84, attr = 0x800000000000000f^M
[   11.061228] kexec-bzImage64: mmap entry, type = 4, va = 0xfffffffeff700000, pa = 0x7f100000, np = 0x300, attr = 0x0^M
[   11.061231] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M <- CORRUPTION!!!
[   11.061234] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061236] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061239] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061241] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061243] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061245] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061248] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061250] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061252] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061255] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061257] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061259] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061262] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061264] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061266] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061268] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061271] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061273] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061275] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061278] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061280] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061282] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061284] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061287] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061289] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061291] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061294] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061296] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061298] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061301] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061303] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061305] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061307] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061310] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061312] kexec-bzImage64: mmap entry, type = 0, va = 0x0, pa = 0x0, np = 0x0, attr = 0x0^M
[   11.061314] kexec-bzImage64: mmap entry, type = 14080, va = 0x14f29, pa = 0x36c0, np = 0x0, attr = 0x0^M
[   11.061317] kexec-bzImage64: mmap entry, type = 85808, va = 0x0, pa = 0x0, np = 0x72, attr = 0x14f40^M
[   11.061320] kexec-bzImage64: mmap entry, type = 0, va = 0x14f4b, pa = 0x65, np = 0x1, attr = 0x0^M
[   11.061323] kexec-bzImage64: mmap entry, type = 85840, va = 0x0, pa = 0x2, np = 0x69, attr = 0x14f59^M
[   11.061325] kexec-bzImage64: mmap entry, type = 0, va = 0x14f65, pa = 0x6c, np = 0x0, attr = 0x0^M
[   11.061328] kexec-bzImage64: mmap entry, type = 85871, va = 0x0, pa = 0x0, np = 0x7a, attr = 0x14f7f^M


...

This EFI phys map address 0x27ffcaf80 is being mem-remapped and also getting freed and then in use after free condition (while setting up the EFI memory map for the next kernel with kexec -s) in the above logs confirm the use-after-free case.

Looking at the above code flow, it makes sense to skip efi_arch_mem_reserve() to fix this issue, as it anyway needs to be skipped for kexec case.

Thanks, Ashish

---

## [81] Dave Young — 2024-06-05
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Wed, 5 Jun 2024 at 06:36, Kalra, Ashish <ashish.kalra@amd.com> wrote:
>
> Re-sending as the earlier response got line-wrapped.

From your debugging the memmap should not be freed.  This piece of
code was added in below commit,  added Dan Williams in cc list:
commit f0ef6523475f18ccd213e22ee593dfd131a2c5ea
Author: Dan Williams <dan.j.williams@intel.com>
Date:   Mon Jan 13 18:22:44 2020 +0100

    efi: Fix efi_memmap_alloc() leaks

    With efi_fake_memmap() and efi_arch_mem_reserve() the efi table may be
    updated and replaced multiple times. When that happens a previous
    dynamically allocated efi memory map can be garbage collected. Use the
    new EFI_MEMMAP_{SLAB,MEMBLOCK} flags to detect when a dynamically
    allocated memory map is being replaced.


>
>         ...

---

## [82] Dave Young — 2024-06-05
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

> >         ...
> >         if (efi.memmap.flags & (EFI_MEMMAP_MEMBLOCK | EFI_MEMMAP_SLAB)) {

Dan, probably those regions should be freed only for "fake" memmap?

---

## [83] Dave Young — 2024-06-05
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Wed, 5 Jun 2024 at 09:52, Dave Young <dyoung@redhat.com> wrote:
>
> > >         ...

Ashish, can you comment out the __efi_memmap_free see if it works for
you just confirm about the behavior.

---

## [84] Kalra, Ashish — 2024-06-04
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

Hello Dave,

On 6/4/2024 8:58 PM, Dave Young wrote:
> On Wed, 5 Jun 2024 at 09:52, Dave Young <dyoung@redhat.com> wrote:
>>>>         ...

Yes, i have already tried and tested that, if i avoid __efi_memmap_free(), then i don't see this memory map corruption.

Thanks, Ashish

---

## [85] Kalra, Ashish — 2024-06-04
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On 6/4/2024 8:48 PM, Dave Young wrote:

> On Wed, 5 Jun 2024 at 06:36, Kalra, Ashish <ashish.kalra@amd.com> wrote:
>> Re-sending as the earlier response got line-wrapped.

Yes, it looks like that it should not be freed, as the new and previous efi memory map can be same.

Thanks, Ashish

> This piece of
> code was added in below commit,  added Dan Williams in cc list:

---

## [86] Dave Young — 2024-06-05
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Wed, 5 Jun 2024 at 10:09, Kalra, Ashish <ashish.kalra@amd.com> wrote:
>
> Hello Dave,

Ok, thanks!  I think the right way is creating two patches,  one to
remove the __efi_memmap_free, another is  skip efi_arch_mem_reserve
when the EFI_MEMORY_RUNTIME bit was set already.  But the first one
should be the fix for the root cause.

efi fake mem is only for debugging purposes,  the "memleak" mentioned
in commit 0f96a99dab36 should be solved in another way if needed (are
they really leaked? or just not useful anymore)

Anyway this is my opinion, please wait for x86 and efi reviewer's inputs.

>
> Thanks, Ashish

---

## [87] Dave Young — 2024-06-05
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Wed, 5 Jun 2024 at 02:03, Borislav Petkov <bp@alien8.de> wrote:
>
> On Tue, Jun 04, 2024 at 07:09:56PM +0800, Dave Young wrote:

It's something good to have but not must for the time being,  also no
idea how to save the status across boot, for EFI boot case probably a
EFI var can be used, but how can it be cleared in case of physical
boot.    Otherwise probably injecting some kernel parameters, anyway
this needs more thinking.

>
> --

---

## [88] Borislav Petkov — 2024-06-05
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Wed, Jun 05, 2024 at 10:53:44AM +0800, Dave Young wrote:
> It's something good to have but not must for the time being,  also no
> idea how to save the status across boot, for EFI boot case probably a

Yes.

> but how can it be cleared in case of physical boot.  Otherwise
> probably injecting some kernel parameters, anyway this needs more

Yeah, this'll need proper analysis whether we can even do that reliably.

We need to increment it only on the kexec reboot paths and clear it on
the normal reboot paths.

Thx.

---

## [89] Ard Biesheuvel — 2024-06-05
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Wed, 5 Jun 2024 at 09:43, Borislav Petkov <bp@alien8.de> wrote:
>
> On Wed, Jun 05, 2024 at 10:53:44AM +0800, Dave Young wrote:

I'd argue for the opposite: ideally, the difference between the first
boot and not-the-first-boot should be abstracted away by the
'bootloader' side of kexec as much as possible, so that the tricky
early startup code doesn't have to be riddled with different code
paths depending on !kexec vs kexec.

TDX is a good case in point here: rather than add more conditionals,
I'd urge to remove them so the TDX startup code doesn't have to care
about the difference at all. If there is anything special that needs
to be done, it belongs in the kexec implementation of the previous
kernel.

---

## [90] Borislav Petkov — 2024-06-05
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

Moving Ard and Dan to To:

On Wed, Jun 05, 2024 at 10:28:18AM +0800, Dave Young wrote:
> Ok, thanks!  I think the right way is creating two patches,  one to
> remove the __efi_memmap_free,

Yap, that 

  f0ef6523475f ("efi: Fix efi_memmap_alloc() leaks")

needs revisiting.

So AFAIU, the flow is this:

In a kexec-ed kernel:

1. efi_arch_mem_reserve() gets called by bgrt, erst, mokvar... whatever
   to hold on to boot services regions for longer otherwise EFI
   "implementations" explode.

2. On same kexec-ed kernel, we call into kexec_enter_virtual_mode()
   because it needs to get the runtime services regions from the first
   kernel

3. As part of that call, it'll do
   efi_memmap_init_late->__efi_memmap_init():

        if (efi.memmap.flags & (EFI_MEMMAP_MEMBLOCK | EFI_MEMMAP_SLAB))
                __efi_memmap_free(efi.memmap.phys_map,

and the memory which got allocated in step 1 is gone, thus reverting
what efi_arch_mem_reserve() is trying to fix.

IOW, we need a

	EFI_MEMMAP_DO_NOT_TOUCH_MY_MEMORY

flag which'll stop this from happening. But I'd prefer it if Ard decides
what the right thing to do here is.

> another is  skip efi_arch_mem_reserve when the EFI_MEMORY_RUNTIME bit
> was set already.

Can that even happen?

Thx.

---

## [91] Borislav Petkov — 2024-06-05
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Wed, Jun 05, 2024 at 10:17:22AM +0200, Ard Biesheuvel wrote:
> I'd argue for the opposite: ideally, the difference between the first
> boot and not-the-first-boot should be abstracted away by the

Well, off and on we end up needing to be able to ask whether the current
kernel is kexec-ed. So you need to be able to access that aspect in
kernel code - not in the bootloader. Perhaps read it from the
bootloader, sure.

But see my other mail from just now - it might end up not needing it
after all and I'd prefer if we never ever have to ask that question but
just from staring at EFI code it reminded me that we do need to ask that
question already:

        if (efi_setup)
                kexec_enter_virtual_mode();
        else
                __efi_enter_virtual_mode();

*exactly* because of EFI and that virtual_map call nonsense of allowing
it only once.

And we check efi_setup here because that works. But you can't use that
globally. And so on...

> TDX is a good case in point here: rather than add more conditionals,
> I'd urge to remove them so the TDX startup code doesn't have to care

Sure, but reality is not as easy sometimes.

Thx.

---

## [92] Kirill A. Shutemov — 2024-06-05
*Subject: Re: [PATCHv11.1 11/19] x86/tdx: Convert shared memory back to
 private on kexec*

On Tue, Jun 04, 2024 at 08:05:54PM +0200, Borislav Petkov wrote:
> On Tue, Jun 04, 2024 at 07:14:00PM +0300, Kirill A. Shutemov wrote:
> > 			/*

Okay.

> So this sentence above can go too, right?

I don't think so.

> Because that comment is in tdx_kexec_finish() and we're basically going
> off to kexec. So can a guest even access it through a private mapping?

This kernel can't. But the next kernel can.

If a page can be accessed via private mapping is determined by the
presence in Secure EPT. This state persist across kexec.

> > 			 * The kdump kernel boot is not impacted as it uses
> > 			 * a pre-reserved memory range that is always private.

Crash kernel provides access to this memory via /proc/vmcore. Crash kernel
will assume all memory there is private.

> > 			 * pr_err() may assist in understanding such crashes.
> 

Okay.

---

## [93] Kirill A. Shutemov — 2024-06-05
*Subject: Re: [PATCHv11 11/19] x86/tdx: Convert shared memory back to private
 on kexec*

On Tue, Jun 04, 2024 at 09:27:59AM -0700, Dave Hansen wrote:
> On 5/28/24 02:55, Kirill A. Shutemov wrote:
> > +/* Stop new private<->shared conversions */

Okay fair enough. Check out the fixup below. Is it what you mean?

One other thing I realized is that these callback are dead code if kernel
compiled without kexec support. Do we want them to be wrapped with
#ifdef COFNIG_KEXEC_CORE everywhere? It is going to be ugly.

Any better ideas?

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 3d23ea0f5d45..1c5aa036b76b 100644
--- a/arch/x86/coco/tdx/tdx.c
+++ b/arch/x86/coco/tdx/tdx.c
@@ -834,7 +834,7 @@ static int tdx_enc_status_change_finish(unsigned long vaddr, int numpages,
 }
 
 /* Stop new private<->shared conversions */
-static void tdx_kexec_begin(bool crash)
+static void tdx_kexec_begin(void)
 {
 	/*
 	 * Crash kernel reaches here with interrupts disabled: can't wait for
@@ -842,7 +842,7 @@ static void tdx_kexec_begin(bool crash)
 	 *
 	 * If race happened, just report and proceed.
 	 */
-	if (!set_memory_enc_stop_conversion(!crash))
+	if (!set_memory_enc_stop_conversion())
 		pr_warn("Failed to stop shared<->private conversions\n");
 }
 
diff --git a/arch/x86/include/asm/set_memory.h b/arch/x86/include/asm/set_memory.h
index d490db38db9e..4b2abce2e3e7 100644
--- a/arch/x86/include/asm/set_memory.h
+++ b/arch/x86/include/asm/set_memory.h
@@ -50,7 +50,7 @@ int set_memory_np(unsigned long addr, int numpages);
 int set_memory_p(unsigned long addr, int numpages);
 int set_memory_4k(unsigned long addr, int numpages);
 
-bool set_memory_enc_stop_conversion(bool wait);
+bool set_memory_enc_stop_conversion(void);
 int set_memory_encrypted(unsigned long addr, int numpages);
 int set_memory_decrypted(unsigned long addr, int numpages);
 
diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index b0f313278967..213cf5379a5a 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -152,8 +152,6 @@ struct x86_init_acpi {
  * @enc_kexec_begin		Begin the two-step process of converting shared memory back
  *				to private. It stops the new conversions from being started
  *				and waits in-flight conversions to finish, if possible.
- *				The @crash parameter denotes whether the function is being
- *				called in the crash shutdown path.
  * @enc_kexec_finish		Finish the two-step process of converting shared memory to
  *				private. All memory is private after the call when
  *				the function returns.
@@ -165,7 +163,7 @@ struct x86_guest {
 	int (*enc_status_change_finish)(unsigned long vaddr, int npages, bool enc);
 	bool (*enc_tlb_flush_required)(bool enc);
 	bool (*enc_cache_flush_required)(void);
-	void (*enc_kexec_begin)(bool crash);
+	void (*enc_kexec_begin)(void);
 	void (*enc_kexec_finish)(void);
 };
 
diff --git a/arch/x86/kernel/crash.c b/arch/x86/kernel/crash.c
index fc52ea80cdc8..340af8155658 100644
--- a/arch/x86/kernel/crash.c
+++ b/arch/x86/kernel/crash.c
@@ -137,7 +137,7 @@ void native_machine_crash_shutdown(struct pt_regs *regs)
 	 * down and interrupts have been disabled. This allows the callback to
 	 * detect a race with the conversion and report it.
 	 */
-	x86_platform.guest.enc_kexec_begin(true);
+	x86_platform.guest.enc_kexec_begin();
 	x86_platform.guest.enc_kexec_finish();
 
 	crash_save_cpu(regs, safe_smp_processor_id());
diff --git a/arch/x86/kernel/reboot.c b/arch/x86/kernel/reboot.c
index 513809b5b27c..0e0a4cf6b5eb 100644
--- a/arch/x86/kernel/reboot.c
+++ b/arch/x86/kernel/reboot.c
@@ -723,7 +723,7 @@ void native_machine_shutdown(void)
 	 * conversions to finish cleanly.
 	 */
 	if (kexec_in_progress)
-		x86_platform.guest.enc_kexec_begin(false);
+		x86_platform.guest.enc_kexec_begin();
 
 	/* Stop the cpus and apics */
 #ifdef CONFIG_X86_IO_APIC
diff --git a/arch/x86/kernel/x86_init.c b/arch/x86/kernel/x86_init.c
index 8a79fb505303..82b128d3f309 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -138,7 +138,7 @@ static int enc_status_change_prepare_noop(unsigned long vaddr, int npages, bool
 static int enc_status_change_finish_noop(unsigned long vaddr, int npages, bool enc) { return 0; }
 static bool enc_tlb_flush_required_noop(bool enc) { return false; }
 static bool enc_cache_flush_required_noop(void) { return false; }
-static void enc_kexec_begin_noop(bool crash) {}
+static void enc_kexec_begin_noop(void) {}
 static void enc_kexec_finish_noop(void) {}
 static bool is_private_mmio_noop(u64 addr) {return false; }
 
diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
index 2a548b65ef5f..443a97e515c0 100644
--- a/arch/x86/mm/pat/set_memory.c
+++ b/arch/x86/mm/pat/set_memory.c
@@ -2240,13 +2240,14 @@ static DECLARE_RWSEM(mem_enc_lock);
  *
  * Taking the exclusive mem_enc_lock waits for in-flight conversions to complete.
  * The lock is not released to prevent new conversions from being started.
- *
- * If sleep is not allowed, as in a crash scenario, try to take the lock.
- * Failure indicates that there is a race with the conversion.
  */
-bool set_memory_enc_stop_conversion(bool wait)
+bool set_memory_enc_stop_conversion(void)
 {
-	if (!wait)
+	/*
+	 * In a crash scenario, sleep is not allowed. Try to take the lock.
+	 * Failure indicates that there is a race with the conversion.
+	 */
+	if (oops_in_progress)
 		return down_write_trylock(&mem_enc_lock);
 
 	down_write(&mem_enc_lock);

---

## [94] Dave Hansen — 2024-06-05
*Subject: Re: [PATCHv11 11/19] x86/tdx: Convert shared memory back to private
 on kexec*

On 6/5/24 05:43, Kirill A. Shutemov wrote:
> Okay fair enough. Check out the fixup below. Is it what you mean?

Yes.  Much better.

> One other thing I realized is that these callback are dead code if kernel
> compiled without kexec support. Do we want them to be wrapped with

The other callbacks don't have #ifdefs either and they're dependent on
memory encryption as far as I can tell.

I think a simple:

	if (IS_ENABLED(COFNIG_KEXEC_CORE))
		return;

in the top of the callbacks will result in a tiny little stub function
when kexec is disabled.  So the bloat will be limited to kernels that
have TDX compiled in but kexec compiled out (probably never).  The bloat
will be two callback pointer, one tiny stub function, and a quick
call/return in a slow path.

I think that probably ends up being a few dozen bytes of bloat in kernel
text for a "probably never" config.

---

## [95] Borislav Petkov — 2024-06-05
*Subject: Re: [PATCHv11.1 11/19] x86/tdx: Convert shared memory back to
 private on kexec*

On Wed, Jun 05, 2024 at 03:21:42PM +0300, Kirill A. Shutemov wrote:
> If a page can be accessed via private mapping is determined by the
> presence in Secure EPT. This state persist across kexec.

I just love it how I tickle out details each time I touch this comment
because we three can't write a single concise and self-contained
explanation. :-(

Ok, next version:

"Private mappings persist across kexec. If tdx_enc_status_changed() fails
in the first kernel, it leaves memory in an unknown state.

If that memory remains shared, accessing it in the *next* kernel through
a private mapping will result in an unrecoverable guest shutdown.

The kdump kernel boot is not impacted as it uses a pre-reserved memory
range that is always private.  However, gathering crash information
could lead to a crash if it accesses unconverted memory through
a private mapping which is possible when accessing that memory through
/proc/vmcore, for example.

In all cases, print error info in order to leave enough bread crumbs for
debugging."

I think this is getting in the right direction as it actually makes
sense now.

---

## [96] Borislav Petkov — 2024-06-05
*Subject: Re: [PATCH v7 2/3] x86/boot/compressed: Skip Video Memory access in
 Decompressor for SEV-ES/SNP.*

On Thu, May 30, 2024 at 11:37:14PM +0000, Ashish Kalra wrote:
> -	lines = boot_params_ptr->screen_info.orig_video_lines;
> -	cols = boot_params_ptr->screen_info.orig_video_cols;

By now I get an allergic reaction from this sprinkling of "if sev..."
everywhere in the code.

>  	init_default_io_ops();

<--- right here there's a call to

	early_tdx_detect();

You can add a early_sev_detect() counterpart here and clear lines and
cols in it along with an explanation why it is being done.

This is at least a bit cleaner than this.

Thx.

---

## [97] Dave Young — 2024-06-06
*Subject: Re: [PATCH v7 1/3] efi/x86: Fix EFI memory map corruption with kexec*

On Wed, 5 Jun 2024 at 19:09, Borislav Petkov <bp@alien8.de> wrote:
>
> Moving Ard and Dan to To:

Yes, let's say we have two different cases both go through
drivers/firmware/efi/efi-bgrt.c -> efi_mem_reserve ->
efi_arch_mem_reserve
1. normal boot (non kexec-ed)
    The bgrt region is reserved and mark as EFI_MEMORY_RUNTIME with a
new efi mem range which is inserted in the memmap, later kexec will
carry over to 2nd kernel (drop those boot service areas without
EFI_MEMORY_RUNTIME)
2. kexec-ed boot
     In the same call path, the previous kernel saved bgrt region has
already set EFI_MEMORY_RUNTIME, but it is re-reserved with a new mem
entry in memmap, this is not necessary and duplicate.   I did not
check the efi boot code if it will de-duplicate the memmap later, but
anyway this is useless and it should be skipped.

Thanks
Dave

---

## [98] Kirill A. Shutemov — 2024-06-06
*Subject: Re: [PATCHv11.1 11/19] x86/tdx: Convert shared memory back to
 private on kexec*

On Wed, Jun 05, 2024 at 06:24:19PM +0200, Borislav Petkov wrote:
> On Wed, Jun 05, 2024 at 03:21:42PM +0300, Kirill A. Shutemov wrote:
> > If a page can be accessed via private mapping is determined by the

s/Private mappings persist /Memory encryption state persists /

> in the first kernel, it leaves memory in an unknown state.
> 

Otherwise looks good to me.

---

## [99] Kirill A. Shutemov — 2024-06-07
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Mon, Jun 03, 2024 at 10:39:30AM +0200, Borislav Petkov wrote:
> > +/*
> > + * Make sure asm_acpi_mp_play_dead() is present in the identity mapping at

Okay, there is a function called kernel_map_pages_in_pgd() in set_memory.c
that does what we need here.

I tried to use it, but encountered a few issues:

- The code in set_memory.c allocates memory using the buddy allocator,
  which is not yet ready. We can work around this limitation by delaying
  the initialization of offlining until later, using a separate
  early_initcall();

- I noticed a complaint that the allocation is being done from an atomic
  context: a spinlock called cpa_lock is taken when populate_pgd()
  allocates memory.

  I am not sure why this was not noticed before. kernel_map_pages_in_pgd()
  has only been used in EFI mapping initialization so far, so maybe it is
  somehow special, I don't know.

  I was able to address this issue by switching cpa_lock to a mutex.
  However, this solution will only work if the callers for set_memory
  interfaces are not called from an atomic context. I need to verify if
  this is the case.

- The function __flush_tlb_all() in kernel_(un)map_pages_in_pgd() must be
  called with preemption disabled. Once again, I am unsure why this has
  not caused issues in the EFI case.

- I discovered a bug in kernel_ident_mapping_free() when it is used on a
  machine with 5-level paging. I will submit a proper patch to fix this
  issue.

The fixup is below.

Any comments?

diff --git a/arch/x86/kernel/acpi/madt_wakeup.c b/arch/x86/kernel/acpi/madt_wakeup.c
index 6cfe762be28b..fbbfe78f7f27 100644
--- a/arch/x86/kernel/acpi/madt_wakeup.c
+++ b/arch/x86/kernel/acpi/madt_wakeup.c
@@ -59,82 +59,55 @@ static void acpi_mp_cpu_die(unsigned int cpu)
 		pr_err("Failed to hand over CPU %d to BIOS\n", cpu);
 }
 
+static void acpi_mp_disable_offlining(struct acpi_madt_multiproc_wakeup *mp_wake)
+{
+	cpu_hotplug_disable_offlining();
+
+	/*
+	 * ACPI MADT doesn't allow to offline a CPU after it was onlined. This
+	 * limits kexec: the second kernel won't be able to use more than one CPU.
+	 *
+	 * To prevent a kexec kernel from onlining secondary CPUs invalidate the
+	 * mailbox address in the ACPI MADT wakeup structure which prevents a
+	 * kexec kernel to use it.
+	 *
+	 * This is safe as the booting kernel has the mailbox address cached
+	 * already and acpi_wakeup_cpu() uses the cached value to bring up the
+	 * secondary CPUs.
+	 *
+	 * Note: This is a Linux specific convention and not covered by the
+	 *       ACPI specification.
+	 */
+	mp_wake->mailbox_address = 0;
+}
+
 /* The argument is required to match type of x86_mapping_info::alloc_pgt_page */
 static void __init *alloc_pgt_page(void *dummy)
 {
-	return memblock_alloc(PAGE_SIZE, PAGE_SIZE);
+	return (void *)get_zeroed_page(GFP_KERNEL);
 }
 
 static void __init free_pgt_page(void *pgt, void *dummy)
 {
-	return memblock_free(pgt, PAGE_SIZE);
+	return free_page((unsigned long)pgt);
 }
 
-/*
- * Make sure asm_acpi_mp_play_dead() is present in the identity mapping at
- * the same place as in the kernel page tables. asm_acpi_mp_play_dead() switches
- * to the identity mapping and the function has be present at the same spot in
- * the virtual address space before and after switching page tables.
- */
-static int __init init_transition_pgtable(pgd_t *pgd)
-{
-	pgprot_t prot = PAGE_KERNEL_EXEC_NOENC;
-	unsigned long vaddr, paddr;
-	p4d_t *p4d;
-	pud_t *pud;
-	pmd_t *pmd;
-	pte_t *pte;
-
-	vaddr = (unsigned long)asm_acpi_mp_play_dead;
-	pgd += pgd_index(vaddr);
-	if (!pgd_present(*pgd)) {
-		p4d = (p4d_t *)alloc_pgt_page(NULL);
-		if (!p4d)
-			return -ENOMEM;
-		set_pgd(pgd, __pgd(__pa(p4d) | _KERNPG_TABLE));
-	}
-	p4d = p4d_offset(pgd, vaddr);
-	if (!p4d_present(*p4d)) {
-		pud = (pud_t *)alloc_pgt_page(NULL);
-		if (!pud)
-			return -ENOMEM;
-		set_p4d(p4d, __p4d(__pa(pud) | _KERNPG_TABLE));
-	}
-	pud = pud_offset(p4d, vaddr);
-	if (!pud_present(*pud)) {
-		pmd = (pmd_t *)alloc_pgt_page(NULL);
-		if (!pmd)
-			return -ENOMEM;
-		set_pud(pud, __pud(__pa(pmd) | _KERNPG_TABLE));
-	}
-	pmd = pmd_offset(pud, vaddr);
-	if (!pmd_present(*pmd)) {
-		pte = (pte_t *)alloc_pgt_page(NULL);
-		if (!pte)
-			return -ENOMEM;
-		set_pmd(pmd, __pmd(__pa(pte) | _KERNPG_TABLE));
-	}
-	pte = pte_offset_kernel(pmd, vaddr);
-
-	paddr = __pa(vaddr);
-	set_pte(pte, pfn_pte(paddr >> PAGE_SHIFT, prot));
-
-	return 0;
-}
-
-static int __init acpi_mp_setup_reset(u64 reset_vector)
+static int __init acpi_mp_setup_reset(union acpi_subtable_headers *header,
+			      const unsigned long end)
 {
+	struct acpi_madt_multiproc_wakeup *mp_wake;
 	struct x86_mapping_info info = {
 		.alloc_pgt_page = alloc_pgt_page,
 		.free_pgt_page	= free_pgt_page,
 		.page_flag      = __PAGE_KERNEL_LARGE_EXEC,
-		.kernpg_flag    = _KERNPG_TABLE_NOENC,
+		.kernpg_flag    = _KERNPG_TABLE,
 	};
+	unsigned long vaddr, pfn;
 	pgd_t *pgd;
 
 	pgd = alloc_pgt_page(NULL);
 	if (!pgd)
-		return -ENOMEM;
+		goto err;
 
 	for (int i = 0; i < nr_pfn_mapped; i++) {
 		unsigned long mstart, mend;
@@ -143,30 +116,45 @@ static int __init acpi_mp_setup_reset(u64 reset_vector)
 		mend   = pfn_mapped[i].end << PAGE_SHIFT;
 		if (kernel_ident_mapping_init(&info, pgd, mstart, mend)) {
 			kernel_ident_mapping_free(&info, pgd);
-			return -ENOMEM;
+			goto err;
 		}
 	}
 
 	if (kernel_ident_mapping_init(&info, pgd,
-				      PAGE_ALIGN_DOWN(reset_vector),
-				      PAGE_ALIGN(reset_vector + 1))) {
+				      PAGE_ALIGN_DOWN(acpi_mp_reset_vector_paddr),
+				      PAGE_ALIGN(acpi_mp_reset_vector_paddr + 1))) {
 		kernel_ident_mapping_free(&info, pgd);
-		return -ENOMEM;
+		goto err;
 	}
 
-	if (init_transition_pgtable(pgd)) {
+	/*
+	 * Make sure asm_acpi_mp_play_dead() is present in the identity mapping
+	 * at the same place as in the kernel page tables.
+	 *
+	 * asm_acpi_mp_play_dead() switches to the identity mapping and the
+	 * function has be present at the same spot in the virtual address space
+	 * before and after switching page tables.
+	 */
+	vaddr = (unsigned long)asm_acpi_mp_play_dead;
+	pfn = __pa(vaddr) >> PAGE_SHIFT;
+	if (kernel_map_pages_in_pgd(pgd, pfn, vaddr, 1, _KERNPG_TABLE)) {
 		kernel_ident_mapping_free(&info, pgd);
-		return -ENOMEM;
+		goto err;
 	}
 
 	smp_ops.play_dead = acpi_mp_play_dead;
 	smp_ops.stop_this_cpu = acpi_mp_stop_this_cpu;
 	smp_ops.cpu_die = acpi_mp_cpu_die;
 
-	acpi_mp_reset_vector_paddr = reset_vector;
 	acpi_mp_pgd = __pa(pgd);
 
 	return 0;
+err:
+	pr_warn("Failed to setup MADT reset vector\n");
+	mp_wake = (struct acpi_madt_multiproc_wakeup *)header;
+	acpi_mp_disable_offlining(mp_wake);
+	return -ENOMEM;
+
 }
 
 static int acpi_wakeup_cpu(u32 apicid, unsigned long start_ip)
@@ -226,28 +214,6 @@ static int acpi_wakeup_cpu(u32 apicid, unsigned long start_ip)
 	return 0;
 }
 
-static void acpi_mp_disable_offlining(struct acpi_madt_multiproc_wakeup *mp_wake)
-{
-	cpu_hotplug_disable_offlining();
-
-	/*
-	 * ACPI MADT doesn't allow to offline a CPU after it was onlined. This
-	 * limits kexec: the second kernel won't be able to use more than one CPU.
-	 *
-	 * To prevent a kexec kernel from onlining secondary CPUs invalidate the
-	 * mailbox address in the ACPI MADT wakeup structure which prevents a
-	 * kexec kernel to use it.
-	 *
-	 * This is safe as the booting kernel has the mailbox address cached
-	 * already and acpi_wakeup_cpu() uses the cached value to bring up the
-	 * secondary CPUs.
-	 *
-	 * Note: This is a Linux specific convention and not covered by the
-	 *       ACPI specification.
-	 */
-	mp_wake->mailbox_address = 0;
-}
-
 int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
 			      const unsigned long end)
 {
@@ -274,10 +240,7 @@ int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
 
 	if (mp_wake->version >= ACPI_MADT_MP_WAKEUP_VERSION_V1 &&
 	    mp_wake->header.length >= ACPI_MADT_MP_WAKEUP_SIZE_V1) {
-		if (acpi_mp_setup_reset(mp_wake->reset_vector)) {
-			pr_warn("Failed to setup MADT reset vector\n");
-			acpi_mp_disable_offlining(mp_wake);
-		}
+		acpi_mp_reset_vector_paddr = mp_wake->reset_vector;
 	} else {
 		/*
 		 * CPU offlining requires version 1 of the ACPI MADT wakeup
@@ -290,3 +253,13 @@ int __init acpi_parse_mp_wake(union acpi_subtable_headers *header,
 
 	return 0;
 }
+
+static int __init acpi_mp_offline_init(void)
+{
+	if (!acpi_mp_reset_vector_paddr)
+		return 0;
+
+	return acpi_table_parse_madt(ACPI_MADT_TYPE_MULTIPROC_WAKEUP,
+				     acpi_mp_setup_reset, 1);
+}
+early_initcall(acpi_mp_offline_init);
diff --git a/arch/x86/mm/ident_map.c b/arch/x86/mm/ident_map.c
index 3996af7b4abf..c45127265f2f 100644
--- a/arch/x86/mm/ident_map.c
+++ b/arch/x86/mm/ident_map.c
@@ -60,7 +60,7 @@ static void free_p4d(struct x86_mapping_info *info, pgd_t *pgd)
 	}
 
 	if (pgtable_l5_enabled())
-		info->free_pgt_page(pgd, info->context);
+		info->free_pgt_page(p4d, info->context);
 }
 
 void kernel_ident_mapping_free(struct x86_mapping_info *info, pgd_t *pgd)
diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
index 443a97e515c0..72715674f492 100644
--- a/arch/x86/mm/pat/set_memory.c
+++ b/arch/x86/mm/pat/set_memory.c
@@ -69,7 +69,7 @@ static const int cpa_warn_level = CPA_PROTECT;
  * entries change the page attribute in parallel to some other cpu
  * splitting a large page entry along with changing the attribute.
  */
-static DEFINE_SPINLOCK(cpa_lock);
+static DEFINE_MUTEX(cpa_lock);
 
 #define CPA_FLUSHTLB 1
 #define CPA_ARRAY 2
@@ -1186,10 +1186,10 @@ static int split_large_page(struct cpa_data *cpa, pte_t *kpte,
 	struct page *base;
 
 	if (!debug_pagealloc_enabled())
-		spin_unlock(&cpa_lock);
+		mutex_unlock(&cpa_lock);
 	base = alloc_pages(GFP_KERNEL, 0);
 	if (!debug_pagealloc_enabled())
-		spin_lock(&cpa_lock);
+		mutex_lock(&cpa_lock);
 	if (!base)
 		return -ENOMEM;
 
@@ -1804,10 +1804,10 @@ static int __change_page_attr_set_clr(struct cpa_data *cpa, int primary)
 			cpa->numpages = 1;
 
 		if (!debug_pagealloc_enabled())
-			spin_lock(&cpa_lock);
+			mutex_lock(&cpa_lock);
 		ret = __change_page_attr(cpa, primary);
 		if (!debug_pagealloc_enabled())
-			spin_unlock(&cpa_lock);
+			mutex_unlock(&cpa_lock);
 		if (ret)
 			goto out;
 
@@ -2516,7 +2516,9 @@ int __init kernel_map_pages_in_pgd(pgd_t *pgd, u64 pfn, unsigned long address,
 	cpa.mask_set = __pgprot(_PAGE_PRESENT | page_flags);
 
 	retval = __change_page_attr_set_clr(&cpa, 1);
+	preempt_disable();
 	__flush_tlb_all();
+	preempt_enable();
 
 out:
 	return retval;
@@ -2551,7 +2553,9 @@ int __init kernel_unmap_pages_in_pgd(pgd_t *pgd, unsigned long address,
 	WARN_ONCE(num_online_cpus() > 1, "Don't call after initializing SMP");
 
 	retval = __change_page_attr_set_clr(&cpa, 1);
+	preempt_disable();
 	__flush_tlb_all();
+	preempt_enable();
 
 	return retval;
 }

---

## [100] Borislav Petkov — 2024-06-10
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Fri, Jun 07, 2024 at 06:14:28PM +0300, Kirill A. Shutemov wrote:
>   I was able to address this issue by switching cpa_lock to a mutex.
>   However, this solution will only work if the callers for set_memory

Dunno, I'd be nervous about this. Althouth from looking at

   ad5ca55f6bdb ("x86, cpa: srlz cpa(), global flush tlb after splitting big page and before doing cpa")

I don't see how "So that we don't allow any other cpu" can't be done
with a mutex. Perhaps the set_memory* interfaces should be usable in as
many contexts as possible.

Have you run this with lockdep enabled?

> - The function __flush_tlb_all() in kernel_(un)map_pages_in_pgd() must be
>   called with preemption disabled. Once again, I am unsure why this has

It could be because EFI does all that setup on the BSP only before the
others have arrived but I don't remember anymore... It is more than
a decade ago when I did this...

Thx.

---

## [101] Kirill A. Shutemov — 2024-06-10
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Mon, Jun 10, 2024 at 03:40:20PM +0200, Borislav Petkov wrote:
> On Fri, Jun 07, 2024 at 06:14:28PM +0300, Kirill A. Shutemov wrote:
> >   I was able to address this issue by switching cpa_lock to a mutex.

Yes, it booted to the shell just fine. However, that doesn't prove
anything. The set_memory_* function has many obscured cases.

> > - The function __flush_tlb_all() in kernel_(un)map_pages_in_pgd() must be
> >   called with preemption disabled. Once again, I am unsure why this has

Are you okay with this? Disabling preemption looks strange, but I don't
see a better option.

---

## [102] Kirill A. Shutemov — 2024-06-11
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Mon, Jun 10, 2024 at 05:01:55PM +0300, Kirill A. Shutemov wrote:
> On Mon, Jun 10, 2024 at 03:40:20PM +0200, Borislav Petkov wrote:
> > On Fri, Jun 07, 2024 at 06:14:28PM +0300, Kirill A. Shutemov wrote:

Borislav, given this code deduplication effort is not trivial, maybe we
can do it as a separate patchset on top of this one?

I also wounder if it makes sense to combine ident_map.c and set_memory.c.
There's some overlap between the two.

---

## [103] H. Peter Anvin — 2024-06-11
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On 6/4/24 08:21, Kirill A. Shutemov wrote:
> 
>  From b45fe48092abad2612c2bafbb199e4de80c99545 Mon Sep 17 00:00:00 2001

If this is the case, I don't really see a reason to clear MCE per se as 
I'm guessing a machine check here will be fatal anyway? It just changes 
the method of death.

Also, is there a reason to save %cr4, run code, and *then* clear the 
relevant bits? Wouldn't it be better to sanitize %cr4 as soon as possible?

	-hpa

---

## [104] Borislav Petkov — 2024-06-11
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Tue, Jun 11, 2024 at 06:47:05PM +0300, Kirill A. Shutemov wrote:
> Borislav, given this code deduplication effort is not trivial, maybe we
> can do it as a separate patchset on top of this one?

Sure, as long as it gets done and doesn't get delayed indefinitely by
new and more important features enablement.

Usually, we do unifications and cleanups first - then new features but
this kexec pile has been long in the making already...

> I also wounder if it makes sense to combine ident_map.c and
> set_memory.c.  There's some overlap between the two.

Yeah, we have a bunch of different pagetable manipulating things, all
with their peculiarities and unifying them and having a good set of APIs
which everything else uses, is always a good thing.

And since we're talking cleanups, there's another thing I've been
looking at critically: CONFIG_X86_5LEVEL. Maybe it is time to get rid of
it and make the 5level stuff unconditional. And get rid of a bunch of
code since both vendors support 5level now...

Thx.

---

## [105] Kirill A. Shutemov — 2024-06-12
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On Tue, Jun 11, 2024 at 11:26:17AM -0700, H. Peter Anvin wrote:
> On 6/4/24 08:21, Kirill A. Shutemov wrote:
> > 

Andrew had a strong opinion on method of death here.

https://lore.kernel.org/all/1144340e-dd95-ee3b-dabb-579f9a65b3c7@citrix.com

> Also, is there a reason to save %cr4, run code, and *then* clear the
> relevant bits? Wouldn't it be better to sanitize %cr4 as soon as possible?

You mean set new CR4 directly in relocate_kernel() before switching CR3?
I guess it is possible.

But I can say I see huge benefit of changing it. Such change would have
own risks.

---

## [106] Kirill A. Shutemov — 2024-06-12
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Tue, Jun 11, 2024 at 09:46:53PM +0200, Borislav Petkov wrote:
> On Tue, Jun 11, 2024 at 06:47:05PM +0300, Kirill A. Shutemov wrote:
> > Borislav, given this code deduplication effort is not trivial, maybe we

I will try to deliver it in timely manner.

> Usually, we do unifications and cleanups first - then new features but
> this kexec pile has been long in the making already...

Will give it a try.

> And since we're talking cleanups, there's another thing I've been
> looking at critically: CONFIG_X86_5LEVEL. Maybe it is time to get rid of

Can do.

---

## [107] Borislav Petkov — 2024-06-12
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Wed, Jun 12, 2024 at 12:24:30PM +0300, Kirill A. Shutemov wrote:
> I will try to deliver it in timely manner.

:-P

> > Yeah, we have a bunch of different pagetable manipulating things, all
> > with their peculiarities and unifying them and having a good set of APIs

Much appreciated, thanks!

---

## [108] Nikolay Borisov — 2024-06-12
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On 3.06.24 г. 17:43 ч., H. Peter Anvin wrote:
> On 5/29/24 03:47, Nikolay Borisov wrote:
>>>


The preceding move to CR4 is itself a serializing instruction, no?

> 
>      -hpa

---

## [109] Andrew Cooper — 2024-06-13
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less
 confusion*

On 12/06/2024 10:22 am, Kirill A. Shutemov wrote:
> On Tue, Jun 11, 2024 at 11:26:17AM -0700, H. Peter Anvin wrote:
>> On 6/4/24 08:21, Kirill A. Shutemov wrote:

Not sure if I intended it to come across that strongly, but given a
choice, the !CR4.MCE death is cleaner because at least you're not
interpreting garbage and trying to use it as a valid IDT.

~Andrew

---

## [110] H. Peter Anvin — 2024-06-12
*Subject: Re: [PATCHv11 05/19] x86/relocate_kernel: Use named labels for less confusion*

On June 12, 2024 4:06:07 PM PDT, Andrew Cooper <andrew.cooper3@citrix.com> wrote:
>On 12/06/2024 10:22 am, Kirill A. Shutemov wrote:
>> On Tue, Jun 11, 2024 at 11:26:17AM -0700, H. Peter Anvin wrote:

Zorch the IDT if it isn't valid?

---

## [111] Kirill A. Shutemov — 2024-06-13
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Wed, Jun 12, 2024 at 11:29:43AM +0200, Borislav Petkov wrote:
> > > And since we're talking cleanups, there's another thing I've been
> > > looking at critically: CONFIG_X86_5LEVEL. Maybe it is time to get rid of

It is easy enough to do. See the patch below.

But I am not sure if I can justify it properly. If someone doesn't really
need 5-level paging, disabling it at compile-time would save ~34K of
kernel code with the configuration.

Is it worth saving ~100 lines of code?

 Documentation/arch/x86/cpuinfo.rst              |  8 +++-----
 Documentation/arch/x86/x86_64/5level-paging.rst |  9 ---------
 arch/x86/Kconfig                                | 24 +-----------------------
 arch/x86/boot/compressed/pgtable_64.c           | 10 +++-------
 arch/x86/boot/header.S                          |  4 ----
 arch/x86/include/asm/disabled-features.h        |  9 +--------
 arch/x86/include/asm/page_64.h                  |  2 --
 arch/x86/include/asm/page_64_types.h            |  7 -------
 arch/x86/include/asm/pgtable_64_types.h         | 18 ------------------
 arch/x86/kernel/alternative.c                   |  2 +-
 arch/x86/kernel/head64.c                        |  5 -----
 arch/x86/kernel/head_64.S                       |  2 --
 arch/x86/mm/init.c                              |  4 ----
 arch/x86/mm/pgtable.c                           |  2 --
 drivers/firmware/efi/libstub/x86-5lvl.c         |  2 +-
 tools/arch/x86/include/asm/disabled-features.h  |  9 +--------
 16 files changed, 11 insertions(+), 106 deletions(-)

diff --git a/Documentation/arch/x86/cpuinfo.rst b/Documentation/arch/x86/cpuinfo.rst
index 8895784d4784..0ea70924c89e 100644
--- a/Documentation/arch/x86/cpuinfo.rst
+++ b/Documentation/arch/x86/cpuinfo.rst
@@ -171,10 +171,10 @@ For example, when an old kernel is running on new hardware.
 
 c: The kernel disabled support for it at compile-time.
 ------------------------------------------------------
-For example, if 5-level-paging is not enabled when building (i.e.,
-CONFIG_X86_5LEVEL is not selected) the flag "la57" will not show up [#f1]_.
+For example, if Linear Address Masking (LAM) is not enabled when building (i.e.,
+CONFIG_ADDRESS_MASKING is not selected) the flag "lam" will not show up.
 Even though the feature will still be detected via CPUID, the kernel disables
-it by clearing via setup_clear_cpu_cap(X86_FEATURE_LA57).
+it by clearing via setup_clear_cpu_cap(X86_FEATURE_LAM).
 
 d: The feature is disabled at boot-time.
 ----------------------------------------
@@ -197,5 +197,3 @@ missing at runtime. For example, AVX flags will not show up if XSAVE feature
 is disabled since they depend on XSAVE feature. Another example would be broken
 CPUs and them missing microcode patches. Due to that, the kernel decides not to
 enable a feature.
-
-.. [#f1] 5-level paging uses linear address of 57 bits.
diff --git a/Documentation/arch/x86/x86_64/5level-paging.rst b/Documentation/arch/x86/x86_64/5level-paging.rst
index 71f882f4a173..ad7ddc13f79d 100644
--- a/Documentation/arch/x86/x86_64/5level-paging.rst
+++ b/Documentation/arch/x86/x86_64/5level-paging.rst
@@ -22,15 +22,6 @@ QEMU 2.9 and later support 5-level paging.
 Virtual memory layout for 5-level paging is described in
 Documentation/arch/x86/x86_64/mm.rst
 
-
-Enabling 5-level paging
-=======================
-CONFIG_X86_5LEVEL=y enables the feature.
-
-Kernel with CONFIG_X86_5LEVEL=y still able to boot on 4-level hardware.
-In this case additional page table level -- p4d -- will be folded at
-runtime.
-
 User-space and large virtual address space
 ==========================================
 On x86, 5-level paging enables 56-bit userspace virtual address space.
diff --git a/arch/x86/Kconfig b/arch/x86/Kconfig
index e8837116704c..c62827c2ecea 100644
--- a/arch/x86/Kconfig
+++ b/arch/x86/Kconfig
@@ -408,8 +408,7 @@ config DYNAMIC_PHYSICAL_MASK
 
 config PGTABLE_LEVELS
 	int
-	default 5 if X86_5LEVEL
-	default 4 if X86_64
+	default 5 if X86_64
 	default 3 if X86_PAE
 	default 2
 
@@ -1491,27 +1490,6 @@ config X86_PAE
 	  has the cost of more pagetable lookup overhead, and also
 	  consumes more pagetable space per process.
 
-config X86_5LEVEL
-	bool "Enable 5-level page tables support"
-	default y
-	select DYNAMIC_MEMORY_LAYOUT
-	select SPARSEMEM_VMEMMAP
-	depends on X86_64
-	help
-	  5-level paging enables access to larger address space:
-	  up to 128 PiB of virtual address space and 4 PiB of
-	  physical address space.
-
-	  It will be supported by future Intel CPUs.
-
-	  A kernel with the option enabled can be booted on machines that
-	  support 4- or 5-level paging.
-
-	  See Documentation/arch/x86/x86_64/5level-paging.rst for more
-	  information.
-
-	  Say N if unsure.
-
 config X86_DIRECT_GBPAGES
 	def_bool y
 	depends on X86_64
diff --git a/arch/x86/boot/compressed/pgtable_64.c b/arch/x86/boot/compressed/pgtable_64.c
index c882e1f67af0..f9b77b66c792 100644
--- a/arch/x86/boot/compressed/pgtable_64.c
+++ b/arch/x86/boot/compressed/pgtable_64.c
@@ -10,12 +10,10 @@
 #define BIOS_START_MIN		0x20000U	/* 128K, less than this is insane */
 #define BIOS_START_MAX		0x9f000U	/* 640K, absolute maximum */
 
-#ifdef CONFIG_X86_5LEVEL
 /* __pgtable_l5_enabled needs to be in .data to avoid being cleared along with .bss */
 unsigned int __section(".data") __pgtable_l5_enabled;
 unsigned int __section(".data") pgdir_shift = 39;
 unsigned int __section(".data") ptrs_per_p4d = 1;
-#endif
 
 /* Buffer to preserve trampoline memory */
 static char trampoline_save[TRAMPOLINE_32BIT_SIZE];
@@ -113,7 +111,6 @@ asmlinkage void configure_5level_paging(struct boot_params *bp, void *pgtable)
 	 * Check if LA57 is desired and supported.
 	 *
 	 * There are several parts to the check:
-	 *   - if the kernel supports 5-level paging: CONFIG_X86_5LEVEL=y
 	 *   - if user asked to disable 5-level paging: no5lvl in cmdline
 	 *   - if the machine supports 5-level paging:
 	 *     + CPUID leaf 7 is supported
@@ -121,10 +118,9 @@ asmlinkage void configure_5level_paging(struct boot_params *bp, void *pgtable)
 	 *
 	 * That's substitute for boot_cpu_has() in early boot code.
 	 */
-	if (IS_ENABLED(CONFIG_X86_5LEVEL) &&
-			!cmdline_find_option_bool("no5lvl") &&
-			native_cpuid_eax(0) >= 7 &&
-			(native_cpuid_ecx(7) & (1 << (X86_FEATURE_LA57 & 31)))) {
+	if (!cmdline_find_option_bool("no5lvl") &&
+	    native_cpuid_eax(0) >= 7 &&
+	    (native_cpuid_ecx(7) & (1 << (X86_FEATURE_LA57 & 31)))) {
 		l5_required = true;
 
 		/* Initialize variables for 5-level paging */
diff --git a/arch/x86/boot/header.S b/arch/x86/boot/header.S
index b5c79f43359b..32361cef909e 100644
--- a/arch/x86/boot/header.S
+++ b/arch/x86/boot/header.S
@@ -361,12 +361,8 @@ xloadflags:
 #endif
 
 #ifdef CONFIG_X86_64
-#ifdef CONFIG_X86_5LEVEL
 #define XLF56 (XLF_5LEVEL|XLF_5LEVEL_ENABLED)
 #else
-#define XLF56 XLF_5LEVEL
-#endif
-#else
 #define XLF56 0
 #endif
 
diff --git a/arch/x86/include/asm/disabled-features.h b/arch/x86/include/asm/disabled-features.h
index c492bdc97b05..19cf1678fcaa 100644
--- a/arch/x86/include/asm/disabled-features.h
+++ b/arch/x86/include/asm/disabled-features.h
@@ -38,12 +38,6 @@
 # define DISABLE_OSPKE		(1<<(X86_FEATURE_OSPKE & 31))
 #endif /* CONFIG_X86_INTEL_MEMORY_PROTECTION_KEYS */
 
-#ifdef CONFIG_X86_5LEVEL
-# define DISABLE_LA57	0
-#else
-# define DISABLE_LA57	(1<<(X86_FEATURE_LA57 & 31))
-#endif
-
 #ifdef CONFIG_MITIGATION_PAGE_TABLE_ISOLATION
 # define DISABLE_PTI		0
 #else
@@ -149,8 +143,7 @@
 #define DISABLED_MASK13	0
 #define DISABLED_MASK14	0
 #define DISABLED_MASK15	0
-#define DISABLED_MASK16	(DISABLE_PKU|DISABLE_OSPKE|DISABLE_LA57|DISABLE_UMIP| \
-			 DISABLE_ENQCMD)
+#define DISABLED_MASK16	(DISABLE_PKU|DISABLE_OSPKE|DISABLE_UMIP|DISABLE_ENQCMD)
 #define DISABLED_MASK17	0
 #define DISABLED_MASK18	(DISABLE_IBT)
 #define DISABLED_MASK19	(DISABLE_SEV_SNP)
diff --git a/arch/x86/include/asm/page_64.h b/arch/x86/include/asm/page_64.h
index cc6b8e087192..3b8cb6a8b122 100644
--- a/arch/x86/include/asm/page_64.h
+++ b/arch/x86/include/asm/page_64.h
@@ -60,7 +60,6 @@ static inline void clear_page(void *page)
 
 void copy_page(void *to, void *from);
 
-#ifdef CONFIG_X86_5LEVEL
 /*
  * User space process size.  This is the first address outside the user range.
  * There are a few constraints that determine this:
@@ -91,7 +90,6 @@ static __always_inline unsigned long task_size_max(void)
 
 	return ret;
 }
-#endif	/* CONFIG_X86_5LEVEL */
 
 #endif	/* !__ASSEMBLY__ */
 
diff --git a/arch/x86/include/asm/page_64_types.h b/arch/x86/include/asm/page_64_types.h
index 06ef25411d62..714e88a72c9f 100644
--- a/arch/x86/include/asm/page_64_types.h
+++ b/arch/x86/include/asm/page_64_types.h
@@ -52,14 +52,7 @@
 /* See Documentation/arch/x86/x86_64/mm.rst for a description of the memory map. */
 
 #define __PHYSICAL_MASK_SHIFT	52
-
-#ifdef CONFIG_X86_5LEVEL
 #define __VIRTUAL_MASK_SHIFT	(pgtable_l5_enabled() ? 56 : 47)
-/* See task_size_max() in <asm/page_64.h> */
-#else
-#define __VIRTUAL_MASK_SHIFT	47
-#define task_size_max()		((_AC(1,UL) << __VIRTUAL_MASK_SHIFT) - PAGE_SIZE)
-#endif
 
 #define TASK_SIZE_MAX		task_size_max()
 #define DEFAULT_MAP_WINDOW	((1UL << 47) - PAGE_SIZE)
diff --git a/arch/x86/include/asm/pgtable_64_types.h b/arch/x86/include/asm/pgtable_64_types.h
index 9053dfe9fa03..576aea58b0c0 100644
--- a/arch/x86/include/asm/pgtable_64_types.h
+++ b/arch/x86/include/asm/pgtable_64_types.h
@@ -23,7 +23,6 @@ typedef struct { pmdval_t pmd; } pmd_t;
 
 extern unsigned int __pgtable_l5_enabled;
 
-#ifdef CONFIG_X86_5LEVEL
 #ifdef USE_EARLY_PGTABLE_L5
 /*
  * cpu_feature_enabled() is not available in early boot code.
@@ -37,10 +36,6 @@ static inline bool pgtable_l5_enabled(void)
 #define pgtable_l5_enabled() cpu_feature_enabled(X86_FEATURE_LA57)
 #endif /* USE_EARLY_PGTABLE_L5 */
 
-#else
-#define pgtable_l5_enabled() 0
-#endif /* CONFIG_X86_5LEVEL */
-
 extern unsigned int pgdir_shift;
 extern unsigned int ptrs_per_p4d;
 
@@ -48,8 +43,6 @@ extern unsigned int ptrs_per_p4d;
 
 #define SHARED_KERNEL_PMD	0
 
-#ifdef CONFIG_X86_5LEVEL
-
 /*
  * PGDIR_SHIFT determines what a top-level page table entry can map
  */
@@ -67,17 +60,6 @@ extern unsigned int ptrs_per_p4d;
 
 #define MAX_POSSIBLE_PHYSMEM_BITS	52
 
-#else /* CONFIG_X86_5LEVEL */
-
-/*
- * PGDIR_SHIFT determines what a top-level page table entry can map
- */
-#define PGDIR_SHIFT		39
-#define PTRS_PER_PGD		512
-#define MAX_PTRS_PER_P4D	1
-
-#endif /* CONFIG_X86_5LEVEL */
-
 /*
  * 3rd level page
  */
diff --git a/arch/x86/kernel/alternative.c b/arch/x86/kernel/alternative.c
index 37596a417094..f1c519abb925 100644
--- a/arch/x86/kernel/alternative.c
+++ b/arch/x86/kernel/alternative.c
@@ -457,7 +457,7 @@ void __init_or_module noinline apply_alternatives(struct alt_instr *start,
 	DPRINTK(ALT, "alt table %px, -> %px", start, end);
 
 	/*
-	 * In the case CONFIG_X86_5LEVEL=y, KASAN_SHADOW_START is defined using
+	 * KASAN_SHADOW_START is defined using
 	 * cpu_feature_enabled(X86_FEATURE_LA57) and is therefore patched here.
 	 * During the process, KASAN becomes confused seeing partial LA57
 	 * conversion and triggers a false-positive out-of-bound report.
diff --git a/arch/x86/kernel/head64.c b/arch/x86/kernel/head64.c
index a817ed0724d1..df19bdea1c86 100644
--- a/arch/x86/kernel/head64.c
+++ b/arch/x86/kernel/head64.c
@@ -52,13 +52,11 @@ extern pmd_t early_dynamic_pgts[EARLY_DYNAMIC_PAGE_TABLES][PTRS_PER_PMD];
 static unsigned int __initdata next_early_pgt;
 pmdval_t early_pmd_flags = __PAGE_KERNEL_LARGE & ~(_PAGE_GLOBAL | _PAGE_NX);
 
-#ifdef CONFIG_X86_5LEVEL
 unsigned int __pgtable_l5_enabled __ro_after_init;
 unsigned int pgdir_shift __ro_after_init = 39;
 EXPORT_SYMBOL(pgdir_shift);
 unsigned int ptrs_per_p4d __ro_after_init = 1;
 EXPORT_SYMBOL(ptrs_per_p4d);
-#endif
 
 #ifdef CONFIG_DYNAMIC_MEMORY_LAYOUT
 unsigned long page_offset_base __ro_after_init = __PAGE_OFFSET_BASE_L4;
@@ -71,9 +69,6 @@ EXPORT_SYMBOL(vmemmap_base);
 
 static inline bool check_la57_support(void)
 {
-	if (!IS_ENABLED(CONFIG_X86_5LEVEL))
-		return false;
-
 	/*
 	 * 5-level paging is detected and enabled at kernel decompression
 	 * stage. Only check if it has been enabled there.
diff --git a/arch/x86/kernel/head_64.S b/arch/x86/kernel/head_64.S
index 330922b328bf..4b2b2138c163 100644
--- a/arch/x86/kernel/head_64.S
+++ b/arch/x86/kernel/head_64.S
@@ -659,12 +659,10 @@ SYM_DATA_START_PTI_ALIGNED(init_top_pgt)
 SYM_DATA_END(init_top_pgt)
 #endif
 
-#ifdef CONFIG_X86_5LEVEL
 SYM_DATA_START_PAGE_ALIGNED(level4_kernel_pgt)
 	.fill	511,8,0
 	.quad	level3_kernel_pgt - __START_KERNEL_map + _PAGE_TABLE_NOENC
 SYM_DATA_END(level4_kernel_pgt)
-#endif
 
 SYM_DATA_START_PAGE_ALIGNED(level3_kernel_pgt)
 	.fill	L3_START_KERNEL,8,0
diff --git a/arch/x86/mm/init.c b/arch/x86/mm/init.c
index eb503f53c319..5a980a452f4c 100644
--- a/arch/x86/mm/init.c
+++ b/arch/x86/mm/init.c
@@ -173,11 +173,7 @@ __ref void *alloc_low_pages(unsigned int num)
  * randomization is enabled.
  */
 
-#ifndef CONFIG_X86_5LEVEL
-#define INIT_PGD_PAGE_TABLES    3
-#else
 #define INIT_PGD_PAGE_TABLES    4
-#endif
 
 #ifndef CONFIG_RANDOMIZE_MEMORY
 #define INIT_PGD_PAGE_COUNT      (2 * INIT_PGD_PAGE_TABLES)
diff --git a/arch/x86/mm/pgtable.c b/arch/x86/mm/pgtable.c
index 93e54ba91fbf..982775ef8b34 100644
--- a/arch/x86/mm/pgtable.c
+++ b/arch/x86/mm/pgtable.c
@@ -691,7 +691,6 @@ void native_set_fixmap(unsigned /* enum fixed_addresses */ idx,
 }
 
 #ifdef CONFIG_HAVE_ARCH_HUGE_VMAP
-#ifdef CONFIG_X86_5LEVEL
 /**
  * p4d_set_huge - setup kernel P4D mapping
  *
@@ -710,7 +709,6 @@ int p4d_set_huge(p4d_t *p4d, phys_addr_t addr, pgprot_t prot)
 void p4d_clear_huge(p4d_t *p4d)
 {
 }
-#endif
 
 /**
  * pud_set_huge - setup kernel PUD mapping
diff --git a/drivers/firmware/efi/libstub/x86-5lvl.c b/drivers/firmware/efi/libstub/x86-5lvl.c
index 77359e802181..f1c5fb45d5f7 100644
--- a/drivers/firmware/efi/libstub/x86-5lvl.c
+++ b/drivers/firmware/efi/libstub/x86-5lvl.c
@@ -62,7 +62,7 @@ efi_status_t efi_setup_5level_paging(void)
 
 void efi_5level_switch(void)
 {
-	bool want_la57 = IS_ENABLED(CONFIG_X86_5LEVEL) && !efi_no5lvl;
+	bool want_la57 = !efi_no5lvl;
 	bool have_la57 = native_read_cr4() & X86_CR4_LA57;
 	bool need_toggle = want_la57 ^ have_la57;
 	u64 *pgt = (void *)la57_toggle + PAGE_SIZE;
diff --git a/tools/arch/x86/include/asm/disabled-features.h b/tools/arch/x86/include/asm/disabled-features.h
index c492bdc97b05..19cf1678fcaa 100644
--- a/tools/arch/x86/include/asm/disabled-features.h
+++ b/tools/arch/x86/include/asm/disabled-features.h
@@ -38,12 +38,6 @@
 # define DISABLE_OSPKE		(1<<(X86_FEATURE_OSPKE & 31))
 #endif /* CONFIG_X86_INTEL_MEMORY_PROTECTION_KEYS */
 
-#ifdef CONFIG_X86_5LEVEL
-# define DISABLE_LA57	0
-#else
-# define DISABLE_LA57	(1<<(X86_FEATURE_LA57 & 31))
-#endif
-
 #ifdef CONFIG_MITIGATION_PAGE_TABLE_ISOLATION
 # define DISABLE_PTI		0
 #else
@@ -149,8 +143,7 @@
 #define DISABLED_MASK13	0
 #define DISABLED_MASK14	0
 #define DISABLED_MASK15	0
-#define DISABLED_MASK16	(DISABLE_PKU|DISABLE_OSPKE|DISABLE_LA57|DISABLE_UMIP| \
-			 DISABLE_ENQCMD)
+#define DISABLED_MASK16	(DISABLE_PKU|DISABLE_OSPKE|DISABLE_UMIP|DISABLE_ENQCMD)
 #define DISABLED_MASK17	0
 #define DISABLED_MASK18	(DISABLE_IBT)
 #define DISABLED_MASK19	(DISABLE_SEV_SNP)

---

## [112] Borislav Petkov — 2024-06-13
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Thu, Jun 13, 2024 at 04:41:00PM +0300, Kirill A. Shutemov wrote:
> It is easy enough to do. See the patch below.

Thanks, will have a look.

> But I am not sure if I can justify it properly. If someone doesn't really
> need 5-level paging, disabling it at compile-time would save ~34K of

Well, it goes both ways: is it worth saving ~34K kernel text and for that make
the code a lot less conditional, more readable, contain less ugly ifdeffery,
...?

---

## [113] Tom Lendacky — 2024-06-14
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for ACPI
 MADT wakeup method*

On 6/13/24 09:56, Borislav Petkov wrote:
> On Thu, Jun 13, 2024 at 04:41:00PM +0300, Kirill A. Shutemov wrote:
>> It is easy enough to do. See the patch below.

Won't getting rid of the config option cause 5-level to be used by default 
on all platforms that support it? The no5lvl command line option would 
have to be used to get 4-level paging at that point.

Thanks,
Tom

> ...?
>

---

## [114] Kirill A. Shutemov — 2024-06-18
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Fri, Jun 14, 2024 at 09:06:30AM -0500, Tom Lendacky wrote:
> On 6/13/24 09:56, Borislav Petkov wrote:
> > On Thu, Jun 13, 2024 at 04:41:00PM +0300, Kirill A. Shutemov wrote:

Yes, there won't be compile-time option to disable 5-level paging.

Is it a problem?

We benchmarked it back when 5-level paging got introduced and were not able
to see a measurable difference between 4- and 5-level paging on the same
machine. There's some memory overhead on more page table, but it shouldn't
be a show stopper.

I would prefer to get 5-level paging enabled if the machine supports it.
"no5lvl" cmdline option can be useful for debug or if your workload is
somehow special.

---

## [115] Borislav Petkov — 2024-06-21
*Subject: Re: [PATCHv11 18/19] x86/acpi: Add support for CPU offlining for
 ACPI MADT wakeup method*

On Thu, Jun 13, 2024 at 04:41:00PM +0300, Kirill A. Shutemov wrote:
>  Documentation/arch/x86/cpuinfo.rst              |  8 +++-----
>  Documentation/arch/x86/x86_64/5level-paging.rst |  9 ---------

This causes

ld: vmlinux.o: in function `rip_rel_ptr':
/home/boris/kernel/5th/linux/./arch/x86/include/asm/asm.h:120:(.head.text+0xb96): undefined reference to `page_offset_base'
ld: /home/boris/kernel/5th/linux/./arch/x86/include/asm/asm.h:120:(.head.text+0xbaa): undefined reference to `vmalloc_base'
ld: /home/boris/kernel/5th/linux/./arch/x86/include/asm/asm.h:120:(.head.text+0xbb4): undefined reference to `vmemmap_base'
make[2]: *** [scripts/Makefile.vmlinux:34: vmlinux] Error 1
make[1]: *** [/mnt/kernel/kernel/5th/linux/Makefile:1171: vmlinux] Error 2
make[1]: *** Waiting for unfinished jobs....
make: *** [Makefile:240: __sub-make] Error 2

with my .config. Attached.

Also:

diff --git a/arch/x86/boot/compressed/pgtable_64.c b/arch/x86/boot/compressed/pgtable_64.c
index f9b77b66c792..25559a788aad 100644
--- a/arch/x86/boot/compressed/pgtable_64.c
+++ b/arch/x86/boot/compressed/pgtable_64.c
@@ -115,12 +115,10 @@ asmlinkage void configure_5level_paging(struct boot_params *bp, void *pgtable)
 	 *   - if the machine supports 5-level paging:
 	 *     + CPUID leaf 7 is supported
 	 *     + the leaf has the feature bit set
-	 *
-	 * That's substitute for boot_cpu_has() in early boot code.
 	 */
 	if (!cmdline_find_option_bool("no5lvl") &&
 	    native_cpuid_eax(0) >= 7 &&
-	    (native_cpuid_ecx(7) & (1 << (X86_FEATURE_LA57 & 31)))) {
+	    (native_cpuid_ecx(7) & BIT_UL(16))) {
 		l5_required = true;
 
 		/* Initialize variables for 5-level paging */

We can simply check CPUID and be done with it, that early.

Other than that, I like it. Let's do it.

Less ifdeffery, less conditionals. A win-win thing.

Thx.

---
