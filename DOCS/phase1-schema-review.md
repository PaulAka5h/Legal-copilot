# Phase 1 and B9 Schema Review Packet

Status: Draft, not shared-database approved.

This packet lists migrations applied only to the local Compose database until
Akash and Backend Dev 2 explicitly approve shared use.

## Roles

- `app_owner`: migration and bootstrap role.
- `app_user`: application role; no superuser, no BYPASSRLS.

## Revisions

| Revision | Scope | Status |
|---|---|---|
| `0001_phase1_baseline` | Phase 1 organizations, users, memberships, profiles, sessions, reset tokens, cases, stages, members, invitations, extensions, RLS, helper functions | Local draft |
| `0002_auth_support` | IP throttle table, audit log table, lookup/throttle/login functions | Local draft |
| `0003_session_revocation` | Scoped session revocation function | Local draft |
| `0004_b9_auth_support` | MFA recovery codes, password-reset lookup/consume functions | Local draft |
| `0005_b10_audit_writer` | Central append-only audit insert function and mutation trigger | Local draft |
| `0006_b12_invitations` | Constrained client invitation acceptance function and active-invitation uniqueness | Local draft |
| `0007_b13_client_visibility` | Hearings, updates, shared documents, tasks, visibility fields, notifications, and RLS | Local draft |
| `0008_b13_client_case_read` | Client SELECT policy for active open cases | Local draft |
| `0009_phase6_strategy_engine` | Dev 2 strategy tables + RLS. Amended by Dev 1 on 2026-11-19 (owner-authorized): policies use `app.is_lawyer_member` instead of the undefined `app.has_case_access`; client SELECT policy on `strategies` removed. Still missing: `app_user` grants and `(case_id, organization_id)` FK | Local draft. Needs Dev 2 + Akash sign-off; live upgrade not yet verified |
| `0010_dev1_rls_and_claims` | Dev 1 Batch 2: (1) strategy tables get `app_user` SELECT/INSERT plus column-level UPDATE on lifecycle fields only (content immutable), `(case_id, organization_id)` FKs, and same-case FKs for scenarios/comparisons; (2) fixes `case_members_create`, where an unqualified subquery made the client-profile check a tautology so a case lawyer could grant client access to any user; (3) claims, claim_sources, verification_results (database.md §9) with FORCE RLS, insert-only grants, and the deferred constraint trigger `claims_require_source`. Links to not-yet-existing Dev 2 tables (`analyses`, `ai_runs`, `document_chunks`, `legal_source_versions`) are plain UUIDs | Local draft. Needs Dev 2 + Akash sign-off. Downgrade/upgrade and base round-trip pass locally |

## Trust boundary

The application sets `app.current_user_id` as transaction-local session state.
Every app connection uses `app_user`, which cannot bypass RLS. The helper is
trusted because the backend credential must remain secret; a party holding the
credential can set a custom GUC and must be restricted to parameterized application
queries.

## RLS and append-only audit

Every case-scoped table uses RLS and case-stage/member/invitation tables are
forced. `audit_logs` is forced through RLS and `app_user` is denied UPDATE,
DELETE, and TRUNCATE. Hash columns remain reserved for Phase 8.

## Shared-schema sign-off

No migration or `DOCS/database.md` change in this packet is applied to a shared
database. Backend Dev 2 must sign off on the baseline and B9 additions before
deployment.

## Batch 2 notes (2026-11-19)

- **Not created (Dev 2-owned, no schema yet):** `documents`, `extracted_pages`,
  `document_chunks`, `evidence_items`, `case_facts`, `case_events`, `ai_runs`,
  `analyses`, `legal_research_results`, `hearing_updates`, `tasks`. RLS (database.md
  §12.1) and the `ai_runs` `case_id IS NULL AND requested_by = app.current_user_id()`
  policy are added when those tables land.
- **Ingest role:** `app_admin_ingest` exists (0001: LOGIN, NOSUPERUSER, NOBYPASSRLS)
  with no case-table grants. Legal KB tables are still created outside Alembic
  (`backend/src/legal_kb/migrations.py`) and do not exist in the local Compose DB.
  When Dev 2 moves them into a revision, that revision should `GRANT SELECT` on
  `legal_sources`, `legal_source_versions` and `legal_chunks` to `app_user`, and
  `SELECT, INSERT, UPDATE` to `app_admin_ingest`. Ingestion connects as
  `app_admin_ingest` (credential provisioned out of band), never as a superuser,
  `app_owner` or `app_user`.
- **Bootstrap:** `alembic/env.py` now allows bootstrap credentials when the version
  table is empty (after `downgrade base`), and still refuses once a revision is applied.
- **Client and `cases`:** clients still have row-level SELECT on `cases` (0008) instead
  of reading only `client_visible_case_fields` (database.md §12.2). The client API
  selects safe columns only; `tests/test_rls_bypass.py` asserts no client payload
  contains `internal_notes`. Moving the client portal fully onto
  `client_visible_case_fields` is open for joint review.
