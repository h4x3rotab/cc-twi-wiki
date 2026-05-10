---
title: '[BUG] Sleeping function called in __cpa_process_fault'
date: 2025-03-19
last_reply: 2025-03-19
message_count: 1
participants: ['Nikolay Borisov']
---

## [1] Nikolay Borisov — 2025-03-19

While playing with the memory encryption state under TDX I managed
to hit the following 2 warnings:

[  534.294565] BUG: sleeping function called from invalid context at ./include/linux/sched/mm.h:321
[  534.299968] in_atomic(): 1, irqs_disabled(): 0, non_block: 0, pid: 466, name: test
[  534.304346] preempt_count: 1, expected: 0
[  534.307131] RCU nest depth: 0, expected: 0
[  534.309895] 2 locks held by test/466:
[  534.309903]  #0: ffffffffb684b950 (mem_enc_lock){.+.+}-{4:4}, at: set_memory_decrypted+0x34/0x70
[  534.309957]  #1: ffffffffb684b998 (cpa_lock){+.+.}-{3:3}, at: __change_page_attr_set_clr+0x56/0xd0
[  534.309986] Preemption disabled at:
[  534.309989] [<0000000000000000>] 0x0
[  534.314658] CPU: 0 UID: 0 PID: 466 Comm: test Not tainted 6.14.0-rc5-default+ #28
[  534.314666] Hardware name: QEMU Standard PC (Q35 + ICH9, 2009), BIOS unknown 02/02/2022
[  534.314670] Call Trace:
[  534.314673]  <TASK>
[  534.314677]  dump_stack_lvl+0x7c/0x90
[  534.314698]  __might_resched+0x19f/0x2b0
[  534.314722]  __alloc_frozen_pages_noprof+0x262/0x300
[  534.314744]  alloc_pages_mpol+0x48/0x120
[  534.314761]  alloc_pages_noprof+0x4c/0x90
[  534.314766]  get_zeroed_page_noprof+0x15/0x80
[  534.314778]  populate_pgd+0x3f/0x1f0
[  534.314796]  __change_page_attr_set_clr+0x61/0xd0
[  534.314810]  __set_memory_enc_pgtable+0x127/0x1d0
[  534.314834]  set_memory_decrypted+0x44/0x70
[  534.314846]  read_mem+0x63/0x240
[  534.314870]  vfs_read+0xd9/0x370
[  534.314888]  ? memory_lseek+0x46/0x80
[  534.314895]  ? __lock_release.isra.0+0x5e/0x170
[  534.314917]  ? memory_lseek+0x46/0x80
[  534.314925]  ? memory_lseek+0x46/0x80
[  534.314933]  ? lock_release+0x87/0x160
[  534.314947]  ksys_read+0x68/0xe0
[  534.314961]  do_syscall_64+0x64/0x140
[  534.314975]  entry_SYSCALL_64_after_hwframe+0x76/0x7e
[  534.314989] RIP: 0033:0x7f1e70d111f2
[  534.314995] Code: c0 e9 c2 fe ff ff 50 48 8d 3d 8a c9 0a 00 e8 d5 1a 02 00 0f 1f 44 00 00 f3 0f 1e fa 64 8b 04 25 18 00 00 00 85 c0 75 10 0f 05 <48> 3d 00 f0 ff ff 77 56 c3 0f 1f 44 00 00 48 83 ec 28 48 89 54 24
[  534.314999] RSP: 002b:00007ffcbaef2b48 EFLAGS: 00000246 ORIG_RAX: 0000000000000000
[  534.315006] RAX: ffffffffffffffda RBX: 0000562bc68c9330 RCX: 00007f1e70d111f2
[  534.315010] RDX: 0000000000000001 RSI: 00007ffcbaef2b53 RDI: 0000000000000003
[  534.315013] RBP: 00007ffcbaef2b60 R08: 0000000000000000 R09: 00007f1e70e18d60
[  534.315016] R10: 0000000000000000 R11: 0000000000000246 R12: 0000562bc68c9120
[  534.315019] R13: 00007ffcbaef2c50 R14: 0000000000000000 R15: 0000000000000000
[  534.315043]  </TASK>




[   22.628756] Call Trace:
[   22.628759]  <TASK>
[   22.628764]  dump_stack_lvl+0x7c/0x90
[   22.628783]  __might_resched+0x19f/0x2b0
[   22.628804]  __alloc_frozen_pages_noprof+0x262/0x300
[   22.628823]  alloc_pages_mpol+0x48/0x120
[   22.628835]  alloc_pages_noprof+0x4c/0x90
[   22.628840]  get_zeroed_page_noprof+0x15/0x80
[   22.628849]  populate_pud+0x293/0x310
[   22.628863]  populate_pgd+0x9c/0x1f0
[   22.628876]  __change_page_attr_set_clr+0x61/0xd0
[   22.628888]  __set_memory_enc_pgtable+0x127/0x1d0
[   22.628909]  set_memory_decrypted+0x44/0x70
[   22.628919]  read_mem+0x63/0x240
[   22.628940]  vfs_read+0xd9/0x370
[   22.628949]  ? memory_lseek+0x46/0x80
[   22.628955]  ? __lock_release.isra.0+0x5e/0x170
[   22.628969]  ? memory_lseek+0x46/0x80
[   22.628975]  ? memory_lseek+0x46/0x80
[   22.628981]  ? lock_release+0x87/0x160
[   22.628994]  ksys_read+0x68/0xe0
[   22.629005]  do_syscall_64+0x64/0x140
[   22.629016]  entry_SYSCALL_64_after_hwframe+0x76/0x7e
[   22.629025] RIP: 0033:0x7ffb898ab1f2


The problem is that __change_page_attr->__cpa_process_fault->populate_pgd may allocate memory with GFP_KERNEL but is called under cpa_lock. Switching the get_zeroed_page calls in the last function to GFP_ATOMIC and also in alloc_pmd_page/alloc_pte_age does shut up the warning but Dave considered this just sweeping the issue under the rug. His suggestion was to preallocate the worst case, but taking care of the pmd level can become hairy. So any suggestion are welcomed.

---
