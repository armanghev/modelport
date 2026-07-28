# Provider Issues

Provider issues in ModelPort usually fall into one of four buckets:

- missing credentials
- unreachable upstream
- provider-specific rate limits
- unsupported provider type

## Health Signals

ModelPort records recent provider health state and exposes it through:

- `GET /admin/providers`
- `GET /admin/providers/health`
- `GET /admin/providers/models`

Health cards report:

- status
- requests today
- success rate
- error rate
- average latency
- available model count
- last checked timestamp
- last error

## Local Provider Notes

Local endpoints such as Ollama can run without an API key, but they still need to be reachable at the configured base URL.

## Upstream Error Handling

ModelPort normalizes upstream failures into proxy errors and avoids returning raw upstream payloads directly. Retryable provider failures can trigger fallback routing before any response body is emitted.
