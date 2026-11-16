# Product Requirements Document (PRD)

Working title: the Platform (name to be decided).
Event: AI Builders Congress.
Status: Draft 1.

## 1. Summary

The Platform is an AI decision-support tool for lawyers in Bangladesh. A lawyer uploads a client's documents, and the Platform reads them, builds a sourced picture of the case, retrieves relevant Bangladesh law, and compares possible legal strategies using a chess-inspired method: propose a move, explore the opponent's likely replies, weigh counters and risks, then compare the lines. After each hearing the lawyer records what happened and the Platform reassesses the strategy.

One application serves two roles: a full lawyer workspace and a simplified client dashboard that shows only what the lawyer has approved.

## 2. Problem

- Lawyers receive large, mixed piles of client material: typed PDFs, Word files, photos of paper, scans, some in Bangla and some in English. Reading and organizing them takes hours.
- Finding the right provisions and precedents is slow, and sources are spread across official sites, gazettes, and paid law reports.
- Strategy work happens in the lawyer's head or in scattered notes. Opposing arguments and weak points are easy to miss.
- After each hearing, the lawyer must re-think the case with no structured record of how the thinking changed.
- Clients keep asking "what is happening with my case?" and the lawyer answers by phone, repeatedly.

## 3. Vision and product principles

1. **Decision support, not decision making.** The lawyer decides. The AI never replaces the lawyer, decides cases, guarantees outcomes, or claims to know what a judge or opposing lawyer will do.
2. **Traceable.** Every important conclusion points to a document page or a legal source.
3. **Honest about uncertainty.** "Insufficient information" is a valid and welcome answer. No invented win percentages.
4. **Confidential by design.** Case data is isolated. Clients see only what the lawyer approves.
5. **History is kept.** Analyses and strategies are versioned, never silently overwritten.

## 4. Goals and non-goals

### 4.1 Goals
| ID | Goal |
|---|---|
| G1 | Help lawyers understand large collections of client documents faster |
| G2 | Surface relevant facts, evidence, contradictions, and missing information |
| G3 | Make Bangladesh legal research easier and traceable |
| G4 | Compare strategies in a structured way, including opposing-side scenarios |
| G5 | Keep the analysis current as hearings happen |
| G6 | Give lawyers a complete case and client workspace |
| G7 | Give clients a simple, controlled view of their own case |
| G8 | Protect confidentiality and isolate each case's data |
| G9 | Make AI conclusions traceable to sources |

### 4.2 Non-goals
- Predicting court outcomes or showing win percentages without a validated, calibrated model and dataset.
- Training a new language model from scratch.
- Filing documents in court or integrating with court e-filing in the first versions.
- Giving legal advice directly to clients or the public.
- Replacing the lawyer's judgment.
- Handwriting recognition at professional accuracy (handwriting is flagged as uncertain, not trusted).

## 5. Users

### 5.1 Lawyer (primary)
Practices in Bangladesh, possibly in a chamber with juniors. Handles several cases at once. Works in English and Bangla. Wants speed, but is accountable for every filing and argument, so needs sources and the ability to correct the AI.

### 5.2 Legal team member (secondary)
A junior lawyer or assistant added to a case by the lead lawyer, with limited permissions the lead chooses.

### 5.3 Client
Often non-technical, may be more comfortable in Bangla, usually on a phone. Wants to know the status, the next hearing, whether they must attend, and what the lawyer needs from them.

### 5.4 Platform administrator (internal)
Manages the legal knowledge base ingestion, provider configuration, and system health. Has no default access to private case content.

## 6. Scope

### 6.1 Release tiers

| Tier | Purpose | Contents |
|---|---|---|
| **Congress demo (MVP)** | A working vertical slice for the AI Builders Congress | Sections 7.1 to 7.9 at demo depth (see 6.2) |
| **v1** | First real lawyer pilot | Full 7.x features, hardened security, real legal knowledge base for chosen areas |
| **Later** | Growth | More case types, team workflows, reports, integrations |

### 6.2 Congress demo scope (proposal)

To show a complete story in limited time, the demo should include one end-to-end case path rather than many half-built features:

1. Lawyer signs in, creates a client and a case.
2. Uploads a mix of PDF and photographed pages (Bangla and English).
3. OCR and extraction run, with a visible low-confidence flag and a lawyer correction.
4. Case analysis with timeline, facts, contradictions, and missing information, each with page references.
5. Legal research over a small, real, verified set of Bangladesh provisions (the team picks one case type and ingests only the sources for it).
6. Strategy engine produces at least three strategies with opposing-side scenario branches and a comparison view.
7. Lawyer records a hearing; the reassessment shows what changed and a maintain or review recommendation.
8. Lawyer approves a client update; the client dashboard shows it, and shows nothing else.
9. Lawyer closes the case; client access to it is removed.

Which case type to pick is an open question (section 11). A common, well-bounded type with clear statutory text gives the cleanest demo. Confirm the choice with a practicing lawyer before building.

## 7. Functional requirements

Priority: **P0** needed for the demo, **P1** needed for v1, **P2** later.

### 7.1 Authentication and accounts
| ID | Requirement | Priority |
|---|---|---|
| AUTH-1 | Lawyers register and sign in with email and password; passwords hashed with Argon2id | P0 |
| AUTH-2 | Optional TOTP two-factor for lawyers (required in v1) | P1 |
| AUTH-3 | Clients join by secure invitation, set their own password, and get a permanent account | P0 |
| AUTH-4 | A client account can be linked to more than one case, each authorized separately | P0 |
| AUTH-5 | Password reset and invitation expiry are time-limited and single-use | P0 |
| AUTH-6 | Session management: sign out, sign out of all devices, session expiry | P1 |
| AUTH-7 | Predictable IDs are never used as credentials | P0 |

### 7.2 Clients and cases
| ID | Requirement | Priority |
|---|---|---|
| CASE-1 | Create and edit client profiles | P0 |
| CASE-2 | Create a case with title or reference, type, court, clients, opposing party, assigned lawyers, status, key dates, description, notes | P0 |
| CASE-3 | Each case has a dedicated workspace with its own documents, analysis, strategies, hearings, updates, tasks, and audit history | P0 |
| CASE-4 | Configurable stage templates per case type; stages are not assumed to be identical across cases | P1 |
| CASE-5 | Invite clients to a case and revoke access | P0 |
| CASE-6 | Add legal team members with a role and permissions | P1 |
| CASE-7 | Close a case; apply the closure policy (see 7.10) | P0 |

### 7.3 Documents and processing
| ID | Requirement | Priority |
|---|---|---|
| DOC-1 | Upload PDF, DOC, DOCX, JPG, PNG, and multiple files at once | P0 |
| DOC-2 | Validate type by file content, size limit, and malware scan; reject unsafe files | P0 |
| DOC-3 | Store the original file securely; it stays the source of truth | P0 |
| DOC-4 | Extract text from digital documents, keeping page numbers | P0 |
| DOC-5 | Run OCR on scans and photos in Bangla and English | P0 |
| DOC-6 | Flag pages with poor or incomplete extraction and uncertain OCR | P0 |
| DOC-7 | Lawyer can review and correct extracted text; corrections are versioned | P0 |
| DOC-8 | Show processing progress per document | P0 |
| DOC-9 | Chunk text, create embeddings, attach source and access metadata | P0 |
| DOC-10 | Reprocess a document when text is corrected or models change | P1 |
| DOC-11 | Authorized deletion of a document and its derived data | P1 |
| DOC-12 | Document viewer with side-by-side original and extracted text | P0 |

### 7.4 Case understanding
| ID | Requirement | Priority |
|---|---|---|
| UND-1 | Identify people, organizations, dates, places, events, statements, agreements | P0 |
| UND-2 | Build a chronological timeline | P0 |
| UND-3 | Identify evidence and show whether it supports or weakens the client's position | P0 |
| UND-4 | Detect contradictions between documents | P0 |
| UND-5 | List missing documents and questions for the client | P0 |
| UND-6 | Show source document and page for each finding | P0 |
| UND-7 | Separate "document says" from "AI infers" in data and UI | P0 |

### 7.5 Bangladesh legal knowledge base
| ID | Requirement | Priority |
|---|---|---|
| LAW-1 | Store Constitution, Acts, codes, rules, regulations, amendments, and repeal data from authoritative sources | P0 (scoped set) |
| LAW-2 | Store Supreme Court and High Court Division judgments and other relevant decisions where licensing allows | P1 |
| LAW-3 | Record source identity, date, issuing authority or court, and legal status | P0 |
| LAW-4 | Version history so amended or repealed provisions are not treated as current | P0 |
| LAW-5 | Update process with a review step before new content goes live | P1 |
| LAW-6 | Citation verification against stored sources | P0 |
| LAW-7 | Research results explain which provisions may apply, why, which judgments, what principles, and whether status was checked | P0 |
| LAW-8 | When a source cannot be verified, the output says so | P0 |

### 7.6 Initial case analysis
| ID | Requirement | Priority |
|---|---|---|
| ANA-1 | Structured analysis: client position, factual issues, legal issues, applicable law, precedents, supporting and weakening evidence, contradictions, missing evidence, open questions, procedural issues, risks, areas for investigation | P0 |
| ANA-2 | Each conclusion links to its source | P0 |
| ANA-3 | Analysis is versioned and dated | P0 |
| ANA-4 | Independent verification pass with visible results | P0 |

### 7.7 Chess-inspired strategy engine
| ID | Requirement | Priority |
|---|---|---|
| STR-1 | Generate multiple legally plausible strategies | P0 |
| STR-2 | For each: legal basis, supporting facts and evidence, provisions, precedents, strengths, weaknesses, missing evidence, objections, procedural risks, practical obstacles, consequences, alternatives | P0 |
| STR-3 | Scenario branches: our approach, possible opposing argument, possible response, remaining risk | P0 |
| STR-4 | Compare strategies side by side with reasons and assumptions | P0 |
| STR-5 | Qualitative ratings only (strong, moderate, weak, insufficient information) with rubric dimensions | P0 |
| STR-6 | No invented win probability; any score states exactly what it measures | P0 |
| STR-7 | Lawyer can edit, reject, or approve strategies and add their own | P0 |
| STR-8 | Wording marks scenarios as plausible, never certain | P0 |
| STR-9 | Show assumptions and what would change the assessment | P0 |
| STR-10 | Independent verification of strategy claims | P0 |
| STR-11 | Control depth and breadth of branch exploration | P1 |

### 7.8 Hearings and continuous reassessment
| ID | Requirement | Priority |
|---|---|---|
| HEAR-1 | Hearing calendar and records | P0 |
| HEAR-2 | Hearing update form: date, what happened, our arguments, opposing arguments, judge's questions as recorded, new evidence, objections, orders, next date, follow-up tasks | P0 |
| HEAR-3 | Preserve the original note and its author; label it as lawyer-entered, not a verified court record | P0 |
| HEAR-4 | After submission, update the timeline, compare to prior analysis, re-evaluate strategy, consider new opposing responses, identify new risks and evidence needs | P0 |
| HEAR-5 | Recommend maintain, review, or change, with reasons | P0 |
| HEAR-6 | Show changes from the previous analysis | P0 |
| HEAR-7 | Keep full version history of analyses and strategies | P0 |
| HEAR-8 | Draft a client update only after the lawyer approves it | P0 |
| HEAR-9 | Next hearing dates are entered or verified by an authorized person, never inferred by the AI | P0 |

### 7.9 Dashboards
| ID | Requirement | Priority |
|---|---|---|
| DASH-1 | One application; the dashboard depends on the authenticated role | P0 |
| DASH-2 | Lawyer navigation: Overview, My Cases, Clients, Create New Case, Documents, AI Case Analysis, Legal Research, Evidence Analysis, Strategy Engine, Opponent Analysis, Hearing Calendar, Case Timeline, Tasks and Follow-ups, Reports, Notifications, Account and Security | P0 (core items), P1 (Reports, full set) |
| DASH-3 | Client navigation: My Case, Case Status, Case Progress, Upcoming Hearing, My Tasks, Shared Documents, Lawyer Updates, Notifications, Account Settings | P0 |
| DASH-4 | The client dashboard shows no lawyer-only tools, internal analysis, private notes, risk assessments, or other clients' data | P0 |
| DASH-5 | The lawyer controls which fields, updates, and documents are visible to the client | P0 |
| DASH-6 | Visual distinction for confirmed info, lawyer notes, AI analysis, unverified info, upcoming dates, completed tasks, risks, client-approved updates | P0 |
| DASH-7 | Responsive layout; client views work well on phones | P0 |
| DASH-8 | Bangla and English interface and content | P1 (content P0) |

### 7.10 Case closure and retention
| ID | Requirement | Priority |
|---|---|---|
| CLOSE-1 | Lawyer marks a case closed | P0 |
| CLOSE-2 | Client access to that case is deactivated or restricted by policy | P0 |
| CLOSE-3 | The client's other cases and the client account are unaffected | P0 |
| CLOSE-4 | Lawyer keeps authorized access to history | P0 |
| CLOSE-5 | Original documents and data stay protected under the retention policy | P0 |
| CLOSE-6 | Permanent deletion only through an explicit, authorized, audited process | P1 |

### 7.11 Notifications, tasks, audit
| ID | Requirement | Priority |
|---|---|---|
| NOTE-1 | In-app notifications for lawyers and clients; email later | P0 (in-app) |
| NOTE-2 | Tasks for lawyers and tasks requested of clients | P0 |
| AUD-1 | Audit log for logins, access changes, document views and downloads, shares, AI runs, approvals, closures, deletions | P0 |

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| Security | See `Security.md`. Row level security, case-level permissions, encrypted storage and transport, private files, audit logs |
| Privacy | No external AI provider before data terms are reviewed; no training on client data without explicit authorization |
| Accuracy | Verification stage on important outputs; citation existence rate of 100% for shown citations |
| Performance | Upload feedback within 2 seconds; first processing results (text) within about 1 minute for a typical 20-page file; strategy runs show progress and finish within a stated time budget (target to be tuned after testing) |
| Availability | Demo: best effort. v1: defined target with backups and recovery tested |
| Language | Bangla and English documents, search, and output |
| Accessibility | Keyboard navigation, readable contrast, scalable text, mobile-friendly client views |
| Maintainability | Modular code, documented modules, tests per module |
| Observability | Metrics, structured logs without document content, AI run records |
| Explainability | Rubrics, assumptions, sources, and changes between versions are visible |

## 9. Delivery phases

| Phase | Focus | Exit check |
|---|---|---|
| 1 Foundation | Project setup, auth, roles, database, case creation, case-level authorization | Isolation tests pass |
| 2 Two dashboards | Lawyer and client dashboards, invitations, per-case client access, lawyer-controlled updates, closure | Client sees only approved items |
| 3 Documents | Case workspace, secure upload, original storage, extraction, OCR, page references, review | Bangla and English samples process correctly |
| 4 RAG and legal knowledge | Chunking, embeddings, pgvector, permission-filtered retrieval, legal source ingestion, versions | Retrieval never crosses cases |
| 5 Case analysis | Summaries, facts, timeline, evidence, contradictions, cited research | Every conclusion has a source |
| 6 Strategy engine | Strategy generation, scenario branches, comparison, verification, lawyer approval | Branch structure complete and verified |
| 7 Hearings | Calendar, hearing updates, reassessment, strategy history, client updates | History preserved on every run |
| 8 Production readiness | Security testing, privacy review, performance, backups, monitoring, ops docs | Checklist in `Security.md` passed |

For the Congress, build a thin path through phases 1 to 7 (section 6.2) and defer the rest.

## 10. Success metrics

### Product
- Time from upload to first usable case summary.
- Share of AI findings the lawyer accepts without edits, edits, or rejects.
- Number of strategies the lawyer considers that they had not considered.
- Share of hearings where the lawyer reads the reassessment.
- Client portal visits and drop in "status" calls (pilot survey).

### Quality
- Citation existence rate (target 100%).
- Unsupported claim leak rate (target near zero).
- OCR low-confidence flag recall.
- Lawyer usefulness rating from the advisor panel.

### Safety
- Zero cross-case or cross-client data exposure in tests and in the pilot.
- Zero AI outputs presented as confirmed court records.

## 11. Open questions

1. Which case type does the demo use? Candidates: a cheque dishonour matter, a civil land dispute, a loan recovery matter, or a family matter. Pick one with a practicing lawyer.
2. Which legal sources can be ingested and under what licence? Official legislation portals are the likeliest starting point; commercial law report series may need permission. Confirm before ingesting.
3. Is a Bangladeshi lawyer available as advisor and tester?
4. Which LLM provider and region are acceptable for client data? Needs a provider review.
5. Is OCR for Bangla good enough with open-source tools on real scanned court papers, or is a paid OCR needed?
6. What retention period applies to closed case files, and does the Bar Council or other rule set one?
7. Does any Bangladeshi data protection law apply to the hosting location and data residency? Ask counsel for the current position.
8. Should an organization (chamber) be a first-class tenant in the demo, or only individual lawyers?
9. Which languages must the client dashboard support at launch (Bangla, English, or both)?
10. Notification channels for clients (in-app only, email, SMS)?

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| AI invents a law or case | Serious harm to the lawyer and client | Citations must exist in the knowledge base; verifier; labelled unverified |
| Poor Bangla OCR | Wrong facts | Confidence flags, lawyer review, side-by-side viewer |
| Incomplete or outdated legal data | Wrong advice | Version tracking, status checks, "insufficient information" outputs |
| Data leak across cases | Loss of trust, legal exposure | Row level security, scoped retrieval, isolation tests |
| Over-trust in AI | Lawyer relies on a wrong rating | Qualitative ratings, visible assumptions, mandatory review state |
| Provider data exposure | Confidentiality breach | Provider review, mock provider by default, no training use |
| Scope too large for the Congress | Unfinished demo | Thin vertical slice (6.2) |

## 12. Glossary

| Term | Meaning |
|---|---|
| RAG | Retrieval-augmented generation: the AI answers using passages retrieved from stored documents |
| Chunk | A short passage of text stored with its source and page |
| Embedding | A numeric representation of text used for similarity search |
| Scenario branch | A chain: our approach, opposing argument, our response, remaining risk |
| Row level security | A database feature that limits which rows a user can read or write |
| Client-visible update | A message or field the lawyer has explicitly approved for the client |
