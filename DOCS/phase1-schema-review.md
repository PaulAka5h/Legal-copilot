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
