# Monitoring and Observability

Status: Draft 1.

## 1. Goals

- Detect issues before clients are affected.
- Provide visibility into system health, performance, and security events.
- Enable rapid incident response with correlated logs, metrics, and traces.
- Meet legal/regulatory requirements for audit and data protection.

## 2. Four Pillars

| Pillar | What | Tools | Retention |
|---|---|---|---|
| Logs | Structured JSON, request ID correlation | stdout → Loki / file | 90 days hot, 1 year cold |
| Metrics | RED (rate, errors, duration), business KPIs | Prometheus + Grafana | 30 days hot, 1 year cold |
| Traces | Distributed request flow | OpenTelemetry → Tempo/Jaeger | 7 days |
| Alerts | Threshold + anomaly, paged to on-call | Alertmanager → PagerDuty/Slack | N/A |

## 3. Structured Logging

All backend logs are JSON via `backend/app/logging_config.py`:

```json
{
  "timestamp": "2026-11-21T14:30:00.123Z",
  "level": "info",
  "logger": "pokkhoai",
  "event": "request.completed",
  "request_id": "abc123",
  "method": "POST",
  "path": "/api/v1/cases",
  "status_code": 201
}
```

**Safe fields only**: `request_id`, `method`, `path`, `status_code`, `exception_type`, `provider`, `model`, `attempts`. Never log case data, document text, prompts, passwords, tokens.

### Log Levels
- `DEBUG`: Development only.
- `INFO`: Request start/end, business events.
- `WARN`: Retries, degraded performance, config warnings.
- `ERROR`: Request failures, unhandled exceptions.
- `CRITICAL`: Data loss, security breach suspected.

## 4. Key Metrics

### 4.1 RED Metrics (per endpoint)

| Metric | PromQL | Alert Threshold |
|---|---|---|
| Rate | `rate(http_requests_total[5m])` | < 0.1 req/s for 10m (stale) |
| Errors | `rate(http_requests_total{status=~"5.."}[5m])` | > 1% |
| Duration (p95) | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` | > 2s |

### 4.2 Business Metrics

| Metric | Description | Target |
|---|---|---|
| `cases_active` | Cases with `status=open` | Monotonic or explained |
| `documents_uploaded_total` | Uploads per day | Track trends |
| `ai_runs_total` | AI analysis/strategy runs | Track trends |
| `invitation_accepted_total` | Client invitations accepted | Track trends |
| `backup_size_bytes` | Size of latest backup | Alert if > 2x baseline |

### 4.3 Security Metrics

| Metric | Description | Alert |
|---|---|---|
| `auth_login_failed_total` | Failed logins | > 10/min from same IP |
| `auth_lockout_total` | Accounts locked | Any |
| `permission_denied_total` | 403 responses | Spike > 5x baseline |
| `invitation_reused_total` | Reused invitation tokens | Any |

## 5. Alert Rules

### 5.1 Critical (page immediately)

| Alert | Condition | Runbook |
|---|---|---|
| `APIHighErrorRate` | `rate(5xx[5m]) > 0.05` | Check logs, recent deploy |
| `DatabaseUnavailable` | `/health/ready` fails | Check pg, connections |
| `BackupFailed` | Backup job exit code != 0 | Check disk, pg_dump |
| `DiskSpaceCritical` | `disk_free_pct < 10%` | Clean up, expand |

### 5.2 Warning (notify on-call, no page)

| Alert | Condition |
|---|---|
| `APIHighLatency` | p95 > 2s for 10m |
| `QueueBacklog` | ARQ queue depth > 100 |
| `AuthAnomaly` | Lockouts or brute force spike |
| `BackupStale` | Last backup > 26h ago |

### 5.3 Info (dashboard only)

| Metric | Use |
|---|---|
| `DailyActiveLawyers` | Product metrics |
| `DocumentsPerCase` | Capacity planning |

## 6. Health Endpoints

| Endpoint | Checks | Use |
|---|---|---|
| `GET /health` | Process alive | Load balancer liveness |
| `GET /health/ready` | DB `SELECT 1` succeeds | Load balancer readiness |

## 7. Distributed Tracing

OpenTelemetry SDK initialized in `create_app()`:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanExporter

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanExporter(OTLPSpanExporter(endpoint="tempo:4317"))
)
tracer = trace.get_tracer("pokkhoai")
```

All FastAPI routes auto-instrumented via `opentelemetry-instrumentation-fastapi`.

## 8. Dashboard Layout (Grafana)

### 8.1 System Overview
- Request rate / error rate / p95 latency (last 1h)
- DB connections active / idle
- Redis memory / hit rate
- MinIO disk usage

### 8.2 Business Dashboard
- Active cases, clients, lawyers
- Documents uploaded (day/week)
- AI runs by type (analysis/strategy/reassessment)
- Client invitations sent/accepted

### 8.3 Security Dashboard
- Auth success/failure rates
- Lockouts, brute force attempts
- Permission denials by endpoint
- Invitation reuse attempts

## 9. Incident Response

1. **Detect**: Alert fires or manual report.
2. **Triage**: Check runbook, correlate logs/metrics/traces.
3. **Contain**: Revoke sessions, disable integration, scale up.
4. **Resolve**: Fix root cause, deploy.
5. **Review**: Post-incident doc within 48h.

Runbooks stored in `DOCS/runbooks/`.

## 10. Open Questions

1. Hosting provider Loki/Tempo/Prometheus managed or self-hosted?
2. Alert notification channel: PagerDuty, Opsgenie, Slack webhook?
3. Log retention policy for compliance (1 year minimum for audit).
4. Business metric targets need lawyer input.