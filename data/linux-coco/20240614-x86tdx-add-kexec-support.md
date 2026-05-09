---
title: 'x86/tdx: Add kexec support'
date: 2024-06-14
last_reply: 2024-10-28
message_count: 57
participants: ['Kirill A. Shutemov', 'Ashish Kalra', 'Borislav Petkov', 'Tom Lendacky']
---

## [1] Kirill A. Shutemov — 2024-06-14

The patchset adds bits and pieces to get kexec (and crashkernel) work on
TDX guest.

The last patch implements CPU offlining according to the approved ACPI
spec change poposal[1]. It unlocks kexec with all CPUs visible in the target
kernel. It requires BIOS-side enabling. If it missing we fallback to booting
2nd kernel with single CPU.

Please review. I would be glad for any feedback.

[1] https://lore.kernel.org/all/13356251.uLZWGnKmhe@kreacher

v12:
  - Drop 'crash' argument from x86_guest::enc_kexec_begin();
  - Rework CR4 setting in identity_mapped();
  - Fix comments and commit message.
  - Add review tags;
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
 arch/x86/coco/tdx/tdx.c              | 121 ++++++++++-
 arch/x86/hyperv/ivm.c                |  22 +-
 arch/x86/include/asm/acpi.h          |   7 +
 arch/x86/include/asm/init.h          |   3 +
 arch/x86/include/asm/pgtable.h       |   5 +
 arch/x86/include/asm/pgtable_types.h |   1 +
 arch/x86/include/asm/set_memory.h    |   3 +
 arch/x86/include/asm/smp.h           |   1 +
 arch/x86/include/asm/x86_init.h      |  14 +-
 arch/x86/kernel/acpi/Makefile        |   1 +
 arch/x86/kernel/acpi/boot.c          |  86 +-------
 arch/x86/kernel/acpi/madt_playdead.S |  28 +++
 arch/x86/kernel/acpi/madt_wakeup.c   | 292 +++++++++++++++++++++++++++
 arch/x86/kernel/crash.c              |  12 ++
 arch/x86/kernel/e820.c               |   9 +-
 arch/x86/kernel/process.c            |   7 +
 arch/x86/kernel/reboot.c             |  18 ++
 arch/x86/kernel/relocate_kernel_64.S |  24 ++-
 arch/x86/kernel/x86_init.c           |   8 +-
 arch/x86/mm/ident_map.c              |  73 +++++++
 arch/x86/mm/init_64.c                |  16 +-
 arch/x86/mm/mem_encrypt_amd.c        |   8 +-
 arch/x86/mm/pat/set_memory.c         |  75 +++++--
 drivers/acpi/tables.c                |  14 ++
 include/acpi/actbl2.h                |  19 +-
 include/linux/cc_platform.h          |  10 -
 include/linux/cpuhplock.h            |   2 +
 kernel/cpu.c                         |  12 +-
 30 files changed, 733 insertions(+), 166 deletions(-)
 create mode 100644 arch/x86/kernel/acpi/madt_playdead.S
 create mode 100644 arch/x86/kernel/acpi/madt_wakeup.c

---

## [2] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 01/19] x86/acpi: Extract ACPI MADT wakeup code into a separate file*

In order to prepare for the expansion of support for the ACPI MADT
wakeup method, move the relevant code into a separate file.

Introduce a new configuration option to clearly indicate dependencies
without the use of ifdefs.

There have been no functional changes.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Acked-by: Borislav Petkov (AMD) <bp@alien8.de>
Acked-by: Kai Huang <kai.huang@intel.com>
Acked-by: Rafael J. Wysocki <rafael.j.wysocki@intel.com>
Reviewed-by: Baoquan He <bhe@redhat.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
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

## [3] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 02/19] x86/apic: Mark acpi_mp_wake_* variables as __ro_after_init*

acpi_mp_wake_mailbox_paddr and acpi_mp_wake_mailbox initialized once
during ACPI MADT init and never changed.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Acked-by: Rafael J. Wysocki <rafael.j.wysocki@intel.com>
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

## [4] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 03/19] cpu/hotplug: Add support for declaring CPU offlining not supported*

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
 include/linux/cpuhplock.h |  2 ++
 kernel/cpu.c              | 13 ++++++++++++-
 2 files changed, 14 insertions(+), 1 deletion(-)

diff --git a/include/linux/cpuhplock.h b/include/linux/cpuhplock.h
index 431560bbd045..f7aa20f62b87 100644
--- a/include/linux/cpuhplock.h
+++ b/include/linux/cpuhplock.h
@@ -21,6 +21,7 @@ void cpus_read_lock(void);
 void cpus_read_unlock(void);
 int  cpus_read_trylock(void);
 void lockdep_assert_cpus_held(void);
+void cpu_hotplug_disable_offlining(void);
 void cpu_hotplug_disable(void);
 void cpu_hotplug_enable(void);
 void clear_tasks_mm_cpumask(int cpu);
@@ -36,6 +37,7 @@ static inline void cpus_read_lock(void) { }
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

## [5] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 04/19] cpu/hotplug, x86/acpi: Disable CPU offlining for ACPI MADT wakeup*

ACPI MADT doesn't allow to offline CPU after it got woke up.

Currently CPU hotplug is prevented based on the confidential computing
attribute which is set for Intel TDX. But TDX is not the only possible
user of the wake up method. Any platform that uses ACPI MADT wakeup
method cannot offline CPU.

Disable CPU offlining on ACPI MADT wakeup enumeration.

The change has no visible effects for users: currently, TDX guest is the
only platform that uses the ACPI MADT wakeup method.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Acked-by: Rafael J. Wysocki <rafael.j.wysocki@intel.com>
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

## [6] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 05/19] x86/relocate_kernel: Use named labels for less confusion*

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
index 54e620021c7e..8b8922de3765 100644
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
 
 	/* Flush the TLB (needed?) */
@@ -162,9 +163,9 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
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
@@ -184,7 +185,7 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
 	 */
 
 	testq	%r11, %r11
-	jnz 1f
+	jnz .Lrelocate
 	xorl	%eax, %eax
 	xorl	%ebx, %ebx
 	xorl    %ecx, %ecx
@@ -205,7 +206,7 @@ SYM_CODE_START_LOCAL_NOALIGN(identity_mapped)
 	ret
 	int3
 
-1:
+.Lrelocate:
 	popq	%rdx
 	leaq	PAGE_SIZE(%r10), %rsp
 	ANNOTATE_RETPOLINE_SAFE

---

## [7] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 06/19] x86/kexec: Keep CR4.MCE set during kexec for TDX guest*

TDX guests run with MCA enabled (CR4.MCE=1b) from the very start. If
that bit is cleared during CR4 register reprogramming during boot or
kexec flows, a #VE exception will be raised which the guest kernel
cannot handle.

Therefore, make sure the CR4.MCE setting is preserved over kexec too and
avoid raising any #VEs.

The change doesn't affect non-TDX-guest environments.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
---
 arch/x86/kernel/relocate_kernel_64.S | 17 ++++++++++-------
 1 file changed, 10 insertions(+), 7 deletions(-)

diff --git a/arch/x86/kernel/relocate_kernel_64.S b/arch/x86/kernel/relocate_kernel_64.S
index 8b8922de3765..042c9a0334e9 100644
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
 
 	/* Flush the TLB (needed?) */
 	movq	%r9, %cr3

---

## [8] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 07/19] x86/mm: Make x86_platform.guest.enc_status_change_*() return errno*

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

## [9] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 08/19] x86/mm: Return correct level from lookup_address() if pte is none*

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

## [10] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 09/19] x86/tdx: Account shared memory*

The kernel will convert all shared memory back to private during kexec.
The direct mapping page tables will provide information on which memory
is shared.

It is extremely important to convert all shared memory. If a page is
missed, it will cause the second kernel to crash when it accesses it.

Keep track of the number of shared pages. This will allow for
cross-checking against the shared information in the direct mapping and
reporting if the shared bit is lost.

Memory conversion is slow and does not happen often. Global atomic is
not going to be a bottleneck.

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

## [11] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 10/19] x86/mm: Add callbacks to prepare encrypted memory for kexec*

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
 arch/x86/include/asm/x86_init.h | 10 ++++++++++
 arch/x86/kernel/crash.c         | 12 ++++++++++++
 arch/x86/kernel/reboot.c        | 12 ++++++++++++
 arch/x86/kernel/x86_init.c      |  4 ++++
 4 files changed, 38 insertions(+)

diff --git a/arch/x86/include/asm/x86_init.h b/arch/x86/include/asm/x86_init.h
index 28ac3cb9b987..213cf5379a5a 100644
--- a/arch/x86/include/asm/x86_init.h
+++ b/arch/x86/include/asm/x86_init.h
@@ -149,12 +149,22 @@ struct x86_init_acpi {
  * @enc_status_change_finish	Notify HV after the encryption status of a range is changed
  * @enc_tlb_flush_required	Returns true if a TLB flush is needed before changing page encryption status
  * @enc_cache_flush_required	Returns true if a cache flush is needed before changing page encryption status
+ * @enc_kexec_begin		Begin the two-step process of converting shared memory back
+ *				to private. It stops the new conversions from being started
+ *				and waits in-flight conversions to finish, if possible.
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
+	void (*enc_kexec_begin)(void);
+	void (*enc_kexec_finish)(void);
 };
 
 /**
diff --git a/arch/x86/kernel/crash.c b/arch/x86/kernel/crash.c
index f06501445cd9..340af8155658 100644
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
+	x86_platform.guest.enc_kexec_begin();
+	x86_platform.guest.enc_kexec_finish();
+
 	crash_save_cpu(regs, safe_smp_processor_id());
 }
 
diff --git a/arch/x86/kernel/reboot.c b/arch/x86/kernel/reboot.c
index f3130f762784..bb7a44af7efd 100644
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
+		x86_platform.guest.enc_kexec_begin();
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
index a7143bb7dd93..82b128d3f309 100644
--- a/arch/x86/kernel/x86_init.c
+++ b/arch/x86/kernel/x86_init.c
@@ -138,6 +138,8 @@ static int enc_status_change_prepare_noop(unsigned long vaddr, int npages, bool
 static int enc_status_change_finish_noop(unsigned long vaddr, int npages, bool enc) { return 0; }
 static bool enc_tlb_flush_required_noop(bool enc) { return false; }
 static bool enc_cache_flush_required_noop(void) { return false; }
+static void enc_kexec_begin_noop(void) {}
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

## [12] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 11/19] x86/tdx: Convert shared memory back to private on kexec*

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
 arch/x86/coco/tdx/tdx.c           | 94 +++++++++++++++++++++++++++++++
 arch/x86/include/asm/pgtable.h    |  5 ++
 arch/x86/include/asm/set_memory.h |  3 +
 arch/x86/mm/pat/set_memory.c      | 42 +++++++++++++-
 4 files changed, 141 insertions(+), 3 deletions(-)

diff --git a/arch/x86/coco/tdx/tdx.c b/arch/x86/coco/tdx/tdx.c
index 979891e97d83..078e2bac2553 100644
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
@@ -831,6 +833,95 @@ static int tdx_enc_status_change_finish(unsigned long vaddr, int numpages,
 	return 0;
 }
 
+/* Stop new private<->shared conversions */
+static void tdx_kexec_begin(void)
+{
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
+
+	/*
+	 * Crash kernel reaches here with interrupts disabled: can't wait for
+	 * conversions to finish.
+	 *
+	 * If race happened, just report and proceed.
+	 */
+	if (!set_memory_enc_stop_conversion())
+		pr_warn("Failed to stop shared<->private conversions\n");
+}
+
+/* Walk direct mapping and convert all shared memory back to private */
+static void tdx_kexec_finish(void)
+{
+	unsigned long addr, end;
+	long found = 0, shared;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
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
+			 * Memory encryption state persists across kexec.
+			 * If tdx_enc_status_changed() fails in the first
+			 * kernel, it leaves memory in an unknown state.
+			 *
+			 * If that memory remains shared, accessing it in the
+			 * *next* kernel through a private mapping will result
+			 * in an unrecoverable guest shutdown.
+			 *
+			 * The kdump kernel boot is not impacted as it uses
+			 * a pre-reserved memory range that is always private.
+			 * However, gathering crash information could lead to
+			 * a crash if it accesses unconverted memory through
+			 * a private mapping which is possible when accessing
+			 * that memory through /proc/vmcore, for example.
+			 *
+			 * In all cases, print error info in order to leave
+			 * enough bread crumbs for debugging.
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
@@ -890,6 +981,9 @@ void __init tdx_early_init(void)
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
index 9aee31862b4a..4b2abce2e3e7 100644
--- a/arch/x86/include/asm/set_memory.h
+++ b/arch/x86/include/asm/set_memory.h
@@ -49,8 +49,11 @@ int set_memory_wb(unsigned long addr, int numpages);
 int set_memory_np(unsigned long addr, int numpages);
 int set_memory_p(unsigned long addr, int numpages);
 int set_memory_4k(unsigned long addr, int numpages);
+
+bool set_memory_enc_stop_conversion(void);
 int set_memory_encrypted(unsigned long addr, int numpages);
 int set_memory_decrypted(unsigned long addr, int numpages);
+
 int set_memory_np_noalias(unsigned long addr, int numpages);
 int set_memory_nonglobal(unsigned long addr, int numpages);
 int set_memory_global(unsigned long addr, int numpages);
diff --git a/arch/x86/mm/pat/set_memory.c b/arch/x86/mm/pat/set_memory.c
index a7a7a6c6a3fb..443a97e515c0 100644
--- a/arch/x86/mm/pat/set_memory.c
+++ b/arch/x86/mm/pat/set_memory.c
@@ -2227,12 +2227,48 @@ static int __set_memory_enc_pgtable(unsigned long addr, int numpages, bool enc)
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
+ */
+bool set_memory_enc_stop_conversion(void)
+{
+	/*
+	 * In a crash scenario, sleep is not allowed. Try to take the lock.
+	 * Failure indicates that there is a race with the conversion.
+	 */
+	if (oops_in_progress)
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

## [13] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 12/19] x86/mm: Make e820__end_ram_pfn() cover E820_TYPE_ACPI ranges*

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

## [14] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 13/19] x86/mm: Do not zap page table entries mapping unaccepted memory table during kdump.*

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

## [15] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 14/19] x86/acpi: Rename fields in acpi_madt_multiproc_wakeup structure*

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
Acked-by: Rafael J. Wysocki <rafael.j.wysocki@intel.com>
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

## [16] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 15/19] x86/acpi: Do not attempt to bring up secondary CPUs in kexec case*

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
Acked-by: Rafael J. Wysocki <rafael.j.wysocki@intel.com>
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

## [17] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 16/19] x86/smp: Add smp_ops.stop_this_cpu() callback*

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
index 0c63035d8164..1b3d417cd6c4 100644
--- a/arch/x86/kernel/process.c
+++ b/arch/x86/kernel/process.c
@@ -832,6 +832,13 @@ void __noreturn stop_this_cpu(void *dummy)
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
index bb7a44af7efd..0e0a4cf6b5eb 100644
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

## [18] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 17/19] x86/mm: Introduce kernel_ident_mapping_free()*

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
index 968d7005f4a7..c45127265f2f 100644
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
+		info->free_pgt_page(p4d, info->context);
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

## [19] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 18/19] x86/acpi: Add support for CPU offlining for ACPI MADT wakeup method*

MADT Multiprocessor Wakeup structure version 1 brings support for CPU
offlining: BIOS provides a reset vector where the CPU has to jump to
for offlining itself. The new TEST mailbox command can be used to test
whether the CPU offlined itself which means the BIOS has control over
the CPU and can online it again via the ACPI MADT wakeup method.

Add CPU offlining support for the ACPI MADT wakeup method by implementing
custom cpu_die(), play_dead() and stop_this_cpu() SMP operations.

CPU offlining makes it possible to hand over secondary CPUs over kexec,
not limiting the second kernel to a single CPU.

The change conforms to the approved ACPI spec change proposal. See the
Link.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Link: https://lore.kernel.org/all/13356251.uLZWGnKmhe@kreacher
Acked-by: Kai Huang <kai.huang@intel.com>
Acked-by: Rafael J. Wysocki <rafael.j.wysocki@intel.com>
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

## [20] Kirill A. Shutemov — 2024-06-14
*Subject: [PATCHv12 19/19] ACPI: tables: Print MULTIPROC_WAKEUP when MADT is parsed*

When MADT is parsed, print MULTIPROC_WAKEUP information:

ACPI: MP Wakeup (version[1], mailbox[0x7fffd000], reset[0x7fffe068])

This debug information will be very helpful during bring up.

Signed-off-by: Kirill A. Shutemov <kirill.shutemov@linux.intel.com>
Acked-by: Kai Huang <kai.huang@intel.com>
Acked-by: Rafael J. Wysocki <rafael.j.wysocki@intel.com>
Reviewed-by: Baoquan He <bhe@redhat.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
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

## [21] Ashish Kalra — 2024-06-17
*Subject: [PATCH v8 0/2] x86/snp: Add kexec support*

From: Ashish Kalra <ashish.kalra@amd.com>

The patchset adds bits and pieces to get kexec (and crashkernel) work on
SNP guest.

This patchset requires the following fix for preventing EFI memory map
corruption while doing SNP guest kexec:
https://lore.kernel.org/all/16131a10-b473-41cc-a96e-d71a4d930353@amd.com/T/#m77f2f33f5521d1369b0e8d461802b99005b4ffd6

The series is based off of and tested against Kirill Shutemov's tree:
  https://github.com/intel/tdx.git guest-kexec

----

v8:
- removed fix EFI memory map corruption with kexec patch as this
  is a use-after-free bug that is not specific to SNP/TDX or kexec
  and a generic fix for the same has been posted. 
- Add new early_sev_detect() and move detection of SEV-ES/SNP guest
  and skip accessing video RAM during decompressor stage into
  this function as per feedback from upstream review.

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

Ashish Kalra (2):
  x86/boot/compressed: Skip Video Memory access in Decompressor for
    SEV-ES/SNP.
  x86/snp: Convert shared memory back to private on kexec

 arch/x86/boot/compressed/misc.c |  23 +++++
 arch/x86/include/asm/sev.h      |   4 +
 arch/x86/kernel/sev.c           | 168 ++++++++++++++++++++++++++++++++
 arch/x86/mm/mem_encrypt_amd.c   |   3 +
 4 files changed, 198 insertions(+)


base-commit: f87c20c019e22be5f2efd11bf9141a532ae876da
prerequisite-patch-id: a911f230c2524bd791c47f62f17f0a93cbf726b6
prerequisite-patch-id: bfe2fa046349978ac1825275eb205acecfbc22f3
prerequisite-patch-id: 36fe38a0547bcc26048bd1c5568d736344173d0a
prerequisite-patch-id: 1f97d0a2edb7509dd58276f628d1a4bda62c154c
prerequisite-patch-id: c890aed9c68e5f6dec8e640194950f0abeddb68c
prerequisite-patch-id: 17a7d996d9af56c6b24a2374e9e498feafe18216
prerequisite-patch-id: 6a8bda2b3cf9bfab8177acdcfc8dd0408ed129fa
prerequisite-patch-id: 99382c42348b9a076ba930eca0dfc9d000ec951d
prerequisite-patch-id: 469a0a3c78b0eca82527cd85e2205fb8fb89d645
prerequisite-patch-id: fda4eb74abfdee49760e508ee6f3b661d52ceb26
prerequisite-patch-id: 6da1f25b8b1646f326911eb10c05f3821343313e
prerequisite-patch-id: 95356474298029468750a9c1bc2224fb09a86eed
prerequisite-patch-id: d4966ae63e86d24b0bf578da4dae871cd9002b12
prerequisite-patch-id: fccde6f1fa385b5af0195f81fcb95acd71822428
prerequisite-patch-id: 16048ee15e392b0b9217b8923939b0059311abd2
prerequisite-patch-id: 5c9ae9aa294f72f63ae2c3551507dfbd92525803
prerequisite-patch-id: 6bd2e291bfdb1f61b6d194899d3bb3c678d534dd
prerequisite-patch-id: c85fd0bb6d183a40da73720eaa607481b1d51daf
prerequisite-patch-id: 60760e0c98ab7ccd2ca22ae3e9f20ff5a94c6e91

---

## [22] Ashish Kalra — 2024-06-17
*Subject: [PATCH v8 1/2] x86/boot/compressed: Skip Video Memory access in Decompressor for SEV-ES/SNP.*

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

Add early_sev_detect() to detect SEV-ES/SNP guest and skip
accessing video RAM during decompressor stage.

Serial console output during decompressor stage works as
boot stage2 #VC handler already supports handling port I/O.

Suggested-by: Borislav Petkov <Borislav.Petkov@amd.com>
Suggested-by: Thomas Lendacy <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
---
 arch/x86/boot/compressed/misc.c | 23 +++++++++++++++++++++++
 1 file changed, 23 insertions(+)

diff --git a/arch/x86/boot/compressed/misc.c b/arch/x86/boot/compressed/misc.c
index b70e4a21c15f..bad924f20a3a 100644
--- a/arch/x86/boot/compressed/misc.c
+++ b/arch/x86/boot/compressed/misc.c
@@ -385,6 +385,27 @@ static void parse_mem_encrypt(struct setup_header *hdr)
 		hdr->xloadflags |= XLF_MEM_ENCRYPTION;
 }
 
+static void early_sev_detect(void)
+{
+	/*
+	 * Accessing guest video memory/RAM during kernel decompressor
+	 * causes guest termination as boot stage2 #VC handler for
+	 * SEV-ES/SNP systems does not support MMIO handling.
+	 *
+	 * This issue is observed with SEV-ES/SNP guest kexec as
+	 * kexec -c adds screen_info to the boot parameters
+	 * passed to the kexec kernel, which causes console output to
+	 * be dumped to both video and serial.
+	 *
+	 * As the decompressor output gets cleared really fast, it is
+	 * preferable to get the console output only on serial, hence,
+	 * skip accessing video RAM during decompressor stage to
+	 * prevent guest termination.
+	 */
+	if (sev_status & MSR_AMD64_SEV_ES_ENABLED)
+		lines = cols = 0;
+}
+
 /*
  * The compressed kernel image (ZO), has been moved so that its position
  * is against the end of the buffer used to hold the uncompressed kernel
@@ -440,6 +461,8 @@ asmlinkage __visible void *extract_kernel(void *rmode, unsigned char *output)
 	 */
 	early_tdx_detect();
 
+	early_sev_detect();
+
 	console_init();
 
 	/*

---

## [23] Ashish Kalra — 2024-06-17
*Subject: [PATCH v8 2/2] x86/snp: Convert shared memory back to private on kexec*

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
 arch/x86/kernel/sev.c         | 168 ++++++++++++++++++++++++++++++++++
 arch/x86/mm/mem_encrypt_amd.c |   3 +
 3 files changed, 175 insertions(+)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ca20cc4e5826..68c08458bb87 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -229,6 +229,8 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end);
 u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
+void snp_kexec_finish(void);
+void snp_kexec_begin(void);
 #else
 static inline void sev_es_ist_enter(struct pt_regs *regs) { }
 static inline void sev_es_ist_exit(void) { }
@@ -258,6 +260,8 @@ static inline void snp_accept_memory(phys_addr_t start, phys_addr_t end) { }
 static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
+static inline void snp_kexec_finish(void) { }
+static inline void snp_kexec_begin(void) { }
 #endif
 
 #ifdef CONFIG_KVM_AMD_SEV
diff --git a/arch/x86/kernel/sev.c b/arch/x86/kernel/sev.c
index 3342ed58e168..ff2f385642e2 100644
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
@@ -913,6 +918,169 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
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
+void snp_kexec_begin(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
+	/*
+	 * Crash kernel reaches here with interrupts disabled: can't wait for
+	 * conversions to finish.
+	 *
+	 * If race happened, just report and proceed.
+	 */
+	if (!set_memory_enc_stop_conversion())
+		pr_warn("Failed to stop shared<->private conversions\n");
+}
+
+/* Walk direct mapping and convert all shared memory back to private */
+void snp_kexec_finish(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
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

## [24] Borislav Petkov — 2024-06-19
*Subject: Re: [PATCH v8 1/2] x86/boot/compressed: Skip Video Memory access in
 Decompressor for SEV-ES/SNP.*

On Mon, Jun 17, 2024 at 09:15:12PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Use this massaged version for your next submission:

From: Ashish Kalra <ashish.kalra@amd.com>
Date: Mon, 17 Jun 2024 21:15:12 +0000
Subject: [PATCH] x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP

Accessing guest video memory/RAM in the decompressor causes guest
termination as the boot stage2 #VC handler for SEV-ES/SNP systems does
not support MMIO handling.

This issue is observed during a SEV-ES/SNP guest kexec as kexec -c adds
screen_info to the boot parameters passed to the second kernel, which
causes console output to be dumped to both video and serial.

As the decompressor output gets cleared really fast, it is preferable to
get the console output only on serial, hence, skip accessing the video
RAM during decompressor stage to prevent guest termination.

Serial console output during decompressor stage works as boot stage2 #VC
handler already supports handling port I/O.

  [ bp: Massage. ]

Suggested-by: Borislav Petkov (AMD) <bp@alien8.de>
Suggested-by: Thomas Lendacy <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
---
 arch/x86/boot/compressed/misc.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/x86/boot/compressed/misc.c b/arch/x86/boot/compressed/misc.c
index 944454306ef4..826b4d5cb1f0 100644
--- a/arch/x86/boot/compressed/misc.c
+++ b/arch/x86/boot/compressed/misc.c
@@ -385,6 +385,19 @@ static void parse_mem_encrypt(struct setup_header *hdr)
 		hdr->xloadflags |= XLF_MEM_ENCRYPTION;
 }
 
+static void early_sev_detect(void)
+{
+	/*
+	 * Accessing video memory causes guest termination because
+	 * the boot stage2 #VC handler of SEV-ES/SNP guests does not
+	 * support MMIO handling and kexec -c adds screen_info to the
+	 * boot parameters passed to the kexec kernel, which causes
+	 * console output to be dumped to both video and serial.
+	 */
+	if (sev_status & MSR_AMD64_SEV_ES_ENABLED)
+		lines = cols = 0;
+}
+
 /*
  * The compressed kernel image (ZO), has been moved so that its position
  * is against the end of the buffer used to hold the uncompressed kernel
@@ -440,6 +453,8 @@ asmlinkage __visible void *extract_kernel(void *rmode, unsigned char *output)
 	 */
 	early_tdx_detect();
 
+	early_sev_detect();
+
 	console_init();
 
 	/*

---

## [25] Ashish Kalra — 2024-06-20
*Subject: [PATCH v9 0/3] x86/snp: Add kexec support*

From: Ashish Kalra <ashish.kalra@amd.com>

The patchset adds bits and pieces to get kexec (and crashkernel) work on
SNP guest.

This patchset requires the following fix for preventing EFI memory map
corruption while doing SNP guest kexec:
  https://lore.kernel.org/all/16131a10-b473-41cc-a96e-d71a4d930353@amd.com/T/#m77f2f33f5521d1369b0e8d461802b99005b4ffd6

The series is based off and tested against tree:
  https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git

----

v9:
- Rebased onto current tip/master;
- Rebased on top of [PATCH] x86/sev: Move SEV compilation units 
  and uses the coco directory hierarchy for SEV guest kexec patches.
- Includes the above mentioned patch as part of this patch-set to
  fix any kernel test robot/build issues.
- Includes the massaged version of patch 2/3 as per upstream
  review/feedback.

v8:
- removed fix EFI memory map corruption with kexec patch as this
  is a use-after-free bug that is not specific to SNP/TDX or kexec
  and a generic fix for the same has been posted. 
- Add new early_sev_detect() and move detection of SEV-ES/SNP guest
  and skip accessing video RAM during decompressor stage into
  this function as per feedback from upstream review.

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

Ashish Kalra (2):
  x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP
  x86/snp: Convert shared memory back to private on kexec

Borislav Petkov (AMD) (1):
  x86/sev: Move SEV compilation units

 arch/x86/boot/compressed/misc.c               |  15 ++
 arch/x86/boot/compressed/sev.c                |   2 +-
 arch/x86/coco/Makefile                        |   1 +
 arch/x86/coco/sev/Makefile                    |   3 +
 arch/x86/{kernel/sev.c => coco/sev/core.c}    | 170 +++++++++++++++++-
 .../sev-shared.c => coco/sev/shared.c}        |   0
 arch/x86/include/asm/sev.h                    |   4 +
 arch/x86/kernel/Makefile                      |   2 -
 arch/x86/mm/mem_encrypt_amd.c                 |   2 +
 9 files changed, 195 insertions(+), 4 deletions(-)
 create mode 100644 arch/x86/coco/sev/Makefile
 rename arch/x86/{kernel/sev.c => coco/sev/core.c} (93%)
 rename arch/x86/{kernel/sev-shared.c => coco/sev/shared.c} (100%)

---

## [26] Ashish Kalra — 2024-06-20
*Subject: [PATCH v9 1/3] x86/sev: Move SEV compilation units*

From: "Borislav Petkov (AMD)" <bp@alien8.de>

From: "Borislav Petkov (AMD)" <bp@alien8.de>

A long time ago we said that we're going to move the coco stuff where it
belongs

  https://lore.kernel.org/all/Yg5nh1RknPRwIrb8@zn.tnic

and not keep it in arch/x86/kernel. TDX did that and SEV can't find time
to do so. So lemme do it. If people have trouble converting their
ongoing featuritis patches, ask me for a sed script.

No functional changes.

Cc: Ashish Kalra <Ashish.Kalra@amd.com>
Cc: Joerg Roedel <joro@8bytes.org>
Cc: Michael Roth <michael.roth@amd.com>
Cc: Nikunj A Dadhania <nikunj@amd.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
---
 arch/x86/boot/compressed/sev.c                      | 2 +-
 arch/x86/coco/Makefile                              | 1 +
 arch/x86/coco/sev/Makefile                          | 3 +++
 arch/x86/{kernel/sev.c => coco/sev/core.c}          | 2 +-
 arch/x86/{kernel/sev-shared.c => coco/sev/shared.c} | 0
 arch/x86/kernel/Makefile                            | 2 --
 6 files changed, 6 insertions(+), 4 deletions(-)
 create mode 100644 arch/x86/coco/sev/Makefile
 rename arch/x86/{kernel/sev.c => coco/sev/core.c} (99%)
 rename arch/x86/{kernel/sev-shared.c => coco/sev/shared.c} (100%)

diff --git a/arch/x86/boot/compressed/sev.c b/arch/x86/boot/compressed/sev.c
index 697057250faa..cd44e120fe53 100644
--- a/arch/x86/boot/compressed/sev.c
+++ b/arch/x86/boot/compressed/sev.c
@@ -127,7 +127,7 @@ static bool fault_in_kernel_space(unsigned long address)
 #include "../../lib/insn.c"
 
 /* Include code for early handlers */
-#include "../../kernel/sev-shared.c"
+#include "../../coco/sev/shared.c"
 
 static struct svsm_ca *svsm_get_caa(void)
 {
diff --git a/arch/x86/coco/Makefile b/arch/x86/coco/Makefile
index c816acf78b6a..eabdc7486538 100644
--- a/arch/x86/coco/Makefile
+++ b/arch/x86/coco/Makefile
@@ -6,3 +6,4 @@ CFLAGS_core.o		+= -fno-stack-protector
 obj-y += core.o
 
 obj-$(CONFIG_INTEL_TDX_GUEST)	+= tdx/
+obj-$(CONFIG_AMD_MEM_ENCRYPT)   += sev/
diff --git a/arch/x86/coco/sev/Makefile b/arch/x86/coco/sev/Makefile
new file mode 100644
index 000000000000..b89ba3fba343
--- /dev/null
+++ b/arch/x86/coco/sev/Makefile
@@ -0,0 +1,3 @@
+# SPDX-License-Identifier: GPL-2.0
+
+obj-y += core.o
diff --git a/arch/x86/kernel/sev.c b/arch/x86/coco/sev/core.c
similarity index 99%
rename from arch/x86/kernel/sev.c
rename to arch/x86/coco/sev/core.c
index 726d9df505e7..082d61d85dfc 100644
--- a/arch/x86/kernel/sev.c
+++ b/arch/x86/coco/sev/core.c
@@ -613,7 +613,7 @@ static __always_inline void vc_forward_exception(struct es_em_ctxt *ctxt)
 }
 
 /* Include code shared with pre-decompression boot stage */
-#include "sev-shared.c"
+#include "shared.c"
 
 static inline struct svsm_ca *svsm_get_caa(void)
 {
diff --git a/arch/x86/kernel/sev-shared.c b/arch/x86/coco/sev/shared.c
similarity index 100%
rename from arch/x86/kernel/sev-shared.c
rename to arch/x86/coco/sev/shared.c
diff --git a/arch/x86/kernel/Makefile b/arch/x86/kernel/Makefile
index 20a0dd51700a..b22ceb9fdf57 100644
--- a/arch/x86/kernel/Makefile
+++ b/arch/x86/kernel/Makefile
@@ -142,8 +142,6 @@ obj-$(CONFIG_UNWINDER_ORC)		+= unwind_orc.o
 obj-$(CONFIG_UNWINDER_FRAME_POINTER)	+= unwind_frame.o
 obj-$(CONFIG_UNWINDER_GUESS)		+= unwind_guess.o
 
-obj-$(CONFIG_AMD_MEM_ENCRYPT)		+= sev.o
-
 obj-$(CONFIG_CFI_CLANG)			+= cfi.o
 
 obj-$(CONFIG_CALL_THUNKS)		+= callthunks.o

---

## [27] Ashish Kalra — 2024-06-20
*Subject: [PATCH v9 2/3] x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP*

From: Ashish Kalra <ashish.kalra@amd.com>

Accessing guest video memory/RAM in the decompressor causes guest
termination as the boot stage2 #VC handler for SEV-ES/SNP systems does
not support MMIO handling.

This issue is observed during a SEV-ES/SNP guest kexec as kexec -c adds
screen_info to the boot parameters passed to the second kernel, which
causes console output to be dumped to both video and serial.

As the decompressor output gets cleared really fast, it is preferable to
get the console output only on serial, hence, skip accessing the video
RAM during decompressor stage to prevent guest termination.

Serial console output during decompressor stage works as boot stage2 #VC
handler already supports handling port I/O.

  [ bp: Massage. ]

Suggested-by: Borislav Petkov (AMD) <bp@alien8.de>
Suggested-by: Thomas Lendacy <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
---
 arch/x86/boot/compressed/misc.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/x86/boot/compressed/misc.c b/arch/x86/boot/compressed/misc.c
index 944454306ef4..826b4d5cb1f0 100644
--- a/arch/x86/boot/compressed/misc.c
+++ b/arch/x86/boot/compressed/misc.c
@@ -385,6 +385,19 @@ static void parse_mem_encrypt(struct setup_header *hdr)
 		hdr->xloadflags |= XLF_MEM_ENCRYPTION;
 }
 
+static void early_sev_detect(void)
+{
+	/*
+	 * Accessing video memory causes guest termination because
+	 * the boot stage2 #VC handler of SEV-ES/SNP guests does not
+	 * support MMIO handling and kexec -c adds screen_info to the
+	 * boot parameters passed to the kexec kernel, which causes
+	 * console output to be dumped to both video and serial.
+	 */
+	if (sev_status & MSR_AMD64_SEV_ES_ENABLED)
+		lines = cols = 0;
+}
+
 /*
  * The compressed kernel image (ZO), has been moved so that its position
  * is against the end of the buffer used to hold the uncompressed kernel
@@ -440,6 +453,8 @@ asmlinkage __visible void *extract_kernel(void *rmode, unsigned char *output)
 	 */
 	early_tdx_detect();
 
+	early_sev_detect();
+
 	console_init();
 
 	/*

---

## [28] Ashish Kalra — 2024-06-20
*Subject: [PATCH v9 3/3] x86/snp: Convert shared memory back to private on kexec*

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
 arch/x86/coco/sev/core.c      | 168 ++++++++++++++++++++++++++++++++++
 arch/x86/include/asm/sev.h    |   4 +
 arch/x86/mm/mem_encrypt_amd.c |   2 +
 3 files changed, 174 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 082d61d85dfc..0ce96123b684 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
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
@@ -1010,6 +1015,169 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
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
+void snp_kexec_begin(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
+	/*
+	 * Crash kernel reaches here with interrupts disabled: can't wait for
+	 * conversions to finish.
+	 *
+	 * If race happened, just report and proceed.
+	 */
+	if (!set_memory_enc_stop_conversion())
+		pr_warn("Failed to stop shared<->private conversions\n");
+}
+
+/* Walk direct mapping and convert all shared memory back to private */
+void snp_kexec_finish(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
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
 static int snp_set_vmsa(void *va, void *caa, int apic_id, bool make_vmsa)
 {
 	int ret;
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ac5886ce252e..56e723bc63e2 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -348,6 +348,8 @@ u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
 void snp_update_svsm_ca(void);
+void snp_kexec_finish(void);
+void snp_kexec_begin(void);
 
 #else	/* !CONFIG_AMD_MEM_ENCRYPT */
 
@@ -384,6 +386,8 @@ static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
 static inline void snp_update_svsm_ca(void) { }
+static inline void snp_kexec_finish(void) { }
+static inline void snp_kexec_begin(void) { }
 
 #endif	/* CONFIG_AMD_MEM_ENCRYPT */
 
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 86a476a426c2..9a2cb740772e 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -467,6 +467,8 @@ void __init sme_early_init(void)
 	x86_platform.guest.enc_status_change_finish  = amd_enc_status_change_finish;
 	x86_platform.guest.enc_tlb_flush_required    = amd_enc_tlb_flush_required;
 	x86_platform.guest.enc_cache_flush_required  = amd_enc_cache_flush_required;
+	x86_platform.guest.enc_kexec_begin	     = snp_kexec_begin;
+	x86_platform.guest.enc_kexec_finish	     = snp_kexec_finish;
 
 	/*
 	 * AMD-SEV-ES intercepts the RDMSR to read the X2APIC ID in the

---

## [29] Tom Lendacky — 2024-06-24
*Subject: Re: [PATCH v9 2/3] x86/boot: Skip video memory access in the
 decompressor for SEV-ES/SNP*

On 6/20/24 17:23, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  arch/x86/boot/compressed/misc.c | 15 +++++++++++++++

---

## [30] Tom Lendacky — 2024-06-24
*Subject: Re: [PATCH v9 3/3] x86/snp: Convert shared memory back to private on
 kexec*

On 6/20/24 17:23, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

The pr_debug() calls don't make a lot of sense (and one appears to be in
the wrong location given what it says vs what is done) and should
probably be removed.

Otherwise:

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

...

> +	/* Check for GHCB for being part of a PMD range. */
> +	if ((unsigned long)ghcb >= addr &&

...

> +		/*
> +		 * Switch to using the MSR protocol to change this cpu's

---

## [31] Ashish Kalra — 2024-06-24
*Subject: [PATCH v10 0/2] x86/snp: Add kexec support*

From: Ashish Kalra <ashish.kalra@amd.com>

The patchset adds bits and pieces to get kexec (and crashkernel) work on
SNP guest.

This patchset requires the following fix for preventing EFI memory map
corruption while doing SNP guest kexec:
  https://lore.kernel.org/all/16131a10-b473-41cc-a96e-d71a4d930353@amd.com/T/#m77f2f33f5521d1369b0e8d461802b99005b4ffd6

The series is based off and tested against tree:
  https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git

----

v10:
- Removed pr_debug() calls as per upstream review feedback.
- Add review tags.

v9:
- Rebased onto current tip/master;
- Rebased on top of [PATCH] x86/sev: Move SEV compilation units 
  and uses the coco directory hierarchy for SEV guest kexec patches.
- Includes the above mentioned patch as part of this patch-set to
  fix any kernel test robot/build issues.
- Includes the massaged version of patch 2/3 as per upstream
  review/feedback.

v8:
- removed fix EFI memory map corruption with kexec patch as this
  is a use-after-free bug that is not specific to SNP/TDX or kexec
  and a generic fix for the same has been posted. 
- Add new early_sev_detect() and move detection of SEV-ES/SNP guest
  and skip accessing video RAM during decompressor stage into
  this function as per feedback from upstream review.

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

Ashish Kalra (2):
  x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP
  Subject: [PATCH v9 3/3] x86/snp: Convert shared memory back to private
    on  kexec

 arch/x86/boot/compressed/misc.c |  15 +++
 arch/x86/coco/sev/core.c        | 166 ++++++++++++++++++++++++++++++++
 arch/x86/include/asm/sev.h      |   4 +
 arch/x86/mm/mem_encrypt_amd.c   |   2 +
 4 files changed, 187 insertions(+)

---

## [32] Ashish Kalra — 2024-06-24
*Subject: [PATCH v10 1/2] x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP*

From: Ashish Kalra <ashish.kalra@amd.com>

Accessing guest video memory/RAM in the decompressor causes guest
termination as the boot stage2 #VC handler for SEV-ES/SNP systems does
not support MMIO handling.

This issue is observed during a SEV-ES/SNP guest kexec as kexec -c adds
screen_info to the boot parameters passed to the second kernel, which
causes console output to be dumped to both video and serial.

As the decompressor output gets cleared really fast, it is preferable to
get the console output only on serial, hence, skip accessing the video
RAM during decompressor stage to prevent guest termination.

Serial console output during decompressor stage works as boot stage2 #VC
handler already supports handling port I/O.

  [ bp: Massage. ]

Suggested-by: Borislav Petkov (AMD) <bp@alien8.de>
Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/boot/compressed/misc.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/x86/boot/compressed/misc.c b/arch/x86/boot/compressed/misc.c
index 944454306ef4..826b4d5cb1f0 100644
--- a/arch/x86/boot/compressed/misc.c
+++ b/arch/x86/boot/compressed/misc.c
@@ -385,6 +385,19 @@ static void parse_mem_encrypt(struct setup_header *hdr)
 		hdr->xloadflags |= XLF_MEM_ENCRYPTION;
 }
 
+static void early_sev_detect(void)
+{
+	/*
+	 * Accessing video memory causes guest termination because
+	 * the boot stage2 #VC handler of SEV-ES/SNP guests does not
+	 * support MMIO handling and kexec -c adds screen_info to the
+	 * boot parameters passed to the kexec kernel, which causes
+	 * console output to be dumped to both video and serial.
+	 */
+	if (sev_status & MSR_AMD64_SEV_ES_ENABLED)
+		lines = cols = 0;
+}
+
 /*
  * The compressed kernel image (ZO), has been moved so that its position
  * is against the end of the buffer used to hold the uncompressed kernel
@@ -440,6 +453,8 @@ asmlinkage __visible void *extract_kernel(void *rmode, unsigned char *output)
 	 */
 	early_tdx_detect();
 
+	early_sev_detect();
+
 	console_init();
 
 	/*

---

## [33] Ashish Kalra — 2024-06-24
*Subject: [PATCH v10 2/2] Subject: [PATCH v9 3/3] x86/snp: Convert shared memory back to private on  kexec*

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

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/sev/core.c      | 166 ++++++++++++++++++++++++++++++++++
 arch/x86/include/asm/sev.h    |   4 +
 arch/x86/mm/mem_encrypt_amd.c |   2 +
 3 files changed, 172 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 082d61d85dfc..9b405237f2c5 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
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
@@ -1010,6 +1015,167 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
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
+void snp_kexec_begin(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
+	/*
+	 * Crash kernel reaches here with interrupts disabled: can't wait for
+	 * conversions to finish.
+	 *
+	 * If race happened, just report and proceed.
+	 */
+	if (!set_memory_enc_stop_conversion())
+		pr_warn("Failed to stop shared<->private conversions\n");
+}
+
+/* Walk direct mapping and convert all shared memory back to private */
+void snp_kexec_finish(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
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
+		pte = lookup_address(kexec_last_addr_to_make_private, &level);
+		size = page_level_size(level);
+		set_pte_enc(pte, level, (void *)kexec_last_addr_to_make_private);
+		snp_set_memory_private(kexec_last_addr_to_make_private, (size / PAGE_SIZE));
+	}
+}
+
 static int snp_set_vmsa(void *va, void *caa, int apic_id, bool make_vmsa)
 {
 	int ret;
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ac5886ce252e..56e723bc63e2 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -348,6 +348,8 @@ u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
 void snp_update_svsm_ca(void);
+void snp_kexec_finish(void);
+void snp_kexec_begin(void);
 
 #else	/* !CONFIG_AMD_MEM_ENCRYPT */
 
@@ -384,6 +386,8 @@ static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
 static inline void snp_update_svsm_ca(void) { }
+static inline void snp_kexec_finish(void) { }
+static inline void snp_kexec_begin(void) { }
 
 #endif	/* CONFIG_AMD_MEM_ENCRYPT */
 
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 86a476a426c2..9a2cb740772e 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -467,6 +467,8 @@ void __init sme_early_init(void)
 	x86_platform.guest.enc_status_change_finish  = amd_enc_status_change_finish;
 	x86_platform.guest.enc_tlb_flush_required    = amd_enc_tlb_flush_required;
 	x86_platform.guest.enc_cache_flush_required  = amd_enc_cache_flush_required;
+	x86_platform.guest.enc_kexec_begin	     = snp_kexec_begin;
+	x86_platform.guest.enc_kexec_finish	     = snp_kexec_finish;
 
 	/*
 	 * AMD-SEV-ES intercepts the RDMSR to read the X2APIC ID in the

---

## [34] Borislav Petkov — 2024-06-24
*Subject: Re: [PATCH v9 3/3] x86/snp: Convert shared memory back to private on
 kexec*

On Thu, Jun 20, 2024 at 10:23:59PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

The secon, kexec-ed, kernel...

> sees E820_TYPE_RAM.

...

> @@ -92,6 +94,9 @@ static struct ghcb *boot_ghcb __section(".data");
>  /* Bitmap of SEV features supported by the hypervisor */

This is particularly yucky.

AFAIU, you want to:

1. Skip GHCB addresses when making all pages private

2. Once you're done converting, in snp_kexec_finish() go over the GHCB
   addresses and convert them explicitly, one-by-one, without this silly
   variable

>  /* #VC handler runtime per-CPU data */
>  struct sev_es_runtime_data {

Code duplication: __set_clr_pte_enc().

You need to refactor the code instead of adding just another, generically
looking helper just because it is easier this way.

> +{
> +	pte_t new_pte;

s/cpu/CPU/g

There are multiple places.

> +		 * at the end of unshared loop so that we continue to use the
> +		 * optimized GHCB protocol and not force the switch to

This ends with a ','. Is anything more coming?

> +	 */
> +

This sentence needs to be written for humans. And come to think of it, you can
simply drop it. lookup_address() can return NULL so you simply need to check
its retval.

> +		 */
> +		if (pte && pte_decrypted(*pte) && !pte_none(*pte)) {

Might as well terminate the guest here.

> +			}
> +

Why is this a separate function and not part of unshare_all_memory()?

> +{
> +	unsigned long vaddr, vaddr_end;

...

---

## [35] Kalra, Ashish — 2024-06-24
*Subject: Re: [PATCH v9 3/3] x86/snp: Convert shared memory back to private on
 kexec*

On 6/24/2024 1:26 PM, Borislav Petkov wrote:

>> @@ -92,6 +94,9 @@ static struct ghcb *boot_ghcb __section(".data");
>>  /* Bitmap of SEV features supported by the hypervisor */

it is simple to compare the current CPU's GHCB while walking the direct mapping, OTOH, comparing each and every address during unshare_all_memory() with all per-CPU GHCB addresses will just make it complicated and less performant too.

By skipping only the current CPU's GHCB and saving a reference to it, we are able to switch this (one) skipped GHCB page to private at the end of kexec_finish().

>
>>  /* #VC handler runtime per-CPU data */

The issue with using __set_clr_pte_enc() is that it is called by early initialization code, it uses early_snp_set_memory_private() which uses the MSR protocol for making page state change calls as early_set_pages_state() can be called during early init code before the GHCB is established.

Hence, added simple static functions make_pte_private() and set_pte_enc() to make use of the more optimized snp_set_memory_private() to use the GHCB instead of the MSR protocol. Additionally, make_pte_private() adds check for GHCB addresses during unshare_all_memory() loop.

Thanks, Ashish

>> +		 * at the end of unshared loop so that we continue to use the
>> +		 * optimized GHCB protocol and not force the switch to

---

## [36] Borislav Petkov — 2024-06-25
*Subject: Re: [PATCH v9 3/3] x86/snp: Convert shared memory back to private on
 kexec*

On Mon, Jun 24, 2024 at 03:57:34PM -0500, Kalra, Ashish wrote:
> ...  Hence, added simple static functions make_pte_private() and
> set_pte_enc() to make use of the more optimized snp_set_memory_private() to

IOW, what you're saying is: "Boris, what you're asking can't be done."

Well, what *you're* asking - for me to maintain crap - can't be done either.
So this will stay where it is.

Unless you make a genuine effort and refactor the code...

---

## [37] Kalra, Ashish — 2024-06-27
*Subject: Re: [PATCH v9 3/3] x86/snp: Convert shared memory back to private on
 kexec*

Hello Boris,

On 6/24/2024 10:59 PM, Borislav Petkov wrote:
> On Mon, Jun 24, 2024 at 03:57:34PM -0500, Kalra, Ashish wrote:
>> ...  Hence, added simple static functions make_pte_private() and

There is an issue with calling __set_clr_pte_enc() here for the _bss_decrypted section being made private again,

when calling __set_clr_pte_enc() on _bss_decrypted section pages, clflush_cache_range() will fail as __va()

on this physical range fails as the bss_decrypted section pages are not in kernel direct map.

Hence, clflush_cache_range() in __set_clr_pte_enc() causes an implicit page state change which is not resolved as below and causes fatal guest exit :

qemu-system-x86_64: warning: memory fault: GPA 0x4000000 size 0x1000 flags 0x8 kvm_convert_memory start 0x4000000 size 0x1000 shared_to_private

...

KVM: unknown exit reason 24 EAX=00000000 EBX=00000000 ECX=00000000 EDX=00000000 ESI=00000000 EDI=00000000 EBP=00000000 ESP=00000000 EIP=00000000 EFL=00000002 [-------] CPL=0 II=0 A20=1 SMM=0 HLT=0

...

This is the reason why i had to pass the vaddr to set_pte_enc(), added here for kexec code, so that i can use it for clflush_cache_range().

So for specific cases such as this, where we can't call __set_clr_pte_enc() on _bss_decrypted section, we probably need a separate set_pte_enc().

Thanks, Ashish

---

## [38] Tom Lendacky — 2024-06-28
*Subject: Re: [PATCH v9 3/3] x86/snp: Convert shared memory back to private on
 kexec*

On 6/27/24 23:27, Kalra, Ashish wrote:
> Hello Boris,
> 

You can probably add a va parameter, that when not NULL, is used for the
flush. If NULL, then use the __va() macro on the pa.

Thanks,
Tom

> 
> Thanks, Ashish

---

## [39] Kalra, Ashish — 2024-06-28
*Subject: Re: [PATCH v9 3/3] x86/snp: Convert shared memory back to private on
 kexec*

Hello Tom,

On 6/28/2024 9:01 AM, Tom Lendacky wrote:
> On 6/27/24 23:27, Kalra, Ashish wrote:
>> Hello Boris,

Yes, i have done exactly that.

Thanks, Ashish

---

## [40] Kalra, Ashish — 2024-06-28
*Subject: Re: [PATCH v9 3/3] x86/snp: Convert shared memory back to private on
 kexec*

On 6/24/2024 1:26 PM, Borislav Petkov wrote:
>> +	 */
>> +
I had to additionally add check for pte_none() here to handle physical memory holes in direct mapping.

Looking at lookup_address_in_pgd_attr(), at pte level it is simply returning pte_offset_kernel() and there does not seem to be a check for returning NULL if pte_none() ?

Probably need to fix lookup_address_in_pgd_attr(), to add check for pte_none() after pte_offset_kernel() and return NULL if it is true.

Thanks, Ashish

>> +		 */
>> +		if (pte && pte_decrypted(*pte) && !pte_none(*pte)) {

---

## [41] Ashish Kalra — 2024-07-02
*Subject: [PATCH v11 0/3] x86/snp: Add kexec support*

From: Ashish Kalra <ashish.kalra@amd.com>

The patchset adds bits and pieces to get kexec (and crashkernel) work on
SNP guest.

This patchset requires the following fix for preventing EFI memory map
corruption while doing SNP guest kexec:
  https://lore.kernel.org/all/16131a10-b473-41cc-a96e-d71a4d930353@amd.com/T/#m77f2f33f5521d1369b0e8d461802b99005b4ffd6

The series is based off and tested against tree:
  https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git

----

v11:
- Refactored __set_clr_pte_enc() and added two new helper functions to
  set/clear PTE C-bit from early SEV/SNP initialization code and
  later during normal system operations and shutdown/kexec.
- Removed kexec_last_addr_to_make_private and now skip per-cpu
  GHCB addresses when making all pages private and then after 
  converting all pages to private in snp_kexec_finish(), go over
  the per-cpu GHCB addresses and convert them to private explicitly.
- Fixed comments and commit logs as per upstream review.

v10:
- Removed pr_debug() calls as per upstream review feedback.
- Add review tags.

v9:
- Rebased onto current tip/master;
- Rebased on top of [PATCH] x86/sev: Move SEV compilation units 
  and uses the coco directory hierarchy for SEV guest kexec patches.
- Includes the above mentioned patch as part of this patch-set to
  fix any kernel test robot/build issues.
- Includes the massaged version of patch 2/3 as per upstream
  review/feedback.

v8:
- removed fix EFI memory map corruption with kexec patch as this
  is a use-after-free bug that is not specific to SNP/TDX or kexec
  and a generic fix for the same has been posted. 
- Add new early_sev_detect() and move detection of SEV-ES/SNP guest
  and skip accessing video RAM during decompressor stage into
  this function as per feedback from upstream review.

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
  x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP
  x86/mm: refactor __set_clr_pte_enc()
  x86/snp: Convert shared memory back to private on kexec

 arch/x86/boot/compressed/misc.c |  15 ++++
 arch/x86/coco/sev/core.c        | 148 ++++++++++++++++++++++++++++++++
 arch/x86/include/asm/sev.h      |  13 +++
 arch/x86/mm/mem_encrypt_amd.c   |  49 +++++++++--
 4 files changed, 217 insertions(+), 8 deletions(-)

---

## [42] Ashish Kalra — 2024-07-02
*Subject: [PATCH v11 1/3] x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP*

From: Ashish Kalra <ashish.kalra@amd.com>

Accessing guest video memory/RAM in the decompressor causes guest
termination as the boot stage2 #VC handler for SEV-ES/SNP systems does
not support MMIO handling.

This issue is observed during a SEV-ES/SNP guest kexec as kexec -c adds
screen_info to the boot parameters passed to the second kernel, which
causes console output to be dumped to both video and serial.

As the decompressor output gets cleared really fast, it is preferable to
get the console output only on serial, hence, skip accessing the video
RAM during decompressor stage to prevent guest termination.

Serial console output during decompressor stage works as boot stage2 #VC
handler already supports handling port I/O.

  [ bp: Massage. ]

Suggested-by: Borislav Petkov (AMD) <bp@alien8.de>
Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/boot/compressed/misc.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/x86/boot/compressed/misc.c b/arch/x86/boot/compressed/misc.c
index 944454306ef4..826b4d5cb1f0 100644
--- a/arch/x86/boot/compressed/misc.c
+++ b/arch/x86/boot/compressed/misc.c
@@ -385,6 +385,19 @@ static void parse_mem_encrypt(struct setup_header *hdr)
 		hdr->xloadflags |= XLF_MEM_ENCRYPTION;
 }
 
+static void early_sev_detect(void)
+{
+	/*
+	 * Accessing video memory causes guest termination because
+	 * the boot stage2 #VC handler of SEV-ES/SNP guests does not
+	 * support MMIO handling and kexec -c adds screen_info to the
+	 * boot parameters passed to the kexec kernel, which causes
+	 * console output to be dumped to both video and serial.
+	 */
+	if (sev_status & MSR_AMD64_SEV_ES_ENABLED)
+		lines = cols = 0;
+}
+
 /*
  * The compressed kernel image (ZO), has been moved so that its position
  * is against the end of the buffer used to hold the uncompressed kernel
@@ -440,6 +453,8 @@ asmlinkage __visible void *extract_kernel(void *rmode, unsigned char *output)
 	 */
 	early_tdx_detect();
 
+	early_sev_detect();
+
 	console_init();
 
 	/*

---

## [43] Ashish Kalra — 2024-07-02
*Subject: [PATCH v11 2/3] x86/mm: refactor __set_clr_pte_enc()*

From: Ashish Kalra <ashish.kalra@amd.com>

Refactor __set_clr_pte_enc() and add two new helper functions to
set/clear PTE C-bit from early SEV/SNP initialization code and
later during normal system operations and shutdown/kexec.

Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/sev.h    |  9 +++++++
 arch/x86/mm/mem_encrypt_amd.c | 47 +++++++++++++++++++++++++++++------
 2 files changed, 48 insertions(+), 8 deletions(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index ac5886ce252e..4f3fd913aadb 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -348,6 +348,10 @@ u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
 void snp_update_svsm_ca(void);
+int prep_set_clr_pte_enc(pte_t *kpte, int level, int enc, void *va,
+			 unsigned long *ret_pfn, unsigned long *ret_pa,
+			 unsigned long *ret_size, pgprot_t *ret_new_prot);
+void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot);
 
 #else	/* !CONFIG_AMD_MEM_ENCRYPT */
 
@@ -384,6 +388,11 @@ static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
 static inline void snp_update_svsm_ca(void) { }
+static inline int
+prep_set_clr_pte_enc(pte_t *kpte, int level, int enc, void *va,
+		     unsigned long *ret_pfn, unsigned long *ret_pa,
+		     unsigned long *ret_size, pgprot_t *ret_new_prot) { }
+static inline void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot) { }
 
 #endif	/* CONFIG_AMD_MEM_ENCRYPT */
 
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 86a476a426c2..42a35040aaf9 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -311,15 +311,16 @@ static int amd_enc_status_change_finish(unsigned long vaddr, int npages, bool en
 	return 0;
 }
 
-static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
+int prep_set_clr_pte_enc(pte_t *kpte, int level, int enc, void *va,
+			 unsigned long *ret_pfn, unsigned long *ret_pa,
+			 unsigned long *ret_size, pgprot_t *ret_new_prot)
 {
 	pgprot_t old_prot, new_prot;
 	unsigned long pfn, pa, size;
-	pte_t new_pte;
 
 	pfn = pg_level_to_pfn(level, kpte, &old_prot);
 	if (!pfn)
-		return;
+		return 1;
 
 	new_prot = old_prot;
 	if (enc)
@@ -329,7 +330,7 @@ static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
 
 	/* If prot is same then do nothing. */
 	if (pgprot_val(old_prot) == pgprot_val(new_prot))
-		return;
+		return 1;
 
 	pa = pfn << PAGE_SHIFT;
 	size = page_level_size(level);
@@ -339,7 +340,39 @@ static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
 	 * physical page attribute from C=1 to C=0 or vice versa. Flush the
 	 * caches to ensure that data gets accessed with the correct C-bit.
 	 */
-	clflush_cache_range(__va(pa), size);
+	if (va)
+		clflush_cache_range(va, size);
+	else
+		clflush_cache_range(__va(pa), size);
+
+	if (ret_new_prot)
+		*ret_new_prot = new_prot;
+	if (ret_size)
+		*ret_size = size;
+	if (ret_pfn)
+		*ret_pfn = pfn;
+	if (ret_pa)
+		*ret_pa = pa;
+
+	return 0;
+}
+
+void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot)
+{
+	pte_t new_pte;
+
+	/* Change the page encryption mask. */
+	new_pte = pfn_pte(pfn, new_prot);
+	set_pte_atomic(kpte, new_pte);
+}
+
+static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
+{
+	unsigned long pfn, pa, size;
+	pgprot_t new_prot;
+
+	if (prep_set_clr_pte_enc(kpte, level, enc, NULL, &pfn, &pa, &size, &new_prot))
+		return;
 
 	/* Encrypt/decrypt the contents in-place */
 	if (enc) {
@@ -354,9 +387,7 @@ static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
 		early_snp_set_memory_shared((unsigned long)__va(pa), pa, 1);
 	}
 
-	/* Change the page encryption mask. */
-	new_pte = pfn_pte(pfn, new_prot);
-	set_pte_atomic(kpte, new_pte);
+	set_pte_enc_mask(kpte, pfn, new_prot);
 
 	/*
 	 * If page is set encrypted in the page table, then update the RMP table to

---

## [44] Ashish Kalra — 2024-07-02
*Subject: [PATCH v11 3/3] x86/snp: Convert shared memory back to private on kexec*

From: Ashish Kalra <ashish.kalra@amd.com>

SNP guests allocate shared buffers to perform I/O. It is done by
allocating pages normally from the buddy allocator and converting them
to shared with set_memory_decrypted().

The second, kexec-ed, kernel has no idea what memory is converted this way.
It only sees E820_TYPE_RAM.

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

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/sev/core.c      | 148 ++++++++++++++++++++++++++++++++++
 arch/x86/include/asm/sev.h    |   4 +
 arch/x86/mm/mem_encrypt_amd.c |   2 +
 3 files changed, 154 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 082d61d85dfc..0c90a8a74a88 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1010,6 +1010,154 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE);
 }
 
+static void set_pte_enc(pte_t *kpte, int level, void *va)
+{
+	unsigned long pfn;
+	pgprot_t new_prot;
+
+	prep_set_clr_pte_enc(kpte, level, 1, va, &pfn, NULL, NULL, &new_prot);
+	set_pte_enc_mask(kpte, pfn, new_prot);
+}
+
+static bool make_pte_private(pte_t *pte, unsigned long addr, int pages, int level)
+{
+	struct sev_es_runtime_data *data;
+	struct ghcb *ghcb;
+	int cpu;
+
+	/*
+	 * Ensure that all the per-cpu GHCBs are made private
+	 * at the end of unshared loop so that we continue to use the
+	 * optimized GHCB protocol and not force the switch to
+	 * MSR protocol till the very end.
+	 */
+	for_each_possible_cpu(cpu) {
+		data = per_cpu(runtime_data, cpu);
+		ghcb = &data->ghcb_page;
+		/* Check for GHCB for being part of a PMD range */
+		if ((unsigned long)ghcb >= addr &&
+		    (unsigned long)ghcb <= (addr + (pages * PAGE_SIZE)))
+			return true;
+	}
+
+	set_pte_enc(pte, level, (void *)addr);
+	snp_set_memory_private(addr, pages);
+
+	return true;
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
+static void unshare_all_memory(void)
+{
+	unsigned long addr, end;
+
+	/*
+	 * Walk direct mapping and convert all shared memory back to private.
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
+		if (pte && pte_decrypted(*pte) && !pte_none(*pte)) {
+			int pages = size / PAGE_SIZE;
+
+			if (!make_pte_private(pte, addr, pages, level)) {
+				pr_err("Failed to unshare range %#lx-%#lx\n",
+				       addr, addr + size);
+			}
+		}
+		addr += size;
+	}
+
+	unshare_all_bss_decrypted_memory();
+
+	__flush_tlb_all();
+
+}
+
+/* Stop new private<->shared conversions */
+void snp_kexec_begin(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
+	/*
+	 * Crash kernel reaches here with interrupts disabled: can't wait for
+	 * conversions to finish.
+	 *
+	 * If race happened, just report and proceed.
+	 */
+	if (!set_memory_enc_stop_conversion())
+		pr_warn("Failed to stop shared<->private conversions\n");
+}
+
+/* Walk direct mapping and convert all shared memory back to private */
+void snp_kexec_finish(void)
+{
+	struct sev_es_runtime_data *data;
+	unsigned int level, cpu;
+	unsigned long size;
+	struct ghcb *ghcb;
+	pte_t *pte;
+
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
+
+	unshare_all_memory();
+
+	/*
+	 * Switch to using the MSR protocol to change per-cpu
+	 * GHCBs to private.
+	 * All the per-cpu GHCBs have been switched back to private,
+	 * so can't do any more GHCB calls to the hypervisor beyond
+	 * this point till the kexec kernel starts running.
+	 */
+	boot_ghcb = NULL;
+	sev_cfg.ghcbs_initialized = false;
+
+	for_each_possible_cpu(cpu) {
+		data = per_cpu(runtime_data, cpu);
+		ghcb = &data->ghcb_page;
+		pte = lookup_address((unsigned long)ghcb, &level);
+		size = page_level_size(level);
+		set_pte_enc(pte, level, (void *)ghcb);
+		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));
+	}
+}
+
 static int snp_set_vmsa(void *va, void *caa, int apic_id, bool make_vmsa)
 {
 	int ret;
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 4f3fd913aadb..4f1a6d1e3f4c 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -352,6 +352,8 @@ int prep_set_clr_pte_enc(pte_t *kpte, int level, int enc, void *va,
 			 unsigned long *ret_pfn, unsigned long *ret_pa,
 			 unsigned long *ret_size, pgprot_t *ret_new_prot);
 void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot);
+void snp_kexec_finish(void);
+void snp_kexec_begin(void);
 
 #else	/* !CONFIG_AMD_MEM_ENCRYPT */
 
@@ -393,6 +395,8 @@ prep_set_clr_pte_enc(pte_t *kpte, int level, int enc, void *va,
 		     unsigned long *ret_pfn, unsigned long *ret_pa,
 		     unsigned long *ret_size, pgprot_t *ret_new_prot) { }
 static inline void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot) { }
+static inline void snp_kexec_finish(void) { }
+static inline void snp_kexec_begin(void) { }
 
 #endif	/* CONFIG_AMD_MEM_ENCRYPT */
 
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 42a35040aaf9..dec24bb08b09 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -498,6 +498,8 @@ void __init sme_early_init(void)
 	x86_platform.guest.enc_status_change_finish  = amd_enc_status_change_finish;
 	x86_platform.guest.enc_tlb_flush_required    = amd_enc_tlb_flush_required;
 	x86_platform.guest.enc_cache_flush_required  = amd_enc_cache_flush_required;
+	x86_platform.guest.enc_kexec_begin	     = snp_kexec_begin;
+	x86_platform.guest.enc_kexec_finish	     = snp_kexec_finish;
 
 	/*
 	 * AMD-SEV-ES intercepts the RDMSR to read the X2APIC ID in the

---

## [45] Borislav Petkov — 2024-07-05
*Subject: Re: [PATCH v11 2/3] x86/mm: refactor __set_clr_pte_enc()*

On Tue, Jul 02, 2024 at 07:57:54PM +0000, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Some serious cleanups ontop which reduce the diffstat even more. Untested ofc.

Holler if something's unclear.

---
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 0c90a8a74a88..5013c3afb0c4 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1012,11 +1012,14 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 
 static void set_pte_enc(pte_t *kpte, int level, void *va)
 {
-	unsigned long pfn;
-	pgprot_t new_prot;
-
-	prep_set_clr_pte_enc(kpte, level, 1, va, &pfn, NULL, NULL, &new_prot);
-	set_pte_enc_mask(kpte, pfn, new_prot);
+	struct pte_enc_desc d = {
+		.kpte	   = kpte,
+		.pte_level = level,
+		.va	   = va
+	};
+
+	prepare_pte_enc(&d);
+	set_pte_enc_mask(kpte, d.pfn, d.new_pgprot);
 }
 
 static bool make_pte_private(pte_t *pte, unsigned long addr, int pages, int level)
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 4f1a6d1e3f4c..68a03fd07665 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -234,6 +234,22 @@ struct svsm_attest_call {
 	u8 rsvd[4];
 };
 
+/* PTE descriptor used for the prepare_pte_enc() operations. */
+struct pte_enc_desc {
+	pte_t *kpte;
+	int pte_level;
+	bool encrypt;
+	/* pfn of the kpte above */
+	unsigned long pfn;
+	/* physical address of @pfn */
+	unsigned long pa;
+	/* virtual address of @pfn */
+	void *va;
+	/* memory covered by the pte */
+	unsigned long size;
+	pgprot_t new_pgprot;
+};
+
 /*
  * SVSM protocol structure
  */
@@ -348,9 +364,7 @@ u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
 void snp_update_svsm_ca(void);
-int prep_set_clr_pte_enc(pte_t *kpte, int level, int enc, void *va,
-			 unsigned long *ret_pfn, unsigned long *ret_pa,
-			 unsigned long *ret_size, pgprot_t *ret_new_prot);
+int prepare_pte_enc(struct pte_enc_desc *d);
 void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot);
 void snp_kexec_finish(void);
 void snp_kexec_begin(void);
@@ -390,10 +404,7 @@ static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
 static inline void snp_update_svsm_ca(void) { }
-static inline int
-prep_set_clr_pte_enc(pte_t *kpte, int level, int enc, void *va,
-		     unsigned long *ret_pfn, unsigned long *ret_pa,
-		     unsigned long *ret_size, pgprot_t *ret_new_prot) { }
+static inline int prepare_pte_enc(struct pte_enc_desc *d) { }
 static inline void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot) { }
 static inline void snp_kexec_finish(void) { }
 static inline void snp_kexec_begin(void) { }
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index dec24bb08b09..774f9677458f 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -311,48 +311,37 @@ static int amd_enc_status_change_finish(unsigned long vaddr, int npages, bool en
 	return 0;
 }
 
-int prep_set_clr_pte_enc(pte_t *kpte, int level, int enc, void *va,
-			 unsigned long *ret_pfn, unsigned long *ret_pa,
-			 unsigned long *ret_size, pgprot_t *ret_new_prot)
+int prepare_pte_enc(struct pte_enc_desc *d)
 {
-	pgprot_t old_prot, new_prot;
-	unsigned long pfn, pa, size;
+	pgprot_t old_prot;
 
-	pfn = pg_level_to_pfn(level, kpte, &old_prot);
-	if (!pfn)
+	d->pfn = pg_level_to_pfn(d->pte_level, d->kpte, &old_prot);
+	if (!d->pfn)
 		return 1;
 
-	new_prot = old_prot;
-	if (enc)
-		pgprot_val(new_prot) |= _PAGE_ENC;
+	d->new_pgprot = old_prot;
+	if (d->encrypt)
+		pgprot_val(d->new_pgprot) |= _PAGE_ENC;
 	else
-		pgprot_val(new_prot) &= ~_PAGE_ENC;
+		pgprot_val(d->new_pgprot) &= ~_PAGE_ENC;
 
 	/* If prot is same then do nothing. */
-	if (pgprot_val(old_prot) == pgprot_val(new_prot))
+	if (pgprot_val(old_prot) == pgprot_val(d->new_pgprot))
 		return 1;
 
-	pa = pfn << PAGE_SHIFT;
-	size = page_level_size(level);
+	d->pa = d->pfn << PAGE_SHIFT;
+	d->size = page_level_size(d->pte_level);
 
 	/*
-	 * We are going to perform in-place en-/decryption and change the
-	 * physical page attribute from C=1 to C=0 or vice versa. Flush the
-	 * caches to ensure that data gets accessed with the correct C-bit.
+	 * In-place en-/decryption and physical page attribute change
+	 * from C=1 to C=0 or vice versa will be performed. Flush the
+	 * caches to ensure that data gets accessed with the correct
+	 * C-bit.
 	 */
-	if (va)
-		clflush_cache_range(va, size);
+	if (d->va)
+		clflush_cache_range(d->va, d->size);
 	else
-		clflush_cache_range(__va(pa), size);
-
-	if (ret_new_prot)
-		*ret_new_prot = new_prot;
-	if (ret_size)
-		*ret_size = size;
-	if (ret_pfn)
-		*ret_pfn = pfn;
-	if (ret_pa)
-		*ret_pa = pa;
+		clflush_cache_range(__va(d->pa), d->size);
 
 	return 0;
 }
@@ -368,33 +357,36 @@ void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot)
 
 static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
 {
-	unsigned long pfn, pa, size;
-	pgprot_t new_prot;
+	struct pte_enc_desc d = {
+		.kpte	     = kpte,
+		.pte_level   = level,
+		.encrypt     = enc
+	};
 
-	if (prep_set_clr_pte_enc(kpte, level, enc, NULL, &pfn, &pa, &size, &new_prot))
+	if (prepare_pte_enc(&d))
 		return;
 
 	/* Encrypt/decrypt the contents in-place */
 	if (enc) {
-		sme_early_encrypt(pa, size);
+		sme_early_encrypt(d.pa, d.size);
 	} else {
-		sme_early_decrypt(pa, size);
+		sme_early_decrypt(d.pa, d.size);
 
 		/*
 		 * ON SNP, the page state in the RMP table must happen
 		 * before the page table updates.
 		 */
-		early_snp_set_memory_shared((unsigned long)__va(pa), pa, 1);
+		early_snp_set_memory_shared((unsigned long)__va(d.pa), d.pa, 1);
 	}
 
-	set_pte_enc_mask(kpte, pfn, new_prot);
+	set_pte_enc_mask(kpte, d.pfn, d.new_pgprot);
 
 	/*
 	 * If page is set encrypted in the page table, then update the RMP table to
 	 * add this page as private.
 	 */
 	if (enc)
-		early_snp_set_memory_private((unsigned long)__va(pa), pa, 1);
+		early_snp_set_memory_private((unsigned long)__va(d.pa), d.pa, 1);
 }
 
 static int __init early_set_memory_enc_dec(unsigned long vaddr,

---

## [46] Borislav Petkov — 2024-07-05
*Subject: Re: [PATCH v11 3/3] x86/snp: Convert shared memory back to private
 on kexec*

On Tue, Jul 02, 2024 at 07:58:11PM +0000, Ashish Kalra wrote:
> +static void unshare_all_bss_decrypted_memory(void)
> +{

Merge the whole unsharing dance into a single function:

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index 5013c3afb0c4..f263ceada006 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1049,58 +1049,47 @@ static bool make_pte_private(pte_t *pte, unsigned long addr, int pages, int leve
 	return true;
 }
 
-static void unshare_all_bss_decrypted_memory(void)
-{
-	unsigned long vaddr, vaddr_end;
-	unsigned int level;
-	unsigned int npages;
-	pte_t *pte;
-
-	vaddr = (unsigned long)__start_bss_decrypted;
-	vaddr_end = (unsigned long)__start_bss_decrypted_unused;
-	npages = (vaddr_end - vaddr) >> PAGE_SHIFT;
-	for (; vaddr < vaddr_end; vaddr += PAGE_SIZE) {
-		pte = lookup_address(vaddr, &level);
-		if (!pte || !pte_decrypted(*pte) || pte_none(*pte))
-			continue;
-
-		set_pte_enc(pte, level, (void *)vaddr);
-	}
-	vaddr = (unsigned long)__start_bss_decrypted;
-	snp_set_memory_private(vaddr, npages);
-}
-
+/* Walk the direct mapping and convert all shared memory back to private. */
 static void unshare_all_memory(void)
 {
-	unsigned long addr, end;
-
-	/*
-	 * Walk direct mapping and convert all shared memory back to private.
-	 */
+	unsigned long addr, end, size;
+	unsigned int npages, level;
+	pte_t *pte;
 
+	/* Unshare the direct mapping. */
 	addr = PAGE_OFFSET;
 	end  = PAGE_OFFSET + get_max_mapped();
 
 	while (addr < end) {
-		unsigned long size;
-		unsigned int level;
-		pte_t *pte;
-
 		pte = lookup_address(addr, &level);
 		size = page_level_size(level);
 
-		if (pte && pte_decrypted(*pte) && !pte_none(*pte)) {
-			int pages = size / PAGE_SIZE;
-
-			if (!make_pte_private(pte, addr, pages, level)) {
-				pr_err("Failed to unshare range %#lx-%#lx\n",
-				       addr, addr + size);
-			}
+		if (!pte || !pte_decrypted(*pte) || pte_none(*pte)) {
+			addr += size;
+			continue;
 		}
-		addr += size;
+
+		npages = size / PAGE_SIZE;
+
+		if (!make_pte_private(pte, addr, npages, level))
+			pr_err("Failed to unshare range %#lx-%#lx\n",
+				addr, addr + size);
 	}
 
-	unshare_all_bss_decrypted_memory();
+	/* Unshare all bss decrypted memory. */
+	addr = (unsigned long)__start_bss_decrypted;
+	end  = (unsigned long)__start_bss_decrypted_unused;
+	npages = (end - addr) >> PAGE_SHIFT;
+
+	for (; addr < end; addr += PAGE_SIZE) {
+		pte = lookup_address(addr, &level);
+		if (!pte || !pte_decrypted(*pte) || pte_none(*pte))
+			continue;
+
+		set_pte_enc(pte, level, (void *)addr);
+	}
+	addr = (unsigned long)__start_bss_decrypted;
+	snp_set_memory_private(addr, npages);
 
 	__flush_tlb_all();
 
@@ -1114,8 +1103,9 @@ void snp_kexec_begin(void)
 
 	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
 		return;
+
 	/*
-	 * Crash kernel reaches here with interrupts disabled: can't wait for
+	 * Crash kernel ends up here with interrupts disabled: can't wait for
 	 * conversions to finish.
 	 *
 	 * If race happened, just report and proceed.
@@ -1124,7 +1114,6 @@ void snp_kexec_begin(void)
 		pr_warn("Failed to stop shared<->private conversions\n");
 }
 
-/* Walk direct mapping and convert all shared memory back to private */
 void snp_kexec_finish(void)
 {
 	struct sev_es_runtime_data *data;

---

## [47] Borislav Petkov — 2024-07-05
*Subject: Re: [PATCH v11 3/3] x86/snp: Convert shared memory back to private
 on kexec*

On Tue, Jul 02, 2024 at 07:58:11PM +0000, Ashish Kalra wrote:
> +static bool make_pte_private(pte_t *pte, unsigned long addr, int pages, int level)
> +{

Zap make_pte_private()
    
diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index f263ceada006..65234ffb1495 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1022,39 +1022,14 @@ static void set_pte_enc(pte_t *kpte, int level, void *va)
 	set_pte_enc_mask(kpte, d.pfn, d.new_pgprot);
 }
 
-static bool make_pte_private(pte_t *pte, unsigned long addr, int pages, int level)
-{
-	struct sev_es_runtime_data *data;
-	struct ghcb *ghcb;
-	int cpu;
-
-	/*
-	 * Ensure that all the per-cpu GHCBs are made private
-	 * at the end of unshared loop so that we continue to use the
-	 * optimized GHCB protocol and not force the switch to
-	 * MSR protocol till the very end.
-	 */
-	for_each_possible_cpu(cpu) {
-		data = per_cpu(runtime_data, cpu);
-		ghcb = &data->ghcb_page;
-		/* Check for GHCB for being part of a PMD range */
-		if ((unsigned long)ghcb >= addr &&
-		    (unsigned long)ghcb <= (addr + (pages * PAGE_SIZE)))
-			return true;
-	}
-
-	set_pte_enc(pte, level, (void *)addr);
-	snp_set_memory_private(addr, pages);
-
-	return true;
-}
-
 /* Walk the direct mapping and convert all shared memory back to private. */
 static void unshare_all_memory(void)
 {
-	unsigned long addr, end, size;
+	unsigned long addr, end, size, ghcb;
+	struct sev_es_runtime_data *data;
 	unsigned int npages, level;
 	pte_t *pte;
+	int cpu;
 
 	/* Unshare the direct mapping. */
 	addr = PAGE_OFFSET;
@@ -1063,17 +1038,28 @@ static void unshare_all_memory(void)
 	while (addr < end) {
 		pte = lookup_address(addr, &level);
 		size = page_level_size(level);
+		npages = size / PAGE_SIZE;
 
 		if (!pte || !pte_decrypted(*pte) || pte_none(*pte)) {
 			addr += size;
 			continue;
 		}
 
-		npages = size / PAGE_SIZE;
+		/*
+		 * Ensure that all the per-cpu GHCBs are made private at the
+		 * end of unsharing loop so that the switch to the slower MSR
+		 * protocol happens last.
+		 */
+		for_each_possible_cpu(cpu) {
+			data = per_cpu(runtime_data, cpu);
+			ghcb = (unsigned long)&data->ghcb_page;
+
+			if (addr <= ghcb && ghcb <= addr + size)
+				continue;
+		}
 
-		if (!make_pte_private(pte, addr, npages, level))
-			pr_err("Failed to unshare range %#lx-%#lx\n",
-				addr, addr + size);
+		set_pte_enc(pte, level, (void *)addr);
+		snp_set_memory_private(addr, npages);
 	}
 
 	/* Unshare all bss decrypted memory. */

---

## [48] Kalra, Ashish — 2024-07-10
*Subject: Re: [PATCH v11 3/3] x86/snp: Convert shared memory back to private on
 kexec*

On 7/5/2024 9:29 AM, Borislav Petkov wrote:

> On Tue, Jul 02, 2024 at 07:58:11PM +0000, Ashish Kalra wrote:
>> +static bool make_pte_private(pte_t *pte, unsigned long addr, int pages, int level)

There is an issue with this implementation, as continue does not skip the inner loop and then after the inner loop is completed makes the ghcb private instead of skipping it, so instead using a jump here.

Thanks, Ashish

> +		}
>

---

## [49] Ashish Kalra — 2024-07-30
*Subject: [PATCH v12 0/3] x86/snp: Add kexec support*

From: Ashish Kalra <ashish.kalra@amd.com>

The patchset adds bits and pieces to get kexec (and crashkernel) work on
SNP guest.

This patchset requires the following fix for preventing EFI memory map
corruption while doing SNP guest kexec:
  https://lore.kernel.org/all/16131a10-b473-41cc-a96e-d71a4d930353@amd.com/T/#m77f2f33f5521d1369b0e8d461802b99005b4ffd6

The series is based off and tested against tree:
  https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git

----

v12:
- cleanups as suggested as per upstream review.
- Moved unshare_all_bss_decrypted_memory() into unshare_all_memory().
- Zap make_pte_private() and merge into unshare_all_memory().

v11:
- Refactored __set_clr_pte_enc() and added two new helper functions to
  set/clear PTE C-bit from early SEV/SNP initialization code and
  later during normal system operations and shutdown/kexec.
- Removed kexec_last_addr_to_make_private and now skip per-cpu
  GHCB addresses when making all pages private and then after 
  converting all pages to private in snp_kexec_finish(), go over
  the per-cpu GHCB addresses and convert them to private explicitly.
- Fixed comments and commit logs as per upstream review.

v10:
- Removed pr_debug() calls as per upstream review feedback.
- Add review tags.

v9:
- Rebased onto current tip/master;
- Rebased on top of [PATCH] x86/sev: Move SEV compilation units 
  and uses the coco directory hierarchy for SEV guest kexec patches.
- Includes the above mentioned patch as part of this patch-set to
  fix any kernel test robot/build issues.
- Includes the massaged version of patch 2/3 as per upstream
  review/feedback.

v8:
- removed fix EFI memory map corruption with kexec patch as this
  is a use-after-free bug that is not specific to SNP/TDX or kexec
  and a generic fix for the same has been posted. 
- Add new early_sev_detect() and move detection of SEV-ES/SNP guest
  and skip accessing video RAM during decompressor stage into
  this function as per feedback from upstream review.

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
  x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP
  x86/mm: refactor __set_clr_pte_enc()
  x86/snp: Convert shared memory back to private on kexec

 arch/x86/boot/compressed/misc.c |  15 ++++
 arch/x86/coco/sev/core.c        | 132 ++++++++++++++++++++++++++++++++
 arch/x86/include/asm/sev.h      |  24 ++++++
 arch/x86/mm/mem_encrypt_amd.c   |  77 ++++++++++++-------
 4 files changed, 222 insertions(+), 26 deletions(-)

---

## [50] Ashish Kalra — 2024-07-30
*Subject: [PATCH v12 1/3] x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP*

From: Ashish Kalra <ashish.kalra@amd.com>

Accessing guest video memory/RAM in the decompressor causes guest
termination as the boot stage2 #VC handler for SEV-ES/SNP systems does
not support MMIO handling.

This issue is observed during a SEV-ES/SNP guest kexec as kexec -c adds
screen_info to the boot parameters passed to the second kernel, which
causes console output to be dumped to both video and serial.

As the decompressor output gets cleared really fast, it is preferable to
get the console output only on serial, hence, skip accessing the video
RAM during decompressor stage to prevent guest termination.

Serial console output during decompressor stage works as boot stage2 #VC
handler already supports handling port I/O.

  [ bp: Massage. ]

Suggested-by: Borislav Petkov (AMD) <bp@alien8.de>
Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/boot/compressed/misc.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/x86/boot/compressed/misc.c b/arch/x86/boot/compressed/misc.c
index 944454306ef4..826b4d5cb1f0 100644
--- a/arch/x86/boot/compressed/misc.c
+++ b/arch/x86/boot/compressed/misc.c
@@ -385,6 +385,19 @@ static void parse_mem_encrypt(struct setup_header *hdr)
 		hdr->xloadflags |= XLF_MEM_ENCRYPTION;
 }
 
+static void early_sev_detect(void)
+{
+	/*
+	 * Accessing video memory causes guest termination because
+	 * the boot stage2 #VC handler of SEV-ES/SNP guests does not
+	 * support MMIO handling and kexec -c adds screen_info to the
+	 * boot parameters passed to the kexec kernel, which causes
+	 * console output to be dumped to both video and serial.
+	 */
+	if (sev_status & MSR_AMD64_SEV_ES_ENABLED)
+		lines = cols = 0;
+}
+
 /*
  * The compressed kernel image (ZO), has been moved so that its position
  * is against the end of the buffer used to hold the uncompressed kernel
@@ -440,6 +453,8 @@ asmlinkage __visible void *extract_kernel(void *rmode, unsigned char *output)
 	 */
 	early_tdx_detect();
 
+	early_sev_detect();
+
 	console_init();
 
 	/*

---

## [51] Ashish Kalra — 2024-07-30
*Subject: [PATCH v12 2/3] x86/mm: refactor __set_clr_pte_enc()*

From: Ashish Kalra <ashish.kalra@amd.com>

Refactor __set_clr_pte_enc() and add two new helper functions to
set/clear PTE C-bit from early SEV/SNP initialization code and
later during shutdown/kexec especially when all CPUs are stopped
and interrupts are disabled and set_memory_xx() interfaces can't
be used.

Co-developed-by: Borislav Petkov (AMD) <bp@alien8.de>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/sev.h    | 20 ++++++++++
 arch/x86/mm/mem_encrypt_amd.c | 75 +++++++++++++++++++++++------------
 2 files changed, 69 insertions(+), 26 deletions(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 79bbe2be900e..fd19a8f413d0 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -285,6 +285,22 @@ struct svsm_attest_call {
 	u8 rsvd[4];
 };
 
+/* PTE descriptor used for the prepare_pte_enc() operations. */
+struct pte_enc_desc {
+	pte_t *kpte;
+	int pte_level;
+	bool encrypt;
+	/* pfn of the kpte above */
+	unsigned long pfn;
+	/* physical address of @pfn */
+	unsigned long pa;
+	/* virtual address of @pfn */
+	void *va;
+	/* memory covered by the pte */
+	unsigned long size;
+	pgprot_t new_pgprot;
+};
+
 /*
  * SVSM protocol structure
  */
@@ -399,6 +415,8 @@ u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
 void snp_update_svsm_ca(void);
+int prepare_pte_enc(struct pte_enc_desc *d);
+void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot);
 
 #else	/* !CONFIG_AMD_MEM_ENCRYPT */
 
@@ -435,6 +453,8 @@ static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
 static inline void snp_update_svsm_ca(void) { }
+static inline int prepare_pte_enc(struct pte_enc_desc *d) { }
+static inline void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot) { }
 
 #endif	/* CONFIG_AMD_MEM_ENCRYPT */
 
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 86a476a426c2..f4be81db72ee 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -311,59 +311,82 @@ static int amd_enc_status_change_finish(unsigned long vaddr, int npages, bool en
 	return 0;
 }
 
-static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
+int prepare_pte_enc(struct pte_enc_desc *d)
 {
-	pgprot_t old_prot, new_prot;
-	unsigned long pfn, pa, size;
-	pte_t new_pte;
+	pgprot_t old_prot;
 
-	pfn = pg_level_to_pfn(level, kpte, &old_prot);
-	if (!pfn)
-		return;
+	d->pfn = pg_level_to_pfn(d->pte_level, d->kpte, &old_prot);
+	if (!d->pfn)
+		return 1;
 
-	new_prot = old_prot;
-	if (enc)
-		pgprot_val(new_prot) |= _PAGE_ENC;
+	d->new_pgprot = old_prot;
+	if (d->encrypt)
+		pgprot_val(d->new_pgprot) |= _PAGE_ENC;
 	else
-		pgprot_val(new_prot) &= ~_PAGE_ENC;
+		pgprot_val(d->new_pgprot) &= ~_PAGE_ENC;
 
 	/* If prot is same then do nothing. */
-	if (pgprot_val(old_prot) == pgprot_val(new_prot))
-		return;
+	if (pgprot_val(old_prot) == pgprot_val(d->new_pgprot))
+		return 1;
 
-	pa = pfn << PAGE_SHIFT;
-	size = page_level_size(level);
+	d->pa = d->pfn << PAGE_SHIFT;
+	d->size = page_level_size(d->pte_level);
 
 	/*
-	 * We are going to perform in-place en-/decryption and change the
-	 * physical page attribute from C=1 to C=0 or vice versa. Flush the
-	 * caches to ensure that data gets accessed with the correct C-bit.
+	 * In-place en-/decryption and physical page attribute change
+	 * from C=1 to C=0 or vice versa will be performed. Flush the
+	 * caches to ensure that data gets accessed with the correct
+	 * C-bit.
 	 */
-	clflush_cache_range(__va(pa), size);
+	if (d->va)
+		clflush_cache_range(d->va, d->size);
+	else
+		clflush_cache_range(__va(d->pa), d->size);
+
+	return 0;
+}
+
+void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot)
+{
+	pte_t new_pte;
+
+	/* Change the page encryption mask. */
+	new_pte = pfn_pte(pfn, new_prot);
+	set_pte_atomic(kpte, new_pte);
+}
+
+static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
+{
+	struct pte_enc_desc d = {
+		.kpte	     = kpte,
+		.pte_level   = level,
+		.encrypt     = enc
+	};
+
+	if (prepare_pte_enc(&d))
+		return;
 
 	/* Encrypt/decrypt the contents in-place */
 	if (enc) {
-		sme_early_encrypt(pa, size);
+		sme_early_encrypt(d.pa, d.size);
 	} else {
-		sme_early_decrypt(pa, size);
+		sme_early_decrypt(d.pa, d.size);
 
 		/*
 		 * ON SNP, the page state in the RMP table must happen
 		 * before the page table updates.
 		 */
-		early_snp_set_memory_shared((unsigned long)__va(pa), pa, 1);
+		early_snp_set_memory_shared((unsigned long)__va(d.pa), d.pa, 1);
 	}
 
-	/* Change the page encryption mask. */
-	new_pte = pfn_pte(pfn, new_prot);
-	set_pte_atomic(kpte, new_pte);
+	set_pte_enc_mask(kpte, d.pfn, d.new_pgprot);
 
 	/*
 	 * If page is set encrypted in the page table, then update the RMP table to
 	 * add this page as private.
 	 */
 	if (enc)
-		early_snp_set_memory_private((unsigned long)__va(pa), pa, 1);
+		early_snp_set_memory_private((unsigned long)__va(d.pa), d.pa, 1);
 }
 
 static int __init early_set_memory_enc_dec(unsigned long vaddr,

---

## [52] Ashish Kalra — 2024-07-30
*Subject: [PATCH v12 3/3] x86/snp: Convert shared memory back to private on kexec*

From: Ashish Kalra <ashish.kalra@amd.com>

SNP guests allocate shared buffers to perform I/O. It is done by
allocating pages normally from the buddy allocator and converting them
to shared with set_memory_decrypted().

The second, kexec-ed, kernel has no idea what memory is converted this way.
It only sees E820_TYPE_RAM.

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

Co-developed-by: Borislav Petkov (AMD) <bp@alien8.de>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/sev/core.c      | 132 ++++++++++++++++++++++++++++++++++
 arch/x86/include/asm/sev.h    |   4 ++
 arch/x86/mm/mem_encrypt_amd.c |   2 +
 3 files changed, 138 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index de1df0cb45da..4278cdbee3a5 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1010,6 +1010,138 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE);
 }
 
+static void set_pte_enc(pte_t *kpte, int level, void *va)
+{
+	struct pte_enc_desc d = {
+		.kpte	   = kpte,
+		.pte_level = level,
+		.va	   = va,
+		.encrypt   = true
+	};
+
+	prepare_pte_enc(&d);
+	set_pte_enc_mask(kpte, d.pfn, d.new_pgprot);
+}
+
+static void unshare_all_memory(void)
+{
+	unsigned long addr, end, size, ghcb;
+	struct sev_es_runtime_data *data;
+	unsigned int npages, level;
+	bool skipped_addr;
+	pte_t *pte;
+	int cpu;
+
+	/* Unshare the direct mapping. */
+	addr = PAGE_OFFSET;
+	end  = PAGE_OFFSET + get_max_mapped();
+
+	while (addr < end) {
+		pte = lookup_address(addr, &level);
+		size = page_level_size(level);
+		npages = size / PAGE_SIZE;
+		skipped_addr = false;
+
+		if (!pte || !pte_decrypted(*pte) || pte_none(*pte)) {
+			addr += size;
+			continue;
+		}
+
+		/*
+		 * Ensure that all the per-cpu GHCBs are made private at the
+		 * end of unsharing loop so that the switch to the slower MSR
+		 * protocol happens last.
+		 */
+		for_each_possible_cpu(cpu) {
+			data = per_cpu(runtime_data, cpu);
+			ghcb = (unsigned long)&data->ghcb_page;
+
+			if (addr <= ghcb && ghcb <= addr + size) {
+				skipped_addr = true;
+				break;
+			}
+		}
+
+		if (!skipped_addr) {
+			set_pte_enc(pte, level, (void *)addr);
+			snp_set_memory_private(addr, npages);
+		}
+		addr += size;
+	}
+
+	/* Unshare all bss decrypted memory. */
+	addr = (unsigned long)__start_bss_decrypted;
+	end  = (unsigned long)__start_bss_decrypted_unused;
+	npages = (end - addr) >> PAGE_SHIFT;
+
+	for (; addr < end; addr += PAGE_SIZE) {
+		pte = lookup_address(addr, &level);
+		if (!pte || !pte_decrypted(*pte) || pte_none(*pte))
+			continue;
+
+		set_pte_enc(pte, level, (void *)addr);
+	}
+	addr = (unsigned long)__start_bss_decrypted;
+	snp_set_memory_private(addr, npages);
+
+	__flush_tlb_all();
+}
+
+/* Stop new private<->shared conversions */
+void snp_kexec_begin(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
+
+	/*
+	 * Crash kernel ends up here with interrupts disabled: can't wait for
+	 * conversions to finish.
+	 *
+	 * If race happened, just report and proceed.
+	 */
+	if (!set_memory_enc_stop_conversion())
+		pr_warn("Failed to stop shared<->private conversions\n");
+}
+
+void snp_kexec_finish(void)
+{
+	struct sev_es_runtime_data *data;
+	unsigned int level, cpu;
+	unsigned long size;
+	struct ghcb *ghcb;
+	pte_t *pte;
+
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
+
+	unshare_all_memory();
+
+	/*
+	 * Switch to using the MSR protocol to change per-cpu
+	 * GHCBs to private.
+	 * All the per-cpu GHCBs have been switched back to private,
+	 * so can't do any more GHCB calls to the hypervisor beyond
+	 * this point till the kexec kernel starts running.
+	 */
+	boot_ghcb = NULL;
+	sev_cfg.ghcbs_initialized = false;
+
+	for_each_possible_cpu(cpu) {
+		data = per_cpu(runtime_data, cpu);
+		ghcb = &data->ghcb_page;
+		pte = lookup_address((unsigned long)ghcb, &level);
+		size = page_level_size(level);
+		set_pte_enc(pte, level, (void *)ghcb);
+		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));
+	}
+}
+
 static int snp_set_vmsa(void *va, void *caa, int apic_id, bool make_vmsa)
 {
 	int ret;
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index fd19a8f413d0..4876ab4c7043 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -417,6 +417,8 @@ void sev_show_status(void);
 void snp_update_svsm_ca(void);
 int prepare_pte_enc(struct pte_enc_desc *d);
 void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot);
+void snp_kexec_finish(void);
+void snp_kexec_begin(void);
 
 #else	/* !CONFIG_AMD_MEM_ENCRYPT */
 
@@ -455,6 +457,8 @@ static inline void sev_show_status(void) { }
 static inline void snp_update_svsm_ca(void) { }
 static inline int prepare_pte_enc(struct pte_enc_desc *d) { }
 static inline void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot) { }
+static inline void snp_kexec_finish(void) { }
+static inline void snp_kexec_begin(void) { }
 
 #endif	/* CONFIG_AMD_MEM_ENCRYPT */
 
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index f4be81db72ee..774f9677458f 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -490,6 +490,8 @@ void __init sme_early_init(void)
 	x86_platform.guest.enc_status_change_finish  = amd_enc_status_change_finish;
 	x86_platform.guest.enc_tlb_flush_required    = amd_enc_tlb_flush_required;
 	x86_platform.guest.enc_cache_flush_required  = amd_enc_cache_flush_required;
+	x86_platform.guest.enc_kexec_begin	     = snp_kexec_begin;
+	x86_platform.guest.enc_kexec_finish	     = snp_kexec_finish;
 
 	/*
 	 * AMD-SEV-ES intercepts the RDMSR to read the X2APIC ID in the

---

## [53] Ashish Kalra — 2024-08-01
*Subject: [PATCH v13 0/3] x86/snp: Add kexec support*

From: Ashish Kalra <ashish.kalra@amd.com>

The patchset adds bits and pieces to get kexec (and crashkernel) work on
SNP guest.

This patchset requires the following fix for preventing EFI memory map
corruption while doing SNP guest kexec:
  https://lore.kernel.org/all/16131a10-b473-41cc-a96e-d71a4d930353@amd.com/T/#m77f2f33f5521d1369b0e8d461802b99005b4ffd6

The series is based off and tested against tree:
  https://git.kernel.org/pub/scm/linux/kernel/git/tip/tip.git

----

v13:
- fix potential kernel build issue without CONFIG_AMD_MEM_ENCRYPT set.

v12:
- cleanups as suggested as per upstream review.
- Moved unshare_all_bss_decrypted_memory() into unshare_all_memory().
- Zap make_pte_private() and merge into unshare_all_memory().

v11:
- Refactored __set_clr_pte_enc() and added two new helper functions to
  set/clear PTE C-bit from early SEV/SNP initialization code and
  later during normal system operations and shutdown/kexec.
- Removed kexec_last_addr_to_make_private and now skip per-cpu
  GHCB addresses when making all pages private and then after 
  converting all pages to private in snp_kexec_finish(), go over
  the per-cpu GHCB addresses and convert them to private explicitly.
- Fixed comments and commit logs as per upstream review.

v10:
- Removed pr_debug() calls as per upstream review feedback.
- Add review tags.

v9:
- Rebased onto current tip/master;
- Rebased on top of [PATCH] x86/sev: Move SEV compilation units 
  and uses the coco directory hierarchy for SEV guest kexec patches.
- Includes the above mentioned patch as part of this patch-set to
  fix any kernel test robot/build issues.
- Includes the massaged version of patch 2/3 as per upstream
  review/feedback.

v8:
- removed fix EFI memory map corruption with kexec patch as this
  is a use-after-free bug that is not specific to SNP/TDX or kexec
  and a generic fix for the same has been posted. 
- Add new early_sev_detect() and move detection of SEV-ES/SNP guest
  and skip accessing video RAM during decompressor stage into
  this function as per feedback from upstream review.

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
  x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP
  x86/mm: refactor __set_clr_pte_enc()
  x86/snp: Convert shared memory back to private on kexec

 arch/x86/boot/compressed/misc.c |  15 ++++
 arch/x86/coco/sev/core.c        | 132 ++++++++++++++++++++++++++++++++
 arch/x86/include/asm/sev.h      |  24 ++++++
 arch/x86/mm/mem_encrypt_amd.c   |  77 ++++++++++++-------
 4 files changed, 222 insertions(+), 26 deletions(-)

---

## [54] Ashish Kalra — 2024-08-01
*Subject: [PATCH v13 1/3] x86/boot: Skip video memory access in the decompressor for SEV-ES/SNP*

From: Ashish Kalra <ashish.kalra@amd.com>

Accessing guest video memory/RAM in the decompressor causes guest
termination as the boot stage2 #VC handler for SEV-ES/SNP systems does
not support MMIO handling.

This issue is observed during a SEV-ES/SNP guest kexec as kexec -c adds
screen_info to the boot parameters passed to the second kernel, which
causes console output to be dumped to both video and serial.

As the decompressor output gets cleared really fast, it is preferable to
get the console output only on serial, hence, skip accessing the video
RAM during decompressor stage to prevent guest termination.

Serial console output during decompressor stage works as boot stage2 #VC
handler already supports handling port I/O.

  [ bp: Massage. ]

Suggested-by: Borislav Petkov (AMD) <bp@alien8.de>
Suggested-by: Thomas Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Reviewed-by: Kuppuswamy Sathyanarayanan <sathyanarayanan.kuppuswamy@linux.intel.com>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
---
 arch/x86/boot/compressed/misc.c | 15 +++++++++++++++
 1 file changed, 15 insertions(+)

diff --git a/arch/x86/boot/compressed/misc.c b/arch/x86/boot/compressed/misc.c
index 944454306ef4..826b4d5cb1f0 100644
--- a/arch/x86/boot/compressed/misc.c
+++ b/arch/x86/boot/compressed/misc.c
@@ -385,6 +385,19 @@ static void parse_mem_encrypt(struct setup_header *hdr)
 		hdr->xloadflags |= XLF_MEM_ENCRYPTION;
 }
 
+static void early_sev_detect(void)
+{
+	/*
+	 * Accessing video memory causes guest termination because
+	 * the boot stage2 #VC handler of SEV-ES/SNP guests does not
+	 * support MMIO handling and kexec -c adds screen_info to the
+	 * boot parameters passed to the kexec kernel, which causes
+	 * console output to be dumped to both video and serial.
+	 */
+	if (sev_status & MSR_AMD64_SEV_ES_ENABLED)
+		lines = cols = 0;
+}
+
 /*
  * The compressed kernel image (ZO), has been moved so that its position
  * is against the end of the buffer used to hold the uncompressed kernel
@@ -440,6 +453,8 @@ asmlinkage __visible void *extract_kernel(void *rmode, unsigned char *output)
 	 */
 	early_tdx_detect();
 
+	early_sev_detect();
+
 	console_init();
 
 	/*

---

## [55] Ashish Kalra — 2024-08-01
*Subject: [PATCH v13 2/3] x86/mm: refactor __set_clr_pte_enc()*

From: Ashish Kalra <ashish.kalra@amd.com>

Refactor __set_clr_pte_enc() and add two new helper functions to
set/clear PTE C-bit from early SEV/SNP initialization code and
later during shutdown/kexec especially when all CPUs are stopped
and interrupts are disabled and set_memory_xx() interfaces can't
be used.

Co-developed-by: Borislav Petkov (AMD) <bp@alien8.de>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/include/asm/sev.h    | 20 ++++++++++
 arch/x86/mm/mem_encrypt_amd.c | 75 +++++++++++++++++++++++------------
 2 files changed, 69 insertions(+), 26 deletions(-)

diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 79bbe2be900e..61684d0a64c0 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -285,6 +285,22 @@ struct svsm_attest_call {
 	u8 rsvd[4];
 };
 
+/* PTE descriptor used for the prepare_pte_enc() operations. */
+struct pte_enc_desc {
+	pte_t *kpte;
+	int pte_level;
+	bool encrypt;
+	/* pfn of the kpte above */
+	unsigned long pfn;
+	/* physical address of @pfn */
+	unsigned long pa;
+	/* virtual address of @pfn */
+	void *va;
+	/* memory covered by the pte */
+	unsigned long size;
+	pgprot_t new_pgprot;
+};
+
 /*
  * SVSM protocol structure
  */
@@ -399,6 +415,8 @@ u64 snp_get_unsupported_features(u64 status);
 u64 sev_get_status(void);
 void sev_show_status(void);
 void snp_update_svsm_ca(void);
+int prepare_pte_enc(struct pte_enc_desc *d);
+void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot);
 
 #else	/* !CONFIG_AMD_MEM_ENCRYPT */
 
@@ -435,6 +453,8 @@ static inline u64 snp_get_unsupported_features(u64 status) { return 0; }
 static inline u64 sev_get_status(void) { return 0; }
 static inline void sev_show_status(void) { }
 static inline void snp_update_svsm_ca(void) { }
+static inline int prepare_pte_enc(struct pte_enc_desc *d) { return 0; }
+static inline void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot) { }
 
 #endif	/* CONFIG_AMD_MEM_ENCRYPT */
 
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index 86a476a426c2..f4be81db72ee 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -311,59 +311,82 @@ static int amd_enc_status_change_finish(unsigned long vaddr, int npages, bool en
 	return 0;
 }
 
-static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
+int prepare_pte_enc(struct pte_enc_desc *d)
 {
-	pgprot_t old_prot, new_prot;
-	unsigned long pfn, pa, size;
-	pte_t new_pte;
+	pgprot_t old_prot;
 
-	pfn = pg_level_to_pfn(level, kpte, &old_prot);
-	if (!pfn)
-		return;
+	d->pfn = pg_level_to_pfn(d->pte_level, d->kpte, &old_prot);
+	if (!d->pfn)
+		return 1;
 
-	new_prot = old_prot;
-	if (enc)
-		pgprot_val(new_prot) |= _PAGE_ENC;
+	d->new_pgprot = old_prot;
+	if (d->encrypt)
+		pgprot_val(d->new_pgprot) |= _PAGE_ENC;
 	else
-		pgprot_val(new_prot) &= ~_PAGE_ENC;
+		pgprot_val(d->new_pgprot) &= ~_PAGE_ENC;
 
 	/* If prot is same then do nothing. */
-	if (pgprot_val(old_prot) == pgprot_val(new_prot))
-		return;
+	if (pgprot_val(old_prot) == pgprot_val(d->new_pgprot))
+		return 1;
 
-	pa = pfn << PAGE_SHIFT;
-	size = page_level_size(level);
+	d->pa = d->pfn << PAGE_SHIFT;
+	d->size = page_level_size(d->pte_level);
 
 	/*
-	 * We are going to perform in-place en-/decryption and change the
-	 * physical page attribute from C=1 to C=0 or vice versa. Flush the
-	 * caches to ensure that data gets accessed with the correct C-bit.
+	 * In-place en-/decryption and physical page attribute change
+	 * from C=1 to C=0 or vice versa will be performed. Flush the
+	 * caches to ensure that data gets accessed with the correct
+	 * C-bit.
 	 */
-	clflush_cache_range(__va(pa), size);
+	if (d->va)
+		clflush_cache_range(d->va, d->size);
+	else
+		clflush_cache_range(__va(d->pa), d->size);
+
+	return 0;
+}
+
+void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot)
+{
+	pte_t new_pte;
+
+	/* Change the page encryption mask. */
+	new_pte = pfn_pte(pfn, new_prot);
+	set_pte_atomic(kpte, new_pte);
+}
+
+static void __init __set_clr_pte_enc(pte_t *kpte, int level, bool enc)
+{
+	struct pte_enc_desc d = {
+		.kpte	     = kpte,
+		.pte_level   = level,
+		.encrypt     = enc
+	};
+
+	if (prepare_pte_enc(&d))
+		return;
 
 	/* Encrypt/decrypt the contents in-place */
 	if (enc) {
-		sme_early_encrypt(pa, size);
+		sme_early_encrypt(d.pa, d.size);
 	} else {
-		sme_early_decrypt(pa, size);
+		sme_early_decrypt(d.pa, d.size);
 
 		/*
 		 * ON SNP, the page state in the RMP table must happen
 		 * before the page table updates.
 		 */
-		early_snp_set_memory_shared((unsigned long)__va(pa), pa, 1);
+		early_snp_set_memory_shared((unsigned long)__va(d.pa), d.pa, 1);
 	}
 
-	/* Change the page encryption mask. */
-	new_pte = pfn_pte(pfn, new_prot);
-	set_pte_atomic(kpte, new_pte);
+	set_pte_enc_mask(kpte, d.pfn, d.new_pgprot);
 
 	/*
 	 * If page is set encrypted in the page table, then update the RMP table to
 	 * add this page as private.
 	 */
 	if (enc)
-		early_snp_set_memory_private((unsigned long)__va(pa), pa, 1);
+		early_snp_set_memory_private((unsigned long)__va(d.pa), d.pa, 1);
 }
 
 static int __init early_set_memory_enc_dec(unsigned long vaddr,

---

## [56] Ashish Kalra — 2024-08-01
*Subject: [PATCH v13 3/3] x86/snp: Convert shared memory back to private on kexec*

From: Ashish Kalra <ashish.kalra@amd.com>

SNP guests allocate shared buffers to perform I/O. It is done by
allocating pages normally from the buddy allocator and converting them
to shared with set_memory_decrypted().

The second, kexec-ed, kernel has no idea what memory is converted this way.
It only sees E820_TYPE_RAM.

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

Co-developed-by: Borislav Petkov (AMD) <bp@alien8.de>
Signed-off-by: Borislav Petkov (AMD) <bp@alien8.de>
Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>
Signed-off-by: Ashish Kalra <ashish.kalra@amd.com>
---
 arch/x86/coco/sev/core.c      | 132 ++++++++++++++++++++++++++++++++++
 arch/x86/include/asm/sev.h    |   4 ++
 arch/x86/mm/mem_encrypt_amd.c |   2 +
 3 files changed, 138 insertions(+)

diff --git a/arch/x86/coco/sev/core.c b/arch/x86/coco/sev/core.c
index de1df0cb45da..4278cdbee3a5 100644
--- a/arch/x86/coco/sev/core.c
+++ b/arch/x86/coco/sev/core.c
@@ -1010,6 +1010,138 @@ void snp_accept_memory(phys_addr_t start, phys_addr_t end)
 	set_pages_state(vaddr, npages, SNP_PAGE_STATE_PRIVATE);
 }
 
+static void set_pte_enc(pte_t *kpte, int level, void *va)
+{
+	struct pte_enc_desc d = {
+		.kpte	   = kpte,
+		.pte_level = level,
+		.va	   = va,
+		.encrypt   = true
+	};
+
+	prepare_pte_enc(&d);
+	set_pte_enc_mask(kpte, d.pfn, d.new_pgprot);
+}
+
+static void unshare_all_memory(void)
+{
+	unsigned long addr, end, size, ghcb;
+	struct sev_es_runtime_data *data;
+	unsigned int npages, level;
+	bool skipped_addr;
+	pte_t *pte;
+	int cpu;
+
+	/* Unshare the direct mapping. */
+	addr = PAGE_OFFSET;
+	end  = PAGE_OFFSET + get_max_mapped();
+
+	while (addr < end) {
+		pte = lookup_address(addr, &level);
+		size = page_level_size(level);
+		npages = size / PAGE_SIZE;
+		skipped_addr = false;
+
+		if (!pte || !pte_decrypted(*pte) || pte_none(*pte)) {
+			addr += size;
+			continue;
+		}
+
+		/*
+		 * Ensure that all the per-cpu GHCBs are made private at the
+		 * end of unsharing loop so that the switch to the slower MSR
+		 * protocol happens last.
+		 */
+		for_each_possible_cpu(cpu) {
+			data = per_cpu(runtime_data, cpu);
+			ghcb = (unsigned long)&data->ghcb_page;
+
+			if (addr <= ghcb && ghcb <= addr + size) {
+				skipped_addr = true;
+				break;
+			}
+		}
+
+		if (!skipped_addr) {
+			set_pte_enc(pte, level, (void *)addr);
+			snp_set_memory_private(addr, npages);
+		}
+		addr += size;
+	}
+
+	/* Unshare all bss decrypted memory. */
+	addr = (unsigned long)__start_bss_decrypted;
+	end  = (unsigned long)__start_bss_decrypted_unused;
+	npages = (end - addr) >> PAGE_SHIFT;
+
+	for (; addr < end; addr += PAGE_SIZE) {
+		pte = lookup_address(addr, &level);
+		if (!pte || !pte_decrypted(*pte) || pte_none(*pte))
+			continue;
+
+		set_pte_enc(pte, level, (void *)addr);
+	}
+	addr = (unsigned long)__start_bss_decrypted;
+	snp_set_memory_private(addr, npages);
+
+	__flush_tlb_all();
+}
+
+/* Stop new private<->shared conversions */
+void snp_kexec_begin(void)
+{
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
+
+	/*
+	 * Crash kernel ends up here with interrupts disabled: can't wait for
+	 * conversions to finish.
+	 *
+	 * If race happened, just report and proceed.
+	 */
+	if (!set_memory_enc_stop_conversion())
+		pr_warn("Failed to stop shared<->private conversions\n");
+}
+
+void snp_kexec_finish(void)
+{
+	struct sev_es_runtime_data *data;
+	unsigned int level, cpu;
+	unsigned long size;
+	struct ghcb *ghcb;
+	pte_t *pte;
+
+	if (!cc_platform_has(CC_ATTR_GUEST_SEV_SNP))
+		return;
+
+	if (!IS_ENABLED(CONFIG_KEXEC_CORE))
+		return;
+
+	unshare_all_memory();
+
+	/*
+	 * Switch to using the MSR protocol to change per-cpu
+	 * GHCBs to private.
+	 * All the per-cpu GHCBs have been switched back to private,
+	 * so can't do any more GHCB calls to the hypervisor beyond
+	 * this point till the kexec kernel starts running.
+	 */
+	boot_ghcb = NULL;
+	sev_cfg.ghcbs_initialized = false;
+
+	for_each_possible_cpu(cpu) {
+		data = per_cpu(runtime_data, cpu);
+		ghcb = &data->ghcb_page;
+		pte = lookup_address((unsigned long)ghcb, &level);
+		size = page_level_size(level);
+		set_pte_enc(pte, level, (void *)ghcb);
+		snp_set_memory_private((unsigned long)ghcb, (size / PAGE_SIZE));
+	}
+}
+
 static int snp_set_vmsa(void *va, void *caa, int apic_id, bool make_vmsa)
 {
 	int ret;
diff --git a/arch/x86/include/asm/sev.h b/arch/x86/include/asm/sev.h
index 61684d0a64c0..733448e72a9b 100644
--- a/arch/x86/include/asm/sev.h
+++ b/arch/x86/include/asm/sev.h
@@ -417,6 +417,8 @@ void sev_show_status(void);
 void snp_update_svsm_ca(void);
 int prepare_pte_enc(struct pte_enc_desc *d);
 void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot);
+void snp_kexec_finish(void);
+void snp_kexec_begin(void);
 
 #else	/* !CONFIG_AMD_MEM_ENCRYPT */
 
@@ -455,6 +457,8 @@ static inline void sev_show_status(void) { }
 static inline void snp_update_svsm_ca(void) { }
 static inline int prepare_pte_enc(struct pte_enc_desc *d) { return 0; }
 static inline void set_pte_enc_mask(pte_t *kpte, unsigned long pfn, pgprot_t new_prot) { }
+static inline void snp_kexec_finish(void) { }
+static inline void snp_kexec_begin(void) { }
 
 #endif	/* CONFIG_AMD_MEM_ENCRYPT */
 
diff --git a/arch/x86/mm/mem_encrypt_amd.c b/arch/x86/mm/mem_encrypt_amd.c
index f4be81db72ee..774f9677458f 100644
--- a/arch/x86/mm/mem_encrypt_amd.c
+++ b/arch/x86/mm/mem_encrypt_amd.c
@@ -490,6 +490,8 @@ void __init sme_early_init(void)
 	x86_platform.guest.enc_status_change_finish  = amd_enc_status_change_finish;
 	x86_platform.guest.enc_tlb_flush_required    = amd_enc_tlb_flush_required;
 	x86_platform.guest.enc_cache_flush_required  = amd_enc_cache_flush_required;
+	x86_platform.guest.enc_kexec_begin	     = snp_kexec_begin;
+	x86_platform.guest.enc_kexec_finish	     = snp_kexec_finish;
 
 	/*
 	 * AMD-SEV-ES intercepts the RDMSR to read the X2APIC ID in the

---

## [57] Tom Lendacky — 2024-10-28
*Subject: Re: [PATCH v13 2/3] x86/mm: refactor __set_clr_pte_enc()*

On 8/1/24 14:14, Ashish Kalra wrote:
> From: Ashish Kalra <ashish.kalra@amd.com>
> 

Reviewed-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  arch/x86/include/asm/sev.h    | 20 ++++++++++

---
