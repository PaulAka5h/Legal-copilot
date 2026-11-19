# Backend Dev 1 Close-out: Batch 0 Gap Report

Date: 2026-11-19 · Branch: `dev1/phase-closeout` · Author: Backend Dev 1 (agent)

> **Scope and limits of this audit.** This machine (Windows 10) has **no usable
> Python environment** (Git Bash has a bare `python3` 3.15 with no pip and no
> packages; PowerShell has none), **no `uv`, no Docker, no PostgreSQL, and no WSL distribution**.
> Nothing could be executed: no `pytest`, no `alembic heads/current`, no app boot,
> no catalog queries. Every finding below comes from **reading the code and
> migrations**. Items that need a live run are marked **BLOCKED (env)**. No
> status row is moved to Done on the basis of this report.

---

## 0. Top-of-report defects (stop-and-ask conditions)

### S1 — SECURITY DEFECT: `gemini` is approved by default (providers.md mismatch)

`DOCS/providers.md` approves **only `mock`**. The code and config approve Gemini:

| File | Line | Problem |
|---|---|---|
| `backend/src/ai/gateway.py` | 72 | `os.getenv("LLM_APPROVED_PROVIDERS", "mock,gemini")`: default allow-list includes `gemini` |
| `backend/.env.example` | 18–20 | `LLM_PROVIDER=gemini`, `GEMINI_API_KEY=…`, `GEMINI_MODEL=…`: copying the example selects Gemini |
| `backend/scripts/live_gemini_demo.py` | 47 | Builds a gateway with `approved_providers=["gemini","mock"]` and sends prompts to Google |
| `Makefile` | `test-gemini-live` | One command sends data to an unreviewed provider |
| `backend/pyproject.toml` | deps | `google-genai` is a runtime dependency |

Per providers.md approval rule 4 this is a defect. Proposed fix (Dev 2 code, so it is
filed as a request and not applied): default `LLM_APPROVED_PROVIDERS=mock`, set
`.env.example` to `LLM_PROVIDER=mock` / `LLM_APPROVED_PROVIDERS=mock`, and gate the
live demo behind an explicit review record. **I sent no data to any provider.**
`GEMINI_API_KEY` is not set in this shell.

### S2 — CROSS-TENANT EXPOSURE: Dev 2 case routes have no authentication or case authorization

Every route in `backend/src/analysis/router.py` and `backend/src/strategy/router.py`
(mounted at `/api/v1/cases/{case_id}/…` by `backend/src/main.py`) runs with **no
session, no role check, no `CaseAccess`, no RLS, and no CSRF check**. State lives
in a process-global in-memory dict keyed by the `case_id` string. The reviewer or
approver identity comes from the **request body** (`reviewer_id`, `lawyer_id`).
`src/main.py` also exposes `/api/v1/documents/process` (anonymous upload that
echoes 150-character page text previews) and `/api/v1/legal-kb/search`
(anonymous). CORS is `allow_origins=["*"]` with `allow_credentials=True`.

Impact: anyone who can reach the dev server can read, generate, approve or select
strategies and analyses for any case ID. `make backend-dev` starts **this** app.
It is not a confirmed leak of real data (all state is synthetic and in-memory),
but it is a cross-tenant break by construction. Per §5 of the brief I am stopping
here.

### S3 — Migration chain cannot reach head on a fresh database — FIXED IN CODE 2026-11-19

> Resolution: the owner authorized Dev 1 to amend 0009. Policies now use
> `app.is_lawyer_member(case_id)` and `strategies_client_read` is removed.
> Regression tests were added in `backend/tests/test_migrations.py`. A static check
> over all revisions finds no undefined `app.*` function in any policy. A live
> downgrade/upgrade has **not** been run (environment). Grants and the composite FK
> are still missing (Batch 2).

`0009_phase6_strategy_engine` (Dev 2) creates policies with
`app.has_case_access(case_id)`. **No migration defines `app.has_case_access`.**
The baseline helpers are `app.is_lawyer_member` / `app.is_client_member`.
`alembic upgrade head` on a fresh DB should fail at 0009 (BLOCKED (env) to confirm).
0009 also:
- grants **no** privileges on `strategies`, `strategy_scenarios` or `strategy_comparisons` to `app_user`, so the tables are unusable by the app role;
- adds `strategies_client_read`, which lets clients read approved strategies directly. That breaks Legal Product Rule 8 and database.md §12 ("client dashboard reads only client-visible tables");
- has `organization_id uuid NOT NULL` with no FK and no `(case_id, organization_id)` composite FK, unlike 0007 tables.

The strategy engine code does not use these tables at all (in-memory only), so the
"PostgreSQL RLS verified" claim in status.md cannot be true against this repo.
Fixing this needs either an edit to 0009 (forbidden for me) or a decision. See open questions.

---

## 1. Runtime checks (all BLOCKED (env))

| Check | Result |
|---|---|
| `alembic heads` | Not run. **Static:** linear chain `0001 → … → 0009`, one head `0009_phase6_strategy_engine`, no branch labels |
| `alembic current` | Not run (no DB) |
| `downgrade base → upgrade head` | Not run. **Static prediction: fails at 0009** (S3) |
| Full `pytest` as `app_user` | Not run. Static count below |
| `/health`, `/health/ready`, `/docs`, `/redoc`, `/openapi.json` | Not run |
| Live RLS catalog queries | Not run. Section 2 is reconstructed from migration source |

**Static test inventory** (test functions; parametrisation may raise counts):

| Group | Files | Functions | Needs DB? |
|---|---|---|---|
| Dev 1 (`tests/test_*.py`) | 13 | 42 | Yes for all but `test_auth_security.py`, `test_migrations.py`, and parts of `test_app.py` |
| Dev 2 (`tests/{ai,analysis,documents,legal_kb,strategy}`) | 18 | 69 | Only `legal_kb/test_pgvector_live.py` |

**Why tests skip** (explains "111 passed + 23 skipped" in rename-report.md):
1. `tests/conftest.py:23` and `tests/test_database.py:63`: skip when `TEST_DATABASE_URL` is unset. **This is most Dev 1 DB/isolation tests.** So the 111/23 run did not exercise Dev 1 isolation tests.
2. `tests/legal_kb/test_pgvector_live.py:24`: skips unless a separate PostgreSQL is on `localhost:5433` with hard-coded `researchsphere:devpassword`.
3. `tests/legal_kb/test_ingestion.py:90`, `test_vector_pipeline.py:60`: skip because the dataset path is a hard-coded `/home/arafath/...` absolute path (protected pending Akash).

---

## 2. Case-scoped tables: RLS reconstructed from migrations

Legend: ✓ present · ✗ missing · n/a. "Grants" = privileges to `app_user`.

| Table | Created in | RLS | FORCE | Policies | `app_user` grants | Isolation test |
|---|---|---|---|---|---|---|
| `cases` | 0001 | ✓ | ✓ | lawyer read/create/update; `client_read_open_cases` (0008) | SELECT, INSERT (+UPDATE via policy/cols) | ✓ `test_database`, `test_domains`, `test_phase2_exit` |
| `case_stages` | 0001 | ✓ | ✓ | `lawyer_case_stages` | SELECT, INSERT, DELETE | ✓ direct RLS |
| `case_members` | 0001 | ✓ | ✓ | read/create/update | SELECT, INSERT | ✓ |
| `case_invitations` | 0001 | ✓ | ✓ | `lawyer_case_invitations` | SELECT, INSERT | ✓ |
| `hearings` | 0007 | ✓ | ✓ | lawyer ALL; client SELECT if confirmed and open | SELECT, INSERT, UPDATE | partial (client read only) |
| `client_visible_updates` | 0007 | ✓ | ✓ | lawyer ALL; client published and open | SELECT, INSERT, UPDATE | ✓ `test_b13`, exit gate |
| `client_shared_documents` | 0007 | ✓ | ✓ | lawyer ALL; client active and open | SELECT, INSERT, UPDATE | ✗ no API test |
| `client_tasks` | 0007 | ✓ | ✓ | lawyer ALL; client **SELECT only** | SELECT, INSERT, UPDATE | ✗ |
| `client_visible_case_fields` | 0007 | ✓ | ✓ | lawyer ALL; client SELECT | SELECT, INSERT, UPDATE | ✗ |
| `notifications` (nullable `case_id`) | 0007 | ✓ | ✓ | `notification_owner` (user_id only) | SELECT, INSERT, UPDATE | ✗ |
| `audit_logs` (nullable `case_id`) | 0002 | ✓ | ✓ | insert via `write_audit_event`; read policy | SELECT (INSERT only via function) | ✓ `test_b10` |
| `strategies` | 0009 | ✓ | ✓ | uses **undefined** `has_case_access`; client read ✗ (should not exist) | **none** | ✗ |
| `strategy_scenarios` | 0009 | ✓ | ✓ | undefined function | **none** | ✗ |
| `strategy_comparisons` | 0009 | ✓ | ✓ | undefined function | **none** | ✗ |

**database.md §12.1 tables that do not exist in any migration** (no schema to secure, so nothing to add RLS to yet):
`documents`, `extracted_pages`, `document_chunks`, `evidence_items`, `case_facts`,
`case_events`, `ai_runs`, `analyses`, `claims`, `claim_sources`,
`verification_results`, `legal_research_results`, `hearing_updates`, `tasks`.
Dev 2's documents, analysis and strategy data are Pydantic objects held in memory.

**Shared legal tables** (`legal_sources`, `legal_chunks`) are created by raw SQL in
`backend/src/legal_kb/migrations.py`, **outside Alembic**. They have no grants to
`app_user`. The `app_admin_ingest` role exists (created by 0001) but has no grants on legal tables. Ingestion connects as `researchsphere`
to a separate DB on port 5433. `legal_source_versions` is mentioned in the
docstring but not created.

Other RLS observations:
- `notification_owner` WITH CHECK covers only `user_id`, so a user can insert a self-notification that references any `case_id`. Low impact.
- The client has row-level SELECT on `cases` (0008), which includes `internal_notes`. The client endpoint selects safe columns only, but database.md §12.2 says the client portal should read `client_visible_case_fields`, not `cases`. A column-level grant or a view is needed.

---

## 3. Route inventory

### 3a. Dev 1 app (`backend/app/main.py`, `[tool.fastapi] entrypoint`)

All routes have `summary`, a typed `response_model` (except where noted) and
declared problem+json errors via `problem_responses(...)`. Errors render as
`application/problem+json` through `app/errors.py`.

| Method | Path | Auth dep | Case access | CSRF | Notes |
|---|---|---|---|---|---|
| GET | `/health` | none | n/a | n/a | liveness |
| GET | `/health/ready` | none | n/a | n/a | DB check; Redis/MinIO not reported |
| POST | `/api/v1/auth/register` | none | n/a | ✓ (router) | |
| POST | `/api/v1/auth/login` | none | n/a | ✓ | per-IP throttle + account lockout; MFA/recovery code; rotates prior session |
| POST | `/api/v1/auth/password/forgot` | none | n/a | ✓ | identical message; **no rate limit**; token stored only in dev app state |
| POST | `/api/v1/auth/password/reset` | none | n/a | ✓ | single-use 30 min; revokes all sessions (DB fn); **no rate limit** |
| POST | `/api/v1/auth/mfa/setup` | CurrentUser | n/a | ✓ | |
| POST | `/api/v1/auth/mfa/verify` | CurrentUser | n/a | ✓ | no attempt limit seen |
| POST | `/api/v1/auth/invitations/accept` | none | n/a | ✓ | per-IP throttle |
| POST | `/api/v1/auth/logout` | CurrentUser | n/a | ✓ | |
| POST | `/api/v1/auth/logout-all` | CurrentUser | n/a | ✓ | |
| GET | `/api/v1/me` | CurrentUser | n/a | n/a | |
| GET | `/api/v1/clients` | Lawyer | org | n/a | no pagination |
| POST | `/api/v1/clients` | Lawyer | org | ✓ | |
| GET/PATCH | `/api/v1/clients/{client_id}` | Lawyer | org (RLS) | PATCH ✓ | |
| GET | `/api/v1/cases` | Lawyer | RLS | n/a | **no cursor pagination** |
| POST | `/api/v1/cases` | Lawyer | org | ✓ | atomic case + lead + stages + audit |
| GET | `/api/v1/cases/{case_id}` | Lawyer | ✓ CaseAccess | n/a | |
| PATCH | `/api/v1/cases/{case_id}` | Lawyer | ✓ | ✓ | **no ETag/If-Match** |
| GET/POST | `/api/v1/cases/{case_id}/members` | Lawyer | ✓ | POST ✓ | |
| DELETE | `/api/v1/cases/{case_id}/members/{member_id}` | Lawyer | ✓ | ✓ | |
| GET | `/api/v1/cases/{case_id}/audit` | Lawyer | ✓ | n/a | |
| POST | `/api/v1/cases/{case_id}/invitations` | Lawyer | ✓ | ✓ | |
| DELETE | `/api/v1/cases/{case_id}/invitations/{invitation_id}` | Lawyer | ✓ | ✓ | |
| POST | `/api/v1/cases/{case_id}/close` / `reopen` | Lawyer | ✓ + `can_close_case` | ✓ | |
| POST | `/api/v1/cases/{case_id}/client-updates` | Lawyer | ✓ | **✗** | no closed-case check; no `can_publish_updates` |
| POST | `/api/v1/client-updates/{update_id}/publish` | Lawyer | **RLS only** | **✗** | no case_id in SQL; no permission flag; no audit event; no closed-case check |
| POST | `/api/v1/client-updates/{update_id}/withdraw` | Lawyer | **RLS only** | **✗** | same as publish |
| POST | `/api/v1/cases/{case_id}/shared-documents` | Lawyer | ✓ | **✗** | `response_model=dict`; no test |
| POST | `/api/v1/cases/{case_id}/tasks` | Lawyer | ✓ | **✗** | `response_model=dict`; no test |
| PATCH | `/api/v1/cases/{case_id}/client-visibility` | Lawyer | ✓ | **✗** | no test |
| GET | `/api/v1/client/cases` | Client | RLS + SQL | n/a | |
| GET | `/api/v1/client/cases/{case_id}/updates` · `/hearing` · `/tasks` · `/documents` | Client | RLS + SQL | n/a | |
| PATCH | `/api/v1/client/tasks/{task_id}` | Client | RLS | **✗** | **likely always 404**: client has no UPDATE policy on `client_tasks`; untested |
| GET | `/api/v1/client/notifications` | Client | user_id | n/a | |
| GET | `/api/v1/client/documents/{document_id}/download-url` | Client | RLS | n/a | `NOT_CONFIGURED` stub; audit action is `client.document_download_requested`, not `document.download` |

Additional Dev 1 contract issues: `client_portal/router.py` imports
`ClientTaskPatch` from `app.cases.schemas` (lawyer schema module), which breaks the
client-only-schema rule. Permission flags `can_upload`, `can_run_ai` and
`can_publish_updates` **do not exist anywhere**; only `can_close_case` is enforced.
No session rotation on privilege change. There is no password-change endpoint.

### 3b. Dev 2 app (`backend/src/main.py`, run by `make backend-dev`)

**No route has authentication, case access, CSRF, or declared problem+json errors.**
HTTPExceptions return FastAPI's default `{"detail": …}` JSON.

| Method | Path | response_model | Flag |
|---|---|---|---|
| GET | `/health` | none | duplicates Dev 1 path |
| GET | `/api/v1/legal-kb/search` | `SearchResponse` | anonymous |
| POST | `/api/v1/documents/process` | **none** | anonymous upload; random case_id; returns page text previews; `str(e)` leaked in 400 |
| POST | `/api/v1/cases/{case_id}/analysis-runs` | `CaseAnalysisRecord` | **case data, no access check** |
| GET | `/api/v1/cases/{case_id}/analysis` | `CaseAnalysisRecord` | seeds synthetic cheque data on miss |
| GET | `/api/v1/cases/{case_id}/timeline` | `List[TimelineEventItem]` | collides with TRD's Dev 1 `/cases/{id}/timeline` |
| GET | `/api/v1/cases/{case_id}/contradictions` | **`Dict[str, Any]`** | |
| GET | `/api/v1/cases/{case_id}/evidence` | `List[EvidenceItem]` | |
| POST | `/api/v1/cases/{case_id}/analysis/{analysis_id}/review` | **`Dict`** | reviewer from body; mutates in place (not versioned) |
| POST | `/api/v1/cases/{case_id}/strategies/generate` | `List[StrategyRecord]` | org_id from body |
| GET | `/api/v1/cases/{case_id}/strategies` | `List[StrategyRecord]` | auto-generates on miss |
| GET | `/api/v1/cases/{case_id}/strategies/comparison` | `StrategyComparisonRecord` | |
| GET | `/api/v1/cases/{case_id}/strategies/{strategy_id}` · `/tree` | typed | |
| POST | `/api/v1/cases/{case_id}/strategies/{strategy_id}/approve` · `/select` · `/reject` | `StrategyRecord` | lawyer_id from body |
| POST | `/api/v1/cases/{case_id}/strategies/report` | `LegalStrategyReportRecord` | |

**No exact path duplicates** between the two apps under `/api/v1/cases/*` except
the planned `/timeline` ownership clash. `/health` exists in both.

---

## 4. Findings for brief §2 items 1–10

| # | Finding | Proposed action |
|---|---|---|
| 1 | Confirmed: status.md rows 54–56 ("Client invitations…", "Client-visible updates…", "Case closure…") say Not started; B12–B14 code exists (`auth/router.py` accept, `visibility_router.py`, `client_portal/router.py`, close/reopen). B13 is **partial**: no CSRF on writes, client task PATCH likely broken, shared-docs/tasks/visibility untested. | Merge rows in Batch 7; B13 → *Partial* until fixed and tested |
| 2 | Confirmed stale: §3 says PostgreSQL at `0003`, LLM gateway "Not started" at `app/agents/gateway.py`. Real: chain at `0009`; gateway at `src/ai/gateway.py` (mock + gemini); OCR `src/documents/ocr.py`; embeddings `src/legal_kb/embeddings.py`; validator `src/documents/validator.py` (ClamAV not wired); ingestion `src/legal_kb/ingest_all.py`. §5 still says client activation and `/client/*` are missing, but they exist. | Rewrite §3/§5 in Batch 7 |
| 3 | **Two app factories, neither complete.** `app.main:app` (pyproject entrypoint, docs command `uv run fastapi dev`) mounts Dev 1 only. `src.main:app` (Makefile `backend-dev`) mounts Dev 2 only, imports via `backend.src.*` (needs repo root on `PYTHONPATH`), hard-codes `researchsphere:devpassword@localhost:5433`, and connects as a non-`app_user` role. | Batch 1: `app.main` becomes the single factory and mounts Dev 2 routers **behind** Dev 1 auth + CaseAccess (needs your OK: see Q2) |
| 4 | Static: single linear head `0009`. 0009 was broken (S3); now amended by Dev 1 with owner authorization. | Verify live in Batch 1 |
| 5 | Confirmed divergence: `legal_chunks` (act_id/act_name/section/is_current, `VECTOR(1024)` e5-large) vs database.md §7 (`legal_source_versions` + `provision_label`). Also created outside Alembic, no `app_user` grants, no ingest role. | Document in schema packet and requests; no change |
| 6 | **Security defect confirmed** (S1). | Request to Dev 2; propose config default fix |
| 7 | Confirmed: `src/documents/pipeline.py:103` uses `cases/{case_id}/documents/{doc_id}/{filename}`. The filename in the key is also a privacy concern. Architecture says `org/{org_id}/case/{case_id}/doc/{doc_id}/{version}`. No real storage client exists (path string only). | Report only |
| 8 | Confirmed overlap: orchestration §2 gives strategy versioning/approval to Dev 1; §3 lists `PATCH/approve/reject /strategies/*` under Dev 2. Jobs/SSE: §2 says Dev 2, §3 lists it under Dev 1. **Neither exists**: no `jobs` table, no `/jobs/*` route, no SSE, and no Redis/worker code. | Not building; needs your assignment (Q3) |
| 9 | `documents` table **does not exist** in any migration. FK cannot be added. | Stays Blocked on Dev 2 |
| 10 | Could not run. 42 Dev 1 + 69 Dev 2 test functions found. The "111 passed + 23 skipped" run most likely skipped the Dev 1 DB/isolation tests (no `TEST_DATABASE_URL`). | Re-run in Batch 1 once env exists |

---

## 5. Real state of status.md rows

| Row | status.md says | Verified state | Gaps |
|---|---|---|---|
| P1 Authentication and sessions | In progress | **Partial** | No rate limit on forgot/reset/MFA verify; no rotation on privilege change; no password-change endpoint; old injected-identity client test still the only "guard" test besides B12; tests unrun here |
| P1 Roles, organizations, case membership | In progress | **Partial** | `can_upload`/`can_run_ai`/`can_publish_updates` flags absent; no generated authorization matrix |
| P1 Database migrations and RLS | In progress | **Partial / broken at head** | S3; §12.1 tables mostly absent; `app_admin_ingest` role has no legal-table grants; legal KB outside Alembic; client reads `cases` directly |
| P1 Case creation | In progress | **Partial** | No ETag/If-Match; no cursor pagination; per-type stage templates absent |
| P2 Lawyer dashboard shell | In progress | **Frontend-only** (mock data) | Batch 6 |
| P2 Lawyer matter detail | In progress | **Frontend-only**; `lawyer.ts` calls Dev 2's unauthenticated analysis API and legal-KB search | Batch 6 |
| P2 Client dashboard shell | In progress | **Frontend-only** | Batch 6 |
| P2 B12 / B13 / B14 | Done | B12 *Done but untested here*; **B13 Partial** (CSRF, task PATCH, missing tests, no publish audit); B14 *Partial* (close/reopen OK; visibility writes ignore closed status) | |
| P2 duplicate rows 54–56 | Not started | Duplicates of B12–B14 | Merge |
| P3 Document Authorization (Dev 1) | not tracked | **Missing**: no document endpoints or tables exist to authorize | Blocked on Dev 2 schema |
| P4 Scoped retrieval (case filter) | In progress | **Missing**: no `document_chunks` table; retrieval covers the legal KB only | Blocked on Dev 2 schema |
| P5 Claims & Verification schema (Dev 1) | not tracked | **Missing**: no `claims` tables or deferred trigger | Could be built (Batch 2) |
| P6 Strategy versioning/approval | Done (Dev 2) | In-memory only; tables broken; no auth | See S2/S3 |

---

## 6. Proposed batch order (revised)

0. **Unblock environment** (needs you): Python ≥ 3.12, `uv`, Docker Desktop (or WSL2 + Docker) so Compose PostgreSQL can run. Without it no batch can reach an honest Done.
1. **Batch 1: integration and boot hygiene**, plus: single factory in `app.main`; Dev 2 routers mounted **only behind** `require_lawyer` + `CaseAccess` + CSRF router-level dependencies (minimal integration touch, logged); `make backend-dev`/`backend-test` point at `app.main`; `/health/ready` reports Redis/MinIO `not_configured`.
2. **Batch 2: RLS and migrations**, after Q1 is resolved: fix the 0009 chain; new Dev 1 revision adds `app_user` grants and lawyer policies for strategy tables, drops the client strategy read, grants `app_admin_ingest` write access and `app_user` SELECT on legal KB tables (if the tables move under Alembic), a client column-safe view for cases, and the claims tables + deferred trigger. RLS bypass suite over every existing case table.
3. **Batch 2b (new): B13 fixes**: CSRF on visibility and client-task routes, closed-case denial, `can_publish_updates`, publish/withdraw audit, typed response models, client task UPDATE path, client-only schemas, tests for shared-docs/tasks/visibility/download.
4. **Batch 3: auth**: rate limits on forgot/reset/MFA, rotation on privilege change, permission flags, generated authorization matrix.
5. **Batch 4: case creation**: ETag/If-Match, cursor pagination.
6. **Batch 5**: largely **Blocked** until Dev 2 lands `documents`/`document_chunks` tables. I would ship only the shared `require_case_permission(...)` dependency and a skipped-with-reason retrieval isolation test scaffold.
7. Batch 6 (ask first), then Batch 7.

---

## 7. Open questions for you

1. ~~**0009 is broken and I may not edit it.**~~ Resolved: owner chose (b); 0009 amended by Dev 1. Options: (a) Dev 2 amends 0009 locally (still unreviewed and unshared) to use `app.is_lawyer_member` and drop the client policy, then I add grants in `0010`; (b) you authorize me to make that edit as an integration fix; (c) I leave the chain broken and report.
2. Answered **yes** (2026-11-19); done in Batch 1. Original question: May I mount Dev 2's routers into `app.main` behind Dev 1 auth + CaseAccess (router-level dependencies only, no change to Dev 2 logic), and repoint `make backend-dev` to `app.main`? Until then, S2 stays live on the dev server.
3. Answered **none** (2026-11-19): Jobs/SSE and strategy approval/versioning are unassigned and out of scope this session. Original question: Who owns Jobs/SSE and strategy approval/versioning (orchestration §2 vs §3 conflict)?
4. Can you install or start Python 3.12 + `uv` + Docker on this machine, or point me to the machine and environment where Compose PostgreSQL runs?

See also `DOCS/dev1-to-dev2-requests.md`.

---

## 8. Batch 1 live verification (2026-11-19)

The environment is now available: Docker Desktop (WSL2), `uv` 0.13.9, project Python 3.12.16.
Compose `db` (pgvector pg16) and `redis` are running. **`minio` cannot start:**
`minio/minio:RELEASE.2025-04-22T22-12-26Z` fails with "pull access denied" on
Docker Hub, so `compose.yaml` needs a reachable MinIO image (Dev 2 storage scope).

| Check | Result |
|---|---|
| `alembic heads` | `0009_phase6_strategy_engine (head)`, single head |
| Fresh `upgrade head` (bootstrap 0001 as `postgres`, then `app_owner`) | **Pass**, so the amended 0009 applies |
| `downgrade base` (as `app_owner`) | **Pass** |
| Re-`upgrade head` after `downgrade base` | Failed before the fix: the bootstrap guard in `alembic/env.py` refused whenever `alembic_version` existed, even when empty. **Fixed** (guard now refuses only when a revision is recorded). Bootstrap 0001 → `app_owner` to head: **pass**. A second bootstrap after 0001 is still refused. All 24 public tables are owned by `app_owner` |
| Roles | `app_user`: NOSUPERUSER, NOBYPASSRLS. `app_owner`: BYPASSRLS (migration role). `app_admin_ingest`: exists, no grants |
| Full `pytest` as `app_user` | **118 passed, 1 failed, 6 skipped** (6 min 37 s) |
| `/health` · `/health/ready` · `/docs` · `/redoc` · `/openapi.json` | all 200; readiness `{"status":"ready","database":"ok","redis":"not_configured","object_storage":"not_configured"}`; OpenAPI 55 paths |
| Anonymous Dev 2 case route | 401 `application/problem+json` |

**Failure (1):** `tests/ai/test_gateway.py::test_gateway_environment_provider_selection`
(Dev 2) asserts that `LLM_PROVIDER=gemini` is accepted. With the providers.md-compliant
`LLM_APPROVED_PROVIDERS=mock` the gateway correctly refuses. The test encodes defect S1,
so I left it unchanged and filed it under R1.

**Skips (6), all Dev 2 legal KB:** `test_ingestion.py:90` and `test_vector_pipeline.py:60`
need the hard-coded `/home/arafath/...` dataset path (pending Akash). The four
`test_pgvector_live.py` tests need a separate DB on `localhost:5433` with hard-coded
`researchsphere` credentials.

**Live RLS catalog** (`pg_class`, `pg_policies`, `role_table_grants`) matches §2 exactly:
14 tables with `case_id` (plus `cases`), all with RLS **and** FORCE RLS. The strategy
tables have only the lawyer policy (no client policy) and **no `app_user` grants** (Batch 2).

**Route-guard tests:** FastAPI 0.164 keeps included routers nested
(`_IncludedRouter`), so iterating `app.routes` sees no API routes. The guard tests
now walk `effective_route_contexts()` and assert more than 40 routes. All 11 pass:
every lawyer `{case_id}` route needs CaseAccess, every write needs the Origin
check, every non-public route needs a session; anonymous → 401, missing Origin →
403, another lawyer's case → the same 404 as an unknown case.

Minor: request logs record the route path without the `/api/v1` prefix (same nesting cause).

---

## 9. Batch 2: RLS and migrations (2026-11-19)

New revision `0010_dev1_rls_and_claims`: 0009 → 0010 → 0009 → 0010 passes, and so does
base → bootstrap 0001 → `app_owner` to head.

| Item | Result |
|---|---|
| Strategy tables | `app_user` SELECT/INSERT; column-level UPDATE on `status`, `is_current_strategy`, `approved_by`, `approved_at`, `updated_at`; `review_status` on comparisons. UPDATE of content and DELETE are denied (tested). `(case_id, organization_id)` FKs and same-case FKs for scenarios/comparisons |
| `case_members_create` (0001 bug) | Subquery columns were unqualified, so the client-profile check compared `cp` to itself. **Proved exploitable** on the old policy (a case lawyer granted client membership to another organization's lawyer); fixed and regression-tested |
| Claims & verification (§9) | Tables, FORCE RLS, insert-only grants; deferred constraint trigger rejects sourced claim types without a `claim_sources` row at commit; assumption/prediction may be unsourced (tested) |
| RLS bypass suite | `tests/test_rls_bypass.py`: all 16 case tables × {no context, other org, owner, client, revoked} + foreign-case INSERT. Client sees rows only in client-visible tables; a user's own membership/audit rows are allowed and checked separately |
| `client_profiles` / `organization_members` (§12.3a) | Verified: clients are not org members, so they read only their own profile; no client payload includes `internal_notes` (tested) |
| Not done (no schema) | §12.1 Dev 2 tables and `ai_runs`; legal KB grants (tables outside Alembic). See schema packet notes |
| Low, open | `notification_owner` WITH CHECK covers `user_id` only. No code writes notifications yet |

Full suite as `app_user`: **131 passed, 1 failed (Dev 2 gateway test, R15), 6 skipped (Dev 2 legal KB)**.

---

## 10. Batch 2b: client-visibility fixes (2026-11-19)

Migration `0011_dev1_client_task_audit`: 0010 → 0011 → 0010 → 0011 passes, and so does base → head.

| Gap (from §3a) | Fix | Test |
|---|---|---|
| No CSRF on visibility/client writes | Router-level Origin check (Batch 1) | route guards |
| No closed-case denial on client-visible writes | Shared `authorize_client_visible_write` / `ClientVisibleWriteDep`: membership 404 → permission 403 → open case 409 | `test_client_visible_writes_are_denied_on_closed_case` |
| `can_publish_updates` absent | Required for create/publish/withdraw updates, share documents, tasks, visibility fields (lead lawyer implied) | `test_client_visible_writes_need_publish_permission` |
| Publish/withdraw RLS-only, unaudited | Resolve `case_id`, authorize, `WHERE id AND case_id`, audit `client_update.published/withdrawn`; another lawyer gets the same 404 as an unknown ID | `test_publish_and_withdraw_are_scoped_and_audited` |
| `response_model=dict` | `SharedDocumentResponse`, `ClientTaskCreatedResponse` (tasks now 201) | typed-response route guard |
| Client task PATCH always 404 | `app.client_set_task_status` (0011); audited `client_task.status_changed` with `case_id` | `test_client_can_update_own_task_and_nothing_else` |
| Download audit name, no `case_id` | `document.download` with `case_id`; client audit allowed by 0011 | `test_shared_document_download_is_authorized_and_audited` |
| Client portal imports lawyer schema | `ClientTaskPatch` moved to `client_portal/schemas.py` | `test_client_portal_imports_no_lawyer_schemas` |
| **New: `POST /cases/{id}/members` always 500** | `INSERT … ON CONFLICT DO UPDATE` needs UPDATE on `role`/`granted_by`, which app_user lacks (never tested). Now insert, or re-activate in place (permissions/status only); role change or RLS rejection → 409 | exercised by the permission test |

Full suite as `app_user`: **138 passed, 1 failed (Dev 2 R15), 6 skipped (Dev 2 legal KB)**.
Still open: shared-document existence is not checked until Dev 2's `documents` table exists (R12).
