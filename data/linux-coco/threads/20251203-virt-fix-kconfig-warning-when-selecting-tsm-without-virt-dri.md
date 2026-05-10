---
title: 'virt: Fix Kconfig warning when selecting TSM without\n VIRT_DRIVERS'
date: 2025-12-03
last_reply: 2025-12-04
message_count: 2
participants: ['Nathan Chancellor', 'dan.j.williams@intel.com']
---

## [1] Nathan Chancellor — 2025-12-03

After commit 3225f52cde56 ("PCI/TSM: Establish Secure Sessions and Link
Encryption"), there is a Kconfig warning when selecting CONFIG_TSM
without CONFIG_VIRT_DRIVERS:

  WARNING: unmet direct dependencies detected for TSM
    Depends on [n]: VIRT_DRIVERS [=n]
    Selected by [y]:
    - PCI_TSM [=y] && PCI [=y]

CONFIG_TSM is defined in drivers/virt/coco/Kconfig but this Kconfig is
only sourced when CONFIG_VIRT_DRIVERS is enabled. Since this symbol is
hidden with no dependencies, it should be available without a symbol
that just enables a menu.

Move the sourcing of drivers/virt/coco/Kconfig outside of
CONFIG_VIRT_DRIVERS and wrap the other source statements in
drivers/virt/coco/Kconfig with CONFIG_VIRT_DRIVERS to ensure users do
not get any additional prompts while ensuring CONFIG_TSM is always
available to select. This complements commit 110c155e8a68 ("drivers/virt:
Drop VIRT_DRIVERS build dependency"), which addressed the build issue
that this Kconfig warning was pointing out.

Fixes: 3225f52cde56 ("PCI/TSM: Establish Secure Sessions and Link Encryption")
Reported-by: kernel test robot <lkp@intel.com>
Closes: https://lore.kernel.org/oe-kbuild-all/202511140712.NubhamPy-lkp@intel.com/
Signed-off-by: Nathan Chancellor <nathan@kernel.org>
---
 drivers/virt/Kconfig      | 4 ++--
 drivers/virt/coco/Kconfig | 2 ++
 2 files changed, 4 insertions(+), 2 deletions(-)

diff --git a/drivers/virt/Kconfig b/drivers/virt/Kconfig
index d8c848cf09a6..52eb7e4ba71f 100644
--- a/drivers/virt/Kconfig
+++ b/drivers/virt/Kconfig
@@ -47,6 +47,6 @@ source "drivers/virt/nitro_enclaves/Kconfig"
 
 source "drivers/virt/acrn/Kconfig"
 
-source "drivers/virt/coco/Kconfig"
-
 endif
+
+source "drivers/virt/coco/Kconfig"
diff --git a/drivers/virt/coco/Kconfig b/drivers/virt/coco/Kconfig
index bb0c6d6ddcc8..df1cfaf26c65 100644
--- a/drivers/virt/coco/Kconfig
+++ b/drivers/virt/coco/Kconfig
@@ -3,6 +3,7 @@
 # Confidential computing related collateral
 #
 
+if VIRT_DRIVERS
 source "drivers/virt/coco/efi_secret/Kconfig"
 
 source "drivers/virt/coco/pkvm-guest/Kconfig"
@@ -14,6 +15,7 @@ source "drivers/virt/coco/tdx-guest/Kconfig"
 source "drivers/virt/coco/arm-cca-guest/Kconfig"
 
 source "drivers/virt/coco/guest/Kconfig"
+endif
 
 config TSM
 	bool

---
base-commit: 4be423572da1f4c11f45168e3fafda870ddac9f8
change-id: 20251203-fix-pci-tsm-select-tsm-warning-5dd724dc74e0

Best regards,
--  
Nathan Chancellor <nathan@kernel.org>

---

## [2] dan.j.williams@intel.com — 2025-12-04
*Subject: Re: [PATCH] virt: Fix Kconfig warning when selecting TSM without
 VIRT_DRIVERS*

Nathan Chancellor wrote:
> After commit 3225f52cde56 ("PCI/TSM: Establish Secure Sessions and Link
> Encryption"), there is a Kconfig warning when selecting CONFIG_TSM

This looks good to me Nathan, thanks. I will include it for the v6.19 update.

---
