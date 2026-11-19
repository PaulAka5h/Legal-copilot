# Approved Providers

This file is the single list of external services that may receive project data. The LLM gateway reads the approved list from configuration (`LLM_APPROVED_PROVIDERS`) and refuses to send case content to anything not on it.

Last updated: 2026-11-16

## Current state

| Provider | Purpose | Data allowed | Status |
|---|---|---|---|
| mock | Tests and local development | Synthetic only | Approved for all non-production use |
| (none yet) | LLM | None | No external provider has been reviewed or approved |
| self-hosted `intfloat/multilingual-e5-large` | Embeddings | Runs on our own hardware; no external data transfer | In use for the legal knowledge base (public statute text only) |
| (none yet) | OCR | None | Local Tesseract is the default; no cloud OCR approved |

Until a provider passes the review below, the platform runs with the mock provider or with synthetic data only. Real client documents must not be uploaded to any environment that can reach an unapproved provider.

## Data allowed per provider

Use one of these values in the table above:

| Value | Meaning |
|---|---|
| Synthetic only | Fake data created for tests and demos |
| Consented demo data | Real documents from a person who gave written consent for demo use |
| Client case data | Real client material, after a full review and counsel sign-off |

## Review checklist

Complete one copy of this checklist per provider and per product tier. Save the answers in section "Review records" below. Do not approve a provider with open items.

| # | Question | Answer | Evidence (link or document) |
|---|---|---|---|
| 1 | Where is data processed and stored (country and region)? | | |
| 2 | Is submitted data retained? For how long? Can retention be turned off or minimized? | | |
| 3 | Is submitted data used to train models? Is that off by contract or by account setting? | | |
| 4 | Who at the provider can access submitted data, and under what controls? | | |
| 5 | Is there a data processing agreement? | | |
| 6 | What are the breach notification terms and timelines? | | |
| 7 | Does the provider offer encryption in transit and at rest? | | |
| 8 | Can we get deletion of submitted data on request? | | |
| 9 | Does the provider log prompts and outputs? Can logging be disabled? | | |
| 10 | Which sub-processors does the provider use? | | |
| 11 | Do the terms fit a lawyer's professional confidentiality duties? (needs counsel) | | |
| 12 | Does any Bangladeshi data protection or transfer rule apply to this transfer? (needs counsel) | | |
| 13 | Is the model's Bangla reading and writing good enough on our evaluation set? | | |
| 14 | Are structured outputs reliable enough for our schemas? | | |
| 15 | Cost per case analysis and per strategy run within budget? | | |

## Approval rules

1. A provider is approved by name, product, and region. A change in any of these needs a new review.
2. Approval states which data class is allowed (synthetic, consented demo, client case data).
3. Approval is recorded below with the date, the reviewer, and the counsel sign-off where required.
4. The approved list in the deployment configuration must match this file. A mismatch is a defect.
5. Review again when the provider changes its terms, when we change region, or at least once a year.
6. Client data is never used to train or fine-tune any model unless a separate written authorization, a lawful basis, and safeguards are recorded here.

## Minimum content rule

Even for an approved provider, send only what the task needs: the retrieved passages and the question, not whole case files. Strip names and contact details when they are not needed for the task. The gateway records which passages were sent in `ai_runs` as IDs and hashes, not as text.

## Model selection record

Model choice is made by testing, not by reputation. Record each comparison here.

| Date | Candidate (provider, model) | Bangla reading | English reading | Structured output reliability | Citation accuracy | Cost per run | Latency | Notes |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

Run the evaluation set from `Skills and agents.md` section 7 for every candidate and on every model change.

## Embedding and OCR choices

| Component | Candidates to test | Chosen | Reason |
|---|---|---|---|
| Embeddings | A multilingual model with Bangla support, such as BGE-M3 or multilingual-e5 | `intfloat/multilingual-e5-large`, self-hosted (2026-11-20, master prompt) | Runs locally via sentence-transformers; weights downloaded once from Hugging Face, no project data leaves the server. Retrieval quality on a labelled bn/en set is still to be measured (Step G eval) |
| OCR | Tesseract with Bengali and English data; a cloud OCR only if local accuracy is not good enough | Not chosen | Test on real scanned papers; a cloud OCR needs a full review |

## Review records

No reviews completed yet.

Template for each record:

```
Provider and product:
Region:
Data class approved:
Review date:
Reviewer:
Counsel sign-off (name, date) or "not required for this data class":
Checklist answers: (link to the filled table)
Conditions: (for example "retention disabled", "zero data retention enabled")
Next review due:
```

## Environment settings

```
LLM_PROVIDER=mock
LLM_APPROVED_PROVIDERS=mock
```

Change these only after a review record exists in this file.
