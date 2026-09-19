# FRONTEND_F1C1 — CS408 Knowledge Workspace Contract Gap

## Result

**RESOLVED (2026-09-17)** — closure evidence in
`FRONTEND_BC3_EXAM_KNOWLEDGE_OPENAPI_CONTRACT_ACCEPTANCE_REPORT.md`.

```text
FRONTEND_BACKEND_CONTRACT_GAP = BLOCKED   → CLOSED
KNOWLEDGE_CONTRACT_TYPED      = FAIL      → PASS
```

Both operations now carry concrete 200 schemas and `frontend/src/types/api.ts` was
regenerated through the established generator:

```text
GET  /exam/11408/subjects/{subject_key}/study-plan
     200 → components["schemas"]["ExamStudyPlanResponse"]

PATCH /exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{item_code}
     request: ExamStudyPlanKnowledgeItemUpdate   (unchanged)
     200   → components["schemas"]["ExamKnowledgeItemUpdateResponse"]
```

F1C1 may now resume with generated types and no handwritten DTO. Notes for the resumption:

* the hierarchy is `chapters[] → children[] (section) → children[] (leaf node)`, and the
  leaf model is **recursive** — depth is whatever the seed map has;
* `status` is the closed union `"not_started" | "learning" | "mastered" | "review_due"`;
* `optional` (a real seed flag, present on 4 data_structure nodes) and the `progress`
  block are genuinely optional keys — absent means absent, not `null`;
* `stored_status` / `user_confirmed_status` are **open strings** because legacy values
  (including Chinese) are passed through verbatim; only the `status` field is normalized;
* `settings.weekly_days` and friends are `number | null`;
* the PATCH response is the 5-key confirmation envelope (`success`, code, title,
  `status` display value, `stored_status` raw value) — they differ when a mastered point
  is already due for review;
* the payload carries **no** mastery score, prediction, or recommendation field, so the
  UI must not infer any.

---

## Original gap report (kept for the record)

Audit date: 2026-09-17  
Scope: generated OpenAPI transport types only (`frontend/src/types/api.ts`).  
No backend files were modified. No handwritten transport DTOs or casts were introduced.

## KNOWLEDGE_FRONTEND_CONTRACT_MATRIX

| Endpoint | Generated request type | Generated success type | Unknown? | Fields actually available to the frontend | Error semantics generated |
| --- | --- | --- | --- | --- | --- |
| `GET /exam/11408/subjects/{subject_key}/study-plan` | Path: `{ subject_key: string }`; optional query: `{ username?: string }` | `unknown` | **Yes** | None. The response cannot be safely read to obtain the hierarchy, point code/title/path, status, review state, or practice mapping. | Only typed `422: HTTPValidationError`; no typed `401`/`403`/`404` response schemas are emitted. |
| `PATCH /exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{item_code}` | Path: `{ subject_key: string; item_code: string }`; body: `ExamStudyPlanKnowledgeItemUpdate` | `unknown` | **Yes** | Request fields: `username`, `subject_key`, `course_id`, `knowledge_point_code`, `knowledge_point_title`, `status`. No typed success fields are available for cache reconciliation. | Only typed `422: HTTPValidationError`; no typed `401`/`403`/`404` response schemas are emitted. |

## Hard type gate

The knowledge workspace cannot render without the study-plan response. Its generated 200 type is `unknown` at `frontend/src/types/api.ts` under operation `get_exam_subject_study_plan_exam_11408_subjects__subject_key__study_plan_get`.

The status mutation also has an `unknown` 200 body at operation `update_exam_study_plan_knowledge_item_exam_11408_subjects__subject_key__study_plan_knowledge_items__item_code__patch`.

Therefore:

```text
KNOWLEDGE_CONTRACT_TYPED = FAIL
HAND_WRITTEN_TRANSPORT_DTOS = 0
BACKEND_FILES_CHANGED = 0
FRONTEND_F1C1_COMPLETE = NO
```

## Required BC3 closure

Regenerate the OpenAPI contract only after the backend declares typed 200 response models for both operations. The GET response must expose the real hierarchy required by the UI (modules/chapters/real optional sections/leaf knowledge points), stable point codes, real titles, status, and only any factual detail fields actually returned. The PATCH response must have a declared typed success model and documented confirmation semantics for status writes.

The error responses used by this frontend should also be represented/documented sufficiently to distinguish authentication, entitlement, missing source, and validation cases without inventing client semantics.

After BC3, run `npm run api:generate`, re-audit the generated `paths`/`operations`, and only then resume F1C1 implementation.

### Status of each requirement

1. Declare typed 200 models for both operations. — **DONE**
2. GET exposes the real hierarchy, point codes, titles, status, and only factual fields. — **DONE**
3. PATCH has a declared typed success model with confirmation semantics. — **DONE**
4. Error contract unchanged (401 / 403 / 404 / 400 / 422 all preserved, untyped). — **DONE**
5. Regenerate `frontend/src/types/api.ts` with the established generator. — **DONE**
6. Re-audit the generated `paths`/`operations` for `unknown`. — **DONE** (both 200s concrete)
7. Resume F1C1 implementation. — **UNBLOCKED**

Closure detail (runtime audit, models, equivalence proof, gates) lives in
`FRONTEND_BC3_EXAM_KNOWLEDGE_OPENAPI_CONTRACT_ACCEPTANCE_REPORT.md`.

## Deliberately not performed

- No route, component, query, mutation, CSS, test, E2E, screenshot, or backend change.
- No `as SomeType`, `as unknown as SomeType`, raw fetch, or manually authored API response type.
- No status write against a contract whose success response is unknown.
