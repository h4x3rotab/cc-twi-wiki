---
title: '[BUG] x86/tdx: handle_in()/handle_out() use one-bit-too-wide GENMASK\n for port I/O'
date: 2026-03-31
last_reply: 2026-03-31
message_count: 1
participants: ['Borys Tsyrulnikov']
---

## [1] Borys Tsyrulnikov — 2026-03-31

handle_in() and handle_out() in arch/x86/coco/tdx/tdx.c use:

    u64 mask = GENMASK(BITS_PER_BYTE * size, 0);

GENMASK(h, l) includes bit h. For size=1 (INB), this produces
GENMASK(8, 0) = 0x1FF (9 bits) instead of GENMASK(7, 0) = 0xFF (8
bits). The mask is one bit too wide for all I/O sizes:

    size=1 (INB): GENMASK(8,0)  = 0x1FF       vs correct 0xFF
(extra: bit 8)
    size=2 (INW): GENMASK(16,0) = 0x1FFFF     vs correct 0xFFFF
(extra: bit 16)
    size=4 (INL): GENMASK(32,0) = 0x1FFFFFFFF vs correct 0xFFFFFFFF
(extra: bit 32)

In handle_in(), this causes the VMM response's extra bit to overwrite
one bit of RAX that should be preserved. For INB, bit 8 (AH bit 0) is
overwritten from the VMM response instead of being preserved from the
guest's prior AX. On native x86, INB only modifies AL -- AH is
preserved.

In handle_out(), one extra bit of regs->ax is sent to the VMM beyond
what the I/O width requires.

I did not find a broad exploit in common kernel callers under tested
GCC/Clang toolchains, because many typed u8/u16/u32 paths naturally
truncate or zero-extend the value before reuse. That is not a full
non-exploitability proof, though: some ordinary in-tree caller shapes
may still preserve the primitive, especially read/test/write-back
sequences such as inl(...) followed by a branch and outl(same_value,
...), or inb(...) followed by if (v) outb(v, ...). I am therefore
treating this as a correctness bug in the #VE emulation path with
guest-config-
dependent leak potential, not as a proven broad exploit.

Expected vs observed (INB, size=1)
----------------------------------

Native x86 INB: writes AL (bits 0-7). AH (bit 8+) is preserved.

TDX handle_in() with buggy mask: clears bits 0-8, then sets bits 0-8
from VMM response. AH bit 0 depends on VMM, not the guest's prior AX.

Live reproduction
-----------------

GCP c3-standard-4 Confidential VM (TDX), kernel 6.17.0-1009-gcp, 2026-03-30.

Kernel module sets AX to two values, does INB from CMOS port 0x71, checks AH:

    Test A (AX=0x0000): result AX=0x0026 AL=0x26 AH=0x00
    Test B (AX=0x0100): result AX=0x0026 AL=0x26 AH=0x00
    *** AH same in both tests (0x00) -- bit 8 from VMM, not initial AX ***
    *** GENMASK off-by-one CONFIRMED on live TDX ***

    10x test: bit8 set with AX=0x0000: 0/10
    10x test: bit8 set with AX=0x0100: 0/10
    *** Bit 8 independent of initial AX -- CONFIRMED ***

In test B, AH should be 0x01 (preserved). Instead it is 0x00 --
overwritten from VMM data. 10/10 consistent. Reproduced twice on
2026-03-30, including a fresh rerun on a new GCP TDX VM.

Additional live write-side confirmation
---------------------------------------

Separate raw-asm kernel modules confirmed the write-side primitive
reaches the outbound sink for all widths:

    [outb] before outb A = 0x005a
    [outb] before outb B = 0x015a
    [outw] before outw A = 0x00008086
    [outw] before outw B = 0x00018086
    [outl] before outl A = 0x0000000012378086
    [outl] before outl B = 0x0000000112378086

For correct emulation, only the intended-width values should be
exposed to the VMM: 0x5a / 0x8086 / 0x12378086. With the current
handle_out() mask, the paired local payload simulator gives:

    outb: 0x05a vs 0x15a
    outw: 0x08086 vs 0x18086
    outl: 0x012378086 vs 0x112378086

This is not a host-side capture on a controllable TDX VMM, so I am not
treating it as a full confidentiality exploit. It does strengthen the
claim that the extra-bit write-side primitive is real on live TDX for
outb, outw, and outl.

Secondary issue: missing zero-extension for INL
------------------------------------------------

Separately, handle_in() does not zero-extend bits 32-63 of RAX for
size=4 (INL). On native x86-64, INL writes EAX which zero-extends to
RAX (Intel SDM Vol. 1, 3.4.1.1). handle_in() preserves bits above the
mask instead.

handle_mmio() in the same file handles this correctly:

    case INSN_MMIO_READ:
        /* Zero-extend for 32-bit operation */
        extend_size = size == 4 ? sizeof(*reg) : 0;

read_msr() also does it correctly:

    regs->ax = lower_32_bits(args.r11);

handle_in() has no equivalent. Same compiler truncation caveat applies
-- no known practical impact via standard inl() callers.

A separate raw-asm kernel module reproduced this on the same GCP TDX
kernel. Preloading RAX=0xDEADBEEF00000000 before INL 0xCFC produced
RAX=0xDEADBEEE12378086, and preloading RAX=0x1234567800000000 produced
RAX=0x1234567812378086. Bits 33-63 remain stale from pre-INL RAX; bit
32 reflects VMM-controlled data; lower 32 bits contain the expected
PCI config data.

Fix
---

In both handle_in() and handle_out(), change:

    u64 mask = GENMASK(BITS_PER_BYTE * size, 0);

to:

    u64 mask = GENMASK(BITS_PER_BYTE * size - 1, 0);

Reproduction modules available on request: portio_test.c (read-side
INB), portio_pure_out_test.c / portio_pure_outw_test.c (write-side),
portio_zeroext_test.c (INL zero-extension).

    Tested on: GCP c3-standard-4 Confidential VM (TDX)
    Kernel:    6.17.0-1009-gcp (Ubuntu 24.04)

Borys Tsyrulnikov

---
