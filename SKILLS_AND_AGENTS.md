# Skills & Agents Guide

This repo uses two kinds of helpers. **Coding helpers** (skills, subagents, rules)
help the AI that writes the code. **Product agents** are the AI components that run
inside the legal platform itself. Do not mix them up.

## Repo Map

```
.agents/skills/                 coding skills (auto-discovered by agents)
├── fastapi/                    FastAPI best practices (official)
├── next-dev-loop               Next.js dev workflow
├── next-cache-components-optimizer
├── next-cache-components-adoption
├── next-partial-prefetching-optimizer
├── next-partial-prefetching-adoption
├── ponytail/                   minimal-code ruleset
├── ponytail-review/            minimal-code code review
├── design-clean/               design system: clean
├── frontend-design/            UI design guidance
├── archify/                    architecture/diagram generator
└── archify-review/             archify diagram review checklist

.claude/
├── agents/                     coding subagents
│   planner · architect · tdd-guide · code-reviewer · security-reviewer
│   build-error-resolver · refactor-cleaner · doc-updater
└── rules/                      8 always-on rule files
    agents · coding-style · git-workflow · hooks · patterns
    performance · security · testing
backend/app/agents/             product agents (runtime AI, see section 4)
```

---

## 1. Coding Skills

| Skill | When the agent uses it |
| ----- | ---------------------- |
| `fastapi` | Any edit in `backend/`. Uses `Annotated[...]`, return types, router prefixes, `fastapi dev` and `fastapi run`, uv |
| `next-dev-loop` | Day-to-day work in `frontend/` |
| `next-cache-components-*`, `next-partial-prefetching-*` | Later, when the dashboards have real traffic to tune |
| `ponytail` | Default while writing code. Minimum code that works |
| `ponytail-review` | Reviewing a diff for over-building |
| `design-clean` | Lawyer dashboard and shared components |
| `frontend-design` | Layout and visual decisions, client dashboard simplicity |
| `archify` | Turning the Mermaid diagrams in `DOCS/` into shareable HTML diagrams |
| `archify-review` | Checking a generated diagram |

### Ponytail and legal safety

Ponytail trims boilerplate. It must never trim these, because the product depends on them:

- Authorization checks and row level security
- Input and file upload validation
- Audit log events
- Source references on AI claims
- Version history

## 2. Coding Subagents (`.claude/agents/`)

| Agent | Use it for |
| ----- | ---------- |
| `planner` | Plan a feature before coding (for example the hearing update flow) |
| `architect` | Design decisions (for example how retrieval scope and RLS fit together) |
| `tdd-guide` | Test-first work: red, green, refactor |
| `code-reviewer` | Review a diff or branch |
| `security-reviewer` | Auth, uploads, retrieval, client dashboard, prompt injection |
| `build-error-resolver` | Fix failed builds and type errors |
| `refactor-cleaner` | Dead code and cleanup |
| `doc-updater` | Keep README, AGENTS, and `DOCS/` in sync with the code |

**Claude Code:** say "Use the code-reviewer agent to review my changes."
**Other agents:** say "Read `.claude/agents/security-reviewer.md` and apply that
persona to `backend/`." The files are plain markdown prompts.

Use `security-reviewer` on every change to: authentication, case membership,
retrieval queries, file uploads, the `/client` API, and AI prompts.

## 3. Rules (`.claude/rules/`)

Always-on guardrails: security, coding style, testing, git workflow, patterns,
performance, hooks, and when to delegate to subagents. Reference them from
`CLAUDE.md` or copy them to `~/.claude/rules/`.

---

## 4. Product Agents (runtime AI inside the platform)

These run in the worker, not in your editor. The orchestrator runs them in a fixed
order. Each one takes typed input and returns typed output, and every claim carries
sources. Full spec: **`DOCS/AI_AGENTS.md`**.

| Agent | What it does |
| ----- | ------------ |
| A1 Intake | Classifies each document, language, quality, relations between documents |
| A2 Facts & Timeline | Extracts people, dates, events, and builds the timeline |
| A3 Evidence | Organizes evidence and what it supports or weakens |
| A4 Gaps & Contradictions | Finds conflicts and missing documents |
| A5 Legal Research | Finds Bangladesh provisions and judgments in the verified knowledge base |
| A6 Strategy Generator | Proposes several legal strategies |
| A7 Opposing-Side Scenarios | Builds the tree: our approach, their argument, our response, remaining risk |
| A8 Evaluator & Comparer | Rates each strategy on a rubric and compares them |
| A9 Verifier | Independently checks claims and citations |
| A10 Hearing Reassessment | Updates the analysis after a hearing: maintain, review, or change |
| A11 Client Update Drafter | Drafts plain-language updates from shareable fields only |

### Run order

```
Case analysis:  A1 > A2 > A3 > A4 > A5 > A9 > draft for lawyer review
Strategy:       A6 > A7 > A8 > A9 > lawyer approval
Reassessment:   A10 > re-run affected A6 to A8 > A9 > maintain / review / change
```

### Product agent rules

- Every claim has a type (document says, lawyer entered, inference, assumption,
  prediction), sources, and a confidence label. No source, no claim.
- A5 cites only sources that exist in the knowledge base. If nothing is found, it
  says so. It never answers from memory.
- A9 sees only the claims and their sources, never the generator's reasoning.
- A8 gives qualitative ratings. The overall rating cannot exceed the weakest
  critical dimension. No percentages.
- A7 labels branches as scenarios, never certainties.
- All model calls go through `backend/app/agents/gateway.py`. Only providers listed
  in `DOCS/providers.md` are allowed. Default is the mock provider.
- Prompts live in versioned files under `backend/app/agents/prompts/`.
- Document text goes into prompts as delimited data, with a rule to ignore any
  instructions inside it.

---

## Quick Reference

| Task | Say this |
| ---- | -------- |
| Plan a phase | "Use the planner agent to plan Phase 1 from DOCS/PRD.md" |
| Build a page | "Build the case workspace page with Next.js, following design-clean" |
| Add an API | "Add the document upload endpoint using the fastapi skill and DOCS/TRD.md" |
| Write tests first | "Use the tdd-guide agent to write the case isolation tests" |
| Review code | "Use the code-reviewer agent on my changes, with ponytail-review" |
| Security pass | "Run the security-reviewer agent over retrieval and the client API" |
| Fix a build | "Use the build-error-resolver agent to fix the failing frontend build" |
| Update docs | "Use the doc-updater agent to update DOCS/status.md" |
| Draw a diagram | "Use archify to turn the strategy flow in DOCS/SystemArchitecture.md into an HTML diagram" |

## Updating Skills

```bash
npx skills update                    # update all installed skills
npx skills add vercel/next.js --yes  # re-pin Next.js skills to a new version
npx skills find <query>              # discover more skills
```
