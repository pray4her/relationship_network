# Domain Docs

This repository uses a single shared domain context for the commercial global-talent matching product.

## Before exploring or changing the product

- Read `CONTEXT.md` at the repository root when it exists.
- Read relevant architecture decisions under `docs/adr/` when they exist.
- If either location does not yet exist, proceed silently; create or update domain documentation only when the task or a domain-modeling workflow requires it.

## Layout

```text
/
├── CONTEXT.md
├── docs/
│   ├── adr/
│   └── agents/
├── backend/
├── frontend/
└── worker/
```

## Vocabulary

Use the domain terms defined in `CONTEXT.md` consistently in issues, tests, APIs, UI copy, reports, and architectural proposals. Important initial terms include tenant, tenant owner, company, job, requirement version, match run, local talent, tenant talent, job candidate, report version, plan version, subscription, entitlement, usage ledger, contact unlock, and data version.

If a new concept has no agreed term, treat that as a domain-modeling gap rather than silently inventing competing synonyms.

## Architecture decisions

Before proposing or implementing a change, check relevant ADRs. If a proposal conflicts with an accepted ADR, state the conflict explicitly and decide whether the ADR should be superseded instead of silently bypassing it.
