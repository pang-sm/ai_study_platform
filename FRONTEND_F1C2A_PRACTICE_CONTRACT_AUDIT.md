# FRONTEND_F1C2A — CS408 Chapter Practice Contract Audit

Date: 2026-09-17. Scope: read-only audit; no backend, schema, generated-type, or production-database changes.

## Verdict

`F1C2A_RESULT = BLOCKED_BY_OPENAPI_CONTRACT`.

The runtime chapter-practice surface exists, is authenticated, and filters chapter questions correctly. However every required chapter-practice success response is `unknown` in `frontend/src/types/api.ts`, while all write bodies are `{ [key: string]: unknown }`. F1C2B cannot use handwritten transport DTOs or casts, so BC5 must close this contract first.

## Practice contract matrix

| Capability | Endpoint | Method | Generated request / success response | Typed | User scoped | Source / side effect | F1C2 status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Chapter discovery | `/exam/11408/{subject_key}/chapter-practice/outline` | GET | none / `unknown` | No | No | `source_type == "chapter"` count by knowledge-point id | BC5 |
| Chapter question list | `/exam/11408/{subject_key}/chapter-practice/questions` | GET | query typed; 200 `unknown` | No | Yes (`practiced`) | active chapter rows only | BC5 |
| Create attempt | `/exam/11408/{subject_key}/chapter-practice/attempts` | POST | record unknown / 200 `unknown` | No | Yes | creates `ExamPracticeAttempt` | BC5 |
| Resume attempt | `/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}` | GET | 200 `unknown` | No | Yes | question snapshot + saved answers | BC5 |
| Save answers | `/.../attempts/{attempt_id}/answers` | POST | record unknown / 200 `unknown` | No | Yes | `answers_json` | BC5 |
| Submit / deterministic grade | `/.../attempts/{attempt_id}/submit` | POST | record unknown / 200 `unknown` | No | Yes | result, done records, wrong records, practice-core mirror | BC5 |
| Static explanation | question-list / submitted-attempt payload | GET | `unknown` | No | N/A | `analysis` can be empty | BC5 |
| Wrong record | submit side effect; `/exam/11408/{subject_key}/wrong-questions` | POST/GET | submit unknown | No | Yes | `ExamWrongQuestion`, then unified wrong-answer mirror | BC5 |
| Question explain | `/exam/11408/{subject_key}/question-analysis` | POST | record unknown / 200 `unknown` | No | Yes | `question.explain` via Exam AI orchestrator; no persistence stated | BC5 |
| Answer grade | past-paper big-answer path only | internal | no F1C2 chapter requirement | N/A | Yes | `answer.grade` is not needed for current chapter choice questions | Not needed |

## Identity and source facts

- Canonical module IDs are consumed directly: `data_structure`, `computer_organization`, `operating_system`, `computer_network`. Legacy `*_11408` is internal course scope and must not enter UI.
- Canonical question identity is `ExamQuestionBank.id` (integer). Attempts persist these IDs in `question_ids_json`; wrong records reference `question_bank_id`.
- A canonical **practice chapter** identity is not exposed. The list endpoint filters `knowledge_point_id`, optionally `knowledge_point_path`, rather than a declared `chapter_code`/`chapter_id`. Chinese titles, tree array index, and frontend hashes are invalid. This is an additional Type B contract gap for F1C2 deep links.
- `db_query_chapter_questions()` filters `subject_key`, `is_active`, and `source_type == "chapter"`. The chapter list cannot return past-paper rows through that query.

## Runtime and data evidence

The TEMP authenticated backend (port 8018, explicit TEMP database) returned 200 for data-structure and operating-system outline/list endpoints but zero rows because that disposable database was not seeded with the chapter bank. This is reported as environment data absence, not a product claim.

`backend/app.db` was queried only with SQLite URI `mode=ro`; it was not started through TestClient and was not modified. Active real chapter-bank distribution:

| Module | choice | big | chapter total |
| --- | ---: | ---: | ---: |
| data_structure | 808 | 202 | 1,010 |
| computer_organization | 960 | 240 | 1,200 |
| operating_system | 1,042 | 78 | 1,120 |
| computer_network | 702 | 173 | 875 |

Only `choice` and `big` occur in active chapter rows. Choice grading is server-side case-insensitive `user_answer.upper() == standard_answer.upper()` with provider calls = 0. Big questions return `correct: null`, `judge: "self_review"`, and static reference material; no current chapter path calls `answer.grade`.

## Persistence and side effects

- An attempt is backend-owned (`ExamPracticeAttempt`) and is created before answers/submit. It stores a question-id set, saved answers, status, and submit result.
- Submit is one-time: only `in_progress` attempts can submit. It writes `ExamQuestionDoneRecord` for every question and mirrors into the unified Practice Core after the primary DB commit.
- Incorrect choice answers create or update one active `ExamWrongQuestion` for the user/question; repeats update review count rather than duplicate active rows. The unified adapter test demonstrates a later correct retry resolves the matching wrong state. The legacy endpoint itself does not visibly resolve an active `ExamWrongQuestion` on a correct submit, so F1C2 must follow the typed contract once supplied rather than infer this behavior from adapters.
- Practice mirror tests verify `service_namespace = exam_prep`, canonical event subject `cs_408`, module context, and no automatic `UserKnowledgeProgress` write. Therefore correct answer does **not** auto-mark knowledge mastered.
- Session capability is **PARTIAL**: attempt ID, question-id snapshot, saved answers, and submitted summary support refresh/resume; retrieval uses SQL `IN (...)` without restoring the stored ID order. No server session-size, pagination, seed, or unseen-first option exists.
- `practiced` is available per chapter-list question from done records, but no server-side unseen-first ordering/exclusion exists.

## Rendering and AI facts

- Serializer returns numeric id, module/subject, `source_type`, `question_type`, stem, options JSON, standard answer, analysis, knowledge-point id/name/path, and year/number where present; exact nullability cannot be consumed safely until BC5 types it.
- Stems/options/analysis are stored as text/JSON strings. No approved typed rich-text/image renderer contract was found for chapter practice. Do not use raw HTML or filesystem paths.
- `/exam/11408/{subject_key}/question-analysis` calls `execute_exam_ai(..., "question.explain", ...)` with canonical CS408 context, not a direct provider. Its request and 200 response are currently unknown. Source indicates it does not write grade, knowledge status, or wrong record.

## BC5 requirements

1. Add Pydantic request/response models and OpenAPI annotations for all six chapter-practice endpoints above; regenerate `frontend/src/types/api.ts`.
2. Type question payload, including all nullable fields and safe rendering/resource representation.
3. Define a canonical URL-safe chapter identity shared by Knowledge Workspace and chapter-practice filtering, or explicitly type a supported `knowledge_point_id/path` deep-link contract.
4. Type deterministic submit results, attempt lifecycle/replay behavior, wrong-record result state, and correct-retry resolution semantics.
5. Type `question.explain` request/response and its 403/429/502 error semantics.

No F1C2 UI, handwritten DTO, or unknown cast was created.
