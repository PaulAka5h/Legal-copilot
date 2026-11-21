# PokkhoAI

An AI decision-support platform for lawyers in Bangladesh, built for the AI Builders Congress.

A lawyer uploads a client's documents (PDFs, Word files, photos, scans). The platform extracts the text, builds a sourced picture of the case, retrieves relevant Bangladesh law, and runs a chess-inspired strategy engine. The engine proposes several legal strategies, explores how the opposing side may respond, weighs counterarguments and risks, and compares the options. After each hearing the lawyer records what happened and the platform reassesses the strategy.

One app serves two roles: a full lawyer workspace, and a simple client dashboard that shows only what the lawyer has approved.

The AI supports the lawyer. It does not decide cases, guarantee outcomes, or claim to know what a judge or opposing lawyer will do.

## Status

Documentation is written. Code has not been started. See `docs/status.md` for what is done and what is next.

Demo deployment (`DOCS/deploy_render_free.md`): demo knowledge base = 19 Acts (717 chunks, Gemini
embeddings, free-tier limit); the full corpus pipeline exists (e5: 29 Acts / 2,652 chunks ingested
and embedded locally; full-dataset dry run 1,176 Acts / 39,637 chunks).

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS |
| Backend | Python, FastAPI |
| Database | PostgreSQL with pgvector |
| API | REST with an OpenAPI schema |
| Jobs | Redis and a worker |
| Files | S3-compatible object storage |
| OCR | Tesseract (Bengali and English), behind an interface |

Details and trade-offs are in `TRD.md`.

## Repository layout (planned)

```
/apps/web         Next.js app (lawyer and client dashboards)
/apps/api         FastAPI app
/apps/worker      Background worker
/packages/api-client   TypeScript client generated from OpenAPI
/infra            Docker Compose and deployment files
/docs             Documentation and status files
```

## Getting started

Commands will be finalized during project setup. The planned shape:

```
cp .env.example .env     # fill in local values, never commit real secrets
make dev                 # start web, api, worker, postgres, redis, minio
make migrate             # apply database migrations
make test                # run unit tests
make test-isolation      # run cross-case and cross-client tests
```

Development uses synthetic data and the mock AI provider by default. Do not load real client documents into a local or demo environment.

## Documentation map

| File | What it covers |
|---|---|
| `Idea.md` | The original product brief |
| `PRD.md` | What we are building, for whom, and in what order |
| `TRD.md` | Technology choices, API conventions, pipelines, testing |
| `SystemArchitecture.md` | Components, data flows, deployment, trust boundaries |
| `database.md` | Schema, row level security, indexes, retention |
| `applicationflow.md` | System behavior from sign-in to case closure |
| `UserFlow.md` | Screens and journeys for lawyers and clients, demo script |
| `Skills and agents.md` | The AI agents and skills inside the product |
| `Security.md` | Threat model, controls, and the production checklist |
| `Agent.md` | Instructions for AI coding agents working on this repo |
| `docs/status.md` | Progress tracker |
| `docs/providers.md` | Approved AI providers and review records |

## Ground rules

1. No invented laws, sections, case names, or citations. Test data that looks like law must be labelled `SAMPLE_DATA_NOT_REAL_LAW`.
2. Every important AI conclusion links to a document page or a legal source.
3. No win percentages. Ratings are qualitative with reasons.
4. A case ID or client ID alone never grants access. Authorization is checked in the backend and in the database.
5. No secrets in the repo. No client data sent to a provider that is not approved in `docs/providers.md`.

## Disclaimer

This software is a decision-support tool for qualified lawyers. It does not give legal advice, and its output must be reviewed by a lawyer before anyone relies on it.
