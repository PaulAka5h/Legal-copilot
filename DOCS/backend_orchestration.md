# Backend Developer Orchestration & Work Division

This document outlines the division of work between the two backend developers (**Backend Dev 1** and **Backend Dev 2**) working on the Legal-Copilot backend.

---

## 1. Team Division & Ownership Principles

To prevent merge conflicts, database migration clashes, and blurred responsibilities:
- **Backend Dev 1 (Core Infrastructure, Security & Case Workspace)** owns core models, database lifecycle, security/auth, and case lifecycle.
- **Backend Dev 2 (Data, Ingestion, OCR & AI Engine)** owns document processing, vector search/retrieval (RAG), and AI agent workflows.
- Shared interfaces (e.g. database schemas, Pydantic schemas, Celery/ARQ task definitions) must be defined and reviewed together before starting implementation of an interdependent chunk.

---

## 2. Chunk-by-Chunk Responsibilities

### Phase 1: Foundation
| Module | Scope | Owner |
|---|---|---|
| **Project Setup & Infra** | Docker Compose (`db`, `redis`, `minio`), uv pyproject.toml | **Backend Dev 1** |
| **Database & Base Models** | PostgreSQL + pgvector setup, Alembic baseline, RLS foundation | **Backend Dev 1** |
| **Auth & Security** | Argon2id, session cookies, CSRF, auth router, RBAC | **Backend Dev 1** |
| **Case Domain** | Cases, organizations, case membership, isolation queries | **Backend Dev 1** |
| **Background Worker Scaffold** | Celery/ARQ broker & worker runner integration | **Backend Dev 2** |

---

### Phase 2: Dashboards & Multi-Tenancy Portal
| Module | Scope | Owner |
|---|---|---|
| **Lawyer Dashboard API** | Endpoints for active cases, metrics, notifications, team access | **Backend Dev 1** |
| **Client Portal API** | Isolated `/api/v1/client` endpoints, access tokens, activation | **Backend Dev 1** |
| **Client Visibility Layer** | `client_visible_updates` & `client_shared_documents` tables/APIs | **Backend Dev 1** |
| **Audit Logging** | Structured append-only audit trail and request middleware | **Backend Dev 1** |

---

### Phase 3: Documents & Ingestion
| Module | Scope | Owner |
|---|---|---|
| **Storage Service** | S3/MinIO client, presigned URLs, validation & MIME checking | **Backend Dev 2** |
| **Document Processing Pipeline** | PyMuPDF text extraction, Word (`.docx`) extraction | **Backend Dev 2** |
| **OCR Worker** | Bengali & English Tesseract integration, page review model | **Backend Dev 2** |
| **Document Endpoints** | Upload handler, page review, status check | **Backend Dev 2** (reviewed with Dev 1) |

---

### Phase 4: Legal KB & RAG
| Module | Scope | Owner |
|---|---|---|
| **Scraper Dataset Ingestion** | Ingesting `data-scrapper/` JSON/JSONL into `legal_sources` | **Backend Dev 2** |
| **Chunking & Vector Embeddings** | Chunking engine, multilingual embedding model, pgvector index | **Backend Dev 2** |
| **Case-Scoped Vector Retrieval** | Hybrid search (full-text + vector) strictly filtered by `case_id` | **Backend Dev 2** |
| **RLS Verification for Search** | SQL test suite verifying non-member cases cannot be retrieved | **Backend Dev 1** |

---

### Phase 5 & 6: Case Analysis & Strategy Engine
| Module | Scope | Owner |
|---|---|---|
| **Claims & Verification Schema** | Fact/evidence models, source citations, claim verification | **Backend Dev 1** |
| **Case Analysis AI Worker** | Fact extraction, chronology/timeline, contradiction detector | **Backend Dev 2** |
| **Strategy Scenario Engine** | Chess-inspired strategy tree, opponent moves, counter-arguments | **Backend Dev 2** |
| **Version History & Superseding** | Strategy comparison endpoints, version immutability | **Backend Dev 1** |

---

### Phase 7 & 8: Hearings, Hardening & Security
| Module | Scope | Owner |
|---|---|---|
| **Hearings & Reassessment** | Hearing updates, strategy re-run trigger, client summary update | **Backend Dev 1** |
| **Isolation & Security Hardening** | Security test suite, penetration checks, RLS validation | **Backend Dev 1** |
| **Worker Performance & Scaling** | AI provider latency, batching, caching, job queue metrics | **Backend Dev 2** |

---

## 3. Communication & Code Review Protocols

1. **Schema First**: Any table change in `DOCS/database.md` or Alembic migration must be reviewed by both developers.
2. **OpenAPI Documentation Requirement**: Every single API endpoint built by either developer must be thoroughly documented in the OpenAPI specification:
   - Provide `summary` and detailed endpoint docstrings / `description`.
   - Explicit typed `response_model` (no raw dict returns).
   - Document parameter and payload constraints with `Field(description=...)`, `Query(...)`, `Path(...)`.
   - Specify accurate HTTP status codes and declare error schemas in `responses={4xx: ..., 5xx: ...}`.
   - Tag endpoints cleanly (`tags=[...]`) so Swagger UI (`/docs`) and Redoc (`/redoc`) provide structured, self-explanatory documentation for frontend integration.
3. **Isolation Guarantee**: No endpoint or worker code is marked "Done" without an automated test asserting tenant and case data isolation.
4. **Status Tracking**: Keep `DOCS/status.md` updated as modules move from `In progress` to `Done`.
