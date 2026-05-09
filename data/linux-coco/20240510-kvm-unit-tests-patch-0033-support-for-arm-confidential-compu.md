---
title: '[kvm-unit-tests PATCH 00/33] Support for Arm Confidential\n Compute Architecture'
date: 2024-05-10
last_reply: 2024-06-03
message_count: 4
participants: ['Andrew Jones', 'Suzuki K Poulose', 'Matias Ezequiel Vara Larsen']
---

## [1] Andrew Jones — 2024-05-10

On Fri, Apr 12, 2024 at 11:33:35AM GMT, Suzuki K Poulose wrote:
> This series adds support for running the kvm-unit-tests in the Arm CCA reference
> software architecture.

Queued patches 1-3 and 16-18 (modified 18 to drop references to realms
since it's independent of realms). Also fixed EFI compile errors with
"arm64: Expand SMCCC arguments and return values" and "arm: Detect FDT overlap
with uninitialised data"

https://gitlab.com/jones-drew/kvm-unit-tests/-/commits/arm/queue?ref_type=heads

Thanks,
drew

---

## [2] Andrew Jones — 2024-05-10
*Subject: Re: [kvm-unit-tests PATCH 18/33] arm: realm: Add test for FPU/SIMD
 context save/restore*

On Fri, Apr 12, 2024 at 11:33:53AM GMT, Suzuki K Poulose wrote:
> From: Subhasish Ghosh <subhasish.ghosh@arm.com>
> 

When I build and run this test with EFI I get an SVE exception.

./configure --arch=arm64 --cross-prefix=aarch64-linux-gnu- --enable-efi --enable-efi-direct
qemu-system-aarch64 -nodefaults \
	-machine virt -accel tcg -cpu max \
	-display none -serial stdio \
	-kernel arm/fpu.efi -append fpu.efi \
	-bios /usr/share/edk2/aarch64/QEMU_EFI.silent.fd \
	-smp 2 -machine acpi=off

UEFI firmware (version edk2-20230524-3.fc38 built at 00:00:00 on Jun 26 2023)
...

Address of image is: 0x43cfd000
PASS: fpu: FPU/SIMD register save/restore mask: 0xffffffff
PASS: fpu: FPU/SIMD register save/restore mask: 0xffffffff
Load address: 43cfd000
PC: 43d0b4e4 PC offset: e4e4
Unhandled exception ec=0x19 (SVE)
Vector: 4 (el1h_sync)
ESR_EL1:         66000000, ec=0x19 (SVE)
FAR_EL1: 0000000000000000 (not valid)
Exception frame registers:
pc : [<0000000043d0b4e4>] lr : [<0000000043d0b4d8>] pstate: 000002c5
sp : 0000000043d2bec0
x29: 0000000043d2bec0 x28: 0000000043d2bf58 
x27: 0000000043d2bf60 x26: 0000000043d2bf68 
x25: 0000000043d2bf70 x24: 8000000000000002 
x23: 0000000043d2bf88 x22: 0000000000000000 
x21: 000000004661b898 x20: 0000000043d2bfa8 
x19: 0000000043d38e60 x18: 0000000000000000 
x17: 00000000ffffa6ab x16: 0000000043d07780 
x15: 0000000000000000 x14: 0000000000000010 
x13: 0000000043d0d4b0 x12: 000000000000000f 
x11: 0000000000000004 x10: 0000000000000066 
x9 : 0000000000000066 x8 : 0000000043d3abf0 
x7 : 0000000000000080 x6 : 0000000000000040 
x5 : 0000000000003bce x4 : 0000000000043cfd 
x3 : 0000000040101000 x2 : 0000000000040105 
x1 : 0000000000000040 x0 : 1301001120110022 

	STACK: @e4e4 752c 1050

EXIT: STATUS=127


Thanks,
drew

---

## [3] Suzuki K Poulose — 2024-05-14
*Subject: Re: [kvm-unit-tests PATCH 18/33] arm: realm: Add test for FPU/SIMD
 context save/restore*

Hi,

On 10/05/2024 16:28, Andrew Jones wrote:
> On Fri, Apr 12, 2024 at 11:33:53AM GMT, Suzuki K Poulose wrote:
>> From: Subhasish Ghosh <subhasish.ghosh@arm.com>

Thanks for the report. We will take look.

Suzuki


> 
>

---

## [4] Matias Ezequiel Vara Larsen — 2024-06-03

Hello,

I tried this series by using kvmtool[1] and Linux/KVM with series "[v2]
Support for Arm CCA VMs on Linux". To try it, I ran "run-realm-tests" in
the FVP model. All tests seem to have passed successfully.

Tested-by: Matias Ezequiel Vara Larsen <mvaralar@redhat.com>

[1] https://gitlab.arm.com/linux-arm/kvmtool-cca cca/v2

On Fri, Apr 12, 2024 at 11:33:35AM +0100, Suzuki K Poulose wrote:
> This series adds support for running the kvm-unit-tests in the Arm CCA reference
> software architecture.

---
