# Deployment Guide

Status: Draft 1.

## 1. Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  Frontend   │────▶│   Backend   │
│  (Browser)  │     │  (Next.js)  │     │  (FastAPI)  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────┬───────────┼───────────┐
                    ▼              ▼           ▼           ▼
               ┌─────────┐    ┌──────────┐ ┌────────┐ ┌─────────┐
               │PostgreSQL│    │  Redis   │ │ MinIO  │ │ Object  │
               │ + pgvector│    │  (ARQ)   │ │ (S3)   │ │ Storage │
               └─────────┘    └──────────┘ └────────┘ └─────────┘
```

## 2. Environments

| Environment | Purpose | Data | URL |
|---|---|---|---|
| Local | Development | Synthetic | `http://localhost:3000` / `http://localhost:8000` |
| Demo | Congress demo | Synthetic/consented | TBD |
| Staging | Pre-release | Synthetic | TBD |
| Production | Real lawyers | Real (encrypted) | TBD |

**Never use real client data in Local, Demo, or Staging.**

## 3. Infrastructure Requirements

### 3.1 Kubernetes (Production)

| Component | Spec | Notes |
|---|---|---|
| PostgreSQL | 2+ nodes, 16GB RAM, 500GB SSD | pgvector, pg_trgm, citext; PITR enabled |
| Redis | 3-node cluster, 8GB RAM | ARQ job queue |
| MinIO | 4+ nodes, 1TB+ each | Erasure coding, versioning |
| Backend | 3+ pods, 2CPU/4GB each | HPA: CPU > 70% |
| Frontend | 3+ pods, 1CPU/2GB each | Static export + SSR |
| Ingress | TLS 1.3, WAF | Cloudflare/AWS ALB |
| Monitoring | Prometheus, Grafana, Loki, Tempo | Separate namespace |

### 3.2 Docker Compose (Local/Demo)

See `compose.yaml`:
```bash
docker compose -f compose.yaml up -d
# PostgreSQL: localhost:5433
# Redis: localhost:6379
# MinIO: localhost:9000 (console :9001)
```

## 4. Configuration

### 4.1 Required Environment Variables

| Variable | Local | Demo/Staging | Production |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://app_user:...@db:5432/legal_copilot` | Managed PG | Managed PG + IAM auth |
| `TEST_DATABASE_URL` | Same as above | CI only | N/A |
| `ALEMBIC_DATABASE_URL` | `postgresql+asyncpg://app_owner:...` | Migration runner | Migration runner |
| `MFA_ENCRYPTION_KEY` | `dev-key-32-bytes...` | **Required** | **Required** |
| `LLM_PROVIDER` | `mock` | `mock` or approved | **Approved only** |
| `LLM_APPROVED_PROVIDERS` | `mock` | `mock,gemini` | **From providers.md** |
| `GEMINI_API_KEY` | (empty) | Demo key | Prod key |
| `MINIO_ENDPOINT` | `minio:9000` | S3 endpoint | S3 endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | IAM role | IAM role |
| `MINIO_SECRET_KEY` | `local-dev...` | IAM role | IAM role |
| `MINIO_BUCKET` | `legal-copilot-dev` | `legal-copilot-demo` | `legal-copilot-prod` |
| `MINIO_SECURE` | `false` | `true` | `true` |
| `MALWARE_SCANNER` | `none` | `clamav` | `clamav` |
| `SESSION_COOKIE_SECURE` | `false` | `true` | `true` |
| `APP_ORIGIN` | `http://localhost:3000` | Demo URL | Prod URL |
| `LOG_LEVEL` | `DEBUG` | `INFO` | `INFO` |

### 4.2 Secrets Management

- **Never** commit `.env` files.
- Use external secrets manager: AWS Secrets Manager, HashiCorp Vault, or 1Password.
- Inject at pod startup via CSI driver or init container.
- Rotate on schedule: DB passwords (90d), API keys (180d), MFA key (365d).

## 5. Database Setup

### 5.1 Initial Bootstrap (One-time)

```bash
# As postgres superuser:
psql -c "CREATE DATABASE legal_copilot;"
psql -c "CREATE ROLE app_owner LOGIN PASSWORD '...';"
psql -c "CREATE ROLE app_user LOGIN PASSWORD '...' NOBYPASSRLS;"
psql -c "CREATE ROLE app_admin_ingest LOGIN PASSWORD '...' NOBYPASSRLS;"
psql -c "GRANT ALL ON DATABASE legal_copilot TO app_owner;"
```

### 5.2 Run Migrations

```bash
# Local (requires bootstrap URL):
ALEMBIC_DATABASE_URL=... ALEMBIC_BOOTSTRAP_DATABASE_URL=... uv run alembic -x bootstrap=true upgrade head

# Later migrations (as app_owner):
ALEMBIC_DATABASE_URL=... uv run alembic upgrade head
```

### 5.3 Verify Runtime Role

```bash
# Must connect as app_user without BYPASSRLS
uv run python -c "
from app.database import create_database_engine, verify_runtime_role
import asyncio
asyncio.run(verify_runtime_role(create_database_engine('...')))
print('OK')
"
```

## 6. Backend Deployment

### 6.1 Build Image

```dockerfile
# backend/Dockerfile.render (multi-stage)
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY . .
RUN uv build

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY --from=builder /app/dist/*.whl ./
RUN pip install ./*.whl
ENV PATH="/app/.venv/bin:$PATH"
CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -f backend/Dockerfile.render -t pokkhoai-backend:latest .
```

### 6.2 Run (Production)

```bash
# With proper env vars from secrets manager:
docker run -d \
  --name backend \
  -p 8000:8000 \
  -e DATABASE_URL=... \
  -e MFA_ENCRYPTION_KEY=... \
  -e LLM_PROVIDER=gemini \
  -e LLM_APPROVED_PROVIDERS=gemini \
  -e GEMINI_API_KEY=... \
  -e MINIO_ENDPOINT=... \
  -e MINIO_BUCKET=... \
  pokkhoai-backend:latest
```

### 6.3 Health Checks

```bash
# Liveness
curl -f http://localhost:8000/health

# Readiness
curl -f http://localhost:8000/health/ready
```

## 7. Frontend Deployment

### 7.1 Build

```bash
cd frontend
npm ci
npm run build  # Outputs to .next/
```

### 7.2 Run (Production)

```bash
# Option A: Standalone server
docker build -f frontend/Dockerfile -t pokkhoai-frontend .
docker run -d -p 3000:3000 pokkhoai-frontend

# Option B: Static export + CDN (preferred)
# next.config.ts: output: 'export'
# Deploy .next/ to Cloudflare Pages / Vercel / S3 + CloudFront
```

### 7.2 Environment Variables

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://api.example.com` |
| `NEXT_PUBLIC_APP_ORIGIN` | `https://app.example.com` |

## 8. Database Migrations in CI/CD

```yaml
# .github/workflows/deploy.yml
jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run migrations
        env:
          ALEMBIC_DATABASE_URL: ${{ secrets.ALEMBIC_DATABASE_URL }}
        run: |
          cd backend
          uv run alembic upgrade head
```

**Never** run migrations automatically on app startup. Run as separate step with approval.

## 9. Backup & Restore

### 9.1 Automated Backup (CronJob)

```yaml
# k8s/backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
spec:
  schedule: "0 2 * * *"  # Daily 02:00 UTC
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:16
            command:
            - pg_dump
            - -h
            - postgres-primary
            - -U
            - postgres
            - -d
            - legal_copilot
            - --no-owner
            - --no-privileges
            - --clean
            - --if-exists
            - -f
            - /backups/legal_copilot_$(date +%F_%H%M).sql
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: pg-credentials
                  key: postgres-password
            volumeMounts:
            - name: backup-storage
              mountPath: /backups
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

### 9.2 Restore Procedure

```bash
# 1. Stop backend pods
kubectl scale deployment backend --replicas=0

# 2. Restore from backup
psql -h postgres-primary -U postgres -d legal_copilot \
  -f /backups/legal_copilot_20261121_0200.sql

# 3. Run migrations (in case backup is older)
ALEMBIC_DATABASE_URL=... uv run alembic upgrade head

# 4. Start backend
kubectl scale deployment backend --replicas=3
```

### 9.3 Recovery Targets

| Metric | Target |
|---|---|
| RPO (Recovery Point Objective) | 24 hours (daily backup) |
| RTO (Recovery Time Objective) | 2 hours |
| Backup Retention | 30 days daily, 12 months monthly |

## 10. TLS & Network

| Layer | Config |
|---|---|
| Ingress → Frontend | TLS 1.3, HSTS, cert-manager |
| Frontend → Backend | mTLS (linkerd/istio) or private VPC |
| Backend → PostgreSQL | TLS required (`sslmode=verify-full`) |
| Backend → Redis | TLS or private VPC |
| Backend → MinIO | TLS (`MINIO_SECURE=true`) |

## 11. Security Hardening Checklist

- [ ] All secrets from secrets manager
- [ ] TLS 1.3 everywhere
- [ ] Database encryption at rest
- [ ] Object storage encryption at rest
- [ ] Backup encryption
- [ ] Malware scanner configured
- [ ] WAF rules deployed
- [ ] Rate limits configured
- [ ] Audit logs shipped off-box
- [ ] MFA required for lawyers
- [ ] Approved LLM provider only
- [ ] Dependency scanning in CI
- [ ] Container image scanning
- [ ] Runtime security (Falco/Tetragon)

## 12. Rollback Procedure

```bash
# 1. Revert deployment
kubectl rollout undo deployment/backend
kubectl rollout undo deployment/frontend

# 2. If migration applied, revert
# (requires manual SQL - test in staging first!)
ALEMBIC_DATABASE_URL=... uv run alembic downgrade -1

# 3. Verify health
curl -f https://api.example.com/health/ready
```

## 13. Open Questions

1. Cloud provider (AWS/GCP/Azure/on-prem)?
2. Managed PostgreSQL (RDS/Cloud SQL) or self-managed?
3. CDN for frontend assets?
4. Email provider for notifications?
5. Log aggregation provider (Grafana Cloud / Datadog / self-hosted)?
6. Certificate management (cert-manager / ACM / manual)?