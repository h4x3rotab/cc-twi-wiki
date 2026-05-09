---
title: '[PATCH v5] x86/sev: Fix making shared pages private during kdump'
date: 2025-05-13
last_reply: 2025-05-13
message_count: 1
participants: ['Aithal, Srikanth']
---

## [1] Aithal, Srikanth — 2025-05-13

On 5/7/2025 3:12 PM, Borislav Petkov wrote:
> On Tue, May 06, 2025 at 06:35:29PM +0000, Ashish Kalra wrote:
>> From: Ashish Kalra <ashish.kalra@amd.com>

I tested the failure scenario with the patch hosted in the referenced 
Git tree [1]. The patch resolves the issue.

Tested-by: Srikanth Aithal <sraithal@amd.com>

[1]: 
https://git.kernel.org/pub/scm/linux/kernel/git/bp/bp.git/log/?h=tip-x86-urgent-sev

---
