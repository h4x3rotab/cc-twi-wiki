---
title: 'KVM: x86: Emulator MMIO fix and cleanups'
date: 2026-02-24
last_reply: 2026-03-05
message_count: 25
participants: ['Sean Christopherson', 'Edgecombe, Rick P', 'Tom Lendacky']
---

## [1] Sean Christopherson — 2026-02-24

Fix a UAF stack bug where KVM references a stack pointer around an exit to
userspace, and then clean up the related code to try to make it easier to
maintain (not necessarily "easy", but "easier").

The SEV-ES and TDX changes are compile-tested only.

Sean Christopherson (14):
  KVM: x86: Use scratch field in MMIO fragment to hold small write
    values
  KVM: x86: Open code handling of completed MMIO reads in
    emulator_read_write()
  KVM: x86: Trace unsatisfied MMIO reads on a per-page basis
  KVM: x86: Use local MMIO fragment variable to clean up
    emulator_read_write()
  KVM: x86: Open code read vs. write userspace MMIO exits in
    emulator_read_write()
  KVM: x86: Move MMIO write tracing into vcpu_mmio_write()
  KVM: x86: Harden SEV-ES MMIO against on-stack use-after-free
  KVM: x86: Dedup kvm_sev_es_mmio_{read,write}()
  KVM: x86: Consolidate SEV-ES MMIO emulation into a single public API
  KVM: x86: Bury emulator read/write ops in
    emulator_{read,write}_emulated()
  KVM: x86: Fold emulator_write_phys() into write_emulate()
  KVM: x86: Rename .read_write_emulate() to .read_write_guest()
  KVM: x86: Don't panic the kernel if completing userspace I/O / MMIO
    goes sideways
  KVM: x86: Add helpers to prepare kvm_run for userspace MMIO exit

 arch/x86/include/asm/kvm_host.h |   3 -
 arch/x86/kvm/emulate.c          |  13 ++
 arch/x86/kvm/svm/sev.c          |  20 +--
 arch/x86/kvm/vmx/tdx.c          |  14 +-
 arch/x86/kvm/x86.c              | 287 ++++++++++++++------------------
 arch/x86/kvm/x86.h              |  30 +++-
 include/linux/kvm_host.h        |   3 +-
 7 files changed, 178 insertions(+), 192 deletions(-)


base-commit: 183bb0ce8c77b0fd1fb25874112bc8751a461e49

---

## [2] Sean Christopherson — 2026-02-24
*Subject: [PATCH 01/14] KVM: x86: Use scratch field in MMIO fragment to hold
 small write values*

When exiting to userspace to service an emulated MMIO write, copy the
to-be-written value to a scratch field in the MMIO fragment if the size
of the data payload is 8 bytes or less, i.e. can fit in a single chunk,
instead of pointing the fragment directly at the source value.

This fixes a class of use-after-free bugs that occur when the emulator
initiates a write using an on-stack, local variable as the source, the
write splits a page boundary, *and* both pages are MMIO pages.  Because
KVM's ABI only allows for physically contiguous MMIO requests, accesses
that split MMIO pages are separated into two fragments, and are sent to
userspace one at a time.  When KVM attempts to complete userspace MMIO in
response to KVM_RUN after the first fragment, KVM will detect the second
fragment and generate a second userspace exit, and reference the on-stack
variable.

The issue is most visible if the second KVM_RUN is performed by a separate
task, in which case the stack of the initiating task can show up as truly
freed data.

  ==================================================================
  BUG: KASAN: use-after-free in complete_emulated_mmio+0x305/0x420
  Read of size 1 at addr ffff888009c378d1 by task syz-executor417/984

  CPU: 1 PID: 984 Comm: syz-executor417 Not tainted 5.10.0-182.0.0.95.h2627.eulerosv2r13.x86_64 #3
  Hardware name: QEMU Standard PC (i440FX + PIIX, 1996), BIOS rel-1.15.0-0-g2dd4b9b3f840-prebuilt.qemu.org 04/01/2014 Call Trace:
  dump_stack+0xbe/0xfd
  print_address_description.constprop.0+0x19/0x170
  __kasan_report.cold+0x6c/0x84
  kasan_report+0x3a/0x50
  check_memory_region+0xfd/0x1f0
  memcpy+0x20/0x60
  complete_emulated_mmio+0x305/0x420
  kvm_arch_vcpu_ioctl_run+0x63f/0x6d0
  kvm_vcpu_ioctl+0x413/0xb20
  __se_sys_ioctl+0x111/0x160
  do_syscall_64+0x30/0x40
  entry_SYSCALL_64_after_hwframe+0x67/0xd1
  RIP: 0033:0x42477d
  Code: <48> 3d 01 f0 ff ff 73 01 c3 48 c7 c1 b0 ff ff ff f7 d8 64 89 01 48
  RSP: 002b:00007faa8e6890e8 EFLAGS: 00000246 ORIG_RAX: 0000000000000010
  RAX: ffffffffffffffda RBX: 00000000004d7338 RCX: 000000000042477d
  RDX: 0000000000000000 RSI: 000000000000ae80 RDI: 0000000000000005
  RBP: 00000000004d7330 R08: 00007fff28d546df R09: 0000000000000000
  R10: 0000000000000000 R11: 0000000000000246 R12: 00000000004d733c
  R13: 0000000000000000 R14: 000000000040a200 R15: 00007fff28d54720

  The buggy address belongs to the page:
  page:0000000029f6a428 refcount:0 mapcount:0 mapping:0000000000000000 index:0x0 pfn:0x9c37
  flags: 0xfffffc0000000(node=0|zone=1|lastcpupid=0x1fffff)
  raw: 000fffffc0000000 0000000000000000 ffffea0000270dc8 0000000000000000
  raw: 0000000000000000 0000000000000000 00000000ffffffff 0000000000000000 page dumped because: kasan: bad access detected

  Memory state around the buggy address:
  ffff888009c37780: ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff
  ffff888009c37800: ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff
  >ffff888009c37880: ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff
                                                   ^
  ffff888009c37900: ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff
  ffff888009c37980: ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff
  ==================================================================

The bug can also be reproduced with a targeted KVM-Unit-Test by hacking
KVM to fill a large on-stack variable in complete_emulated_mmio(), i.e. by
overwrite the data value with garbage.

Limit the use of the scratch fields to 8-byte or smaller accesses, and to
just writes, as larger accesses and reads are not affected thanks to
implementation details in the emulator, but add a sanity check to ensure
those details don't change in the future.  Specifically, KVM never uses
on-stack variables for accesses larger that 8 bytes, e.g. uses an operand
in the emulator context, and *all* reads are buffered through the mem_read
cache.

Note!  Using the scratch field for reads is not only unnecessary, it's
also extremely difficult to handle correctly.  As above, KVM buffers all
reads through the mem_read cache, and heavily relies on that behavior when
re-emulating the instruction after a userspace MMIO read exit.  If a read
splits a page, the first page is NOT an MMIO page, and the second page IS
an MMIO page, then the MMIO fragment needs to point at _just_ the second
chunk of the destination, i.e. its position in the mem_read cache.  Taking
the "obvious" approach of copying the fragment value into the destination
when re-emulating the instruction would clobber the first chunk of the
destination, i.e. would clobber the data that was read from guest memory.

Fixes: f78146b0f923 ("KVM: Fix page-crossing MMIO")
Suggested-by: Yashu Zhang <zhangjiaji1@huawei.com>
Reported-by: Yashu Zhang <zhangjiaji1@huawei.com>
Closes: https://lore.kernel.org/all/369eaaa2b3c1425c85e8477066391bc7@huawei.com
Cc: stable@vger.kernel.org
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c       | 14 +++++++++++++-
 include/linux/kvm_host.h |  3 ++-
 2 files changed, 15 insertions(+), 2 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index db3f393192d9..ff3a6f86973f 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -8226,7 +8226,13 @@ static int emulator_read_write_onepage(unsigned long addr, void *val,
 	WARN_ON(vcpu->mmio_nr_fragments >= KVM_MAX_MMIO_FRAGMENTS);
 	frag = &vcpu->mmio_fragments[vcpu->mmio_nr_fragments++];
 	frag->gpa = gpa;
-	frag->data = val;
+	if (write && bytes <= 8u) {
+		frag->val = 0;
+		frag->data = &frag->val;
+		memcpy(&frag->val, val, bytes);
+	} else {
+		frag->data = val;
+	}
 	frag->len = bytes;
 	return X86EMUL_CONTINUE;
 }
@@ -8241,6 +8247,9 @@ static int emulator_read_write(struct x86_emulate_ctxt *ctxt,
 	gpa_t gpa;
 	int rc;
 
+	if (WARN_ON_ONCE((bytes > 8u || !ops->write) && object_is_on_stack(val)))
+		return X86EMUL_UNHANDLEABLE;
+
 	if (ops->read_write_prepare &&
 		  ops->read_write_prepare(vcpu, val, bytes))
 		return X86EMUL_CONTINUE;
@@ -11847,6 +11856,9 @@ static int complete_emulated_mmio(struct kvm_vcpu *vcpu)
 		frag++;
 		vcpu->mmio_cur_fragment++;
 	} else {
+		if (WARN_ON_ONCE(frag->data == &frag->val))
+			return -EIO;
+
 		/* Go forward to the next mmio piece. */
 		frag->data += len;
 		frag->gpa += len;
diff --git a/include/linux/kvm_host.h b/include/linux/kvm_host.h
index 2c7d76262898..0bb2a34fb93d 100644
--- a/include/linux/kvm_host.h
+++ b/include/linux/kvm_host.h
@@ -320,7 +320,8 @@ static inline bool kvm_vcpu_can_poll(ktime_t cur, ktime_t stop)
 struct kvm_mmio_fragment {
 	gpa_t gpa;
 	void *data;
-	unsigned len;
+	u64 val;
+	unsigned int len;
 };
 
 struct kvm_vcpu {

---

## [3] Sean Christopherson — 2026-02-24
*Subject: [PATCH 02/14] KVM: x86: Open code handling of completed MMIO reads in emulator_read_write()*

Open code the handling of completed MMIO reads instead of using an ops
hook, as burying the logic behind a (likely RETPOLINE'd) indirect call,
and with an unintuitive name, makes relatively straightforward code hard
to comprehend.

Opportunistically add comments to explain the dependencies between the
emulator's mem_read cache and the MMIO read completion logic, as it's very
easy to overlook the cache's role in getting the read data into the
correct destination.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/emulate.c | 13 +++++++++++++
 arch/x86/kvm/x86.c     | 33 ++++++++++++++++-----------------
 2 files changed, 29 insertions(+), 17 deletions(-)

diff --git a/arch/x86/kvm/emulate.c b/arch/x86/kvm/emulate.c
index c8e292e9a24d..70850e591350 100644
--- a/arch/x86/kvm/emulate.c
+++ b/arch/x86/kvm/emulate.c
@@ -1297,12 +1297,25 @@ static int read_emulated(struct x86_emulate_ctxt *ctxt,
 	int rc;
 	struct read_cache *mc = &ctxt->mem_read;
 
+	/*
+	 * If the read gets a cache hit, simply copy the value from the cache.
+	 * A "hit" here means that there is unused data in the cache, i.e. when
+	 * re-emulating an instruction to complete a userspace exit, KVM relies
+	 * on "no decode" to ensure the instruction is re-emulated in the same
+	 * sequence, so that multiple reads are fulfilled in the correct order.
+	 */
 	if (mc->pos < mc->end)
 		goto read_cached;
 
 	if (KVM_EMULATOR_BUG_ON((mc->end + size) >= sizeof(mc->data), ctxt))
 		return X86EMUL_UNHANDLEABLE;
 
+	/*
+	 * Route all reads to the cache.  This allows @dest to be an on-stack
+	 * variable without triggering use-after-free if KVM needs to exit to
+	 * userspace to handle an MMIO read (the MMIO fragment will point at
+	 * the current location in the cache).
+	 */
 	rc = ctxt->ops->read_emulated(ctxt, addr, mc->data + mc->end, size,
 				      &ctxt->exception);
 	if (rc != X86EMUL_CONTINUE)
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index ff3a6f86973f..8b1f02cc8196 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -8109,8 +8109,6 @@ int emulator_write_phys(struct kvm_vcpu *vcpu, gpa_t gpa,
 }
 
 struct read_write_emulator_ops {
-	int (*read_write_prepare)(struct kvm_vcpu *vcpu, void *val,
-				  int bytes);
 	int (*read_write_emulate)(struct kvm_vcpu *vcpu, gpa_t gpa,
 				  void *val, int bytes);
 	int (*read_write_mmio)(struct kvm_vcpu *vcpu, gpa_t gpa,
@@ -8120,18 +8118,6 @@ struct read_write_emulator_ops {
 	bool write;
 };
 
-static int read_prepare(struct kvm_vcpu *vcpu, void *val, int bytes)
-{
-	if (vcpu->mmio_read_completed) {
-		trace_kvm_mmio(KVM_TRACE_MMIO_READ, bytes,
-			       vcpu->mmio_fragments[0].gpa, val);
-		vcpu->mmio_read_completed = 0;
-		return 1;
-	}
-
-	return 0;
-}
-
 static int read_emulate(struct kvm_vcpu *vcpu, gpa_t gpa,
 			void *val, int bytes)
 {
@@ -8167,7 +8153,6 @@ static int write_exit_mmio(struct kvm_vcpu *vcpu, gpa_t gpa,
 }
 
 static const struct read_write_emulator_ops read_emultor = {
-	.read_write_prepare = read_prepare,
 	.read_write_emulate = read_emulate,
 	.read_write_mmio = vcpu_mmio_read,
 	.read_write_exit_mmio = read_exit_mmio,
@@ -8250,9 +8235,23 @@ static int emulator_read_write(struct x86_emulate_ctxt *ctxt,
 	if (WARN_ON_ONCE((bytes > 8u || !ops->write) && object_is_on_stack(val)))
 		return X86EMUL_UNHANDLEABLE;
 
-	if (ops->read_write_prepare &&
-		  ops->read_write_prepare(vcpu, val, bytes))
+	/*
+	 * If the read was already completed via a userspace MMIO exit, there's
+	 * nothing left to do except trace the MMIO read.  When completing MMIO
+	 * reads, KVM re-emulates the instruction to propagate the value into
+	 * the correct destination, e.g. into the correct register, but the
+	 * value itself has already been copied to the read cache.
+	 *
+	 * Note!  This is *tightly* coupled to read_emulated() satisfying reads
+	 * from the emulator's mem_read cache, so that the MMIO fragment data
+	 * is copied to the correct chunk of the correct operand.
+	 */
+	if (!ops->write && vcpu->mmio_read_completed) {
+		trace_kvm_mmio(KVM_TRACE_MMIO_READ, bytes,
+			       vcpu->mmio_fragments[0].gpa, val);
+		vcpu->mmio_read_completed = 0;
 		return X86EMUL_CONTINUE;
+	}
 
 	vcpu->mmio_nr_fragments = 0;

---

## [4] Sean Christopherson — 2026-02-24
*Subject: [PATCH 03/14] KVM: x86: Trace unsatisfied MMIO reads on a per-page basis*

Invoke the "unsatisfied MMIO reads" when KVM first detects that a
particular access "chunk" requires an exit to userspace instead of tracing
the entire access at the time KVM initiates the exit to userspace.  I.e.
precisely trace the first and/or second fragments of a page split instead
of tracing the entire access, as the GPA could be wrong on a page split
case.

Leave the completion tracepoint alone, at least for now, as fixing the
completion path would incur significantly complexity to track exactly which
fragment(s) of the overall access actually triggered MMIO, but add a
comment that the tracing for completed reads in is technically wrong.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 9 ++++++++-
 1 file changed, 8 insertions(+), 1 deletion(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 8b1f02cc8196..a74ae3a81076 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -7808,6 +7808,9 @@ static int vcpu_mmio_read(struct kvm_vcpu *vcpu, gpa_t addr, int len, void *v)
 		v += n;
 	} while (len);
 
+	if (len)
+		trace_kvm_mmio(KVM_TRACE_MMIO_READ_UNSATISFIED, len, addr, NULL);
+
 	return handled;
 }
 
@@ -8139,7 +8142,6 @@ static int write_mmio(struct kvm_vcpu *vcpu, gpa_t gpa, int bytes, void *val)
 static int read_exit_mmio(struct kvm_vcpu *vcpu, gpa_t gpa,
 			  void *val, int bytes)
 {
-	trace_kvm_mmio(KVM_TRACE_MMIO_READ_UNSATISFIED, bytes, gpa, NULL);
 	return X86EMUL_IO_NEEDED;
 }
 
@@ -8247,6 +8249,11 @@ static int emulator_read_write(struct x86_emulate_ctxt *ctxt,
 	 * is copied to the correct chunk of the correct operand.
 	 */
 	if (!ops->write && vcpu->mmio_read_completed) {
+		/*
+		 * For simplicity, trace the entire MMIO read in one shot, even
+		 * though the GPA might be incorrect if there are two fragments
+		 * that aren't contiguous in the GPA space.
+		 */
 		trace_kvm_mmio(KVM_TRACE_MMIO_READ, bytes,
 			       vcpu->mmio_fragments[0].gpa, val);
 		vcpu->mmio_read_completed = 0;

---

## [5] Sean Christopherson — 2026-02-24
*Subject: [PATCH 04/14] KVM: x86: Use local MMIO fragment variable to clean up emulator_read_write()*

Grab the MMIO fragment used by emulator_read_write() to initiate an exit
to userspace in a local variable to make the code easier to read.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 11 +++++------
 1 file changed, 5 insertions(+), 6 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index a74ae3a81076..7cbd6f7d8578 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -8231,7 +8231,7 @@ static int emulator_read_write(struct x86_emulate_ctxt *ctxt,
 			const struct read_write_emulator_ops *ops)
 {
 	struct kvm_vcpu *vcpu = emul_to_vcpu(ctxt);
-	gpa_t gpa;
+	struct kvm_mmio_fragment *frag;
 	int rc;
 
 	if (WARN_ON_ONCE((bytes > 8u || !ops->write) && object_is_on_stack(val)))
@@ -8287,17 +8287,16 @@ static int emulator_read_write(struct x86_emulate_ctxt *ctxt,
 	if (!vcpu->mmio_nr_fragments)
 		return X86EMUL_CONTINUE;
 
-	gpa = vcpu->mmio_fragments[0].gpa;
-
 	vcpu->mmio_needed = 1;
 	vcpu->mmio_cur_fragment = 0;
 
-	vcpu->run->mmio.len = min(8u, vcpu->mmio_fragments[0].len);
+	frag = &vcpu->mmio_fragments[0];
+	vcpu->run->mmio.len = min(8u, frag->len);
 	vcpu->run->mmio.is_write = vcpu->mmio_is_write = ops->write;
 	vcpu->run->exit_reason = KVM_EXIT_MMIO;
-	vcpu->run->mmio.phys_addr = gpa;
+	vcpu->run->mmio.phys_addr = frag->gpa;
 
-	return ops->read_write_exit_mmio(vcpu, gpa, val, bytes);
+	return ops->read_write_exit_mmio(vcpu, frag->gpa, val, bytes);
 }
 
 static int emulator_read_emulated(struct x86_emulate_ctxt *ctxt,

---

## [6] Sean Christopherson — 2026-02-24
*Subject: [PATCH 05/14] KVM: x86: Open code read vs. write userspace MMIO exits
 in emulator_read_write()*

Open code the differences in read vs. write userspace MMIO exits instead
of burying three lines of code behind indirect callbacks, as splitting the
logic makes it extremely hard to track that KVM's handling of reads vs.
write is _significantly_ different.  Add a comment to explain why the
semantics are different, and how on earth an MMIO write ends up triggering
an exit to userspace.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 33 +++++++++++++--------------------
 1 file changed, 13 insertions(+), 20 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 7cbd6f7d8578..5fde5bb010e7 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -8116,8 +8116,6 @@ struct read_write_emulator_ops {
 				  void *val, int bytes);
 	int (*read_write_mmio)(struct kvm_vcpu *vcpu, gpa_t gpa,
 			       int bytes, void *val);
-	int (*read_write_exit_mmio)(struct kvm_vcpu *vcpu, gpa_t gpa,
-				    void *val, int bytes);
 	bool write;
 };
 
@@ -8139,31 +8137,14 @@ static int write_mmio(struct kvm_vcpu *vcpu, gpa_t gpa, int bytes, void *val)
 	return vcpu_mmio_write(vcpu, gpa, bytes, val);
 }
 
-static int read_exit_mmio(struct kvm_vcpu *vcpu, gpa_t gpa,
-			  void *val, int bytes)
-{
-	return X86EMUL_IO_NEEDED;
-}
-
-static int write_exit_mmio(struct kvm_vcpu *vcpu, gpa_t gpa,
-			   void *val, int bytes)
-{
-	struct kvm_mmio_fragment *frag = &vcpu->mmio_fragments[0];
-
-	memcpy(vcpu->run->mmio.data, frag->data, min(8u, frag->len));
-	return X86EMUL_CONTINUE;
-}
-
 static const struct read_write_emulator_ops read_emultor = {
 	.read_write_emulate = read_emulate,
 	.read_write_mmio = vcpu_mmio_read,
-	.read_write_exit_mmio = read_exit_mmio,
 };
 
 static const struct read_write_emulator_ops write_emultor = {
 	.read_write_emulate = write_emulate,
 	.read_write_mmio = write_mmio,
-	.read_write_exit_mmio = write_exit_mmio,
 	.write = true,
 };
 
@@ -8296,7 +8277,19 @@ static int emulator_read_write(struct x86_emulate_ctxt *ctxt,
 	vcpu->run->exit_reason = KVM_EXIT_MMIO;
 	vcpu->run->mmio.phys_addr = frag->gpa;
 
-	return ops->read_write_exit_mmio(vcpu, frag->gpa, val, bytes);
+	/*
+	 * For MMIO reads, stop emulating and immediately exit to userspace, as
+	 * KVM needs the value to correctly emulate the instruction.  For MMIO
+	 * writes, continue emulating as the write to MMIO is a side effect for
+	 * all intents and purposes.  KVM will still exit to userspace, but
+	 * after completing emulation (see the check on vcpu->mmio_needed in
+	 * x86_emulate_instruction()).
+	 */
+	if (!ops->write)
+		return X86EMUL_IO_NEEDED;
+
+	memcpy(vcpu->run->mmio.data, frag->data, min(8u, frag->len));
+	return X86EMUL_CONTINUE;
 }
 
 static int emulator_read_emulated(struct x86_emulate_ctxt *ctxt,

---

## [7] Sean Christopherson — 2026-02-24
*Subject: [PATCH 06/14] KVM: x86: Move MMIO write tracing into vcpu_mmio_write()*

Move the invocation of MMIO write tracepoint into vcpu_mmio_write() and
drop its largely-useless wrapper to cull pointless code and to make the
code symmetrical with respect to vcpu_mmio_read().

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 13 +++++--------
 1 file changed, 5 insertions(+), 8 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 5fde5bb010e7..7abd6f93c386 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -7769,11 +7769,14 @@ static void kvm_init_msr_lists(void)
 }
 
 static int vcpu_mmio_write(struct kvm_vcpu *vcpu, gpa_t addr, int len,
-			   const void *v)
+			   void *__v)
 {
+	const void *v = __v;
 	int handled = 0;
 	int n;
 
+	trace_kvm_mmio(KVM_TRACE_MMIO_WRITE, len, addr, __v);
+
 	do {
 		n = min(len, 8);
 		if (!(lapic_in_kernel(vcpu) &&
@@ -8131,12 +8134,6 @@ static int write_emulate(struct kvm_vcpu *vcpu, gpa_t gpa,
 	return emulator_write_phys(vcpu, gpa, val, bytes);
 }
 
-static int write_mmio(struct kvm_vcpu *vcpu, gpa_t gpa, int bytes, void *val)
-{
-	trace_kvm_mmio(KVM_TRACE_MMIO_WRITE, bytes, gpa, val);
-	return vcpu_mmio_write(vcpu, gpa, bytes, val);
-}
-
 static const struct read_write_emulator_ops read_emultor = {
 	.read_write_emulate = read_emulate,
 	.read_write_mmio = vcpu_mmio_read,
@@ -8144,7 +8141,7 @@ static const struct read_write_emulator_ops read_emultor = {
 
 static const struct read_write_emulator_ops write_emultor = {
 	.read_write_emulate = write_emulate,
-	.read_write_mmio = write_mmio,
+	.read_write_mmio = vcpu_mmio_write,
 	.write = true,
 };

---

## [8] Sean Christopherson — 2026-02-24
*Subject: [PATCH 07/14] KVM: x86: Harden SEV-ES MMIO against on-stack use-after-free*

Add a sanity check to ensure KVM doesn't use an on-stack variable when
handling an MMIO request for an SEV-ES guest.  The source/destination
for SEV-ES MMIO should _always_ be the #VMGEXIT scratch area.

Opportunistically update the comment in the completion side of things
to clarify that frag->data doesn't need to be copied anywhere, and the
VMEGEXIT is trap-like (the current comment doesn't clarify *how* RIP is
advanced).

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 10 ++++++----
 1 file changed, 6 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 7abd6f93c386..2db0bf738d2d 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -14273,8 +14273,10 @@ static int complete_sev_es_emulated_mmio(struct kvm_vcpu *vcpu)
 	if (vcpu->mmio_cur_fragment >= vcpu->mmio_nr_fragments) {
 		vcpu->mmio_needed = 0;
 
-		// VMG change, at this point, we're always done
-		// RIP has already been advanced
+		/*
+		 * All done, as frag->data always points at the GHCB scratch
+		 * area and VMGEXIT is trap-like (RIP is advanced by hardware).
+		 */
 		return 1;
 	}
 
@@ -14297,7 +14299,7 @@ int kvm_sev_es_mmio_write(struct kvm_vcpu *vcpu, gpa_t gpa, unsigned int bytes,
 	int handled;
 	struct kvm_mmio_fragment *frag;
 
-	if (!data)
+	if (!data || WARN_ON_ONCE(object_is_on_stack(data)))
 		return -EINVAL;
 
 	handled = write_emultor.read_write_mmio(vcpu, gpa, bytes, data);
@@ -14336,7 +14338,7 @@ int kvm_sev_es_mmio_read(struct kvm_vcpu *vcpu, gpa_t gpa, unsigned int bytes,
 	int handled;
 	struct kvm_mmio_fragment *frag;
 
-	if (!data)
+	if (!data || WARN_ON_ONCE(object_is_on_stack(data)))
 		return -EINVAL;
 
 	handled = read_emultor.read_write_mmio(vcpu, gpa, bytes, data);

---

## [9] Sean Christopherson — 2026-02-24
*Subject: [PATCH 08/14] KVM: x86: Dedup kvm_sev_es_mmio_{read,write}()*

Dedup the SEV-ES emulated MMIO code by using the read vs. write emulator
ops to handle the few differences between reads and writes.

Opportunistically tweak the comment about fragments to call out that KVM
should verify that userspace can actually handle MMIO requests that cross
page boundaries.  Unlike emulated MMIO, the request is made in the GPA
space, not the GVA space, i.e. emulation across page boundaries can work
generically, at least in theory.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 110 +++++++++++++++++++--------------------------
 1 file changed, 45 insertions(+), 65 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 2db0bf738d2d..f93f0f8961af 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -14293,80 +14293,60 @@ static int complete_sev_es_emulated_mmio(struct kvm_vcpu *vcpu)
 	return 0;
 }
 
+static int kvm_sev_es_do_mmio(struct kvm_vcpu *vcpu, gpa_t gpa,
+			      unsigned int bytes, void *data,
+			      const struct read_write_emulator_ops *ops)
+{
+	struct kvm_mmio_fragment *frag;
+	int handled;
+
+	if (!data || WARN_ON_ONCE(object_is_on_stack(data)))
+		return -EINVAL;
+
+	handled = ops->read_write_mmio(vcpu, gpa, bytes, data);
+	if (handled == bytes)
+		return 1;
+
+	bytes -= handled;
+	gpa += handled;
+	data += handled;
+
+	/*
+	 * TODO: Determine whether or not userspace plays nice with MMIO
+	 *       requests that split a page boundary.
+	 */
+	frag = vcpu->mmio_fragments;
+	vcpu->mmio_nr_fragments = 1;
+	frag->len = bytes;
+	frag->gpa = gpa;
+	frag->data = data;
+
+	vcpu->mmio_needed = 1;
+	vcpu->mmio_cur_fragment = 0;
+
+	vcpu->run->mmio.phys_addr = gpa;
+	vcpu->run->mmio.len = min(8u, frag->len);
+	vcpu->run->mmio.is_write = ops->write;
+	if (ops->write)
+		memcpy(vcpu->run->mmio.data, frag->data, min(8u, frag->len));
+	vcpu->run->exit_reason = KVM_EXIT_MMIO;
+
+	vcpu->arch.complete_userspace_io = complete_sev_es_emulated_mmio;
+
+	return 0;
+}
+
 int kvm_sev_es_mmio_write(struct kvm_vcpu *vcpu, gpa_t gpa, unsigned int bytes,
 			  void *data)
 {
-	int handled;
-	struct kvm_mmio_fragment *frag;
-
-	if (!data || WARN_ON_ONCE(object_is_on_stack(data)))
-		return -EINVAL;
-
-	handled = write_emultor.read_write_mmio(vcpu, gpa, bytes, data);
-	if (handled == bytes)
-		return 1;
-
-	bytes -= handled;
-	gpa += handled;
-	data += handled;
-
-	/*TODO: Check if need to increment number of frags */
-	frag = vcpu->mmio_fragments;
-	vcpu->mmio_nr_fragments = 1;
-	frag->len = bytes;
-	frag->gpa = gpa;
-	frag->data = data;
-
-	vcpu->mmio_needed = 1;
-	vcpu->mmio_cur_fragment = 0;
-
-	vcpu->run->mmio.phys_addr = gpa;
-	vcpu->run->mmio.len = min(8u, frag->len);
-	vcpu->run->mmio.is_write = 1;
-	memcpy(vcpu->run->mmio.data, frag->data, min(8u, frag->len));
-	vcpu->run->exit_reason = KVM_EXIT_MMIO;
-
-	vcpu->arch.complete_userspace_io = complete_sev_es_emulated_mmio;
-
-	return 0;
+	return kvm_sev_es_do_mmio(vcpu, gpa, bytes, data, &write_emultor);
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_sev_es_mmio_write);
 
 int kvm_sev_es_mmio_read(struct kvm_vcpu *vcpu, gpa_t gpa, unsigned int bytes,
 			 void *data)
 {
-	int handled;
-	struct kvm_mmio_fragment *frag;
-
-	if (!data || WARN_ON_ONCE(object_is_on_stack(data)))
-		return -EINVAL;
-
-	handled = read_emultor.read_write_mmio(vcpu, gpa, bytes, data);
-	if (handled == bytes)
-		return 1;
-
-	bytes -= handled;
-	gpa += handled;
-	data += handled;
-
-	/*TODO: Check if need to increment number of frags */
-	frag = vcpu->mmio_fragments;
-	vcpu->mmio_nr_fragments = 1;
-	frag->len = bytes;
-	frag->gpa = gpa;
-	frag->data = data;
-
-	vcpu->mmio_needed = 1;
-	vcpu->mmio_cur_fragment = 0;
-
-	vcpu->run->mmio.phys_addr = gpa;
-	vcpu->run->mmio.len = min(8u, frag->len);
-	vcpu->run->mmio.is_write = 0;
-	vcpu->run->exit_reason = KVM_EXIT_MMIO;
-
-	vcpu->arch.complete_userspace_io = complete_sev_es_emulated_mmio;
-
-	return 0;
+	return kvm_sev_es_do_mmio(vcpu, gpa, bytes, data, &read_emultor);
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_sev_es_mmio_read);

---

## [10] Sean Christopherson — 2026-02-24
*Subject: [PATCH 09/14] KVM: x86: Consolidate SEV-ES MMIO emulation into a
 single public API*

Dedup kvm_sev_es_mmio_{read,write}() into a single API, as the "cost" of
plumbing in a boolean is largely negligible since KVM pulls out a boolean
for ops->write anyways, and consolidating the APIs will allow for
additional cleanups.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/svm/sev.c | 20 ++++++--------------
 arch/x86/kvm/x86.c     | 29 +++++++++--------------------
 arch/x86/kvm/x86.h     |  6 ++----
 3 files changed, 17 insertions(+), 38 deletions(-)

diff --git a/arch/x86/kvm/svm/sev.c b/arch/x86/kvm/svm/sev.c
index ea515cf41168..723f4452302a 100644
--- a/arch/x86/kvm/svm/sev.c
+++ b/arch/x86/kvm/svm/sev.c
@@ -4434,25 +4434,17 @@ int sev_handle_vmgexit(struct kvm_vcpu *vcpu)
 
 	switch (control->exit_code) {
 	case SVM_VMGEXIT_MMIO_READ:
-		ret = setup_vmgexit_scratch(svm, true, control->exit_info_2);
-		if (ret)
-			break;
+	case SVM_VMGEXIT_MMIO_WRITE: {
+		bool is_write = control->exit_code == SVM_VMGEXIT_MMIO_WRITE;
 
-		ret = kvm_sev_es_mmio_read(vcpu,
-					   control->exit_info_1,
-					   control->exit_info_2,
-					   svm->sev_es.ghcb_sa);
-		break;
-	case SVM_VMGEXIT_MMIO_WRITE:
-		ret = setup_vmgexit_scratch(svm, false, control->exit_info_2);
+		ret = setup_vmgexit_scratch(svm, !is_write, control->exit_info_2);
 		if (ret)
 			break;
 
-		ret = kvm_sev_es_mmio_write(vcpu,
-					    control->exit_info_1,
-					    control->exit_info_2,
-					    svm->sev_es.ghcb_sa);
+		ret = kvm_sev_es_mmio(vcpu, is_write, control->exit_info_1,
+				      control->exit_info_2, svm->sev_es.ghcb_sa);
 		break;
+	}
 	case SVM_VMGEXIT_NMI_COMPLETE:
 		++vcpu->stat.nmi_window_exits;
 		svm->nmi_masked = false;
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index f93f0f8961af..022e953906f7 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -14293,9 +14293,8 @@ static int complete_sev_es_emulated_mmio(struct kvm_vcpu *vcpu)
 	return 0;
 }
 
-static int kvm_sev_es_do_mmio(struct kvm_vcpu *vcpu, gpa_t gpa,
-			      unsigned int bytes, void *data,
-			      const struct read_write_emulator_ops *ops)
+int kvm_sev_es_mmio(struct kvm_vcpu *vcpu, bool is_write, gpa_t gpa,
+		    unsigned int bytes, void *data)
 {
 	struct kvm_mmio_fragment *frag;
 	int handled;
@@ -14303,7 +14302,10 @@ static int kvm_sev_es_do_mmio(struct kvm_vcpu *vcpu, gpa_t gpa,
 	if (!data || WARN_ON_ONCE(object_is_on_stack(data)))
 		return -EINVAL;
 
-	handled = ops->read_write_mmio(vcpu, gpa, bytes, data);
+	if (is_write)
+		handled = vcpu_mmio_write(vcpu, gpa, bytes, data);
+	else
+		handled = vcpu_mmio_read(vcpu, gpa, bytes, data);
 	if (handled == bytes)
 		return 1;
 
@@ -14326,8 +14328,8 @@ static int kvm_sev_es_do_mmio(struct kvm_vcpu *vcpu, gpa_t gpa,
 
 	vcpu->run->mmio.phys_addr = gpa;
 	vcpu->run->mmio.len = min(8u, frag->len);
-	vcpu->run->mmio.is_write = ops->write;
-	if (ops->write)
+	vcpu->run->mmio.is_write = is_write;
+	if (is_write)
 		memcpy(vcpu->run->mmio.data, frag->data, min(8u, frag->len));
 	vcpu->run->exit_reason = KVM_EXIT_MMIO;
 
@@ -14335,20 +14337,7 @@ static int kvm_sev_es_do_mmio(struct kvm_vcpu *vcpu, gpa_t gpa,
 
 	return 0;
 }
-
-int kvm_sev_es_mmio_write(struct kvm_vcpu *vcpu, gpa_t gpa, unsigned int bytes,
-			  void *data)
-{
-	return kvm_sev_es_do_mmio(vcpu, gpa, bytes, data, &write_emultor);
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_sev_es_mmio_write);
-
-int kvm_sev_es_mmio_read(struct kvm_vcpu *vcpu, gpa_t gpa, unsigned int bytes,
-			 void *data)
-{
-	return kvm_sev_es_do_mmio(vcpu, gpa, bytes, data, &read_emultor);
-}
-EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_sev_es_mmio_read);
+EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_sev_es_mmio);
 
 static void advance_sev_es_emulated_pio(struct kvm_vcpu *vcpu, unsigned count, int size)
 {
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index 94d4f07aaaa0..1d0f0edd31b3 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -712,10 +712,8 @@ static inline bool __kvm_is_valid_cr4(struct kvm_vcpu *vcpu, unsigned long cr4)
 	__reserved_bits;                                \
 })
 
-int kvm_sev_es_mmio_write(struct kvm_vcpu *vcpu, gpa_t src, unsigned int bytes,
-			  void *dst);
-int kvm_sev_es_mmio_read(struct kvm_vcpu *vcpu, gpa_t src, unsigned int bytes,
-			 void *dst);
+int kvm_sev_es_mmio(struct kvm_vcpu *vcpu, bool is_write, gpa_t gpa,
+		    unsigned int bytes, void *data);
 int kvm_sev_es_string_io(struct kvm_vcpu *vcpu, unsigned int size,
 			 unsigned int port, void *data,  unsigned int count,
 			 int in);

---

## [11] Sean Christopherson — 2026-02-24
*Subject: [PATCH 10/14] KVM: x86: Bury emulator read/write ops in emulator_{read,write}_emulated()*

Now that SEV-ES invokes vcpu_mmio_{read,write}() directly, bury the
read vs. write emulator ops in the dedicated emulator callbacks so that
they are colocated with their usage, and to make it harder for
non-emulator code to use hooks that are intended for the emulator.

Opportunistically rename the structures to get rid of the long-standing
"emultor" typo.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 29 ++++++++++++++---------------
 1 file changed, 14 insertions(+), 15 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 022e953906f7..5fb5259c208f 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -8134,17 +8134,6 @@ static int write_emulate(struct kvm_vcpu *vcpu, gpa_t gpa,
 	return emulator_write_phys(vcpu, gpa, val, bytes);
 }
 
-static const struct read_write_emulator_ops read_emultor = {
-	.read_write_emulate = read_emulate,
-	.read_write_mmio = vcpu_mmio_read,
-};
-
-static const struct read_write_emulator_ops write_emultor = {
-	.read_write_emulate = write_emulate,
-	.read_write_mmio = vcpu_mmio_write,
-	.write = true,
-};
-
 static int emulator_read_write_onepage(unsigned long addr, void *val,
 				       unsigned int bytes,
 				       struct x86_exception *exception,
@@ -8295,8 +8284,13 @@ static int emulator_read_emulated(struct x86_emulate_ctxt *ctxt,
 				  unsigned int bytes,
 				  struct x86_exception *exception)
 {
-	return emulator_read_write(ctxt, addr, val, bytes,
-				   exception, &read_emultor);
+	static const struct read_write_emulator_ops ops = {
+		.read_write_emulate = read_emulate,
+		.read_write_mmio = vcpu_mmio_read,
+		.write = false,
+	};
+
+	return emulator_read_write(ctxt, addr, val, bytes, exception, &ops);
 }
 
 static int emulator_write_emulated(struct x86_emulate_ctxt *ctxt,
@@ -8305,8 +8299,13 @@ static int emulator_write_emulated(struct x86_emulate_ctxt *ctxt,
 			    unsigned int bytes,
 			    struct x86_exception *exception)
 {
-	return emulator_read_write(ctxt, addr, (void *)val, bytes,
-				   exception, &write_emultor);
+	static const struct read_write_emulator_ops ops = {
+		.read_write_emulate = write_emulate,
+		.read_write_mmio = vcpu_mmio_write,
+		.write = true,
+	};
+
+	return emulator_read_write(ctxt, addr, (void *)val, bytes, exception, &ops);
 }
 
 #define emulator_try_cmpxchg_user(t, ptr, old, new) \

---

## [12] Sean Christopherson — 2026-02-24
*Subject: [PATCH 11/14] KVM: x86: Fold emulator_write_phys() into write_emulate()*

Fold emulator_write_phys() into write_emulate() to drop a superfluous
wrapper, and to provide more symmetry between the read and write paths.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/include/asm/kvm_host.h |  3 ---
 arch/x86/kvm/x86.c              | 20 +++++++-------------
 2 files changed, 7 insertions(+), 16 deletions(-)

diff --git a/arch/x86/include/asm/kvm_host.h b/arch/x86/include/asm/kvm_host.h
index ff07c45e3c73..aa030fbd669d 100644
--- a/arch/x86/include/asm/kvm_host.h
+++ b/arch/x86/include/asm/kvm_host.h
@@ -2097,9 +2097,6 @@ void kvm_zap_gfn_range(struct kvm *kvm, gfn_t gfn_start, gfn_t gfn_end);
 
 int load_pdptrs(struct kvm_vcpu *vcpu, unsigned long cr3);
 
-int emulator_write_phys(struct kvm_vcpu *vcpu, gpa_t gpa,
-			  const void *val, int bytes);
-
 extern bool tdp_enabled;
 
 u64 vcpu_tsc_khz(struct kvm_vcpu *vcpu);
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 5fb5259c208f..5a3ba161db7b 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -8102,18 +8102,6 @@ static int vcpu_mmio_gva_to_gpa(struct kvm_vcpu *vcpu, unsigned long gva,
 	return vcpu_is_mmio_gpa(vcpu, gva, *gpa, write);
 }
 
-int emulator_write_phys(struct kvm_vcpu *vcpu, gpa_t gpa,
-			const void *val, int bytes)
-{
-	int ret;
-
-	ret = kvm_vcpu_write_guest(vcpu, gpa, val, bytes);
-	if (ret < 0)
-		return 0;
-	kvm_page_track_write(vcpu, gpa, val, bytes);
-	return 1;
-}
-
 struct read_write_emulator_ops {
 	int (*read_write_emulate)(struct kvm_vcpu *vcpu, gpa_t gpa,
 				  void *val, int bytes);
@@ -8131,7 +8119,13 @@ static int read_emulate(struct kvm_vcpu *vcpu, gpa_t gpa,
 static int write_emulate(struct kvm_vcpu *vcpu, gpa_t gpa,
 			 void *val, int bytes)
 {
-	return emulator_write_phys(vcpu, gpa, val, bytes);
+	int ret;
+
+	ret = kvm_vcpu_write_guest(vcpu, gpa, val, bytes);
+	if (ret < 0)
+		return 0;
+	kvm_page_track_write(vcpu, gpa, val, bytes);
+	return 1;
 }
 
 static int emulator_read_write_onepage(unsigned long addr, void *val,

---

## [13] Sean Christopherson — 2026-02-24
*Subject: [PATCH 12/14] KVM: x86: Rename .read_write_emulate() to .read_write_guest()*

Rename the ops and helpers to read/write guest memory to clarify that they
do exactly that, i.e. aren't generic emulation flows and don't do anything
related to emulated MMIO.

Opportunistically add comments to explain the flow, e.g. it's not exactly
obvious that KVM deliberately treats "failed" accesses to guest memory as
emulated MMIO.

No functional change intended.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 38 ++++++++++++++++++++++++++++----------
 1 file changed, 28 insertions(+), 10 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 5a3ba161db7b..f3e2ec7e1828 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -8103,21 +8103,21 @@ static int vcpu_mmio_gva_to_gpa(struct kvm_vcpu *vcpu, unsigned long gva,
 }
 
 struct read_write_emulator_ops {
-	int (*read_write_emulate)(struct kvm_vcpu *vcpu, gpa_t gpa,
-				  void *val, int bytes);
+	int (*read_write_guest)(struct kvm_vcpu *vcpu, gpa_t gpa,
+				void *val, int bytes);
 	int (*read_write_mmio)(struct kvm_vcpu *vcpu, gpa_t gpa,
 			       int bytes, void *val);
 	bool write;
 };
 
-static int read_emulate(struct kvm_vcpu *vcpu, gpa_t gpa,
-			void *val, int bytes)
+static int emulator_read_guest(struct kvm_vcpu *vcpu, gpa_t gpa,
+			       void *val, int bytes)
 {
 	return !kvm_vcpu_read_guest(vcpu, gpa, val, bytes);
 }
 
-static int write_emulate(struct kvm_vcpu *vcpu, gpa_t gpa,
-			 void *val, int bytes)
+static int emulator_write_guest(struct kvm_vcpu *vcpu, gpa_t gpa,
+				void *val, int bytes)
 {
 	int ret;
 
@@ -8157,11 +8157,22 @@ static int emulator_read_write_onepage(unsigned long addr, void *val,
 			return X86EMUL_PROPAGATE_FAULT;
 	}
 
-	if (!ret && ops->read_write_emulate(vcpu, gpa, val, bytes))
+	/*
+	 * If the memory is not _known_ to be emulated MMIO, attempt to access
+	 * guest memory.  If accessing guest memory fails, e.g. because there's
+	 * no memslot, then handle the access as MMIO.  Note, treating the
+	 * access as emulated MMIO is technically wrong if there is a memslot,
+	 * i.e. if accessing host user memory failed, but this has been KVM's
+	 * historical ABI for decades.
+	 */
+	if (!ret && ops->read_write_guest(vcpu, gpa, val, bytes))
 		return X86EMUL_CONTINUE;
 
 	/*
-	 * Is this MMIO handled locally?
+	 * Attempt to handle emulated MMIO within the kernel, e.g. for accesses
+	 * to an in-kernel local or I/O APIC, or to an ioeventfd range attached
+	 * to MMIO bus.  If the access isn't fully resolved, insert an MMIO
+	 * fragment with the relevant details.
 	 */
 	handled = ops->read_write_mmio(vcpu, gpa, bytes, val);
 	if (handled == bytes)
@@ -8182,6 +8193,13 @@ static int emulator_read_write_onepage(unsigned long addr, void *val,
 		frag->data = val;
 	}
 	frag->len = bytes;
+
+	/*
+	 * Continue emulating, even though KVM needs to (eventually) do an MMIO
+	 * exit to userspace.  If the access splits multiple pages, then KVM
+	 * needs to exit to userspace only after emulating both parts of the
+	 * access.
+	 */
 	return X86EMUL_CONTINUE;
 }
 
@@ -8279,7 +8297,7 @@ static int emulator_read_emulated(struct x86_emulate_ctxt *ctxt,
 				  struct x86_exception *exception)
 {
 	static const struct read_write_emulator_ops ops = {
-		.read_write_emulate = read_emulate,
+		.read_write_guest = emulator_read_guest,
 		.read_write_mmio = vcpu_mmio_read,
 		.write = false,
 	};
@@ -8294,7 +8312,7 @@ static int emulator_write_emulated(struct x86_emulate_ctxt *ctxt,
 			    struct x86_exception *exception)
 {
 	static const struct read_write_emulator_ops ops = {
-		.read_write_emulate = write_emulate,
+		.read_write_guest = emulator_write_guest,
 		.read_write_mmio = vcpu_mmio_write,
 		.write = true,
 	};

---

## [14] Sean Christopherson — 2026-02-24
*Subject: [PATCH 13/14] KVM: x86: Don't panic the kernel if completing
 userspace I/O / MMIO goes sideways*

Kill the VM instead of the host kernel if KVM botches I/O and/or MMIO
handling.  There is zero danger to the host or guest, i.e. panicking the
host isn't remotely justified.

Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/x86.c | 12 ++++++++----
 1 file changed, 8 insertions(+), 4 deletions(-)

diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index f3e2ec7e1828..5376b370b4db 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -9710,7 +9710,8 @@ static int complete_fast_pio_in(struct kvm_vcpu *vcpu)
 	unsigned long val;
 
 	/* We should only ever be called with arch.pio.count equal to 1 */
-	BUG_ON(vcpu->arch.pio.count != 1);
+	if (KVM_BUG_ON(vcpu->arch.pio.count != 1, vcpu->kvm))
+		return -EIO;
 
 	if (unlikely(!kvm_is_linear_rip(vcpu, vcpu->arch.cui_linear_rip))) {
 		vcpu->arch.pio.count = 0;
@@ -11820,7 +11821,8 @@ static inline int complete_emulated_io(struct kvm_vcpu *vcpu)
 
 static int complete_emulated_pio(struct kvm_vcpu *vcpu)
 {
-	BUG_ON(!vcpu->arch.pio.count);
+	if (KVM_BUG_ON(!vcpu->arch.pio.count, vcpu->kvm))
+		return -EIO;
 
 	return complete_emulated_io(vcpu);
 }
@@ -11849,7 +11851,8 @@ static int complete_emulated_mmio(struct kvm_vcpu *vcpu)
 	struct kvm_mmio_fragment *frag;
 	unsigned len;
 
-	BUG_ON(!vcpu->mmio_needed);
+	if (KVM_BUG_ON(!vcpu->mmio_needed, vcpu->kvm))
+		return -EIO;
 
 	/* Complete previous fragment */
 	frag = &vcpu->mmio_fragments[vcpu->mmio_cur_fragment];
@@ -14262,7 +14265,8 @@ static int complete_sev_es_emulated_mmio(struct kvm_vcpu *vcpu)
 	struct kvm_mmio_fragment *frag;
 	unsigned int len;
 
-	BUG_ON(!vcpu->mmio_needed);
+	if (KVM_BUG_ON(!vcpu->mmio_needed, vcpu->kvm))
+		return -EIO;
 
 	/* Complete previous fragment */
 	frag = &vcpu->mmio_fragments[vcpu->mmio_cur_fragment];

---

## [15] Sean Christopherson — 2026-02-24
*Subject: [PATCH 14/14] KVM: x86: Add helpers to prepare kvm_run for userspace
 MMIO exit*

Add helpers to fill kvm_run for userspace MMIO exits to deduplicate a
variety of code, and to allow for a cleaner return path in
emulator_read_write().

No functional change intended.

Cc: Rick Edgecombe <rick.p.edgecombe@intel.com>
Cc: Binbin Wu <binbin.wu@linux.intel.com>
Cc: Xiaoyao Li <xiaoyao.li@intel.com>
Cc: Tom Lendacky <thomas.lendacky@amd.com>
Cc: Michael Roth <michael.roth@amd.com>
Signed-off-by: Sean Christopherson <seanjc@google.com>
---
 arch/x86/kvm/vmx/tdx.c | 14 ++++----------
 arch/x86/kvm/x86.c     | 42 ++++++++----------------------------------
 arch/x86/kvm/x86.h     | 24 ++++++++++++++++++++++++
 3 files changed, 36 insertions(+), 44 deletions(-)

diff --git a/arch/x86/kvm/vmx/tdx.c b/arch/x86/kvm/vmx/tdx.c
index 5df9d32d2058..a813c502336c 100644
--- a/arch/x86/kvm/vmx/tdx.c
+++ b/arch/x86/kvm/vmx/tdx.c
@@ -1467,17 +1467,11 @@ static int tdx_emulate_mmio(struct kvm_vcpu *vcpu)
 
 	/* Request the device emulation to userspace device model. */
 	vcpu->mmio_is_write = write;
-	if (!write)
+
+	__kvm_prepare_emulated_mmio_exit(vcpu, gpa, size, &val, write);
+
+	if (!write) {
 		vcpu->arch.complete_userspace_io = tdx_complete_mmio_read;
-
-	vcpu->run->mmio.phys_addr = gpa;
-	vcpu->run->mmio.len = size;
-	vcpu->run->mmio.is_write = write;
-	vcpu->run->exit_reason = KVM_EXIT_MMIO;
-
-	if (write) {
-		memcpy(vcpu->run->mmio.data, &val, size);
-	} else {
 		vcpu->mmio_fragments[0].gpa = gpa;
 		vcpu->mmio_fragments[0].len = size;
 		trace_kvm_mmio(KVM_TRACE_MMIO_READ_UNSATISFIED, size, gpa, NULL);
diff --git a/arch/x86/kvm/x86.c b/arch/x86/kvm/x86.c
index 5376b370b4db..889a9098403c 100644
--- a/arch/x86/kvm/x86.c
+++ b/arch/x86/kvm/x86.c
@@ -8210,7 +8210,6 @@ static int emulator_read_write(struct x86_emulate_ctxt *ctxt,
 			const struct read_write_emulator_ops *ops)
 {
 	struct kvm_vcpu *vcpu = emul_to_vcpu(ctxt);
-	struct kvm_mmio_fragment *frag;
 	int rc;
 
 	if (WARN_ON_ONCE((bytes > 8u || !ops->write) && object_is_on_stack(val)))
@@ -8268,12 +8267,9 @@ static int emulator_read_write(struct x86_emulate_ctxt *ctxt,
 
 	vcpu->mmio_needed = 1;
 	vcpu->mmio_cur_fragment = 0;
+	vcpu->mmio_is_write = ops->write;
 
-	frag = &vcpu->mmio_fragments[0];
-	vcpu->run->mmio.len = min(8u, frag->len);
-	vcpu->run->mmio.is_write = vcpu->mmio_is_write = ops->write;
-	vcpu->run->exit_reason = KVM_EXIT_MMIO;
-	vcpu->run->mmio.phys_addr = frag->gpa;
+	kvm_prepare_emulated_mmio_exit(vcpu, &vcpu->mmio_fragments[0]);
 
 	/*
 	 * For MMIO reads, stop emulating and immediately exit to userspace, as
@@ -8283,11 +8279,7 @@ static int emulator_read_write(struct x86_emulate_ctxt *ctxt,
 	 * after completing emulation (see the check on vcpu->mmio_needed in
 	 * x86_emulate_instruction()).
 	 */
-	if (!ops->write)
-		return X86EMUL_IO_NEEDED;
-
-	memcpy(vcpu->run->mmio.data, frag->data, min(8u, frag->len));
-	return X86EMUL_CONTINUE;
+	return ops->write ? X86EMUL_CONTINUE : X86EMUL_IO_NEEDED;
 }
 
 static int emulator_read_emulated(struct x86_emulate_ctxt *ctxt,
@@ -11884,12 +11876,7 @@ static int complete_emulated_mmio(struct kvm_vcpu *vcpu)
 		return complete_emulated_io(vcpu);
 	}
 
-	run->exit_reason = KVM_EXIT_MMIO;
-	run->mmio.phys_addr = frag->gpa;
-	if (vcpu->mmio_is_write)
-		memcpy(run->mmio.data, frag->data, min(8u, frag->len));
-	run->mmio.len = min(8u, frag->len);
-	run->mmio.is_write = vcpu->mmio_is_write;
+	kvm_prepare_emulated_mmio_exit(vcpu, frag);
 	vcpu->arch.complete_userspace_io = complete_emulated_mmio;
 	return 0;
 }
@@ -14296,15 +14283,8 @@ static int complete_sev_es_emulated_mmio(struct kvm_vcpu *vcpu)
 	}
 
 	// More MMIO is needed
-	run->mmio.phys_addr = frag->gpa;
-	run->mmio.len = min(8u, frag->len);
-	run->mmio.is_write = vcpu->mmio_is_write;
-	if (run->mmio.is_write)
-		memcpy(run->mmio.data, frag->data, min(8u, frag->len));
-	run->exit_reason = KVM_EXIT_MMIO;
-
+	kvm_prepare_emulated_mmio_exit(vcpu, frag);
 	vcpu->arch.complete_userspace_io = complete_sev_es_emulated_mmio;
-
 	return 0;
 }
 
@@ -14333,23 +14313,17 @@ int kvm_sev_es_mmio(struct kvm_vcpu *vcpu, bool is_write, gpa_t gpa,
 	 *       requests that split a page boundary.
 	 */
 	frag = vcpu->mmio_fragments;
-	vcpu->mmio_nr_fragments = 1;
 	frag->len = bytes;
 	frag->gpa = gpa;
 	frag->data = data;
 
 	vcpu->mmio_needed = 1;
 	vcpu->mmio_cur_fragment = 0;
+	vcpu->mmio_nr_fragments = 1;
+	vcpu->mmio_is_write = is_write;
 
-	vcpu->run->mmio.phys_addr = gpa;
-	vcpu->run->mmio.len = min(8u, frag->len);
-	vcpu->run->mmio.is_write = is_write;
-	if (is_write)
-		memcpy(vcpu->run->mmio.data, frag->data, min(8u, frag->len));
-	vcpu->run->exit_reason = KVM_EXIT_MMIO;
-
+	kvm_prepare_emulated_mmio_exit(vcpu, frag);
 	vcpu->arch.complete_userspace_io = complete_sev_es_emulated_mmio;
-
 	return 0;
 }
 EXPORT_SYMBOL_FOR_KVM_INTERNAL(kvm_sev_es_mmio);
diff --git a/arch/x86/kvm/x86.h b/arch/x86/kvm/x86.h
index 1d0f0edd31b3..d66f1c53d2b5 100644
--- a/arch/x86/kvm/x86.h
+++ b/arch/x86/kvm/x86.h
@@ -718,6 +718,30 @@ int kvm_sev_es_string_io(struct kvm_vcpu *vcpu, unsigned int size,
 			 unsigned int port, void *data,  unsigned int count,
 			 int in);
 
+static inline void __kvm_prepare_emulated_mmio_exit(struct kvm_vcpu *vcpu,
+						    gpa_t gpa, unsigned int len,
+						    const void *data,
+						    bool is_write)
+{
+	struct kvm_run *run = vcpu->run;
+
+	run->mmio.len = min(8u, len);
+	run->mmio.is_write = is_write;
+	run->exit_reason = KVM_EXIT_MMIO;
+	run->mmio.phys_addr = gpa;
+	if (is_write)
+		memcpy(run->mmio.data, data, min(8u, len));
+}
+
+static inline void kvm_prepare_emulated_mmio_exit(struct kvm_vcpu *vcpu,
+						  struct kvm_mmio_fragment *frag)
+{
+	WARN_ON_ONCE(!vcpu->mmio_needed || !vcpu->mmio_nr_fragments);
+
+	__kvm_prepare_emulated_mmio_exit(vcpu, frag->gpa, frag->len, frag->data,
+					 vcpu->mmio_is_write);
+}
+
 static inline bool user_exit_on_hypercall(struct kvm *kvm, unsigned long hc_nr)
 {
 	return kvm->arch.hypercall_exit_enabled & BIT(hc_nr);

---

## [16] Edgecombe, Rick P — 2026-02-25
*Subject: Re: [PATCH 00/14] KVM: x86: Emulator MMIO fix and cleanups*

On Tue, 2026-02-24 at 17:20 -0800, Sean Christopherson wrote:
> Fix a UAF stack bug where KVM references a stack pointer around an exit to
> userspace, and then clean up the related code to try to make it easier to

I ran it through our TDX CI.

Tested-by: Rick Edgecombe <rick.p.edgecombe@intel.com>

---

## [17] Edgecombe, Rick P — 2026-02-25
*Subject: Re: [PATCH 14/14] KVM: x86: Add helpers to prepare kvm_run for
 userspace MMIO exit*

On Tue, 2026-02-24 at 17:20 -0800, Sean Christopherson wrote:
> +static inline void __kvm_prepare_emulated_mmio_exit(struct kvm_vcpu *vcpu,
> +						    gpa_t gpa, unsigned int len,

I would think to extract this to a local var so it can be used twice.

> +	run->mmio.is_write = is_write;
> +	run->exit_reason = KVM_EXIT_MMIO;

---

## [18] Sean Christopherson — 2026-02-25
*Subject: Re: [PATCH 14/14] KVM: x86: Add helpers to prepare kvm_run for
 userspace MMIO exit*

On Wed, Feb 25, 2026, Rick P Edgecombe wrote:
> On Tue, 2026-02-24 at 17:20 -0800, Sean Christopherson wrote:
> > +static inline void __kvm_prepare_emulated_mmio_exit(struct kvm_vcpu *vcpu,

Ya, either way works for me.  The copy+paste is a little gross, but it's also
unlikely that anyone is going to modify this code (or if they did, that any goofs
wouldn't be immediately disastrous).

> > +	run->mmio.is_write = is_write;
> > +	run->exit_reason = KVM_EXIT_MMIO;

---

## [19] Tom Lendacky — 2026-02-25
*Subject: Re: [PATCH 00/14] KVM: x86: Emulator MMIO fix and cleanups*

On 2/24/26 19:20, Sean Christopherson wrote:
> Fix a UAF stack bug where KVM references a stack pointer around an exit to
> userspace, and then clean up the related code to try to make it easier to

A quick boot test was fine. I'm scheduling it to run through our CI to
see if anything pops up.

Thanks,
Tom

> 
>

---

## [20] Tom Lendacky — 2026-02-27
*Subject: Re: [PATCH 00/14] KVM: x86: Emulator MMIO fix and cleanups*

On 2/25/26 14:19, Tom Lendacky wrote:
> On 2/24/26 19:20, Sean Christopherson wrote:
>> Fix a UAF stack bug where KVM references a stack pointer around an exit to

Nothing popped up in our SEV CI, so...

Tested-by: Tom Lendacky <thomas.lendacky@gmail.com>

Thanks,
Tom

> 
> Thanks,

---

## [21] Sean Christopherson — 2026-03-02
*Subject: Re: [PATCH 14/14] KVM: x86: Add helpers to prepare kvm_run for
 userspace MMIO exit*

On Wed, Feb 25, 2026, Sean Christopherson wrote:
> On Wed, Feb 25, 2026, Rick P Edgecombe wrote:
> > On Tue, 2026-02-24 at 17:20 -0800, Sean Christopherson wrote:

Ooh, better idea.  Since TDX is the only direct user of
__kvm_prepare_emulated_mmio_exit() and it only supports lenths of 1, 2, 4, and 8,
kvm_prepare_emulated_mmio_exit() is the only path that actually needs to cap the
length.  Then the inner helper can assert a valid length.  Doesn't change anything
in practice, but I like the idea of making the caller be aware of the limitation
(even if that caller is itself a helper).

static inline void __kvm_prepare_emulated_mmio_exit(struct kvm_vcpu *vcpu,
						    gpa_t gpa, unsigned int len,
						    const void *data,
						    bool is_write)
{
	struct kvm_run *run = vcpu->run;

	KVM_BUG_ON(len > 8, vcpu->kvm);

	run->mmio.len = len;
	run->mmio.is_write = is_write;
	run->exit_reason = KVM_EXIT_MMIO;
	run->mmio.phys_addr = gpa;
	if (is_write)
		memcpy(run->mmio.data, data, len);
}

static inline void kvm_prepare_emulated_mmio_exit(struct kvm_vcpu *vcpu,
						  struct kvm_mmio_fragment *frag)
{
	WARN_ON_ONCE(!vcpu->mmio_needed || !vcpu->mmio_nr_fragments);

	__kvm_prepare_emulated_mmio_exit(vcpu, frag->gpa, min(8u, frag->len),
					 frag->data, vcpu->mmio_is_write);
}

---

## [22] Edgecombe, Rick P — 2026-03-03
*Subject: Re: [PATCH 14/14] KVM: x86: Add helpers to prepare kvm_run for
 userspace MMIO exit*

On Mon, 2026-03-02 at 18:24 -0800, Sean Christopherson wrote:
> Ooh, better idea.  Since TDX is the only direct user of
> __kvm_prepare_emulated_mmio_exit() and it only supports lenths of 1, 2, 4, and 8,

Seems ok and an improvement over the patch. But looking at the other callers,
there is quite a bit of min(8u, len) logic spread around. Might be worth a wider
cleanup someday.

---

## [23] Sean Christopherson — 2026-03-03
*Subject: Re: [PATCH 14/14] KVM: x86: Add helpers to prepare kvm_run for
 userspace MMIO exit*

On Tue, Mar 03, 2026, Rick P Edgecombe wrote:
> On Mon, 2026-03-02 at 18:24 -0800, Sean Christopherson wrote:
> > Ooh, better idea.  Since TDX is the only direct user of

LOL, "might".  :-)

Definitely a project for the future though, especially given how subtle and brittle
this all is.

---

## [24] Edgecombe, Rick P — 2026-03-03
*Subject: Re: [PATCH 14/14] KVM: x86: Add helpers to prepare kvm_run for
 userspace MMIO exit*

On Tue, 2026-03-03 at 11:44 -0800, Sean Christopherson wrote:
> > 
> > Seems ok and an improvement over the patch. But looking at the other

Trying to not set you off... :)

> 
> Definitely a project for the future though, especially given how subtle and

---

## [25] Sean Christopherson — 2026-03-05
*Subject: Re: [PATCH 00/14] KVM: x86: Emulator MMIO fix and cleanups*

On Tue, 24 Feb 2026 17:20:35 -0800, Sean Christopherson wrote:
> Fix a UAF stack bug where KVM references a stack pointer around an exit to
> userspace, and then clean up the related code to try to make it easier to

Applied to kvm-x86 mmio, with the hardened version of the helper in patch 14.
Thanks for the testing!

[01/14] KVM: x86: Use scratch field in MMIO fragment to hold small write values
        https://github.com/kvm-x86/linux/commit/0b16e69d17d8
[02/14] KVM: x86: Open code handling of completed MMIO reads in emulator_read_write()
        https://github.com/kvm-x86/linux/commit/4046823e78b0
[03/14] KVM: x86: Trace unsatisfied MMIO reads on a per-page basis
        https://github.com/kvm-x86/linux/commit/4f11fded5381
[04/14] KVM: x86: Use local MMIO fragment variable to clean up emulator_read_write()
        https://github.com/kvm-x86/linux/commit/523b6269f700
[05/14] KVM: x86: Open code read vs. write userspace MMIO exits in emulator_read_write()
        https://github.com/kvm-x86/linux/commit/cbbf8228c071
[06/14] KVM: x86: Move MMIO write tracing into vcpu_mmio_write()
        https://github.com/kvm-x86/linux/commit/72f36f99072c
[07/14] KVM: x86: Harden SEV-ES MMIO against on-stack use-after-free
        https://github.com/kvm-x86/linux/commit/144089f5c394
[08/14] KVM: x86: Dedup kvm_sev_es_mmio_{read,write}()
        https://github.com/kvm-x86/linux/commit/33e09e2f9735
[09/14] KVM: x86: Consolidate SEV-ES MMIO emulation into a single public API
        https://github.com/kvm-x86/linux/commit/326e810eaaa5
[10/14] KVM: x86: Bury emulator read/write ops in emulator_{read,write}_emulated()
        https://github.com/kvm-x86/linux/commit/3517193ef9c2
[11/14] KVM: x86: Fold emulator_write_phys() into write_emulate()
        https://github.com/kvm-x86/linux/commit/929613b3cd1a
[12/14] KVM: x86: Rename .read_write_emulate() to .read_write_guest()
        https://github.com/kvm-x86/linux/commit/216729846603
[13/14] KVM: x86: Don't panic the kernel if completing userspace I/O / MMIO goes sideways
        https://github.com/kvm-x86/linux/commit/4f09e62afcd6
[14/14] KVM: x86: Add helpers to prepare kvm_run for userspace MMIO exit
        https://github.com/kvm-x86/linux/commit/e2138c4a5be1

--
https://github.com/kvm-x86/linux/tree/next

---
