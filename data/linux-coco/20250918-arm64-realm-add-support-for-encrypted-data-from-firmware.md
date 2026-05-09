---
title: 'arm64: realm: Add support for encrypted data from firmware'
date: 2025-09-18
last_reply: 2025-11-24
message_count: 9
participants: ['Suzuki K Poulose', 'Will Deacon', 'Mauro Carvalho Chehab']
---

## [1] Suzuki K Poulose — 2025-09-18

Confidential compute firmware may provide secret data via reserved memory regions
(e.g., ACPI CCEL, EFI Coco secret area). These must be ioremap'ed() as encrypted.
As of now, realm only maps "trusted devices" (RIPAS = RSI_RIPAS_DEV) as encrypted.
This series adds support for mapping areas that are protected
(i.e., RIPAS = RSI_RIPAS_RAM) as encrypted. Also, extrapolating that, we can map
anything that is not RIPAS_EMPTY as protected, as it is guaranteed to be "protected".

With this in place, we can naturally map any firmware provided area based on the
RIPAS value. If the firmware provides a shared region (not trusted), it must have
set the RIPAS accordingly, before placing the data, as the transition is always
destructive.

Confidential Compute Event Log is exposed as EFI_ACPI_MEMORY_NVS, which is
reserved for firmware use even after the firmware exits the boot services [0].
Thus map the region as READ only in the kernel.

[0] https://uefi.org/specs/UEFI/2.10/07_Services_Boot_Services.html#memory-type-usage-before-exitbootservices

Changes since v2:
  https://lkml.kernel.org/r/20250908223519.1759020-1-suzuki.poulose@arm.com/
 - Collect Review (Gavin) and Tested (Sami) tags for Patch 3
 - Merge the case with other PAGE_KERNEL_RO cases for ACPI_MEMORY_NVS in Patch 3

Changes since v1: 
  https://lkml.kernel.org/r/20250613111153.1548928-1-suzuki.poulose@arm.com/
 - Collect tags
 - Map EFI_MEMORY_ACPI_NVS as READ-ONLY, update comment and commit description


Suzuki K Poulose (3):
  arm64: realm: ioremap: Allow mapping memory as encrypted
  arm64: Enable EFI secret area Securityfs support
  arm64: acpi: Enable ACPI CCEL support

 arch/arm64/include/asm/io.h          |  6 +++++-
 arch/arm64/include/asm/rsi.h         |  2 +-
 arch/arm64/kernel/acpi.c             | 10 ++++++++++
 arch/arm64/kernel/rsi.c              | 26 ++++++++++++++++++++++----
 drivers/virt/coco/efi_secret/Kconfig |  2 +-
 5 files changed, 39 insertions(+), 7 deletions(-)

---

## [2] Suzuki K Poulose — 2025-09-18
*Subject: [PATCH v3 1/3] arm64: realm: ioremap: Allow mapping memory as encrypted*

For ioremap(), so far we only checked if it was a device (RIPAS_DEV) to choose
an encrypted vs decrypted mapping. However, we may have firmware reserved memory
regions exposed to the OS (e.g., EFI Coco Secret Securityfs, ACPI CCEL).
We need to make sure that anything that is RIPAS_RAM (i.e., Guest
protected memory with RMM guarantees) are also mapped as encrypted.

Rephrasing the above, anything that is not RIPAS_EMPTY is guaranteed to be
protected by the RMM. Thus we choose encrypted mapping for anything that is not
RIPAS_EMPTY. While at it, rename the helper function

  __arm64_is_protected_mmio => arm64_rsi_is_protected

to clearly indicate that this not an arm64 generic helper, but something to do
with Realms.

Cc: Sami Mujawar <sami.mujawar@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Cc: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Reviewed-by: Steven Price <steven.price@arm.com>
Tested-by: Sami Mujawar <sami.mujawar@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
 arch/arm64/include/asm/io.h  |  2 +-
 arch/arm64/include/asm/rsi.h |  2 +-
 arch/arm64/kernel/rsi.c      | 26 ++++++++++++++++++++++----
 3 files changed, 24 insertions(+), 6 deletions(-)

diff --git a/arch/arm64/include/asm/io.h b/arch/arm64/include/asm/io.h
index 9b96840fb979..82276282a3c7 100644
--- a/arch/arm64/include/asm/io.h
+++ b/arch/arm64/include/asm/io.h
@@ -311,7 +311,7 @@ extern bool arch_memremap_can_ram_remap(resource_size_t offset, size_t size,
 static inline bool arm64_is_protected_mmio(phys_addr_t phys_addr, size_t size)
 {
 	if (unlikely(is_realm_world()))
-		return __arm64_is_protected_mmio(phys_addr, size);
+		return arm64_rsi_is_protected(phys_addr, size);
 	return false;
 }
 
diff --git a/arch/arm64/include/asm/rsi.h b/arch/arm64/include/asm/rsi.h
index b42aeac05340..88b50d660e85 100644
--- a/arch/arm64/include/asm/rsi.h
+++ b/arch/arm64/include/asm/rsi.h
@@ -16,7 +16,7 @@ DECLARE_STATIC_KEY_FALSE(rsi_present);
 
 void __init arm64_rsi_init(void);
 
-bool __arm64_is_protected_mmio(phys_addr_t base, size_t size);
+bool arm64_rsi_is_protected(phys_addr_t base, size_t size);
 
 static inline bool is_realm_world(void)
 {
diff --git a/arch/arm64/kernel/rsi.c b/arch/arm64/kernel/rsi.c
index ce4778141ec7..c64a06f58c0b 100644
--- a/arch/arm64/kernel/rsi.c
+++ b/arch/arm64/kernel/rsi.c
@@ -84,7 +84,25 @@ static void __init arm64_rsi_setup_memory(void)
 	}
 }
 
-bool __arm64_is_protected_mmio(phys_addr_t base, size_t size)
+/*
+ * Check if a given PA range is Trusted (e.g., Protected memory, a Trusted Device
+ * mapping, or an MMIO emulated in the Realm world).
+ *
+ * We can rely on the RIPAS value of the region to detect if a given region is
+ * protected.
+ *
+ *  RIPAS_DEV - A trusted device memory or a trusted emulated MMIO (in the Realm
+ *		world
+ *  RIPAS_RAM - Memory (RAM), protected by the RMM guarantees. (e.g., Firmware
+ *		reserved regions for data sharing).
+ *
+ *  RIPAS_DESTROYED is a special case of one of the above, where the host did
+ *  something without our permission and as such we can't do anything about it.
+ *
+ * The only case where something is emulated by the untrusted hypervisor or is
+ * backed by shared memory is indicated by RSI_RIPAS_EMPTY.
+ */
+bool arm64_rsi_is_protected(phys_addr_t base, size_t size)
 {
 	enum ripas ripas;
 	phys_addr_t end, top;
@@ -101,18 +119,18 @@ bool __arm64_is_protected_mmio(phys_addr_t base, size_t size)
 			break;
 		if (WARN_ON(top <= base))
 			break;
-		if (ripas != RSI_RIPAS_DEV)
+		if (ripas == RSI_RIPAS_EMPTY)
 			break;
 		base = top;
 	}
 
 	return base >= end;
 }
-EXPORT_SYMBOL(__arm64_is_protected_mmio);
+EXPORT_SYMBOL(arm64_rsi_is_protected);
 
 static int realm_ioremap_hook(phys_addr_t phys, size_t size, pgprot_t *prot)
 {
-	if (__arm64_is_protected_mmio(phys, size))
+	if (arm64_rsi_is_protected(phys, size))
 		*prot = pgprot_encrypted(*prot);
 	else
 		*prot = pgprot_decrypted(*prot);

---

## [3] Suzuki K Poulose — 2025-09-18
*Subject: [PATCH v3 2/3] arm64: Enable EFI secret area Securityfs support*

Enable EFI COCO secrets support. Provide the ioremap_encrypted() support required
by the driver.

Cc: Sami Mujawar <sami.mujawar@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Cc: Steven Price <steven.price@arm.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Tested-by: Sami Mujawar <sami.mujawar@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
 arch/arm64/include/asm/io.h          | 4 ++++
 drivers/virt/coco/efi_secret/Kconfig | 2 +-
 2 files changed, 5 insertions(+), 1 deletion(-)

diff --git a/arch/arm64/include/asm/io.h b/arch/arm64/include/asm/io.h
index 82276282a3c7..83e03abbb2ca 100644
--- a/arch/arm64/include/asm/io.h
+++ b/arch/arm64/include/asm/io.h
@@ -274,6 +274,10 @@ int arm64_ioremap_prot_hook_register(const ioremap_prot_hook_t hook);
 #define ioremap_np(addr, size)	\
 	ioremap_prot((addr), (size), __pgprot(PROT_DEVICE_nGnRnE))
 
+
+#define ioremap_encrypted(addr, size)	\
+	ioremap_prot((addr), (size), PAGE_KERNEL)
+
 /*
  * io{read,write}{16,32,64}be() macros
  */
diff --git a/drivers/virt/coco/efi_secret/Kconfig b/drivers/virt/coco/efi_secret/Kconfig
index 4404d198f3b2..94d88e5da707 100644
--- a/drivers/virt/coco/efi_secret/Kconfig
+++ b/drivers/virt/coco/efi_secret/Kconfig
@@ -1,7 +1,7 @@
 # SPDX-License-Identifier: GPL-2.0-only
 config EFI_SECRET
 	tristate "EFI secret area securityfs support"
-	depends on EFI && X86_64
+	depends on EFI && (X86_64 || ARM64)
 	select EFI_COCO_SECRET
 	select SECURITYFS
 	help

---

## [4] Suzuki K Poulose — 2025-09-18
*Subject: [PATCH v3 3/3] arm64: acpi: Enable ACPI CCEL support*

Add support for ACPI CCEL by handling the EfiACPIMemoryNVS type memory.
As per UEFI specifications NVS memory is reserved for Firmware use even
after exiting boot services. Thus map the region as read-only.

Cc: Sami Mujawar <sami.mujawar@arm.com>
Cc: Will Deacon <will@kernel.org>
Cc: Catalin Marinas <catalin.marinas@arm.com>
Cc: Aneesh Kumar K.V <aneesh.kumar@kernel.org>
Cc: Steven Price <steven.price@arm.com>
Cc: Sudeep Holla <sudeep.holla@arm.com>
Cc: Gavin Shan <gshan@redhat.com>
Reviewed-by: Gavin Shan <gshan@redhat.com>
Tested-by: Sami Mujawar <sami.mujawar@arm.com>
Signed-off-by: Suzuki K Poulose <suzuki.poulose@arm.com>
---
 arch/arm64/kernel/acpi.c | 10 ++++++++++
 1 file changed, 10 insertions(+)

diff --git a/arch/arm64/kernel/acpi.c b/arch/arm64/kernel/acpi.c
index 4d529ff7ba51..b3195b3b895f 100644
--- a/arch/arm64/kernel/acpi.c
+++ b/arch/arm64/kernel/acpi.c
@@ -357,6 +357,16 @@ void __iomem *acpi_os_ioremap(acpi_physical_address phys, acpi_size size)
 			 * as long as we take care not to create a writable
 			 * mapping for executable code.
 			 */
+			fallthrough;
+
+		case EFI_ACPI_MEMORY_NVS:
+			/*
+			 * ACPI NVS marks an area reserved for use by the
+			 * firmware, even after exiting the boot service.
+			 * This may be used by the firmware for sharing dynamic
+			 * tables/data (e.g., ACPI CCEL) with the OS. Map it
+			 * as read-only.
+			 */
 			prot = PAGE_KERNEL_RO;
 			break;

---

## [5] Will Deacon — 2025-09-19
*Subject: Re: [PATCH v3 0/3] arm64: realm: Add support for encrypted data from firmware*

On Thu, 18 Sep 2025 13:56:15 +0100, Suzuki K Poulose wrote:
> Confidential compute firmware may provide secret data via reserved memory regions
> (e.g., ACPI CCEL, EFI Coco secret area). These must be ioremap'ed() as encrypted.

Applied to arm64 (for-next/cca), thanks!

[1/3] arm64: realm: ioremap: Allow mapping memory as encrypted
      https://git.kernel.org/arm64/c/fa84e534c3ec
[2/3] arm64: Enable EFI secret area Securityfs support
      https://git.kernel.org/arm64/c/9e8a3df3e7f7
[3/3] arm64: acpi: Enable ACPI CCEL support
      https://git.kernel.org/arm64/c/d02c2e45b1e7

Cheers,

---

## [6] Mauro Carvalho Chehab — 2025-11-21
*Subject: [REGRESSION] GHES firmware can't be readonly - Was: Re: [PATCH v3
 3/3] arm64: acpi: Enable ACPI CCEL support*

Hi,

Em Thu, 18 Sep 2025 13:56:18 +0100
Suzuki K Poulose <suzuki.poulose@arm.com> escreveu:

> Add support for ACPI CCEL by handling the EfiACPIMemoryNVS type memory.
> As per UEFI specifications NVS memory is reserved for Firmware use even

Please revert this change.

Making area reserved to be used by firmware breaks some APEI 
notification mechanisms:

[    3.787189] {1}[Hardware Error]: Hardware error from APEI Generic Hardware Error Source: 1
[    3.787286] {1}[Hardware Error]: event severity: recoverable
[    3.787367] {1}[Hardware Error]:  Error 0, type: recoverable
[    3.787471] {1}[Hardware Error]:   section_type: ARM processor error
[    3.787520] {1}[Hardware Error]:   MIDR: 0x00000000000f0510
[    3.787555] {1}[Hardware Error]:   Multiprocessor Affinity Register (MPIDR): 0x0000000080000000
[    3.787577] {1}[Hardware Error]:   running state: 0x0
[    3.787591] {1}[Hardware Error]:   Power State Coordination Interface state: 0
[    3.787621] {1}[Hardware Error]:   Error info structure 0:
[    3.787635] {1}[Hardware Error]:   num errors: 2
[    3.787736] {1}[Hardware Error]:    error_type: 0x02: cache error
[    3.787760] {1}[Hardware Error]:    error_info: 0x000000000091000f
[    3.787795] {1}[Hardware Error]:     transaction type: Data Access
[    3.787823] {1}[Hardware Error]:     cache error, operation type: Data write
[    3.787851] {1}[Hardware Error]:     cache level: 2
[    3.787876] {1}[Hardware Error]:     processor context not corrupted
[    3.788666] [Firmware Warn]: GHES: Unhandled processor error type 0x02: cache error
[    3.789258] Unable to handle kernel write to read-only memory at virtual address ffff800080035018
[    3.789277] Mem abort info:
[    3.789289]   ESR = 0x000000009600004f
[    3.789324]   EC = 0x25: DABT (current EL), IL = 32 bits
[    3.789343]   SET = 0, FnV = 0
[    3.789358]   EA = 0, S1PTW = 0
[    3.789376]   FSC = 0x0f: level 3 permission fault
[    3.789396] Data abort info:
[    3.789411]   ISV = 0, ISS = 0x0000004f, ISS2 = 0x00000000
[    3.789427]   CM = 0, WnR = 1, TnD = 0, TagAccess = 0
[    3.789444]   GCS = 0, Overlay = 0, DirtyBit = 0, Xs = 0
[    3.789501] swapper pgtable: 4k pages, 52-bit VAs, pgdp=00000000505d7000
[    3.789524] [ffff800080035018] pgd=10000000510bc003, p4d=1000000100229403, pud=100000010022a403, pmd=100000010022b403, pte=0060000139b90483
[    3.789936] Internal error: Oops: 000000009600004f [#1]  SMP
[    3.798553] Modules linked in:
[    3.799147] CPU: 0 UID: 0 PID: 161 Comm: kworker/0:2 Not tainted 6.18.0-rc1-00016-g166324c9c7aa-dirty #46 PREEMPT 
[    3.799754] Hardware name: QEMU QEMU Virtual Machine, BIOS unknown 02/02/2022
[    3.800251] Workqueue: kacpi_notify acpi_os_execute_deferred
[    3.800928] pstate: 614020c5 (nZCv daIF +PAN -UAO -TCO +DIT -SSBS BTYPE=--)
[    3.801207] pc : acpi_os_write_memory+0x120/0x190
[    3.801415] lr : acpi_os_write_memory+0x2c/0x190
[    3.801577] sp : ffff800080a83b60
[    3.801748] x29: ffff800080a83b60 x28: ffff9f6c0f423a38 x27: ffff9f6c0d4e75b0
[    3.802080] x26: ffff9f6c0f7bd930 x25: ffff9f6c0f1dae70 x24: 0000000000000000
[    3.802369] x23: 0000000000000000 x22: ffff9f6c0e35acf8 x21: 0000000000000040
[    3.802641] x20: 0000000000000001 x19: 0000000139b90018 x18: 0000000000000010
[    3.802880] x17: 0000000000000000 x16: 0000000000000002 x15: 0000000000000020
[    3.803133] x14: 00000000ffffffff x13: 0000000000000030 x12: fff00000c09392a0
[    3.803422] x11: 0000000000000058 x10: 0000000000000018 x9 : ffff9f6c0d491634
[    3.803681] x8 : 0000000000000010 x7 : 0000000139b90018 x6 : ffff9f6c0f41b518
[    3.803925] x5 : 0000000139b91000 x4 : 0000000000000018 x3 : fff00000c09391e0
[    3.804176] x2 : 0000000000000040 x1 : 0000000000000008 x0 : ffff800080035018
[    3.804512] Call trace:
[    3.804715]  acpi_os_write_memory+0x120/0x190 (P)
[    3.804956]  apei_write+0xd0/0xf0
[    3.805112]  ghes_clear_estatus.part.0+0xc8/0xe0
[    3.805290]  ghes_proc+0xa4/0x220
[    3.805417]  ghes_notify_hed+0x5c/0xb8
[    3.805546]  notifier_call_chain+0x78/0x148
[    3.805746]  blocking_notifier_call_chain+0x4c/0x80
[    3.805945]  acpi_hed_notify+0x28/0x40
[    3.806082]  acpi_ev_notify_dispatch+0x50/0x80
[    3.806255]  acpi_os_execute_deferred+0x24/0x48
[    3.806446]  process_one_work+0x15c/0x3b0
[    3.806574]  worker_thread+0x2d0/0x400
[    3.806721]  kthread+0x148/0x228
[    3.806849]  ret_from_fork+0x10/0x20
[    3.807114] Code: 17ffffeb 710102bf 54000341 d50332bf (f9000014) 
[    3.807504] ---[ end trace 0000000000000000 ]---
[    4.116196] note: kworker/0:2[161] exited with irqs disabled
[    4.116700] note: kworker/0:2[161] exited with preempt_count 1

The problem happens when APEI tries to notify the firmware that a GPIO
notification was accepted by writing a value at the read_ack_register:

	(gdb) list *ghes_clear_estatus+0xc8
	0xffff800080945b90 is in ghes_clear_estatus (../drivers/acpi/apei/ghes.c:264).
	259                     return;
	260
	261             val &= gv2->read_ack_preserve << gv2->read_ack_register.bit_offset;
	262             val |= gv2->read_ack_write    << gv2->read_ack_register.bit_offset;
	263
	264             apei_write(val, &gv2->read_ack_register);
	265     }
	266
	267     static struct ghes *ghes_new(struct acpi_hest_generic *generic)
	268     {

-

You can reproduce it with QEMU v10.2.0-rc1:

    qemu-system-aarch64 -bios ../emulator/QEMU_EFI-silent.fd \
    --nographic -monitor telnet:127.0.0.1:1234,server,nowait -m \
    4g,maxmem=8G,slots=8 -no-reboot -device pcie-root-port,id=root_port1 -device \
    virtio-blk-pci,drive=hd -device virtio-net-pci,netdev=mynet,id=bob -object \
    memory-backend-ram,size=4G,id=mem0 -netdev \
    type=user,id=mynet,hostfwd=tcp::5555-:22 -qmp \
    tcp:localhost:4445,server=on,wait=off -M virt,nvdimm=on,ras=on -cpu max -smp \
    4 -numa node,nodeid=0,cpus=0-3,memdev=mem0 -kernel \
    ../work/arm64_build/arch/arm64/boot/Image.gz -append \
    "earlycon nomodeset root=/dev/vda1 fsck.mode=skip tp_printk maxcpus=4" \
    -drive if=none,file=../emulator/debian.qcow2,format=qcow2,id=hd

using:

	scripts/ghes_inject.py arm

Kernel 6.17 is not affected. The problem happens after 6.18-rc1.

Thanks,
Mauro

---

## [7] Suzuki K Poulose — 2025-11-24
*Subject: Re: [REGRESSION] GHES firmware can't be readonly - Was: Re: [PATCH v3
 3/3] arm64: acpi: Enable ACPI CCEL support*

On 21/11/2025 21:46, Mauro Carvalho Chehab wrote:
> Hi,
> 

Thanks for the report. Clearly, we missed this case. I am happy for this
patch to be reverted and we can work out the handling of NVS later.

We had this as PAGE_KERNEL in the first version, and "tightened to RO".

Pardon my ignorance, but the ACPI specifications say,
EFI_ACPI_MEMORY_NVS regions are reserved for the Firmware as noted in
(linked in cover letter) [1].

Is this a standard practise to write to NVS across the architectures ?
I could see that x86 marks it as PAGE_KERNEL (but didn't really see
why). I could use the reference to fix this. Also, are you able to
dump the attributes for the region from the EFI memory map ?

Kind regards
Suzuki

[1] 
https://uefi.org/specs/UEFI/2.10/07_Services_Boot_Services.html#memory-type-usage-before-exitbootservices


> 
> [    3.787189] {1}[Hardware Error]: Hardware error from APEI Generic Hardware Error Source: 1

---

## [8] Mauro Carvalho Chehab — 2025-11-24
*Subject: Re: [REGRESSION] GHES firmware can't be readonly - Was: Re: [PATCH
 v3 3/3] arm64: acpi: Enable ACPI CCEL support*

Em Mon, 24 Nov 2025 05:21:00 +0000
Suzuki K Poulose <suzuki.poulose@arm.com> escreveu:

> On 21/11/2025 21:46, Mauro Carvalho Chehab wrote:
> > Hi,

Hi Susuki,

Not sure if this is broken or not on x86, as I don't have any code
yet to test APEI implementation on x86.

The problem here is related to GHESv2 spec:

	https://uefi.org/specs/ACPI/6.5/18_Platform_Error_Interfaces.html#generic-hardware-error-source-version-2-ghesv2-structure

As you can see there, GHESv2 BIOS has a "Read Ack register". Such registers
are inside the firmware memory, inside the HEST table.

As described there:

	"This field specifies the location of the Read Ack Register used to 
	 notify the RAS controller that OSPM has processed the Error Status
	 Block. The OSPM writes the bit(s) specified in Read Ack Write, 
	 while preserving the bit(s) specified in Read Ack Preserve."

The HEST table basically contains a data structure which is used by
the BIOS to report errors. As it is inside the firmware allocated memory,
so it should be marked as EfiACPIMemoryNVS.

If it contains GHESv2, one of the fields inside the records is a pointer to
the Read Ack Register. It is placed elsewhere, but its location is also 
marked as EfiACPIMemoryNVS, as it is a firmware file. So, also marked
as EfiACPIMemoryNVS.

When a hardware error is detected, the firmware fills the HEST table
and notifies the OSPM. For GHESv2, the notification is asynchronous
(typically using GED on ARM). As the BIOS needs to wait for the OSPM to 
handle before re-using the memory region to report new errors, it writes
zero to the Read Ack Register.

When the OSPM handles the error, it writes one to it, allowing the
BIOS to re-use the GHESv2 memory region to report a new error.

So, for GHESv2 to work, Linux has to mark the Read Ack Registers
as R/W - or the entire pages where they're contained(*).

(*) The spec allows multiple GHESv2 records, so one may have multiple
    GHESv2 Read Ack Registers.

In the specific case of the QEMU implementation, the HEST table is
placed together with other ACPI tables like DSDT, but we place the
actual error records and the read ack registers are stored on a separate
firmware file.

You can see its current mapping at:

	https://github.com/qemu/qemu/blob/master/docs/specs/acpi_hest_ghes.rst

> Also, are you able to dump the attributes for the region from the EFI memory map ?

This is the dump for the HEST table:

/*
 * Intel ACPI Component Architecture
 * AML/ASL+ Disassembler version 20240927 (64-bit version)
 * Copyright (c) 2000 - 2023 Intel Corporation
 * 
 * Disassembly of hest.dat
 *
 * ACPI Data Table [HEST]
 *
 * Format: [HexOffset DecimalOffset ByteLength]  FieldName : FieldValue (in hex)
 */

[000h 0000 004h]                   Signature : "HEST"    [Hardware Error Source 
Table]
[004h 0004 004h]                Table Length : 000000E0
[008h 0008 001h]                    Revision : 01
[009h 0009 001h]                    Checksum : E4
[00Ah 0010 006h]                      Oem ID : "BOCHS "
[010h 0016 008h]                Oem Table ID : "BXPC    "
[018h 0024 004h]                Oem Revision : 00000001
[01Ch 0028 004h]             Asl Compiler ID : "BXPC"
[020h 0032 004h]       Asl Compiler Revision : 00000001

[024h 0036 004h]          Error Source Count : 00000002

[028h 0040 002h]               Subtable Type : 000A [Generic Hardware Error Sour
ce V2]
[02Ah 0042 002h]                   Source Id : 0000
[02Ch 0044 002h]           Related Source Id : FFFF
[02Eh 0046 001h]                    Reserved : 00
[02Fh 0047 001h]                     Enabled : 01
[030h 0048 004h]      Records To Preallocate : 00000001
[034h 0052 004h]     Max Sections Per Record : 00000001
[038h 0056 004h]         Max Raw Data Length : 00001000

[03Ch 0060 00Ch]        Error Status Address : [Generic Address Structure]
[03Ch 0060 001h]                    Space ID : 00 [SystemMemory]
[03Dh 0061 001h]                   Bit Width : 40
[03Eh 0062 001h]                  Bit Offset : 00
[03Fh 0063 001h]        Encoded Access Width : 04 [QWord Access:64]
[040h 0064 008h]                     Address : 0000000139B90000

[048h 0072 01Ch]                      Notify : [Hardware Error Notification Stru
cture]
[048h 0072 001h]                 Notify Type : 08 [SEA]
[049h 0073 001h]               Notify Length : 1C
[04Ah 0074 002h]  Configuration Write Enable : 0000
[04Ch 0076 004h]                PollInterval : 00000000
[050h 0080 004h]                      Vector : 00000000
[054h 0084 004h]     Polling Threshold Value : 00000000
[058h 0088 004h]    Polling Threshold Window : 00000000
[05Ch 0092 004h]       Error Threshold Value : 00000000
[060h 0096 004h]      Error Threshold Window : 00000000

[064h 0100 004h]   Error Status Block Length : 00001000
[068h 0104 00Ch]           Read Ack Register : [Generic Address Structure]
[068h 0104 001h]                    Space ID : 00 [SystemMemory]
[069h 0105 001h]                   Bit Width : 40
[06Ah 0106 001h]                  Bit Offset : 00
[06Bh 0107 001h]        Encoded Access Width : 04 [QWord Access:64]
[06Ch 0108 008h]                     Address : 0000000139B90010

[074h 0116 008h]           Read Ack Preserve : FFFFFFFFFFFFFFFE
[07Ch 0124 008h]              Read Ack Write : 0000000000000001

[084h 0132 002h]               Subtable Type : 000A [Generic Hardware Error Sour
ce V2]
[086h 0134 002h]                   Source Id : 0001
[088h 0136 002h]           Related Source Id : FFFF
[08Ah 0138 001h]                    Reserved : 00
[08Bh 0139 001h]                     Enabled : 01
[08Ch 0140 004h]      Records To Preallocate : 00000001
[090h 0144 004h]     Max Sections Per Record : 00000001
[094h 0148 004h]         Max Raw Data Length : 00001000

[098h 0152 00Ch]        Error Status Address : [Generic Address Structure]
[098h 0152 001h]                    Space ID : 00 [SystemMemory]
[099h 0153 001h]                   Bit Width : 40
[09Ah 0154 001h]                  Bit Offset : 00
[09Bh 0155 001h]        Encoded Access Width : 04 [QWord Access:64]
[09Ch 0156 008h]                     Address : 0000000139B90008

[0A4h 0164 01Ch]                      Notify : [Hardware Error Notification Stru
cture]
[0A4h 0164 001h]                 Notify Type : 07 [GPIO]
[0A5h 0165 001h]               Notify Length : 1C
[0A6h 0166 002h]  Configuration Write Enable : 0000
[0A8h 0168 004h]                PollInterval : 00000000
[0ACh 0172 004h]                      Vector : 00000000
[0B0h 0176 004h]     Polling Threshold Value : 00000000
[0B4h 0180 004h]    Polling Threshold Window : 00000000
[0B8h 0184 004h]       Error Threshold Value : 00000000
[0BCh 0188 004h]      Error Threshold Window : 00000000

[0C0h 0192 004h]   Error Status Block Length : 00001000
[0C4h 0196 00Ch]           Read Ack Register : [Generic Address Structure]
[0C4h 0196 001h]                    Space ID : 00 [SystemMemory]
[0C5h 0197 001h]                   Bit Width : 40
[0C6h 0198 001h]                  Bit Offset : 00
[0C7h 0199 001h]        Encoded Access Width : 04 [QWord Access:64]
[0C8h 0200 008h]                     Address : 0000000139B90018

[0D0h 0208 008h]           Read Ack Preserve : FFFFFFFFFFFFFFFE
[0D8h 0216 008h]              Read Ack Write : 0000000000000001

Raw Table Data: Length 224 (0xE0)

    0000: 48 45 53 54 E0 00 00 00 01 E4 42 4F 43 48 53 20  // HEST......BOCHS 
    0010: 42 58 50 43 20 20 20 20 01 00 00 00 42 58 50 43  // BXPC    ....BXPC
    0020: 01 00 00 00 02 00 00 00 0A 00 00 00 FF FF 00 01  // ................
    0030: 01 00 00 00 01 00 00 00 00 10 00 00 00 40 00 04  // .............@..
    0040: 00 00 B9 39 01 00 00 00 08 1C 00 00 00 00 00 00  // ...9............
    0050: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  // ................
    0060: 00 00 00 00 00 10 00 00 00 40 00 04 10 00 B9 39  // .........@.....9
    0070: 01 00 00 00 FE FF FF FF FF FF FF FF 01 00 00 00  // ................
    0080: 00 00 00 00 0A 00 01 00 FF FF 00 01 01 00 00 00  // ................
    0090: 01 00 00 00 00 10 00 00 00 40 00 04 08 00 B9 39  // .........@.....9
    00A0: 01 00 00 00 07 1C 00 00 00 00 00 00 00 00 00 00  // ................
    00B0: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  // ................
    00C0: 00 10 00 00 00 40 00 04 18 00 B9 39 01 00 00 00  // .....@.....9....
    00D0: FE FF FF FF FF FF FF FF 01 00 00 00 00 00 00 00  // ................

I hope that helps.

Regards,
Mauro
 
> Kind regards
> Suzuki



Thanks,
Mauro

---

## [9] Will Deacon — 2025-11-24
*Subject: Re: [REGRESSION] GHES firmware can't be readonly - Was: Re: [PATCH
 v3 3/3] arm64: acpi: Enable ACPI CCEL support*

On Mon, Nov 24, 2025 at 05:21:00AM +0000, Suzuki K Poulose wrote:
> On 21/11/2025 21:46, Mauro Carvalho Chehab wrote:
> > Hi,

I'll revert the change shortly.

Will

---
