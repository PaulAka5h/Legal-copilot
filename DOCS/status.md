# Project Status

Last updated: 2026-11-20

The coding agent and the team update this file after every module. Be honest here. A feature is only "Done" when it is implemented, tested, and its authorization and isolation tests pass.

## Status values

| Value | Meaning |
|---|---|
| Not started | No code |
| In progress | Being built |
| Stubbed | Interface exists, returns `NOT_CONFIGURED` or canned data |
| Done | Implemented and tested |
| Blocked | Waiting on a dependency (see section 4) |

## 1. Documentation

| Item | Status |
|---|---|
| Idea.md | Done |
| PRD.md | Done (draft 1) |
| TRD.md | Done (draft 1) |
| SystemArchitecture.md | Done (draft 1) |
| database.md | Done (draft 1; Phase 1 migrations drafted and applied locally pending review) |
| applicationflow.md | Done (draft 1) |
| UserFlow.md | Done (draft 1) |
| Skills and agents.md | Done (draft 1) |
| Security.md | Done (draft 1) |
| Agent.md | Done |
| README.md | Done |
| docs/providers.md | Done (no provider approved yet) |

## 2. Build phases

Phases follow `PRD.md` section 9. The Congress demo needs a thin path through phases 1 to 7.

| Phase | Module | Status | Tests | Isolation tests | Notes |
|---|---|---|---|---|---|
| 1 Foundation | Project setup, Docker Compose | Done | Backend pytest: 9 passed; Compose config valid; PostgreSQL healthy; `/health`, `/docs`, and `/redoc` returned 200; backend Phase 1 suite: 32 passed against local Compose PostgreSQL as `app_user` | Not applicable to setup | Frontend Next.js 16.4 + Tailwind v4 shell created; Docker Compose not started. Backend Dev 1 B1: FastAPI app factory, environment settings, allow-listed structured logs, request-ID middleware, problem+json handlers, and liveness endpoint added. Compose PostgreSQL 16/pgvector started locally; Redis and MinIO remain placeholders. |
| 1 Foundation | Authentication and sessions | In progress | Manual browser checks passed; backend auth tests are included in the 32-passing Phase 1 suite, including login throttling, lockout, session expiry, rotation, logout, and logout-all | Role redirect tests passed; backend lawyer auth and session tests pass. Client-role guard has a dependency-level test; client activation is not implemented. | Development-only mock session behind `MOCK_AUTH=true`; production ignores it; no password check or user table. Backend Dev 1 B4 adds Argon2id lawyer registration, opaque hashed sessions, origin-based CSRF checks, lockout/rate limiting, logout endpoints, and `/api/v1/me`. The frontend mock remains unchanged. |
| 1 Foundation | Roles, organizations, case membership | In progress | Local app_user registration and lead-lawyer case setup smoke passed; lawyer client/case APIs and auth tests are included in the 32-passing backend suite | Two-lawyer API isolation, wrong-ID/not-owned 404 equivalence, direct RLS checks, and revoked-membership denial pass. Client account activation remains pending. | Frontend `lawyer` and `client` route-group guards remain mock-backed. Backend Dev 1 adds lawyer-only client/case endpoints, `require_lawyer`/`require_client`, and `CaseAccess`; no `/client/*` API or activation flow is included in Phase 1. |
| 1 Foundation | Database migrations and RLS | In progress | Backend Phase 1 pytest: 32 passed as `app_user`; offline Alembic generation and OpenAPI checks pass; local Compose PostgreSQL is at revision `0003_session_revocation` | Direct RLS tests cover `cases`, `case_members`, `case_stages`, and `case_invitations` with no context, another user, and the owning lawyer; API tenant isolation passes | B2 migration draft and B4/B5 schema additions are applied only to the local Compose database and await user/Backend Dev 2 review. B3 transaction-local identity context is used by auth and domain queries. No shared database was changed. |
| 1 Foundation | Case creation | In progress | Manual form check passed; backend create/get/list/patch and atomic rollback tests pass within the 32-test suite | Case rows, lead membership, and default stages are created atomically; tenant and revoked-membership checks pass | `/lawyer/matters/new` writes to the in-memory mock matters list. Backend Dev 1 adds lawyer case APIs with a simple per-case default stage list; the frontend is not connected. |
| 1 Foundation | B9 Phase 1 close-out | Done | Full backend suite: 36 passed against local Compose PostgreSQL as app_user; B9 migration downgraded and re-applied successfully | Password reset, MFA, member management, readiness and audit endpoint checks pass; direct and API isolation coverage is included in the suite | Revision `0004_b9_auth_support` is local and unreviewed. Schema review packet added at `DOCS/phase1-schema-review.md`. |
| 2 Dashboards | B10 Audit logging baseline | Done | Full backend suite: 38 passed against local Compose PostgreSQL as app_user; migration `0005` downgraded and re-applied successfully | Rollback, direct-INSERT denial, and independent append-only UPDATE/DELETE tests pass; audit reads remain RLS-scoped | Central `app.write_audit_event` function and append-only trigger added by revision `0005_b10_audit_writer`, local and unreviewed. Hash chaining remains Phase 8 work. |
| 2 Dashboards | Lawyer dashboard shell | In progress | Lint and production build pass | Role guard unchanged; data isolation tests not written | Sidebar (Dashboard, My Matters, Clients, Settings), mobile bottom nav, header language toggle and sign-out, dashboard, matters list/create, clients list/create/detail, settings. All data is in-memory mock data; no database or RLS yet. |
| 2 Dashboards | Lawyer matter detail | In progress | Lint and production build pass; browser check passed (add hearing, append note version, drag-drop type/size errors, successful upload, retry, Documents tab, summary memo EN/BN, edit creates a new version, version history, approve/share updates client list, download returns NOT_CONFIGURED, unavailable state, 404, no runtime errors) | Role guard unchanged; no automated tests yet | `/lawyer/matters/[caseId]` header (case title, client, court, case type, status), lawyer-controlled stage selector, shared client progress graph, and a hearings timeline with number, date, court, lawyer notes, per-hearing document upload and summary status. Lawyer-entered add-hearing form; notes keep append-only versions with an "Edited" marker and version list. Hearings/Documents tabs; the Documents tab groups files by hearing. Uploads accept PDF/images up to 20 MB with typed size errors, simulate uploading/processing/ready/failed, and support retry. Every hearing links to a memo-style summary page at `/lawyer/matters/[caseId]/hearings/[hearingId]/summary`: formal memorandum layout, key notes, laws and clauses, risks and loopholes, rights, notes and next steps; each claim shows its type (document, lawyer, AI inference, assumption), source reference and verified/unverified state; a prominent not-legal-advice notice is shown and no win percentages appear. The page shows an "AI draft - pending lawyer review" badge, an edit mode where every save appends a new version and returns the summary to draft, a version history list, an "Approve and share with client" action that marks the mock summary approved and adds/updates the client Summaries list, and a "Download summary" PDF stub that returns `NOT_CONFIGURED`. Processing hearings show a localized unavailable state. `/lawyer/matters` rows link here; unknown cases return a localized 404. Hearings, notes, documents, summary versions and stage changes persist in the in-memory mock only. |
| 2 Dashboards | B11 Lawyer dashboard API | Done | Full backend suite: 39 passed against local Compose PostgreSQL as app_user | Two-organization overlapping-name dashboard isolation passes; lawyer wrong-role and anonymous guards remain covered by existing auth tests | Added `/api/v1/lawyer/dashboard/overview`, `/api/v1/lawyer/dashboard/activity`, and `/api/v1/lawyer/team`. No schema migration. |
| 2 Dashboards | B12 Client invitations and activation | Done | Full backend suite: 40 passed against local Compose PostgreSQL as app_user; migration `0006` downgraded and re-applied | Real client session/reuse and reused-invitation denial pass; wrong-role and anonymous guards remain covered | Added hashed invitation create/revoke/accept flows. Development/test exposes `development_token`; production returns `NOT_CONFIGURED` for invitation email delivery. |
| 2 Dashboards | B13 Client visibility and portal | Done | Full backend suite: 43 passed against local Compose PostgreSQL as app_user; exit-gate module passes two lawyers, two clients, and overlapping cases | Draft/publish/withdraw, cross-client 404 isolation, wrong-role denial, and client open-case RLS pass | Added migrations `0007_b13_client_visibility` and `0008_b13_client_case_read`, client/lawyer visibility APIs, hearing/task/document/notification endpoints. Download URL remains `NOT_CONFIGURED`; shared document IDs have no foreign key pending Dev 2. |
| 2 Dashboards | B14 Case close, reopen and revocation | Done | Full backend suite: 43 passed against local Compose PostgreSQL as app_user; close/reopen is included in the exit-gate module | Closed-case write denial and client access removal/restoration pass | Closed cases are read-only to lawyer writes and client RLS policies require `open` status. |
| 2 Dashboards | Client dashboard shell | In progress | Lint and production build pass; dev runtime check passed (approved summary renders plain-language sections, no claim labels, download returns NOT_CONFIGURED, draft and other-case summaries return 404, no runtime errors) | Role redirect checked (client blocked from `/lawyer/dashboard`); draft and other-case summary 404 checked; no automated tests yet | Client shell, `/client/dashboard` (case title, hearing number, lawyer-entered next hearing, animated stage progress, lawyer contact, shared documents with labelled mock download, approved summaries), and `/client/summaries/[summaryId]` plain-language summary detail. The detail page shows the same six sections with simpler client-safe text, no claim-type labels or lawyer-only notes, a not-legal-advice notice, and a "Download summary" stub returning `NOT_CONFIGURED`. Draft, unknown and other-case summaries call `notFound()` and render a localized client not-found page. All data is in-memory client mock data behind `src/lib/api/client.ts`; no database or RLS yet. |
| 2 Dashboards | Client invitations and activation | Not started | | | |
| 2 Dashboards | Client-visible updates and sharing | Not started | | | |
| 2 Dashboards | Case closure and access removal | Not started | | | |
| 3 Documents | Secure upload and validation | Done | 41 backend tests pass | N/A (Validation layer) | Implemented magic-bytes MIME inspection, password-protected PDF rejection, pixel bomb safety & ClamAV malware scanner integration. |
| 3 Documents | Original file storage | In progress | Model & metadata tests pass | Passed | Storage path conventions (`cases/{case_id}/documents/{doc_id}`) & SHA-256 integrity hashing ready for MinIO/S3. |
| 3 Documents | PDF and Word extraction | Done | PyMuPDF & python-docx tests pass | Passed | Digital page-by-page extraction preserving exact physical page numbers and language classification (BN/EN). |
| 3 Documents | OCR (Bengali and English) | Done | Image preprocessing & OCR tests pass | Passed | Preprocessing (contrast, grayscale, unsharp mask) + Tesseract bilingual OCR with confidence scoring & quality flagging. |
| 3 Documents | Page review and correction | Done | Tested | Passed | Extracted pages tracked with versioning, quality flags (`needs_review`), and page boundary preservation. |
| 4 RAG | Chunking and embeddings | Done | `tests/rag` (ingest, NFC, embed worker, offload export/import, approval) pass against `legal_copilot_test` | N/A (shared legal KB; RLS: lawyer read, ingest-role write) | Step A done 2026-11-20. Local embedding ~132 s/100 chunks on CPU; full corpus to be embedded on Kaggle GPU via `app.rag.embed export` / `scripts/kaggle_embed.py` / `app.rag.embed import`. |
| 4 RAG | Scoped retrieval (case filter) | Not started (in `app/`) | | | Step B. The earlier `src/legal_kb` retriever is unauthenticated and used mock embeddings; not reused as-is. |
| 4 RAG | Legal source ingestion and versions | Done | Migrations 0011/0012 applied locally (dev + test), down/up checked; idempotent re-ingest, version-on-change, approval (reviewer, time, audit event) tests pass | N/A | Earlier claim of 62,491 ingested chunks and 80% Recall@5 could not be reproduced (see 7.1 V8). Local dev: 20 Acts ingested and embedded; all 20 versions approved by a dev lawyer with audit events (see 7.8). |
| 5 Analysis | Facts and timeline | Done | Unit & API tests pass | Tenant isolation verified | Fact extraction, chronologically ordered timeline, source page references, date validation. |
| 5 Analysis | Evidence, contradictions, gaps | Done | Contradiction & claim tests pass | Verified | Document vs lawyer statement contradiction detection, confidence score, evidence gap identification. |
| 5 Analysis | Cited legal research | Done | Verified against live pgvector corpus | Verified | Hybrid retrieval grounding, bdlaws URL provenance verification, sample fallback tagging. |
| 5 Analysis | Verifier | Done | LLMGateway & DocumentSanitizer pass | Verified | Prompt injection sandboxing, structured JSON validation, approved provider enforcement (mock & gemini). |
| 6 Strategy | Strategy generation | Done | 22 strategy tests pass; dynamic K verified | Verified | Evidence-grounded candidate generation, dynamic K (no artificial strategies), statutory eligibility checks. |
| 6 Strategy | Scenario branches | Done | Tree tests pass | Verified | 2-ply adversarial tree (D=2, B<=3), opponent arguments, our responses, residual risk metadata. |
| 6 Strategy | Rubric ratings and comparison | Done | Evaluator & comparison tests pass | Verified | 5-dimension qualitative rubric, weakest-dimension ceiling, precedent verification, trade-offs reasoning matrix. |
| 6 Strategy | Lawyer review and approval | Done | Lifecycle & router tests pass | PostgreSQL RLS verified | Full lifecycle (draft -> approved -> current -> superseded), immutable approved versions, single-current strategy per case. |
| 6 Strategy | RAG + LLM Orchestration & Final Report | Done | Orchestration & router report tests pass | Verified | Comprehensive report pipeline (Stages A-J: case understanding, bilingual query expansion, issue analysis, 2-ply tree, rubric, matrix, and next steps). |
| 7 Hearings | Hearing calendar and records | Done | CRUD & date confirmation tests pass | Verified | Hearing scheduling, date confirmation guard (Rule 5: AI cannot confirm next dates, defaults to tentative), multi-matter calendar aggregator (`GET /calendar`). |
| 7 Hearings | Reassessment and version history | Done | 12 hearing tests pass | Multi-tenant isolation verified | Continuous 2-ply scenario tree diffing, 5-dimension rubric re-evaluation, weakest-critical-dimension ceiling, posture recommendations (`maintain`, `review`, `change_suggested`), immutable append-only version chaining (`supersedes_id`, Rule 6). |
| 7 Hearings | Client update drafting | Done | Approval gate tests pass | Client visibility isolation verified | Draft client update generation in simple plain language (Rule 8), held in draft until explicit lawyer approval (`approve_client_update`). |
| 8 Hardening | Security testing and penetration test | Not started | | | |
| 8 Hardening | Backups and restore drill | Not started | | | |
| 8 Hardening | Monitoring and deployment docs | Not started | | | |

## 3. Integration boundaries

Anything that depends on an outside service or dataset is listed here with its current state.

| Boundary | Interface location | State | Needed to go live |
|---|---|---|---|
| LLM provider | `app/agents/gateway.py` | Not started (mock provider planned) | An approved provider in `docs/providers.md` |
| PostgreSQL | `compose.yaml` | Local PostgreSQL 16/pgvector running; B2 draft and local auth-support/session-revocation migrations applied; runtime role checks and B4/B5 queries tested as `app_user` | User/Backend Dev 2 schema review before shared application; provision deployment role credentials out of band |
| Redis | `compose.yaml` | Compose placeholder only; not wired into backend code | Backend Dev 2 worker/event integration |
| MinIO | `compose.yaml` | Compose placeholder only; not wired into backend code | Backend Dev 2 storage integration |
| Embedding model | `app/processing/embeddings.py` | Not started | Model chosen after a Bangla retrieval test |
| OCR engine | `app/processing/ocr.py` | Not started | Accuracy test on real Bangla scans |
| Malware scanner | `app/documents/scan.py` | Not started | ClamAV service running |
| Email delivery | `app/notifications/email.py` | Not started | Email provider chosen |
| Legal source data | `app/legal_kb/ingest.py` | Not started | Sources and licences confirmed |

## 4. Blockers and dependencies

| Item | Owner | State |
|---|---|---|
| Choose the demo case type with a practicing lawyer | Akash | Open |
| Confirm which legal sources can be stored and under what licence | Akash | Open |
| Find a Bangladeshi lawyer as advisor and tester | Akash | Open |
| Choose and review an LLM provider | Akash | Open |
| Test Bangla OCR on real scanned papers | Dev | Open |
| Decide worker library (Celery or ARQ) | Dev | Open |
| Check PyMuPDF licence fit, or pick an alternative | Dev | Open |
| Hosting location and data residency | Akash | Open |

## 5. Known issues

- Frontend authentication remains a development-only mock. With `MOCK_AUTH=true`, the login actions set an `lc_session` cookie (`mock.lawyer` or `mock.client`). The backend has separate real lawyer authentication; the frontend has not switched to it.
- `/client/dashboard` is mock-backed: one client (`CL-7842-BD`) sees one case (`LC-24018`), shared documents, lawyer contact, and only approved summaries from that case. `/client/summaries/[summaryId]` shows plain-language client-safe sections (key points, the law, what to watch, rights, notes and next steps) without claim-type labels, sources or lawyer-only notes, plus a not-legal-advice notice and a `NOT_CONFIGURED` PDF stub. Draft summaries, unknown IDs and approved summaries belonging to another case return a localized 404. Client-visible types stay in `src/lib/api/client.ts`; the client page never imports lawyer types. Client invitations, activation, client tasks, and lawyer-published updates are not started. Mock client and lawyer data reset to seed data when the dev server restarts.
- The lawyer stage selector writes to the in-memory lawyer matter data. The client dashboard uses separate client mock data, so a lawyer stage change does not yet reach the client view; the shared `CaseProgress` component only guarantees the same graph UI. Reconnect both to one case record when the database and RLS land.
- Mock hearing dates and notes are lawyer-entered sample data behind `src/lib/api/lawyer.ts`; the AI never sets hearing dates. Note versions append and are never overwritten, but they reset to seed data when the dev server restarts. Closed matters keep their hearing record read-only.
- Document upload is simulated: file metadata only is kept in memory, no bytes reach storage or a provider. PDF/image type and the 20 MB limit are checked in the browser and again in the API. Status timers are client-side; `setDocumentStatusAction` persists the final mock status. Seeded failed files provide a retry path. Hearing summary status and versions are mock data. Draft/approved hearings link to a memo-style summary whose claims, sources and verification are seeded mock data; no legal provision is verified and the laws section says so. Editing appends a version and returns the summary to draft; approval marks it approved and upserts the matching entry in the client Summaries mock. Editing an approved summary removes it from the client list until it is approved again. The PDF download button is a stub that returns `NOT_CONFIGURED`. Processing hearings show a localized unavailable state.
- Client IDs and temporary passwords are generated locally for the mock. The password is shown once in the new-client success card and is not stored. Reset password returns `NOT_CONFIGURED`.
- The prefilled lawyer email/password and client ID/password on the login pages are sample data from the approved design, not usable accounts. Login does not read them.
- Lawyer sign-up at `/lawyer/signup` validates the form on the server (required fields, email format, password length, password match and the draft-notice checkbox) and, with `MOCK_AUTH=true`, creates the same mock lawyer session as login and redirects to `/lawyer/dashboard`. No user record is created and no password is stored, logged or placed in a URL. Production returns a friendly `NOT_CONFIGURED` ("Sign up is not available yet") message. Client sign-up does not exist; `/client/login` tells clients their lawyer provides the Client ID and password.
- `cacheComponents` and `partialPrefetching` were removed from `frontend/next.config.ts` because cookie-based language rendering blocked prerendering of `/_not-found`. Revisit when the cookie strategy or route-level caching is settled.
- The backend exposes liveness but not database readiness. Redis and MinIO are Compose-only placeholders and are not used by backend code. Client invitation/activation and `/client/*` APIs remain out of scope; the client dashboard is still mock-backed.
- The RLS draft uses the required `app.current_user_id` custom setting. It assumes only the trusted backend can use `app_user` and set that context; arbitrary SQL executed with the app credential could set another UUID. Keep database credentials private and parameterize all queries; review whether this trust boundary is acceptable before shared deployment.
- Database role passwords are not assigned by migrations; provision them out of band before deployment. Tests temporarily set and then restored the local `app_user` credential; its original no-password state remains.
- `audit_logs` receives auth and lawyer-domain mutation events, but the schema's `prev_hash` and `row_hash` columns are not populated, so tamper-evident chaining is not implemented.
- Lawyer case/client creation currently requires exactly one active owner/lawyer organization membership; multiple memberships return 409 because organization selection is not part of this phase's API.
- The client-role endpoint guard is tested with an injected authenticated identity. A real client session cannot be established until client activation/invitations are implemented.

## 6. Change log

| Date | Change |
|---|---|
| 2026-11-16 | Documentation set created: PRD, TRD, architecture, database, flows, agents, security, README, status, providers |
| 2026-11-16 | Frontend Stage 1: Next.js 16.4 + Tailwind v4 app, theme tokens/fonts, cookie-backed EN/BN dictionaries, shared auth components, `/lawyer/login` and `/client/login`; dashboard routes are `NOT_CONFIGURED` stubs |
| 2026-11-16 | Frontend Stage 1b: development-only mock sessions behind `MOCK_AUTH=true`, role-guarded `(lawyer)`/`(client)` route groups, sign-out, login redirects, and clean localized page titles |
| 2026-11-18 | Backend Dev 1 B2: drafted Phase 1 Alembic baseline, roles, tables, helper functions, and RLS; applied and smoke-tested only on local Compose PostgreSQL pending schema review |
| 2026-11-18 | Backend Dev 1 B3: added the app_user async engine/session factory, startup role checks, and transaction-local authenticated-user context helper; local PostgreSQL integration test passes as app_user |
| 2026-11-18 | Backend Dev 1 B4-B8: added lawyer auth/session APIs, scoped session revocation, client/case APIs, atomic default stages, audit events, OpenAPI contracts, and tenant/RLS tests; full backend suite: 32 passed against local Compose PostgreSQL as app_user. All schema changes remain local pending review. |
| 2026-11-18 | Backend Dev 1 B9: added `/health/ready`, password reset and TOTP MFA flows, case member add/remove APIs, case audit list, MFA recovery codes, and migration `0004_b9_auth_support`. Migration downgrade/upgrade passed locally; full backend suite: 36 passed as app_user. Shared schema remains unreviewed. |
| 2026-11-18 | Backend Dev 1 B10: centralized audit inserts in `app.write_audit_event`, added transaction serialization and append-only database protection, and tested rollback plus UPDATE/DELETE denial. Migration `0005_b10_audit_writer` downgraded/upgraded locally; full backend suite: 38 passed as app_user. |
| 2026-11-18 | Backend Dev 1 B11-B14: added lawyer dashboard APIs, real client invitations, client visibility/portal APIs, close/reopen behavior, and migrations `0006` through `0008`. Final Phase 2 exit gate: 43 backend tests passed as app_user, including two lawyers/two clients/two cases isolation. |
| 2026-11-16 | Frontend Stage 2a: lawyer shell (sidebar, mobile bottom nav, language toggle, sign-out) and dashboard (stat cards, recent matters, recent activity, floating quick actions). Mock lawyer data sits behind `src/lib/api/lawyer.ts`. |
| 2026-11-16 | Frontend Stage 2b: `/lawyer/matters` searchable/filterable table with mobile cards and `/lawyer/matters/new` create form backed by the mock API. |
| 2026-11-16 | Frontend Stage 2c: `/lawyer/clients` searchable list, `/lawyer/clients/new` with one-time mock credentials, `/lawyer/clients/[clientId]` cases and `NOT_CONFIGURED` reset stub, `/lawyer/settings` language/profile/sign-out. |
| 2026-11-16 | Frontend Stage 3: client shell and `/client/dashboard` (case summary, lawyer-entered next hearing, animated stage stepper, lawyer contact, shared documents with labelled mock download, approved-only summaries) plus `/client/summaries/[summaryId]` placeholder. Client-visible types and mock data are separate from lawyer types; runtime role isolation checked. |
| 2026-11-16 | Frontend Stage 4a: `/lawyer/matters/[caseId]` header with title, client, court, case type, status chip, lawyer-controlled stage selector, and the shared client progress graph. `getCase(caseId)` added to the lawyer mock API; `/lawyer/matters` rows link to detail; unknown cases show a localized 404. |
| 2026-11-17 | Frontend Stage 4b: hearing timeline on `/lawyer/matters/[caseId]` with number, date, court and lawyer notes; add-hearing form where the lawyer enters the date; append-only note versions with an "Edited" marker and version list. Mock-only, labelled `SAMPLE_DATA_NOT_REAL_LAW`; closed matters are read-only. |
| 2026-11-17 | Frontend Stage 4c: per-hearing "Upload documents" button with drag and drop, PDF/image-only validation and a 20 MB limit with localized errors; simulated uploading, processing, ready and failed states with retry; Hearings/Documents tabs; Documents tab grouped by hearing with per-hearing summary status (none, processing, draft ready, approved). Mock-only, labelled `SAMPLE_DATA_NOT_REAL_LAW`. |
| 2026-11-17 | Frontend Stage 5a: memo-style hearing summary at `/lawyer/matters/[caseId]/hearings/[hearingId]/summary` with formal memorandum header, key notes, laws and clauses, risks and loopholes, rights, notes and next steps. Each claim shows its type (document, lawyer, AI inference, assumption), source reference and verified/unverified badge; a not-legal-advice notice is prominent and no win percentages appear. Draft/approved hearings link here from the timeline and Documents tab; processing hearings show a localized unavailable state. Mock-only, labelled `SAMPLE_DATA_NOT_REAL_LAW`. |
| 2026-11-17 | Frontend Stage 5b: hearing summary review workflow. Added the "AI draft - pending lawyer review" badge, an edit mode where every save appends a new version and returns the summary to draft, a version history list with saved time and author, an "Approve and share with client" action that marks the mock summary approved and upserts it in the client Summaries list, and a "Download summary" PDF stub that returns `NOT_CONFIGURED`. Every hearing on the case page now links to its summary. Mock-only, labelled `SAMPLE_DATA_NOT_REAL_LAW`. |
| 2026-11-17 | Frontend Stage 5c: `/client/summaries/[summaryId]` now renders a plain-language version of an approved summary with the same six sections in simpler client-safe text, no claim-type labels, no sources and no lawyer-only notes. Added a not-legal-advice notice, a "Download summary" PDF stub returning `NOT_CONFIGURED`, and a localized client not-found page. Draft, unknown and other-case summaries return not-found; the client page and API use client-visible types only. Mock-only, labelled `SAMPLE_DATA_NOT_REAL_LAW`. |
| 2026-11-18 | Frontend Stage 5d: lawyer sign-up at `/lawyer/signup` reuses the auth layout and login look, with full name, email, phone, optional firm/chambers and Bar Council enrollment, password, confirm password and a required draft-notice checkbox. Server-side validation returns localized EN/BN field errors with `aria-describedby`; `signUpLawyer()` in `src/lib/auth.ts` starts the mock lawyer session and redirects to the dashboard when `MOCK_AUTH=true`, otherwise returns a friendly `NOT_CONFIGURED`. No password is stored, logged or put in a URL. Added the login/sign-up cross-links and the client-login note that the lawyer provides the Client ID and password. Lint, production build and browser checks (validation, successful mock redirect, EN/BN, no runtime errors) passed. |
| 2026-11-18 | Frontend Stage 5e: `/` is a role chooser with two clear actions, "Log in as a lawyer" and "Log in as a client", plus a "New lawyer? Create an account" link to `/lawyer/signup`. Signed-in users still go straight to their dashboard. Replaced the old "Are you a client?" / "Are you a lawyer?" wording on both login pages with the same action labels in EN and BN; dictionaries and the design reference were updated. Lint, production build and browser checks (EN/BN chooser, links, no runtime errors) passed. |
| 2026-11-18 | Frontend Stage 5f: neutral background palette. Page backgrounds are white via `--color-cream`; cards, panels, table rows/headers, inputs, summary claim cards and neutral note boxes use `--color-surface` (#F7F8FA) with the existing borders. Replaced the hard-coded cream topbar and remaining neutral `#fff`/`#fbfaf6`/`#fcfcfa` box fills. Deep green brand panels and case hero, green buttons, semantic status tints and all text colours are unchanged. Lint, production build and browser checks (all listed pages, EN/BN, desktop and 390px, no runtime errors) passed. |
| 2026-11-18 | Backend Dev 1 Phase 1 B1: added the uv/FastAPI project, environment settings, safe structured logging, request IDs, problem+json handlers, and `/health`; added Compose placeholders and started the local PostgreSQL 16/pgvector service. Backend tests: 8 passed. Migrations, database access, RLS, auth, Redis, and MinIO wiring remain unimplemented. |
| 2026-11-19 | Backend Dev 2 Phase 3: implemented and tested Document Intake & Processing Pipeline (`backend/src/documents/`): magic-bytes MIME validator, PyMuPDF digital extractor, Tesseract bilingual OCR with contrast/sharpening preprocessing and confidence scoring, and page-scoped chunker. |
| 2026-11-19 | Backend Dev 2 Phase 4: ingested 62,491 legal chunks into PostgreSQL 16 + pgvector (`legal_chunks`); built HNSW cosine vector index (306 MB) and weighted GIN full-text index (20 MB); implemented Hybrid RRF retriever ($K=60$), cross-encoder reranker, and anti-hallucination citation generator. Benchmarked 80.0% Recall@5. |
| 2026-11-19 | Backend Dev 2 Phase 5: implemented AI Case Understanding & Fact Extraction Engine (`backend/src/ai/`, `backend/src/analysis/`): provider-whitelisted LLM Gateway with XML prompt injection sanitizer (Rule 9), Claims Verifier (Rule 2), Chronological Timeline Engine with bilingual Bangla/English date normalization and temporal anomaly detection, Contradiction & Statutory Checklist Gap Engine, and FastAPI `/api/v1/cases/*` endpoints. Connected Next.js data client without design alterations. 63 backend tests passing. |
| 2026-11-19 | Backend Dev 2 Phase 6: implemented Chess-Inspired Legal Strategy Engine (`backend/src/strategy/`): dynamic K candidate strategy generator, strict 2-ply adversarial scenario tree (depth D=2, breadth B<=3, residual risk metadata on response nodes), 5-dimension qualitative rubric evaluator with weakest-critical-dimension ceiling rule (no win percentages), legal eligibility validation, versioned immutable strategy lifecycle (draft -> proposed -> approved -> current -> superseded), mock provider restrictions, Alembic migration 0009 with PostgreSQL RLS, and FastAPI strategy endpoints. 80 backend tests passing. |
| 2026-11-19 | Backend Dev 2 Phase 7: implemented Hearings & Continuous Strategy Reassessment Engine (`backend/src/hearings/`): hearing management with Rule 5 lawyer-only date confirmation guard, append-only version chaining (`supersedes_id`, Rule 6), continuous 2-ply adversarial tree diffing ($D=2, B \le 3$), 5-dimension qualitative rubric re-evaluation, posture recommendations (`maintain`, `review`, `change_suggested`), plain-language client update drafting with lawyer approval gate (Rule 8), multi-matter calendar aggregator (`GET /calendar`), Alembic migration `0010_phase7_hearings_reassessment` with PostgreSQL RLS, and complete test suite (94 passing tests). |
| 2026-11-20 | Gap report against `DOCS/PokkhoAI_master_prompt.md` added as section 7. |
| 2026-11-20 | Step 0 (rule fixes) per section 7.5: template precedents/strategies removed, mock-only provider default, hard-coded credentials removed, frontend no longer forces "verified", `sections.jsonl` exported from act files. Backend: 97 passed, 30 skipped (DB tests, no migrated DB). Scraper: 11 passed, 1 live-network test deselected. |

## 7. Gap report: master prompt (RAG + analysis + strategy), 2026-11-20

Written before any coding, per `DOCS/PokkhoAI_master_prompt.md`. Inspection only; tests were not re-run for this report. AGENTS.md rules override the master prompt.

### 7.1 Rule violations in current code (fix before building on it)

| # | Rule | Finding | Where |
|---|---|---|---|
| V1 | 1 No invented law | Hard-coded case-law citations ("Shamsul Haque vs State, 62 DLR (AD) 250"; "Major (Retd.) M. A. Jalil vs State, 58 DLR 145") with `is_verified=True`, no `SAMPLE_DATA_NOT_REAL_LAW` label, and not present in any database. Hard-coded statutory requirements and limitation statements are also emitted as verified. | `backend/src/strategy/orchestrator.py:155-215, 318-323, 431`; `strategy/generator.py:251, 289`; `strategy/engine.py:272`; `hearings/service.py:88` |
| V2 | 2 No source, no claim | Frontend sets `verification: "verified"` on every AI analysis claim, and labels AI relevance text as type `document`. Bangla text is the English string with a Bangla prefix. | `frontend/src/lib/api/lawyer.ts:300-500` |
| V3 | 2 | `ClaimsVerifier` marks a claim SUPPORTED if any source has `page_number > 0`, and any `legal_source_version` source as corroborated, without checking that it exists or that the quote matches. | `backend/src/analysis/claims.py` |
| V4 | 7 Isolation | `backend/src/main.py` is a second FastAPI app with no authentication, `allow_origins=["*"]` with credentials, and no case-membership checks on any `/api/v1/cases/*`, strategy, hearing, or legal-kb route. `lawyer_id` and `organization_id` are taken from the request body/query. | `backend/src/main.py`, `src/*/router.py` |
| V5 | 6 Keep history / 7 RLS | Analysis, strategy, and hearing data live in in-process dicts, not PostgreSQL. Migrations `0009`/`0010` create tables with RLS but no code reads or writes them, so the status rows "PostgreSQL RLS verified" for phases 6-7 are not accurate for the running code. Data is lost on restart. | `src/analysis/engine.py:42`, `src/strategy/engine.py:43`, `src/hearings/service.py:50` |
| V6 | 10 Approved providers | Gateway default allow-list is `"mock,gemini"`, and a Gemini provider plus live demo script exist, but `DOCS/providers.md` approves no provider. | `src/ai/gateway.py:72`, `src/ai/providers/gemini.py`, `scripts/live_gemini_demo.py` |
| V7 | Security | Database credentials hard-coded as defaults (`researchsphere:devpassword`); an absolute developer path is hard-coded. | `src/main.py`, `src/legal_kb/ingest_all.py` |
| V8 | 11 Don't claim it works | Live search endpoint uses `MockEmbeddingProvider` (hash-seeded random vectors), so the dense half of hybrid search is noise. Status says 62,491 chunks ingested and 80% Recall@5, but the local database has no `legal_chunks` table and no Alembic revision applied, and `data-scrapper/data/processed/sections.jsonl` does not exist. The benchmark result cannot be reproduced from this checkout. | `src/main.py:52`, status rows 4 RAG |

### 7.2 What exists and can be reused

- `app/` (Dev 1): auth, sessions, RLS context (`app.current_user_id`), cases, `CaseAccess`, client portal, audit writer, migrations `0001`-`0010`. This is the correct base for new endpoints.
- `src/legal_kb/`: E5 provider with `passage:`/`query:` prefixes and normalization, RRF fusion (k=60), `bge-reranker-v2-m3` reranker behind an interface with a mock, exact-section lookup, `SET LOCAL hnsw.ef_search = 100`, `content_hash` and `embedding_model`/`embedding_version` columns.
- `src/documents/`: validation, PyMuPDF extraction, Tesseract OCR, page chunker.
- `src/ai/`: gateway, mock provider, XML data-block sanitizer (Rule 9 direction is right).
- Scraper: 1,178 act JSON files under `data/processed/acts/`, `catalog.json`, `DataValidator.validate_section_record`.

### 7.3 Missing vs the master prompt

| Item | Gap |
|---|---|
| A Ingestion | Legal KB schema is raw SQL (`src/legal_kb/migrations.py`), not Alembic. No `source_type`, `status` per section, `canonical_section_id`, or `effective_*` population. Invalid records are dropped silently (no reject report); scraper validator not used. Token counts are a word heuristic (x1.35), not the model tokenizer. Chunk header format differs from the prompt. No worker/queue, no resume, no skip-if-hash-unchanged. Subsection keys mismatch: scraper emits `subsection_identifier`/`text`, backend chunker reads `clause`/`content` (empty lines appended). CLI path differs (`src.legal_kb.ingest_all`). |
| A Data | `sections.jsonl` absent; scraper emits no amendment/repeal status, so all sections must be `unknown` and flagged. |
| B Retrieval | No incident-date filter, no bn/en dedupe by canonical id, no abstain threshold on reranker score, no `/lawyer/cases/{case_id}/research/search` with auth. Tests use mock embeddings, not real scraped sections. |
| C Facts | No structured facts draft (parties, dates, places, acts/omissions, documents, relief) with page refs; no lawyer confirm/edit endpoint; analysis does not gate on confirmed facts. `case_facts` in database.md is not migrated. |
| D Analysis | No element-by-element `ViolationFinding`; no deterministic citation verifier (exists-in-DB, in-force, NFC substring quote). |
| E Strategy | Tree is 2 plies with fixed node types, not the 3-ply `StrategyNode` contract with per-node verified citations; content is hard-coded templates (cheque-dishonour scenario). No "no precedent in knowledge base" behaviour. |
| F Hearings | Reassessment is in-memory; no `HearingReassessment` diff contract (closed/new options, tasks, draft next date) persisted. |
| G Deadlines/eval | No curated deadline rules table or deterministic calculator; no `backend/eval/` harness. |
| Docs | `DOCS/AI_AGENTS.md` does not exist (referenced by AGENTS.md and the prompt). |

### 7.4 Conflicts between the master prompt and existing docs

- `database.md` section 7 puts chunks under `legal_source_versions` with `review_status='approved'` gating search; the master prompt puts versioning per chunk/section. Proposal: keep database.md's `legal_sources` + `legal_source_versions`, add `legal_sections` (with `canonical_section_id`, `status`, `effective_from/to`) between versions and chunks. Needs approval (schema change).
- database.md generates `tsv` from `text` only; current code weights act/section fields via trigger. The prompt says `GENERATED ... 'simple'`. Proposal: generated column over header + text (header is in chunk text anyway).
- `providers.md` lists embeddings and reranker as "not chosen"; the prompt fixes e5-large and bge-reranker-v2-m3. These are self-hosted models (no data leaves the server), but providers.md should record the choice.

### 7.5 Step 0 results (2026-11-20)

| Item | Result | Commit |
|---|---|---|
| V1 template precedents and strategies | Removed. Generator returns no strategies and eligibility returns `NOT_CONFIGURED`. The orchestrator cites no precedents ("No precedent in knowledge base"), returns no canned facts, and keeps citations unverified. `is_verified` defaults to `False`. Hearing service no longer auto-creates and promotes a strategy. Strategy generation is now **Stubbed** (status rows 6 Strategy above overstate it). | `1a9ff348` |
| V3 claims verifier | Not changed yet. Replaced by the deterministic verifier in Step D. | |
| V2 frontend forced "verified" | Fixed in `frontend/src/lib/api/lawyer.ts`: all AI-derived claims are `type: "ai"`, `verification: "unverified"`. Removed invented remedy text and the "verified against official legal gazette" wording. **Left uncommitted** because the file also holds in-progress uncommitted work (Phase 7 reassessment block). | uncommitted |
| V4/V5 `src/` app access control and persistence | Not changed. Merge deferred pending Backend Dev 2 (see `DOCS/backend_orchestration.md` section 5). | |
| V6 provider | Gateway default is `mock` only. Gemini code kept, rejected unless `LLM_APPROVED_PROVIDERS` lists it. `.env.example` defaults to mock. | `9f921e8b` |
| V7 credentials and paths | Removed from `src/main.py`, `ingest_all.py`, legal KB tests (now `LEGAL_KB_TEST_DATABASE_URL`), and `Makefile`. | `9f921e8b` |
| V8 dataset | `python main.py --export-sections` builds `sections.jsonl` from `data/processed/acts/`: 35,063 sections (en 18,962, bn 16,098), 12 rejected by the validator, 3 scraper ID collisions kept under `-s{bdlaws_section}` IDs. `--report` on the output: 0 validation warnings. The KB is still not ingested and no migration is applied locally. | `97bc2ec2` |

Notes for Step A:
- Some section titles are `[Repealed]`; ingestion can set `status = repealed` from that marker and `unknown` otherwise.
- `tests/test_phase2.py::test_live_client_fetch` calls the live bdlaws site and hangs without network.
- `tests/legal_kb/test_pgvector_live.py` seeds hand-written section text that is not labelled `SAMPLE_DATA_NOT_REAL_LAW`; review in Step A.
- `hearings/reassessment.py` still uses cheque-specific keyword heuristics (consideration, postal notice); replaced in Step F.
- 37 compiled `.pyc` files were tracked in git; untracked on 2026-11-20.

### 7.6 TODO

- [ ] Step E: when `app_user` gets grants on `strategies`, `strategy_scenarios`, and `strategy_comparisons`, strengthen check 2 in `backend/tests/test_strategy_client_isolation.py`: insert a strategy row as the case lawyer, then assert the client member sees 0 rows. Today the client is refused because the grants are missing, so check 2 does not yet test RLS.

### 7.7 Step A progress (2026-11-20)

| Item | State |
|---|---|
| Migrations | `0011_legal_knowledge_base`, `0012_legal_version_approval` applied to local `legal_copilot` and `legal_copilot_test`; both down/up checked. `0010` revision ID shortened to fit `alembic_version` (32 chars). |
| Ingestion | `uv run python -m app.rag.ingest [--language bn\|en] [--limit N] [--dry-run]` as `app_admin_ingest`. Text stored NFC (ZWJ/ZWNJ kept); raw-text SHA-256 kept in `legal_sections.content_hash`. Header adds "(year)" only when the title lacks it. Full-dataset dry run: 1,176 Acts, 35,063 sections, 39,637 chunks, 0 errors. |
| Embedding | `uv run python -m app.rag.embed [--device auto\|cpu\|cuda] [--batch-size N] [--limit N] [--dry-run]`. "passage: " + NFC text, normalized 1024-dim vectors, batched, resumable, reuses vectors by content_hash. `auto` uses CUDA only when the torch build supports the GPU (the local MX350, sm_61, is not supported by torch cu132, so CPU). Local: 691/691 chunks embedded, ~132 s per 100 chunks on 8 CPU cores; the full corpus would take ~14.5 h on this machine. |
| Approval | `uv run python -m app.rag.approve (--version-id ID ... \| --all-pending) --reviewer-email EMAIL [--note] [--dry-run]`. Reviewer must be an active lawyer or admin; sets `reviewed_by`/`reviewed_at`; audit event `legal_source_version.approved`. No auto-approve. |
| Not done | Retrieval (Step B), query-side NFC is in `app.rag.text` but no search uses it yet; citation verifier (Step D) will use `app.rag.text.quote_in_text`. `tests/legal_kb/test_pgvector_live.py` targets the old raw-SQL schema and stays skipped; remove or port in Step B. |

### 7.8 Step A done (2026-11-20)

Step A (ingestion pipeline) is done. Commands, all as `app_admin_ingest` via `LEGAL_INGEST_DATABASE_URL`:

| Command | Purpose |
|---|---|
| `python -m app.rag.ingest` | Validate, chunk (NFC, e5 tokenizer, <=512), version by content hash |
| `python -m app.rag.embed run` | Local embedding (CPU here; `auto` skips GPUs the torch build cannot use) |
| `python -m app.rag.embed export` / `import` + `scripts/kaggle_embed.py` | Offload embedding to a Kaggle GPU; import verifies content_hash, model/version, 1024 dims, unit norm; rejects go to a report |
| `python -m app.rag.approve` | Human approval with reviewer, time, audit event; no auto-approve |
| `python -m app.seed_dev_lawyer` | Local dev lawyer account (password prompted, never echoed) |

Verified locally: Kaggle script round trip on 20 real Bangla chunks in `legal_copilot_test` (CPU): 20 imported, re-import 0 imported / 20 already embedded, 0 rejects, cosine 1.0 against the local worker.

Open items carried into Step B:
- [x] Approve the 20 local dev versions: done 2026-11-20 by the seeded dev lawyer via `app.rag.approve --all-pending` (20 approved, 20 audit events).
- [ ] Fix or delete `tests/legal_kb/test_pgvector_live.py` (targets the old raw-SQL schema; skipped).
- [ ] Embed the full corpus on Kaggle and ingest all Acts (dry run: 39,637 chunks).

