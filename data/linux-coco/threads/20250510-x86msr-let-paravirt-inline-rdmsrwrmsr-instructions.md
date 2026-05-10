---
title: '[PATCH 0/6] x86/msr: let paravirt inline rdmsr/wrmsr instructions'
date: 2025-05-10
last_reply: 2025-05-10
message_count: 1
participants: ['Michael Kelley']
---

## [1] Michael Kelley — 2025-05-10

From: Juergen Gross <jgross@suse.com> Sent: Tuesday, May 6, 2025 2:20 AM
> 
> When building a kernel with CONFIG_PARAVIRT_XXL the paravirt

I've tested in SEV-SNP and TDX guests with paravisor on Hyper-V. Basic
smoke test showed no issues.

Tested-by: Michael Kelley <mhklinux@outlook.com>

> 
> There has been another approach by Xin Li, which used dedicated #ifdef

---
