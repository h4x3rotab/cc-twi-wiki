---
topic_id: 117367917
subject: "Fw: [WIMSE] Re: Problem statement: early routing vs workload identity in mTLS"
participants: ["Mark Novak"]
first_post: 2026-01-20
last_post: 2026-01-20
message_count: 1
source: https://lists.confidentialcomputing.io/g/Trustworthy-Workload-Identity-SIG/topic/fw_wimse_re_problem/117367917
---

# Fw: [WIMSE] Re: Problem statement: early routing vs workload identity in mTLS

## Message 1 (#122) — Mark Novak — 2026-01-20 18:24 UTC

Potentially interesting discussion happening on the WIMSE IETF mailing list.

[toggle quoted message
Show quoted text](#quoted-261673146)

---

**From:** Jason Costello <jason@...>  
**Sent:** Tuesday, January 20, 2026 6:32 AM  
**To:** Olivier CANO <ocano=40scaleway.com@...>  
**Cc:** Wimse@... <Wimse@...>  
**Subject:** [WIMSE] Re: Problem statement: early routing vs workload identity in mTLS

Hi Olivier,

You might already be aware but I believe this (in progress, pre-adoption) work is somewhat related to your statement, though I'll let the authors clarify

<https://datatracker.ietf.org/doc/draft-rosomakho-tls-wimse-cert-hint/>

—Jason

  

On Tue, 20 Jan 2026 at 14:04, Olivier CANO <ocano=[40scaleway.com@...](mailto:40scaleway.com@...)> wrote:

> Hello WIMSE WG,  
>   
> I’d like to sanity-check a problem statement that keeps coming up in large-scale, mutualized load-balancer deployments using mTLS and workload identities (URI SAN / SPIFFE-like).  
>   
> Problem: in TLS, routing decisions for mutualized LBs must happen at ClientHello time. Today, the only widely deployable signal is SNI (DNS-shaped) and, marginally, ALPN. However, workload identity for mTLS is intentionally carried in certificate SANs (often
> URI SANs), which are only available after the handshake completes.  
>   
> This creates a structural mismatch:  
>   
> \* Routing needs an early signal.  
> \* Identity arrives late.  
> \* Operators are forced into synthetic DNS SNI, termination at the LB, or IP/port sharding.  
> \* ECH further weakens SNI as a long-term routing primitive.  
>   
> This is not about overloading SNI with identity, but about the lack of a principled, early, non-DNS routing signal that aligns with workload identity models promoted by WIMSE.  
>   
>
> Questions to the WG
>
> \* Is this problem considered in-scope for WIMSE as a cross-cutting identity + deployment concern?  
> \* If not, is there existing or planned work that addresses the routing / handshake phase gap for URI-based workload identities?  
>   
> I’m explicitly not proposing a solution yet (SNI extension, new TLS extension, etc.), only trying to validate whether the problem statement resonates and where it should live.  
>   
> Pointers to prior discussion or related drafts welcome.  
>   
> Thanks,  
> Olivier Cano
>
> --   
> WIMSE mailing list -- [wimse@...](mailto:wimse@...)  
> To unsubscribe send an email to [wimse-leave@...](mailto:wimse-leave@...)

contentLoaded(false, function() {
$('#quoted-261673146').on('show.bs.collapse', function() {
$('#qlabel-261673146').text("Hide quoted text");
})
$('#quoted-261673146').on('hide.bs.collapse', function() {
$('#qlabel-261673146').text("Show quoted text");
})
});
