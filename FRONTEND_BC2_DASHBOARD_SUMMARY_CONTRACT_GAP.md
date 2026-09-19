# FRONTEND_BC2 Dashboard Summary Contract Gap

## Status

**RESOLVED (2026-09-17)** — closure evidence in
`FRONTEND_BC2_DASHBOARD_SUMMARY_CONTRACT_ACCEPTANCE_REPORT.md`.

```text
FRONTEND_BACKEND_CONTRACT_GAP = dashboard-summary 200 response is unknown   → CLOSED
```

The endpoint now declares `response_model=ExamSubjectDashboardSummaryResponse`, the
OpenAPI 200 schema is a concrete `$ref`, `frontend/src/types/api.ts` was regenerated and
types it as `components["schemas"]["ExamSubjectDashboardSummaryResponse"]`, and the
runtime JSON was verified byte-identical to the pre-change response across all four
modules. F1B2 may now consume the summary with generated types and no hand-written DTO.

---

## Original gap report (kept for the record)

**BLOCKED — F1B2 implementation paused.**

```text
FRONTEND_BACKEND_CONTRACT_GAP = dashboard-summary 200 response is unknown
```

## Evidence

The generated frontend transport contract maps:

```text
GET /exam/11408/subjects/{subject_key}/dashboard-summary
200 application/json → unknown
```

The safe temporary VQA backend returns real fields such as `subject_key`, `subject_name`,
`overview`, `today_plan`, and `materials`; however, those fields are not represented by a
generated OpenAPI schema.

## Decision

F1B2 must not:

- handwrite a dashboard-summary DTO or type assertion;
- parse or display fields from the `unknown` payload;
- issue four summary requests solely to render loading/error states;
- modify backend, database, migrations, API schemas, or generated API types.

The CS408 workspace visual and information architecture is therefore not frozen or implemented
until BC2 supplies a generated, typed 200 response contract for dashboard-summary.

## Required BC2 closure

1. Define the dashboard-summary 200 response schema at the contract source. — **DONE**
2. Regenerate `frontend/src/types/api.ts` through the established API-generation workflow. — **DONE**
3. Verify the generated operation response has a concrete schema instead of `unknown`. — **DONE**
4. Resume F1B2 with typed parallel module-summary queries, local failure isolation, factual
   status mappings, and no inferred progress or recommendation fields. — **UNBLOCKED**

Closure detail (models, field-level audit, byte-equivalence proof, gates) lives in
`FRONTEND_BC2_DASHBOARD_SUMMARY_CONTRACT_ACCEPTANCE_REPORT.md`.

Note for F1B2 resumption: the generated type is narrow on purpose. `materials` and
`overview` are plain integer counters, `today_plan[].computed_status` is the closed enum
`"not_started" | "in_progress" | "completed"`, and `quota.material_upload.remaining` is
typed `number` (int or float — the two shapes are both real). The payload carries **no**
progress estimate, mastery probability, or recommendation field, so the UI must not infer
any.
