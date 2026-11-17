# Project Status

Last updated: 2026-11-17

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
| database.md | Done (draft 1, not yet turned into migrations) |
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
| 1 Foundation | Project setup, Docker Compose | In progress | | | Frontend Next.js 16.4 + Tailwind v4 shell created; Docker Compose not started |
| 1 Foundation | Authentication and sessions | Stubbed | Manual browser checks passed | Role redirect tests passed | Development-only mock session behind `MOCK_AUTH=true`; production ignores it; no password check or user table |
| 1 Foundation | Roles, organizations, case membership | In progress | | | `lawyer` and `client` roles enforced by route-group guards; organizations and case membership not started |
| 1 Foundation | Database migrations and RLS | Not started | | | |
| 1 Foundation | Case creation | Stubbed | Manual form check passed | Role guard unchanged | `/lawyer/matters/new` writes to the in-memory mock matters list; no database yet. |
| 2 Dashboards | Lawyer dashboard shell | In progress | Lint and production build pass | Role guard unchanged; data isolation tests not written | Sidebar (Dashboard, My Matters, Clients, Settings), mobile bottom nav, header language toggle and sign-out, dashboard, matters list/create, clients list/create/detail, settings. All data is in-memory mock data; no database or RLS yet. |
| 2 Dashboards | Lawyer matter detail | In progress | Lint and production build pass; browser check passed (add hearing, append note version, drag-drop type/size errors, successful upload, retry, Documents tab, no runtime errors) | Role guard unchanged; no automated tests yet | `/lawyer/matters/[caseId]` header (case title, client, court, case type, status), lawyer-controlled stage selector, shared client progress graph, and a hearings timeline with number, date, court, lawyer notes, per-hearing document upload and summary status. Lawyer-entered add-hearing form; notes keep append-only versions with an "Edited" marker and version list. Hearings/Documents tabs; the Documents tab groups files by hearing. Uploads accept PDF/images up to 20 MB with typed size errors, simulate uploading/processing/ready/failed, and support retry. `/lawyer/matters` rows link here; unknown cases return a localized 404. Hearings, notes, documents and stage changes persist in the in-memory mock only. |
| 2 Dashboards | Client dashboard shell | In progress | Lint and production build pass; dev runtime check passed | Role redirect checked (client blocked from `/lawyer/dashboard`); no automated tests yet | Client shell, `/client/dashboard` (case title, hearing number, lawyer-entered next hearing, animated stage progress, lawyer contact, shared documents with labelled mock download, approved summaries), and `/client/summaries/[summaryId]` placeholder. All data is in-memory client mock data behind `src/lib/api/client.ts`; no database or RLS yet. |
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

- Authentication is a development-only mock. With `MOCK_AUTH=true`, the login actions set an `lc_session` cookie (`mock.lawyer` or `mock.client`). There is no password check, user table, organization, case membership, or RLS yet. Production always ignores the mock cookie and returns `NOT_CONFIGURED`.
- `/client/dashboard` is mock-backed: one client (`CL-7842-BD`) sees one case, shared documents, lawyer contact, and only approved summaries. The summary detail page is a labelled placeholder. Client invitations, activation, client tasks, and lawyer-published updates are not started. Mock client and lawyer data reset to seed data when the dev server restarts.
- The lawyer stage selector writes to the in-memory lawyer matter data. The client dashboard uses separate client mock data, so a lawyer stage change does not yet reach the client view; the shared `CaseProgress` component only guarantees the same graph UI. Reconnect both to one case record when the database and RLS land.
- Mock hearing dates and notes are lawyer-entered sample data behind `src/lib/api/lawyer.ts`; the AI never sets hearing dates. Note versions append and are never overwritten, but they reset to seed data when the dev server restarts. Closed matters keep their hearing record read-only.
- Document upload is simulated: file metadata only is kept in memory, no bytes reach storage or a provider. PDF/image type and the 20 MB limit are checked in the browser and again in the API. Status timers are client-side; `setDocumentStatusAction` persists the final mock status. Seeded failed files provide a retry path. Summary status per hearing is mock data with no editing flow yet.
- Client IDs and temporary passwords are generated locally for the mock. The password is shown once in the new-client success card and is not stored. Reset password returns `NOT_CONFIGURED`.
- The prefilled lawyer email/password and client ID/password on the login pages are sample data from the approved design, not usable accounts. Login does not read them.
- `cacheComponents` and `partialPrefetching` were removed from `frontend/next.config.ts` because cookie-based language rendering blocked prerendering of `/_not-found`. Revisit when the cookie strategy or route-level caching is settled.

## 6. Change log

| Date | Change |
|---|---|
| 2026-11-16 | Documentation set created: PRD, TRD, architecture, database, flows, agents, security, README, status, providers |
| 2026-11-16 | Frontend Stage 1: Next.js 16.4 + Tailwind v4 app, theme tokens/fonts, cookie-backed EN/BN dictionaries, shared auth components, `/lawyer/login` and `/client/login`; dashboard routes are `NOT_CONFIGURED` stubs |
| 2026-11-16 | Frontend Stage 1b: development-only mock sessions behind `MOCK_AUTH=true`, role-guarded `(lawyer)`/`(client)` route groups, sign-out, login redirects, and clean localized page titles |
| 2026-11-16 | Frontend Stage 2a: lawyer shell (sidebar, mobile bottom nav, language toggle, sign-out) and dashboard (stat cards, recent matters, recent activity, floating quick actions). Mock lawyer data sits behind `src/lib/api/lawyer.ts`. |
| 2026-11-16 | Frontend Stage 2b: `/lawyer/matters` searchable/filterable table with mobile cards and `/lawyer/matters/new` create form backed by the mock API. |
| 2026-11-16 | Frontend Stage 2c: `/lawyer/clients` searchable list, `/lawyer/clients/new` with one-time mock credentials, `/lawyer/clients/[clientId]` cases and `NOT_CONFIGURED` reset stub, `/lawyer/settings` language/profile/sign-out. |
| 2026-11-16 | Frontend Stage 3: client shell and `/client/dashboard` (case summary, lawyer-entered next hearing, animated stage stepper, lawyer contact, shared documents with labelled mock download, approved-only summaries) plus `/client/summaries/[summaryId]` placeholder. Client-visible types and mock data are separate from lawyer types; runtime role isolation checked. |
| 2026-11-16 | Frontend Stage 4a: `/lawyer/matters/[caseId]` header with title, client, court, case type, status chip, lawyer-controlled stage selector, and the shared client progress graph. `getCase(caseId)` added to the lawyer mock API; `/lawyer/matters` rows link to detail; unknown cases show a localized 404. |
| 2026-11-17 | Frontend Stage 4b: hearing timeline on `/lawyer/matters/[caseId]` with number, date, court and lawyer notes; add-hearing form where the lawyer enters the date; append-only note versions with an "Edited" marker and version list. Mock-only, labelled `SAMPLE_DATA_NOT_REAL_LAW`; closed matters are read-only. |
| 2026-11-17 | Frontend Stage 4c: per-hearing "Upload documents" button with drag and drop, PDF/image-only validation and a 20 MB limit with localized errors; simulated uploading, processing, ready and failed states with retry; Hearings/Documents tabs; Documents tab grouped by hearing with per-hearing summary status (none, processing, draft ready, approved). Mock-only, labelled `SAMPLE_DATA_NOT_REAL_LAW`. |
