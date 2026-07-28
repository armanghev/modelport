# Rate Limits

ModelPort does not implement its own client-facing rate limiter today. Rate-limit behavior mainly comes from upstream providers.

## What Happens

When an upstream provider rate-limits a request:

- the proxy records the failure
- provider health can be marked degraded
- fallback routing may be attempted if you supplied `fallback_providers` and no response body has been emitted yet

## Practical Mitigations

- configure fallback providers for important workloads
- spread traffic across providers when model parity allows it
- monitor `GET /analytics/requests` and `GET /admin/providers/health`
- override pricing carefully if you start moving traffic to more expensive backups
