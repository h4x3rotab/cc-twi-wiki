---
title: 'crypto/ccp: Fix CONFIG_PCI=n build'
date: 2025-12-02
last_reply: 2025-12-05
message_count: 3
participants: ['Dan Williams', 'Alexey Kardashevskiy', 'Tom Lendacky']
---

## [1] Dan Williams — 2025-12-02

It turns out that the PCI driver for ccp is unconditionally built into the
kernel in the CONFIG_PCI=y case. This means that the new SEV-TIO support
needs an explicit dependency on PCI to avoid build errors when
CONFIG_CRYPTO_DEV_SP_PSP=y and CONFIG_PCI=n.

Reported-by: kernel test robot <lkp@intel.com>
Closes: http://lore.kernel.org/202512030743.6pVPA4sx-lkp@intel.com
Cc: Alexey Kardashevskiy <aik@amd.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Cc: John Allen <john.allen@amd.com>
Signed-off-by: Dan Williams <dan.j.williams@intel.com>
---
 drivers/crypto/ccp/Kconfig | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/drivers/crypto/ccp/Kconfig b/drivers/crypto/ccp/Kconfig
index e2b127f0986b..f16a0f611317 100644
--- a/drivers/crypto/ccp/Kconfig
+++ b/drivers/crypto/ccp/Kconfig
@@ -39,7 +39,7 @@ config CRYPTO_DEV_SP_PSP
 	bool "Platform Security Processor (PSP) device"
 	default y
 	depends on CRYPTO_DEV_CCP_DD && X86_64 && AMD_IOMMU
-	select PCI_TSM
+	select PCI_TSM if PCI
 	help
 	 Provide support for the AMD Platform Security Processor (PSP).
 	 The PSP is a dedicated processor that provides support for key

base-commit: f7ae6d4ec6520a901787cbab273983e96d8516da
prerequisite-patch-id: 085ed7fc143cfcfd0418527cfad03db88d4b64ec
prerequisite-patch-id: c1d1a6d802b3b4bfffb9f45fc5ac6a9a1b5e361d
prerequisite-patch-id: 44c6ea6fb683418ae67ff3efdb0c07fda013e6b2
prerequisite-patch-id: 407daf59d54ecebcb7fefd22a5b5833e03c038e4

---

## [2] Alexey Kardashevskiy — 2025-12-04
*Subject: Re: [PATCH] crypto/ccp: Fix CONFIG_PCI=n build*

On 3/12/25 14:19, Dan Williams wrote:
> It turns out that the PCI driver for ccp is unconditionally built into the
> kernel in the CONFIG_PCI=y case. This means that the new SEV-TIO support

Acked-by: Alexey Kardashevskiy <aik@amd.com>

>   	help
>   	 Provide support for the AMD Platform Security Processor (PSP).

oh it can do this too now, cool :) Thanks,

---

## [3] Tom Lendacky — 2025-12-05
*Subject: Re: [PATCH] crypto/ccp: Fix CONFIG_PCI=n build*

On 12/2/25 21:19, Dan Williams wrote:
> It turns out that the PCI driver for ccp is unconditionally built into the
> kernel in the CONFIG_PCI=y case. This means that the new SEV-TIO support

Acked-by: Tom Lendacky <thomas.lendacky@amd.com>

> ---
>  drivers/crypto/ccp/Kconfig | 2 +-

---
