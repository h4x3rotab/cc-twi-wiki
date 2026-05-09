---
title: 'x86/virt/tdx: accurately distinguishes TDX module loading situations'
date: 2024-06-23
last_reply: 2024-07-19
message_count: 4
participants: ['Jun Miao', 'Kirill A. Shutemov', 'Huang, Kai']
---

## [1] Jun Miao — 2024-06-23

The first SEAMCALL is important to response the state of TDX Module/BIOS.

In actual incorrect BIOS setup or deployment, the sysinit_ret will be
-EOPNOTSUPP. But the message "module not loaded" isn`t enough to describe
the accurate loading situation when module loaded but SEAMCALL failed
for some BIOS wrong setting. So add the error return operation code number.

Signed-off-by: Jun Miao <jun.miao@intel.com>
---
 arch/x86/virt/vmx/tdx/tdx.c | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 4e2b2e2ac9f9..787dfaf44036 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -122,10 +122,14 @@ static int try_init_module_global(void)
 	/*
 	 * The first SEAMCALL also detects the TDX module, thus
 	 * it can fail due to the TDX module is not loaded.
-	 * Dump message to let the user know.
+	 * Dump more detailed message to let the user know.
 	 */
 	if (sysinit_ret == -ENODEV)
 		pr_err("module not loaded\n");
+	else if (sysinit_ret)
+		pr_warn("module loaded error ret=%d\n",sysinit_ret);
+	else
+		pr_info("module loaded\n");
 
 	sysinit_done = true;
 out:

---

## [2] Kirill A. Shutemov — 2024-06-24
*Subject: Re: [PATCH] x86/virt/tdx: accurately distinguishes TDX module
 loading situations*

On Sun, Jun 23, 2024 at 01:50:37AM +0800, Jun Miao wrote:
> The first SEAMCALL is important to response the state of TDX Module/BIOS.
> 

Do you want to actually check for EOPNOTSUPP and print a
user-understandable message for it?

> Signed-off-by: Jun Miao <jun.miao@intel.com>
> ---

s/loaded/load/

> +	else
> +		pr_info("module loaded\n");

---

## [3] Jun Miao — 2024-06-29
*Subject: Re: [PATCH] x86/virt/tdx: accurately distinguishes TDX module loading
 situations*

On 6/24/24 19:26, Kirill A. Shutemov wrote:
> On Sun, Jun 23, 2024 at 01:50:37AM +0800, Jun Miao wrote:
>> The first SEAMCALL is important to response the state of TDX Module/BIOS.

It`s like this: I am a customer service support engineer, I awlays 
deploy TDX on site such as ByteDance/meituan
TDX is not simple but full stack.If boot up a TD guest, the follwing 
three requirements must be met:
     - The IFWI includes the correct seamldr and module in the BIOS, as 
the same time have the ability to load the TDX module.
     - Setting the TDX series of options, such as TME/SGX in the bios.
     - At last, loading the kernel, check if it can be boot with below 
demsg(when loaded successfully)

dmesg | grep - i tdx
[0.303913] virt/tdx: BIOS enabled: private KeyID range [64, 128)
[0.303916] virt/tdx: Disable Kexec. Turn off TDX in the BIOS to use KEXEC.
[0.303918] virt/tdx: Disable ACPI S3. Turn off TDX in the BIOS to use 
ACPI S3.
[4.846924] usb usb1: Manufacturer: Linux 6.6.0-tdx.1.0.v1 xhci-hcd
[4.847748] usb usb2: Manufacturer: Linux 6.6.0-tdx.1.0.v1 xhci-hcd
[6.577811] BOOT_IMAGE=(hd0,gpt2)/vmlinuz-6.6.0-tdx.1.0.v1
[17.723174] virt/tdx: 1575964 KB? allocated for PAMT
[17.723185] virt/tdx: module initialized

But this time,? It took a lot of effort to find the SEAMLDR.bin loading 
failed, since enable the bios debug need OEM cooperation
Got the bios log below as:

[TdxDxe]: [TDX_LATE-HANDLE_SEAMLDR] LoadTdxSeamldr BEGIN FATAL ERROR - 
RaiseTpl withOldTpl(0x1F) > NewTpl(0x10) ASSERT 
[DxeCore]e:\w\r\MdeModulePkg\Core\Dxe\Event\Tpl.c(66): ((BOOLEAN)(0==1))

[TdxDxe]: [TDX_LATE-HANDLE_SEAMLDR LoadTdxSeamldr END (Load Error)

But In the kernel, there is too little log message to find the error 
like this(loading failed):
dmesg | grep - i tdx
[0.303913] virt/tdx: BIOS enabled: private KeyID range [64, 
128)[0.303916] virt/tdx: Disable Kexec. Turn off TDX in the BIOS to use 
KEXEC.
[0.303918] virt/tdx: Disable ACPI S3. Turn off TDX in the BIOS to use 
ACPI S3.

I add the printk in the kernel and find the sysinit_ret = -19 = -EOPNOTSUPP
 From the current logic,? no ¡°module not loaded¡± always meaning module 
loaded.? But in fact, sysinit_ret is -EOPNOTSUPP(-19).
I will believe the module block at next seamcall: TDH_SYS_LP_INIT, which 
is misleading.

 >    if (sysinit_ret == -ENODEV)
 >    pr_err("module not loaded\n");
... ...
 >    ret = seamcall_prerr(TDH_SYS_LP_INIT,&args);?? ?

However I also use the old bkc kernel, there is a useful message to find 
such issues.¡± SEAMRR is not enabled by BIOS¡± to remind me where the 
problem lies.
In order to more accurately find the problems, add some printing 
reminders here will help the On site deployment engineer like me. ?

The story is a bit long. Thank you again for reading it over. Looking 
forward to your suggestions.

---
Jun Miao


>
>> Signed-off-by: Jun Miao <jun.miao@intel.com>

---

## [4] Huang, Kai — 2024-07-19
*Subject: Re: [PATCH] x86/virt/tdx: accurately distinguishes TDX module loading
 situations*

On Sun, 2024-06-23 at 01:50 +0800, Jun Miao wrote:
> The first SEAMCALL is important to response the state of TDX Module/BIOS.
> 

(firstly, please CC me in the future, and please also CC x86 maintainers,
x86@kernel.org, and linux-kernel@vger.kernel.org). 

So this is the case where TDX is detected as enabled by the kernel (TDX KeyID
reports valid info), but TDX actually isn't enabled by the BIOS.

This seems BIOS bug to me.  The BIOS should never report valid TDX KeyID if TDX
isn't enabled.  I guess it happens on development machines, but I am not sure
whether the production machine would fix this.

Anyway ...

> 
> Signed-off-by: Jun Miao <jun.miao@intel.com>

... printing the error code won't help user a lot since it is not obvious to the
user.  I think we can do something below.

Hi Dave/Kirill,

Any comments?

diff --git a/arch/x86/virt/vmx/tdx/tdx.c b/arch/x86/virt/vmx/tdx/tdx.c
index 49a1c6890b55..a8c273cfe17e 100644
--- a/arch/x86/virt/vmx/tdx/tdx.c
+++ b/arch/x86/virt/vmx/tdx/tdx.c
@@ -119,13 +119,35 @@ static int try_init_module_global(void)
        args.rcx = 0;
        sysinit_ret = seamcall_prerr(TDH_SYS_INIT, &args);
 
-       /*
-        * The first SEAMCALL also detects the TDX module, thus
-        * it can fail due to the TDX module is not loaded.
-        * Dump message to let the user know.
-        */
-       if (sysinit_ret == -ENODEV)
+       switch (sysinit_ret) {
+       case -ENODEV:
+               /*
+                * The first SEAMCALL also detects the TDX module,
+                * thus it can fail due to the TDX module is not
+                * loaded.  Dump message to let the user know.
+                */
                pr_err("module not loaded\n");
+               break;
+       case -EOPNOTSUPP:
+               /*
+                * Some TDX-capable development machines may report
+                * valid TDX KeyID when TDX is actually not enabled
+                * by the BIOS (e.g., due to BIOS misconfiguration).
+                * Let the user know.
+                */
+               pr_err("[BIOS bug]: TDX isn't enabled.\n");
+               break;
+       case -EACCES:
+               /*
+                * -EACCES happens when this is called when CPU is
+                * not in post-VMXON state.  It's kernel issue, so
+                * don't dump error message.
+                */
+               break;
+       default:
+               /* Actual SEAMCALL failure, message already printed */
+               break;
+       }
 
        sysinit_done = true;
 out:

---
