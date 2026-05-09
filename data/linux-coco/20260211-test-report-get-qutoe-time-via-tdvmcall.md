---
title: '[Test Report] get qutoe time via tdvmcall'
date: 2026-02-11
last_reply: 2026-03-10
message_count: 5
participants: ['Jun Miao', 'Kuppuswamy Sathyanarayanan']
---

## [1] Jun Miao — 2026-02-11

[Background]
Currently, many mobile device vendors (such as OPPO and Xiaomi) use TDVM for security management.
Each mobile terminal must perform remote attestation before it can access the TDVM confidential container.
As a result, there are a large number of remote attestation get-quote requests, especially in cases 
where vsock is not configured or misconfigured and cannot be used.

[Limitation]
Currently, the polling interval is set to 1 second, which allows at most one quote to be retrieved per second.
For workloads with frequent remote attestations, polling once per second severely limits performance.
Test like this:
[root@INTELTDX ~]# ./test_tdx_attest-thread
Start tdx_att_get_quote concurrent loop, duration: 1 s, threads: 1
Summary (tdx_att_get_quote)
Threads: 1
Mode: concurrent
Duration: requested 1 s, actual 1.036 s
Total:   1
Success: 1
Failure: 0
Avg total per 1s:   0.97
Avg success per 1s: 0.97
Avg total per 1s per thread:   0.97
Avg success per 1s per thread: 0.97
Min elapsed_time: 1025.95 ms
Max elapsed_time: 1025.95 ms

[Optimization Rationale]
But the actual trace the get quote time on GNR platform:
test_tdx_attest-598     [001] .....   371.214611: tdx_report_new: [debug start wait]===: I am in function wait_for_quote_completion    LINE=155===
test_tdx_attest-598     [001] .....   371.220287: tdx_report_new: [debug end wait]===: I am in function wait_for_quote_completion    LINE=162===

Cost time: 371.220287 - 371.215611 = 0.004676 = 4.6ms

The following test results were obtained on the GNR platform:
| msleep_interruptible(time)     | 1ms      | 5ms      | 1s         |
| ------------------------------ | -------- | -------- | ---------- |
| Duration                       | 1.004 s  | 1.005 s  | 1.036 s    |
| Total(Get Quote)               | 167      | 142      | 1          |
| Success:                       | 167      | 142      | 1          |
| Failure:                       | 0        | 0        | 0          |
| Avg total / 1s                 | 166.35   | 141.31   | 0.97       |
| Avg success / 1s               | 166.35   | 141.31   | 0.97       |
| Avg total / 1s / thread        | 166.35   | 141.31   | 0.97       |
| Avg success / 1s / thread      | 166.35   | 141.31   | 0.97       |
| Min elapsed_time               | 2.99 ms  | 6.85 ms  | 1025.95 ms |
| Max elapsed_time               | 10.76 ms | 10.93 ms | 1025.95 ms |



Jun Miao (1):
  virt: tdx-guest: Optimize the get-quote polling interval time

 drivers/virt/coco/tdx-guest/tdx-guest.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

---

## [2] Jun Miao — 2026-02-11
*Subject: [PATCH 1/1] virt: tdx-guest: Optimize the get-quote polling interval time*

The TD guest sends TDREPORT to the TD Quoting Enclave via a vsock or
a tdvmcall. In general, vsock is indeed much faster than tdvmcall,
and Quote requests usually take a few millisecond to complete rather
than seconds based on actual measurements.

The following get quote time via tdvmcall were obtained on the GNR:

| msleep_interruptible(time)     | 1s       | 5ms      | 1ms        |
| ------------------------------ | -------- | -------- | ---------- |
| Duration                       | 1.004 s  | 1.005 s  | 1.036 s    |
| Total(Get Quote)               | 167      | 142      | 167        |
| Success:                       | 167      | 142      | 167        |
| Failure:                       | 0        | 0        | 0          |
| Avg total / 1s                 | 0.97     | 141.31   | 166.35     |
| Avg success / 1s               | 0.97     | 141.31   | 166.35     |
| Avg total / 1s / thread        | 0.97     | 141.31   | 166.35     |
| Avg success / 1s / thread      | 0.97     | 141.31   | 166.35     |
| Min elapsed_time               | 1025.95ms| 6.85 ms  | 2.99 ms    |
| Max elapsed_time               | 1025.95ms| 10.93 ms | 10.76 ms   |

According to trace analysis, the typical execution tdvmcall get the
quote time is 4 ms. Therefore, 5 ms is a reasonable balance between
performance efficiency and CPU overhead.

And compared to the previous throughput of one request per second,
the current 5ms can get 142 requests per second delivers a
142× performance improvement, which is critical for high-frequency
use cases without vsock.

So, change the 1s (MSEC_PER_SEC) -> 5ms (MSEC_PER_SEC / 200)

Signed-off-by: Jun Miao <jun.miao@intel.com>
---
 drivers/virt/coco/tdx-guest/tdx-guest.c | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)

diff --git a/drivers/virt/coco/tdx-guest/tdx-guest.c b/drivers/virt/coco/tdx-guest/tdx-guest.c
index 4e239ec960c9..71d2d7304b1a 100644
--- a/drivers/virt/coco/tdx-guest/tdx-guest.c
+++ b/drivers/virt/coco/tdx-guest/tdx-guest.c
@@ -251,11 +251,11 @@ static int wait_for_quote_completion(struct tdx_quote_buf *quote_buf, u32 timeou
 	int i = 0;
 
 	/*
-	 * Quote requests usually take a few seconds to complete, so waking up
-	 * once per second to recheck the status is fine for this use case.
+	 * Quote requests usually take a few milliseconds to complete, so waking up
+	 * once per 5 milliseconds to recheck the status is fine for this use case.
 	 */
-	while (quote_buf->status == GET_QUOTE_IN_FLIGHT && i++ < timeout) {
-		if (msleep_interruptible(MSEC_PER_SEC))
+	while (quote_buf->status == GET_QUOTE_IN_FLIGHT && i++ < 200 * timeout) {
+		if (msleep_interruptible(MSEC_PER_SEC / 200))
 			return -EINTR;
 	}

---

## [3] Kuppuswamy Sathyanarayanan — 2026-02-20
*Subject: Re: [PATCH 1/1] virt: tdx-guest: Optimize the get-quote polling
 interval time*

Hi Miao,

On 2/11/2026 12:58 AM, Jun Miao wrote:
> The TD guest sends TDREPORT to the TD Quoting Enclave via a vsock or
> a tdvmcall. In general, vsock is indeed much faster than tdvmcall,

Thanks for sharing the data!

> According to trace analysis, the typical execution tdvmcall get the
> quote time is 4 ms. Therefore, 5 ms is a reasonable balance between

Since the average is 4 ms, why choose 5ms?

> 
> And compared to the previous throughput of one request per second,

Is this addressing a real customer issue or a theoretical improvement? 
If this is solving a real problem, could you share more details about
the use case and Quoting Service implementation you're testing against?

I ask because the Quote completion time depends heavily on the Quoting
Service implementation, which varies by deployment. Since we're optimizing
for performance, I'm wondering if we should consider an interrupt-based
approach using the SetupEventNotifyInterrupt TDVMCALL instead of polling.

> 
> So, change the 1s (MSEC_PER_SEC) -> 5ms (MSEC_PER_SEC / 200)

---

## [4] Miao, Jun — 2026-02-22
*Subject: RE: [PATCH 1/1] virt: tdx-guest: Optimize the get-quote polling
 interval time*

>On 2/11/2026 12:58 AM, Jun Miao wrote:
>> The TD guest sends TDREPORT to the TD Quoting Enclave via a vsock or a

Hi Kuppuswamy,

From the customer issue, the more detail "Test Report"
[PATCH 0/1] [Test Report] get qutoe time via tdvmcall
[Background]
Currently, many mobile device vendors (such as OPPO and Xiaomi) use TDVM for security management.
Each mobile terminal must perform remote attestation before it can access the TDVM confidential container.
As a result, there are a large number of remote attestation get-quote requests, especially in cases where vsock 
is not configured or misconfigured and cannot be used.

>If this is solving a real problem, could you share more details about the use case
>and Quoting Service implementation you're testing against?
Version Service chooses v1.22 DCAP:
https://download.01.org/intel-sgx/sgx-dcap/1.22/
Which includes the test case tdx-quote-generation-sample.
And the test case which I have shared all the test examples and the complete test environment with you through the team.

I’m curious about how the 1-second figure was obtained.
Was it based on actual test data, or was it just an estimate?

Warm regards
Jun Miao

>I ask because the Quote completion time depends heavily on the Quoting Service
>implementation, which varies by deployment. Since we're optimizing for

---

## [5] Kuppuswamy Sathyanarayanan — 2026-03-10
*Subject: Re: [PATCH 1/1] virt: tdx-guest: Optimize the get-quote polling
 interval time*

Hi Jun,

On 2/21/2026 6:17 PM, Miao, Jun wrote:
>> On 2/11/2026 12:58 AM, Jun Miao wrote:
>>> The TD guest sends TDREPORT to the TD Quoting Enclave via a vsock or a

Thanks for the details.

Since it's a real issue, I'm fine with updating the polling interval to 5ms. 
Given that deployed QEs respond fast, we should also reduce the maximum wait 
time to 2 seconds (from 30 seconds) to fail faster on errors.

You can use read_poll_timeout() from <linux/iopoll.h> to simplify the 
timeout handling instead of manual loop counters.

That said, polling with fixed intervals doesn't scale well since QE response 
times vary by implementation. The proper long-term solution is still an 
interrupt-based approach to eliminate the polling overhead entirely.

---
