# Project Status

Last updated: 2026-11-18

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
| 2 Dashboards | Lawyer dashboard shell | In progress | Lint and production build pass | Role guard unchanged; data isolation tests not written | Sidebar (Dashboard, My Matters, Clients, Settings), mobile bottom nav, header language toggle and sign-out, dashboard, matters list/create, clients list/create/detail, settings. All data is in-memory mock data; no database or RLS yet. |
| 2 Dashboards | Lawyer matter detail | In progress | Lint and production build pass; browser check passed (add hearing, append note version, drag-drop type/size errors, successful upload, retry, Documents tab, summary memo EN/BN, edit creates a new version, version history, approve/share updates client list, download returns NOT_CONFIGURED, unavailable state, 404, no runtime errors) | Role guard unchanged; no automated tests yet | `/lawyer/matters/[caseId]` header (case title, client, court, case type, status), lawyer-controlled stage selector, shared client progress graph, and a hearings timeline with number, date, court, lawyer notes, per-hearing document upload and summary status. Lawyer-entered add-hearing form; notes keep append-only versions with an "Edited" marker and version list. Hearings/Documents tabs; the Documents tab groups files by hearing. Uploads accept PDF/images up to 20 MB with typed size errors, simulate uploading/processing/ready/failed, and support retry. Every hearing links to a memo-style summary page at `/lawyer/matters/[caseId]/hearings/[hearingId]/summary`: formal memorandum layout, key notes, laws and clauses, risks and loopholes, rights, notes and next steps; each claim shows its type (document, lawyer, AI inference, assumption), source reference and verified/unverified state; a prominent not-legal-advice notice is shown and no win percentages appear. The page shows an "AI draft - pending lawyer review" badge, an edit mode where every save appends a new version and returns the summary to draft, a version history list, an "Approve and share with client" action that marks the mock summary approved and adds/updates the client Summaries list, and a "Download summary" PDF stub that returns `NOT_CONFIGURED`. Processing hearings show a localized unavailable state. `/lawyer/matters` rows link here; unknown cases return a localized 404. Hearings, notes, documents, summary versions and stage changes persist in the in-memory mock only. |
| 2 Dashboards | Client dashboard shell | In progress | Lint and production build pass; dev runtime check passed (approved summary renders plain-language sections, no claim labels, download returns NOT_CONFIGURED, draft and other-case summaries return 404, no runtime errors) | Role redirect checked (client blocked from `/lawyer/dashboard`); draft and other-case summary 404 checked; no automated tests yet | Client shell, `/client/dashboard` (case title, hearing number, lawyer-entered next hearing, animated stage progress, lawyer contact, shared documents with labelled mock download, approved summaries), and `/client/summaries/[summaryId]` plain-language summary detail. The detail page shows the same six sections with simpler client-safe text, no claim-type labels or lawyer-only notes, a not-legal-advice notice, and a "Download summary" stub returning `NOT_CONFIGURED`. Draft, unknown and other-case summaries call `notFound()` and render a localized client not-found page. All data is in-memory client mock data behind `src/lib/api/client.ts`; no database or RLS yet. |
| 2 Dashboards | Client invitations and activation | Not started | | | |
| 2 Dashboards | Client-visible updates and sharing | Not started | | | |
| 2 Dashboards | Case closure and access removal | Not started | | | |
| 3 Documents | Secure upload and validation | Not started | | | |
| 3 Documents | Original file storage | Not started | | | |
| 3 Documents | PDF and Word extraction | Not started | | | |
| 3 Documents | OCR (Bengali and English) | Not started | | | |
| 3 Documents | Page review and correction | Not started | | | |
| 4 RAG | Chunking and embeddings | Not started | | | |
| 4 RAG | Scoped retrieval (case filter) | Not started | | | |
| 4 RAG | Legal source ingestion and versions | Not started | | | |
| 5 Analysis | Facts and timeline | Not started | | | |
| 5 Analysis | Evidence, contradictions, gaps | Not started | | | |
| 5 Analysis | Cited legal research | Not started | | | |
| 5 Analysis | Verifier | Not started | | | |
| 6 Strategy | Strategy generation | Not started | | | |
| 6 Strategy | Scenario branches | Not started | | | |
| 6 Strategy | Rubric ratings and comparison | Not started | | | |
| 6 Strategy | Lawyer review and approval | Not started | | | |
| 7 Hearings | Hearing calendar and records | Not started | | | |
| 7 Hearings | Reassessment and version history | Not started | | | |
| 7 Hearings | Client update drafting | Not started | | | |
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
| 2026-11-18 | Backend Dev 1 Phase 1 B1: added the uv/FastAPI project, environment settings, safe structured logging, request IDs, problem+json handlers, and `/health`; added Compose placeholders and started the local PostgreSQL 16/pgvector service. Backend tests: 8 passed. Migrations, database access, RLS, auth, Redis, and MinIO wiring remain unimplemented. |
