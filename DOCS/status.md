# Project Status

Last updated: 2026-11-16

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
| 1 Foundation | Project setup, Docker Compose | Not started | | | |
| 1 Foundation | Authentication and sessions | Not started | | | |
| 1 Foundation | Roles, organizations, case membership | Not started | | | |
| 1 Foundation | Database migrations and RLS | Not started | | | |
| 1 Foundation | Case creation | Not started | | | |
| 2 Dashboards | Lawyer dashboard shell | Not started | | | |
| 2 Dashboards | Client dashboard shell | Not started | | | |
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

None yet.

## 6. Change log

| Date | Change |
|---|---|
| 2026-11-16 | Documentation set created: PRD, TRD, architecture, database, flows, agents, security, README, status, providers |
