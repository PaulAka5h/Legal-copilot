# Technical Requirements Document (TRD)

Status: Draft 1. Items marked **(decide)** need a decision during project setup. Items marked **(test)** must be chosen by testing, not by assumption.

## 1. Technology choices

| Area | Choice | Why | Trade-off |
|---|---|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui | Server-side role routing, good mobile performance, strong ecosystem | Needs care to keep secrets and role logic on the server |
| Backend | Python, FastAPI, Pydantic v2 | Python has the best OCR and NLP libraries; FastAPI gives typed APIs and an OpenAPI schema automatically | Async code needs discipline around blocking OCR and file work (run these in workers) |
| ORM and migrations | SQLAlchemy 2.x (async), Alembic | Mature, explicit | More boilerplate than lighter tools |
| Database | PostgreSQL 16+ | One store for relational data, row level security, full-text search, and vectors | Vector scale limits are lower than a dedicated vector database; fine for this scale |
| Vector search | pgvector (HNSW index) | Same database and same transaction as the permission data, so filters and security rules apply together | Filtered vector search needs care (see 6.4) |
| API style | REST with OpenAPI 3.1 | Resource-shaped data; schema is generated; TypeScript client can be generated; easy to test | Less flexible for ad hoc queries than GraphQL |
| Background jobs | Redis plus a worker library, Celery or ARQ **(decide)** | OCR, embeddings, and AI runs take longer than a request | Extra service to run |
| Object storage | S3-compatible (MinIO in development) | Private buckets, pre-signed URLs, lifecycle rules | Needs encryption and access policy setup |
| OCR | Tesseract with Bengali and English data behind an interface **(test)** | Open source, runs locally, no client data leaves the system | Accuracy on poor scans and handwriting is limited; a cloud OCR may be needed after privacy review |
| PDF text | PyMuPDF or pdfplumber | Fast page-level text and image extraction | Licence check for PyMuPDF (AGPL) **(decide)** |
| DOC and DOCX | python-docx for DOCX; LibreOffice headless to convert DOC to DOCX or PDF | Handles both | LibreOffice must run in a sandbox |
| Embeddings | A multilingual model with Bangla support, for example BGE-M3 or multilingual-e5 **(test)** | Documents and law texts are in Bangla and English | Dimension and speed vary; must be tested on Bangla legal text |
| LLM | Provider-agnostic gateway; model chosen by evaluation **(test)** | Avoids lock-in; privacy and cost differ by provider | A gateway adds a layer to maintain |
| Auth | Backend-managed sessions, Argon2id, httpOnly secure cookies | Keeps tokens out of JavaScript, simple to revoke | Must handle CSRF |
| Search (text) | PostgreSQL full-text plus pg_trgm | Keyword and fuzzy match for names, section numbers | Bangla stemming is limited; combine with vectors |
| Frontend data | TanStack Query with a client generated from OpenAPI | Typed, cached | Requires regenerating after API changes |
| Testing | pytest, Playwright, Vitest, schemathesis | Covers unit, end-to-end, and API contract fuzzing | Setup time |
| Containers | Docker and Docker Compose for development | Reproducible | |

## 2. System requirements

### 2.1 Functional modules (backend)

`auth`, `cases`, `documents`, `processing`, `legal_kb`, `analysis`, `strategy`, `hearings`, `client_portal`, `agents`, `audit`, `notifications`. Each module has its own router, service layer, repository layer, Pydantic schemas, and tests.

### 2.2 Environments

| Environment | Purpose | Data |
|---|---|---|
| Local | Development | Synthetic data only |
| Demo | Congress | Synthetic or consented sample data only; mock or approved LLM provider |
| Staging | Pre-release tests | Synthetic data |
| Production | Real lawyers | Real data under `Security.md` controls |

## 3. API design

### 3.1 Conventions
- Base path `/api/v1` for lawyer and shared endpoints. Client portal endpoints live under `/api/v1/client`. The two namespaces use different schemas and different authorization dependencies.
- JSON bodies; UUID identifiers; ISO 8601 timestamps in UTC.
- Pagination: cursor-based (`?cursor=...&limit=...`).
- Errors: `application/problem+json` with `type`, `title`, `status`, `detail`, `instance`, and `request_id`.
- Long-running work: `POST` returns `202 Accepted` with a `job` resource. Progress via `GET /jobs/{id}` and server-sent events at `/jobs/{id}/events`.
- Idempotency: an `Idempotency-Key` header on job-starting and notification-sending endpoints.
- Concurrency: `ETag` and `If-Match` on editable resources (case, hearing, extracted text).
- Versioned AI resources return `version` and `supersedes_id`.
- OpenAPI schema is served at `/openapi.json` in non-production and exported in CI to build the TypeScript client.
- CORS allows only the web app origin. CSRF protection on cookie-authenticated state-changing requests.

### 3.2 Endpoint catalog (initial)

**Auth**
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | Lawyer registration |
| POST | `/auth/login` | Sets session cookie |
| POST | `/auth/logout` | |
| POST | `/auth/logout-all` | Revokes all sessions |
| POST | `/auth/password/forgot` | Always returns the same response |
| POST | `/auth/password/reset` | Single-use token |
| POST | `/auth/mfa/setup` and `/auth/mfa/verify` | TOTP |
| POST | `/auth/invitations/accept` | Client sets password using invitation token |
| GET | `/me` | Current user and role |

**Clients and cases (lawyer)**
| Method | Path |
|---|---|
| GET, POST | `/clients` |
| GET, PATCH | `/clients/{client_id}` |
| GET, POST | `/cases` |
| GET, PATCH | `/cases/{case_id}` |
| POST | `/cases/{case_id}/close` |
| POST | `/cases/{case_id}/reopen` |
| GET, POST | `/cases/{case_id}/members` |
| DELETE | `/cases/{case_id}/members/{member_id}` |
| POST | `/cases/{case_id}/invitations` |
| DELETE | `/cases/{case_id}/invitations/{id}` |
| GET | `/cases/{case_id}/timeline` |
| GET | `/cases/{case_id}/audit` |

**Documents**
| Method | Path | Notes |
|---|---|---|
| POST | `/cases/{case_id}/documents` | Multipart upload, multiple files |
| GET | `/cases/{case_id}/documents` | |
| GET | `/documents/{id}` | Metadata and processing status |
| GET | `/documents/{id}/download-url` | Short-lived pre-signed URL, audited |
| GET | `/documents/{id}/pages` | Extracted pages with OCR confidence |
| PATCH | `/documents/{id}/pages/{page_no}` | Lawyer correction, creates a new text version |
| POST | `/documents/{id}/reprocess` | |
| DELETE | `/documents/{id}` | Authorized deletion with reason |

**Analysis**
| Method | Path |
|---|---|
| POST | `/cases/{case_id}/analysis-runs` |
| GET | `/cases/{case_id}/analyses` |
| GET | `/analyses/{id}` |
| GET | `/cases/{case_id}/facts` |
| GET | `/cases/{case_id}/evidence` |
| GET | `/cases/{case_id}/contradictions` |
| GET | `/cases/{case_id}/gaps` |

**Legal research**
| Method | Path |
|---|---|
| POST | `/cases/{case_id}/research-runs` |
| GET | `/cases/{case_id}/research-results` |
| GET | `/legal-sources` |
| GET | `/legal-sources/{id}` and `/legal-sources/{id}/versions` |
| POST | `/legal-sources/verify-citation` |

**Strategy**
| Method | Path |
|---|---|
| POST | `/cases/{case_id}/strategy-runs` |
| GET | `/cases/{case_id}/strategies` |
| GET | `/strategies/{id}` and `/strategies/{id}/scenarios` |
| PATCH | `/strategies/{id}` (lawyer edit, creates a new version) |
| POST | `/strategies/{id}/approve` and `/strategies/{id}/reject` |
| GET | `/cases/{case_id}/strategy-comparisons/latest` |
| GET | `/strategies/{id}/history` |

**Hearings**
| Method | Path |
|---|---|
| GET, POST | `/cases/{case_id}/hearings` |
| GET, PATCH | `/hearings/{id}` |
| POST | `/hearings/{id}/updates` (starts reassessment job) |
| GET | `/hearings/{id}/reassessment` |
| GET | `/calendar` |

**Client-visible content (lawyer side)**
| Method | Path |
|---|---|
| GET, POST | `/cases/{case_id}/client-updates` |
| PATCH | `/client-updates/{id}` (edit draft) |
| POST | `/client-updates/{id}/publish` |
| POST | `/client-updates/{id}/withdraw` |
| POST, DELETE | `/cases/{case_id}/shared-documents` |
| GET, POST, PATCH | `/cases/{case_id}/tasks` |
| PATCH | `/cases/{case_id}/client-visibility` (which summary fields the client sees) |

**Client portal**
| Method | Path |
|---|---|
| GET | `/client/cases` |
| GET | `/client/cases/{case_id}` (status, stage, plain summary) |
| GET | `/client/cases/{case_id}/updates` |
| GET | `/client/cases/{case_id}/hearing` (next confirmed hearing) |
| GET | `/client/cases/{case_id}/tasks` |
| PATCH | `/client/tasks/{id}` (mark done, upload requested document) |
| GET | `/client/cases/{case_id}/documents` |
| GET | `/client/documents/{id}/download-url` |
| GET | `/client/notifications` |

**Admin (platform)**
| Method | Path |
|---|---|
| POST | `/admin/legal-sources/ingest` |
| POST | `/admin/legal-sources/{id}/approve` |
| GET | `/admin/health` |

Administrators cannot read private case data through any endpoint.

## 4. Authentication and authorization

### 4.1 Identity
- `users` holds an email, Argon2id password hash, role (`lawyer`, `client`, `admin`), and status.
- Sessions: opaque session ID in an httpOnly, secure, SameSite=Lax cookie, stored server-side with expiry and device info. Rotation on login and privilege change.
- Rate limiting and lockout backoff on login, reset, and invitation endpoints.

### 4.2 Authorization layers
1. **Route dependency:** checks the role for the namespace (`lawyer` for `/api/v1/*`, `client` for `/api/v1/client/*`).
2. **Case membership check:** a `CaseAccess` dependency loads the `case_members` row for the user and case, and returns the permission set. No row, no access.
3. **Database row level security:** every case-scoped table has policies that use `current_setting('app.current_user_id')`. If application code forgets a check, the database still blocks the row.
4. **Client isolation by construction:** the client portal reads only from client-visible tables.

### 4.3 Permission model
`case_members.role`: `lead_lawyer`, `team_lawyer`, `assistant`, `client`. Permissions are explicit flags (for example `can_upload`, `can_run_ai`, `can_publish_updates`, `can_close_case`). Clients have none of the lawyer flags.

### 4.4 Client invitations
Invitation tokens are random (at least 256 bits), stored hashed, single-use, expire within a short window, and are tied to a client profile and a case. Accepting an invitation creates or links a client account and a `case_members` row. A case ID or client reference alone does nothing without authentication and membership.

## 5. Document processing pipeline

```
Upload ─► validate ─► store original ─► queue job
   job: detect type ─► extract text or OCR ─► quality check ─► save pages
        ─► clean ─► chunk ─► embed ─► store chunks ─► status = ready
```

### 5.1 Validation
- Check content by magic bytes, not extension. Allow-list: PDF, DOC, DOCX, JPEG, PNG (more later).
- Size limit per file and per request; page-count limit per PDF; pixel-count limit per image (image bomb protection).
- Reject encrypted PDFs with a clear message (or ask for a password later).
- Malware scan (ClamAV) before processing. Files that fail go to quarantine.
- Strip active content (PDF JavaScript, Word macros) during conversion. Do not execute macros.
- Run conversion and OCR in a sandboxed worker with no network access and limited CPU, memory, and time.

### 5.2 Extraction
- Digital PDF: text layer per page. If a page has little or no text, send that page to OCR.
- DOCX: paragraph and heading text. Map to pages via a PDF rendering when page numbers are needed.
- Images and scans: pre-process (rotate, deskew, denoise, contrast), then OCR with Bengali and English models.
- Store per page: `text`, `source_method` (`text_layer`, `ocr`), `ocr_confidence`, `quality_flag`, `language`.
- Pages below the confidence threshold or with very little text get `quality_flag = needs_review`.
- Handwriting is detected where possible and flagged `uncertain`.

### 5.3 Lawyer correction
A correction creates a new `extracted_page_versions` row with the editor and time. The latest approved version feeds chunking. The original OCR output is kept.

### 5.4 Chunking
- Chunk by paragraph or sentence groups, target around 300 to 600 tokens with a small overlap **(test)**.
- A chunk never crosses a page boundary in the first version, so page references stay exact.
- Each chunk stores: `case_id`, `organization_id`, `document_id`, `page_number`, `char_start`, `char_end`, `text_version_id`, `embedding_model`, `embedding_version`, `access_class`.

### 5.5 Reprocessing
Changing a page version, the chunker, or the embedding model creates new chunk rows with a new `embedding_version`. Old rows are marked inactive, then deleted after the new set is confirmed.

## 6. RAG design

### 6.1 Two knowledge areas
- **Private case knowledge:** `document_chunks`, scoped by case.
- **Shared legal knowledge:** `legal_chunks` linked to `legal_source_versions`, readable by authenticated lawyers under licence terms.

They live in separate tables and are queried by separate skills.

### 6.2 Retrieval
1. Build a query (from the question and case issues).
2. Run a hybrid search: vector similarity plus full-text, restricted by `case_id` (and for law, by status and jurisdiction).
3. Merge with reciprocal rank fusion.
4. Optionally rerank with a cross-encoder **(test)**.
5. Return chunks with source metadata. The agent cites chunk IDs, which resolve to document and page.

### 6.3 Permission filtering
The case filter is part of the SQL query, not a post-filter in Python. Row level security applies on top. The retrieval skill takes its scope from the run, not from model output.

### 6.4 pgvector notes
- Use HNSW indexes for the legal knowledge base.
- For private chunks, queries always include `case_id`. Per-case row counts are small, so an index scan on `case_id` followed by exact distance sorting is accurate and fast; add partial or partitioned indexes only if measurement shows a need.
- If approximate index scans are used with filters, enable iterative scanning (available in recent pgvector versions) and verify recall with tests **(test)**.
- Fix the embedding dimension per model and store the model name with every vector. Changing models means re-embedding.

### 6.5 Citations
Agents return chunk or legal source version IDs. The server resolves them to document and page or source and provision. IDs that do not resolve cause the claim to be rejected before it is shown.

## 7. AI integration

- **Gateway:** one module exposes `generate_structured(schema, prompt, scope)` and `embed(texts)`. Providers are plugins (mock, local, external).
- **Structured output:** responses are validated against Pydantic schemas; one retry on invalid output.
- **Prompt storage:** versioned files; the prompt version is saved on every run.
- **Cost and time limits:** per run and per user per day, configurable.
- **Mock provider:** deterministic canned outputs for tests and for local work without a key.
- **Data egress control:** the gateway checks that the selected provider is on the approved list in configuration before sending any case content.
- **No training use:** use provider settings or contract terms that disallow training on submitted data; record the setting per provider.

Agent behavior is specified in `Skills and agents.md`.

## 8. Strategy engine technical design

### 8.1 Data model
- `strategies` (versioned) with legal basis, supporting claims, weaknesses, missing evidence.
- `strategy_scenarios`: a tree using `parent_id`, with node types `opposing_argument`, `our_response`, `remaining_risk`.
- `strategy_comparisons`: rubric ratings per strategy, assumptions, and the summary.

### 8.2 Procedure
1. Generate K candidate strategies (default 4).
2. For each, expand the scenario tree to a depth limit D (default 2 exchanges) and breadth limit B (default 3 opposing arguments per node).
3. Prune branches judged low relevance, recording why.
4. Rate each strategy on the five rubric dimensions.
5. Apply the aggregation rule (overall rating capped by the weakest critical dimension).
6. Verify claims independently.
7. Save as a draft version for lawyer review.

The depth, breadth, and K are settings and are recorded on each run.

### 8.3 Reassessment
After a hearing update the engine compares the new facts with the previous analysis version, marks which strategies and branches are affected, re-runs only affected parts where possible, and stores a new version linked to the old one with a field-level diff.

## 9. Client portal technical design

- Separate tables: `client_visible_updates`, `client_shared_documents`, `client_visible_case_fields`, `client_tasks`.
- Publishing an update copies approved content into these tables; later edits to internal notes do not change it.
- Withdrawing an update hides it from the client and keeps it in the audit trail.
- Pre-signed download URLs are issued only for documents with an active share record and only to authenticated clients with active membership.
- On case closure, the membership for clients is set to `revoked` (or `read_only` by policy). Row level security uses membership status, so access stops immediately.

## 10. Notifications and tasks

- In-app notifications stored in `notifications`, delivered through polling or server-sent events.
- Email delivery is an integration boundary (provider to be chosen). Do not put case details in email bodies; use a generic message with a sign-in link.
- Client tasks are created by the lawyer and visible to the client only when marked client-visible.

## 11. Audit logging

Audit events are written in the same transaction as the action. Fields: actor, role, action, object type and ID, case ID, timestamp, IP, user agent, request ID, and a small details object (no document text). The table is append-only (no update or delete grants for the application role) and rows carry a hash chain value to detect tampering **(decide)**.

## 12. Observability

- Structured logs with request ID, user ID, case ID. No document text or prompts in logs.
- Metrics: request rate and latency, job queue depth, OCR duration and failure rate, AI run duration, tokens, cost, verification failure rate.
- Tracing across web, API, and worker.
- Alerts on failed jobs, queue backlog, auth anomalies, and authorization denials spikes.

## 13. Performance targets (starting values, adjust after measurement)

| Item | Target |
|---|---|
| API p95 for non-AI endpoints | under 400 ms |
| Upload acknowledgment | under 2 s |
| Text extraction of 20-page digital PDF | under 30 s |
| OCR of one scanned page | under 10 s on baseline hardware (test) |
| Retrieval query | under 500 ms |
| Case analysis run | progress visible within 5 s; complete in minutes, with stage progress |
| Strategy run | same as above, with a hard time limit and a partial result option |

## 14. Testing strategy

- **Unit tests:** services, parsers, chunking, date normalization, rubric aggregation.
- **API tests:** every endpoint against role and membership combinations; schemathesis for contract fuzzing.
- **Isolation tests (mandatory in CI):** two lawyers, two clients, overlapping text; assert no cross-access via API, retrieval, downloads, notifications, or search.
- **Pipeline tests:** golden files in Bangla, English, and mixed; corrupt, encrypted, and oversize files.
- **Agent tests:** schema validity, rejection of unsourced claims, prompt injection samples, evaluation set from `Skills and agents.md`.
- **End-to-end:** Playwright flows from `UserFlow.md`.
- **Security tests:** see `Security.md`.

## 15. CI/CD

- Pull request checks: lint, type check, unit tests, isolation tests, OpenAPI export and client generation diff, dependency and secret scanning.
- Migrations run in CI against a fresh database and against a copy of the previous schema.
- Build container images; deploy to staging; run smoke and end-to-end tests; manual approval to production.

## 16. Configuration

Environment variables (no values in the repo):

```
DATABASE_URL
REDIS_URL
OBJECT_STORE_ENDPOINT, OBJECT_STORE_BUCKET, OBJECT_STORE_ACCESS_KEY, OBJECT_STORE_SECRET_KEY
SESSION_SECRET
APP_BASE_URL, ALLOWED_ORIGINS
LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, LLM_APPROVED_PROVIDERS
EMBEDDING_MODEL, EMBEDDING_DIM
OCR_ENGINE, OCR_LANGS, OCR_CONFIDENCE_THRESHOLD
MAX_UPLOAD_MB, MAX_PDF_PAGES
STRATEGY_K, STRATEGY_DEPTH, STRATEGY_BREADTH
CLAMAV_HOST
SMTP_* (when email is added)
```

## 17. Risks and dependencies

| Item | Note |
|---|---|
| Legal data availability and licence | Needs confirmation per source before ingestion |
| Bangla OCR quality | Test on real scans early; plan a cloud OCR option behind the interface |
| Embedding quality on Bangla legal text | Compare models on a small labelled retrieval set |
| LLM provider terms | Review before any real client data is sent |
| PyMuPDF licence | Check compatibility or use an alternative |
| Pgvector filtered search recall | Verify with tests |
| Time budget for the Congress | Build the vertical slice first |
