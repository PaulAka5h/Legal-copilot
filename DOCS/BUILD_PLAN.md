# Backend Build Plan: 3 Days, 2 Developers

Goal: a working demo slice (see `PRD.md` section 6.2): upload, OCR, case analysis, strategies with opposing-side scenarios, hearing reassessment, client view, case closure.

Tick boxes as you finish. Update `status.md` at the end of each day.

## Team split

| Dev | Area |
|---|---|
| **Dev A** | Platform and client side: auth, cases, RLS, uploads, hearings, client portal, closure, security tests, deploy |
| **Dev B** | AI pipeline: OCR, chunking, embeddings, retrieval, legal knowledge base, agents, strategy, reassessment |

Rules: one branch per module, small commits, only one person edits a migration at a time, merge to `main` at every checkpoint.

## Cuts (do not build these in 3 days)

- [ ] Agreed: no Redis, Celery, or SSE. Use a `jobs` table, FastAPI background tasks, and polling.
- [ ] Agreed: no MFA, no email sending. The invitation link shows in the lawyer UI.
- [ ] Agreed: no ClamAV or sandboxed conversion. Only type, size, and page-count checks. Say so in the demo.
- [ ] Agreed: no MinIO. Local disk behind a storage interface.
- [ ] Agreed: no admin ingest UI. One script loads the legal provisions.
- [ ] Agreed: only lead lawyer and client roles. No team members, reports, deletion flow, or reprocessing.
- [ ] Agreed: plain `audit_logs` inserts on key actions. No hash chain.

Keep, because they are the selling points: row level security, citations on every claim, client-visible tables, versioned analyses, qualitative ratings only.

## Before Day 1 (tonight, about 2 hours)

- [ ] Pick the demo case type with a practicing lawyer if possible.
- [ ] Write 4 to 5 synthetic documents: a digital PDF, a photographed page, a scanned page, in Bangla and English.
- [ ] Collect 10 to 15 real legal provisions for that case type, copied from official text. Anything you cannot verify is labelled `SAMPLE_DATA_NOT_REAL_LAW`.
- [ ] Choose one LLM provider for synthetic data only. Record it in `providers.md`.
- [ ] Get API keys. Put them in `.env`, never in git.
- [ ] Both devs have Docker, Python with uv, Node, and Tesseract with `ben` and `eng` language data installed.

## Day 1: Foundation and documents

### Together (hours 0 to 2)

- [ ] Repo scaffold: `backend/`, `frontend/`, `DOCS/`, `infra/`, `.env.example`
- [ ] Docker Compose with PostgreSQL and pgvector
- [ ] Alembic set up
- [ ] All migrations written once, trimmed from `database.md` (users, sessions, organizations, cases, case_members, case_invitations, documents, extracted_pages, document_chunks, legal tables, claims, claim_sources, analyses, strategies, strategy_scenarios, strategy_comparisons, hearings, hearing_updates, tasks, client_visible_*, jobs, ai_runs, audit_logs)
- [ ] RLS helper functions and policies applied
- [ ] FastAPI skeleton with problem+json errors and request IDs
- [ ] Mock LLM provider returning canned schema-valid output
- [ ] Endpoint list below frozen, and the OpenAPI schema shared with whoever builds the frontend

### Dev A (hours 2 to 10)

- [ ] Registration and login with Argon2id and cookie sessions
- [ ] Logout and `GET /me`
- [ ] Role dependency (`lawyer` vs `client` namespace)
- [ ] Case CRUD and case membership
- [ ] `CaseAccess` dependency, `app.current_user_id` set per request
- [ ] Document upload: magic-byte type check, size limit, page limit, SHA-256 duplicate check
- [ ] Local file storage behind a storage interface
- [ ] `jobs` table, `GET /jobs/{id}`, background task runner
- [ ] Document list and detail endpoints, page listing
- [ ] Download via short-lived signed path with membership check
- [ ] Audit events: login, upload, download, case create
- [ ] Isolation test v1: two lawyers cannot read each other's cases or documents

### Dev B (hours 2 to 10)

- [ ] PDF text extraction with page numbers
- [ ] Tesseract OCR (Bangla and English) with per-page confidence
- [ ] Quality flags: `needs_review` for low confidence or little text
- [ ] Page text saved with version and `is_current`
- [ ] `PATCH /documents/{id}/pages/{n}` correction creating a new version
- [ ] Chunker (does not cross pages) and embeddings with a multilingual model
- [ ] Hybrid retrieval (vector and keyword), always filtered by `case_id` in SQL
- [ ] Test 10 Bangla and English queries on the sample documents
- [ ] LLM gateway: structured output validation with one retry, approved-provider check, `ai_runs` logging

**Decision gate (Dev B, hour 4):** if Bangla OCR is too weak, stop tuning. Flag those pages for correction and move on.

### Day 1 checkpoint

- [ ] Log in, create a case, upload a mixed file
- [ ] Pages show with flags, one correction saved as a new version
- [ ] Chunk search returns results for the case and nothing from another case
- [ ] Isolation test passes
- [ ] Everything merged to `main`, `status.md` updated

## Day 2: Analysis and strategy

### Dev A

- [ ] Claims and claim_sources read endpoints
- [ ] Timeline, evidence, contradictions, gaps, research-results read endpoints
- [ ] Analysis list and latest endpoint with version numbers
- [ ] Hearings and hearing updates (original note stored unchanged, `lawyer_entered` label, edits create versions)
- [ ] Hearing date `confirmed` field settable only by a person
- [ ] Tasks (lawyer and client visible flag)
- [ ] Strategy read, approve, reject endpoints; only one current strategy per case
- [ ] Client-visible tables with RLS policies
- [ ] Client updates: draft, edit, publish, withdraw
- [ ] Shared documents: share and revoke
- [ ] Client visibility switches (`client_visible_case_fields`)
- [ ] Client invitation create and accept (token hashed, single use, expires)
- [ ] `/client` endpoints: cases, case, updates, hearing, tasks, documents, download URL

### Dev B

- [ ] Legal knowledge base ingest script (approved versions only)
- [ ] Legal search function (status and approval filters)
- [ ] Citation resolver: IDs must exist or the claim is rejected
- [ ] Case analysis, call 1: facts, timeline, evidence
- [ ] Case analysis, call 2: contradictions and gaps
- [ ] Case analysis, call 3: legal research
- [ ] Verifier agent (sees only claims and sources)
- [ ] Unsupported claims removed or marked `unverified`
- [ ] Analysis saved as versioned draft with claims and sources
- [ ] Strategy generator: 3 strategies
- [ ] Scenario tree per strategy: approach, opposing argument, response, remaining risk, depth 2, breadth 3
- [ ] Scenario generation runs in parallel across strategies
- [ ] Rubric ratings on five dimensions and the weakest-link cap
- [ ] Comparison with assumptions and "what would change this"
- [ ] Token, time, and branch caps with a `partial` result state

### Day 2 checkpoint

- [ ] Through the API only: upload, analysis, research, strategy comparison on the sample case
- [ ] Every shown citation resolves to a real chunk or legal source
- [ ] Client sees a published update and nothing else
- [ ] `status.md` updated and everything merged

## Day 3: Reassessment, hardening, demo

### Morning: Dev B

- [ ] Hearing reassessment run: add to timeline, diff against previous analysis, re-run affected strategies only
- [ ] Recommendation: `maintain`, `review`, or `change_suggested`, with reasons and assumptions
- [ ] New versions linked to old ones, nothing overwritten
- [ ] Client update drafter (uses only shareable fields)
- [ ] Prompt tuning on the sample case
- [ ] Prompt injection test: a document with hidden instructions does not change output

### Morning: Dev A

- [ ] Case closure transaction: status closed, client membership revoked for this case only, client tasks cancelled
- [ ] Client boundary test: scan every client response for forbidden fields (private notes, analysis, strategy, risk)
- [ ] Authorization matrix test: anonymous, wrong role, wrong case, revoked client, closed case
- [ ] Login rate limit and lockout
- [ ] CORS and cookie settings checked (httpOnly, secure, SameSite)
- [ ] Unauthorized and missing resources both return 404

### Afternoon

- [ ] **Dev A:** idempotent demo seed script (client, case, users, legal provisions)
- [ ] **Dev A:** Docker Compose runs the full stack from a clean checkout
- [ ] **Dev A:** deployed to one VM with TLS
- [ ] **Dev B:** pre-run a complete analyzed and strategized case as a fallback
- [ ] **Dev B:** fallback switch in config if the live LLM is slow or down
- [ ] **Together:** rehearse the demo script in `UserFlow.md` section 10, twice
- [ ] **Together:** fix bugs found in rehearsal
- [ ] **Together:** feature freeze 3 hours before the demo
- [ ] Final `status.md` update, listing everything stubbed or cut

## Frozen endpoint list (demo slice)

Freeze this at Day 1 hour 2. Add nothing until Day 3 without telling the frontend dev.

**Auth:** `POST /auth/register` · `POST /auth/login` · `POST /auth/logout` · `POST /auth/invitations/accept` · `GET /me`

**Clients and cases:** `GET, POST /clients` · `GET, POST /cases` · `GET, PATCH /cases/{id}` · `POST /cases/{id}/invitations` · `POST /cases/{id}/close`

**Documents:** `POST /cases/{id}/documents` · `GET /cases/{id}/documents` · `GET /documents/{id}` · `GET /documents/{id}/pages` · `PATCH /documents/{id}/pages/{n}` · `GET /documents/{id}/download-url`

**Jobs:** `GET /jobs/{id}`

**Analysis:** `POST /cases/{id}/analysis-runs` · `GET /cases/{id}/analyses/latest` · `GET /cases/{id}/timeline` · `GET /cases/{id}/evidence` · `GET /cases/{id}/contradictions` · `GET /cases/{id}/gaps` · `GET /cases/{id}/research-results`

**Strategy:** `POST /cases/{id}/strategy-runs` · `GET /cases/{id}/strategies` · `GET /strategies/{id}/scenarios` · `GET /cases/{id}/strategy-comparisons/latest` · `POST /strategies/{id}/approve` · `POST /strategies/{id}/reject`

**Hearings:** `GET, POST /cases/{id}/hearings` · `POST /hearings/{id}/updates` · `GET /hearings/{id}/reassessment`

**Client view (lawyer side):** `PATCH /cases/{id}/client-visibility` · `GET, POST /cases/{id}/client-updates` · `POST /cases/{id}/client-updates/draft` · `POST /client-updates/{id}/publish` · `POST /client-updates/{id}/withdraw` · `POST /cases/{id}/shared-documents` · `GET, POST /cases/{id}/tasks`

**Client portal:** `GET /client/cases` · `GET /client/cases/{id}` · `GET /client/cases/{id}/updates` · `GET /client/cases/{id}/hearing` · `GET /client/cases/{id}/tasks` · `PATCH /client/tasks/{id}` · `GET /client/cases/{id}/documents` · `GET /client/documents/{id}/download-url`

## Must-pass tests before the demo

- [ ] Lawyer A cannot read lawyer B's cases, documents, chunks, analyses, or strategies
- [ ] Retrieval never returns another case's text
- [ ] Client cannot call any lawyer endpoint
- [ ] Client responses contain no forbidden fields
- [ ] Revoked client loses access to the closed case at once, other cases unaffected
- [ ] Citations: a fake chunk ID makes the claim fail validation
- [ ] Reassessment keeps the old analysis and strategy versions
- [ ] No response or log contains document text outside the intended endpoints

## Risks and fallbacks

| Risk | Fallback |
|---|---|
| Strategy run takes too long | Cap it, show progress, switch to the pre-run case |
| Bangla retrieval is weak | Lean on keyword search for the demo queries |
| OCR is poor on the photographed page | Show the flag and correction flow as a feature |
| LLM provider is down or slow | Config switch to cached or mock output, say so openly |
| Migration conflict | One person owns migrations at a time |
| Frontend not ready | Build against the frozen OpenAPI schema or mock data |
| Scope creep | Anything not in this file waits until after the demo |

## What the demo does not claim

- Full security hardening, malware scanning, MFA, and email delivery are not built.
- The legal knowledge base is a small, hand-checked set, not a full database of Bangladesh law.
- AI output is a draft for lawyer review, and no strategy rating is a prediction of the outcome.
