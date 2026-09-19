# FRONTEND_F1C2B Acceptance Report

```text
FRONTEND_F1C2B_COMPLETE

PRACTICE_ROUTE = /exam/cs408/practice
CHAPTER_SELECTOR = module -> outline chapter selector -> chapter URL
CHAPTER_URL_IDENTITY = module + chapter_code

ANSWER_DESK_PATTERN = question navigator + focused single-question answer desk

CHOICE_FLOW = select option -> create attempt -> save/submit -> server result only
BIG_FLOW = free-text answer -> submit -> neutral self-review state

ATTEMPT_CREATE = generated OpenAPI client POST only
ANSWER_SAVE = generated OpenAPI client POST only; answers keyed by question_id
SUBMIT = generated OpenAPI client POST only; choice status is rendered from backend result
ATTEMPT_RELOAD = saved_answers reconciled against returned question.id, never array index

FRONTEND_GRADING_COMPARISON = NO
PRE_SUBMIT_ANSWER_LEAK = NO
PRE_SUBMIT_EXPLANATION_LEAK = NO
EMPTY_ANALYSIS_BEHAVIOR = no analysis surface in F1C2B
FRONTEND_WRONG_RECORD_WRITE = NO
KNOWLEDGE_STATUS_WRITE = NO
QUESTION_INDEX_AS_IDENTITY = NO

SCREENSHOTS = %TEMP%/zhixue-f1c2b-vqa/screenshots/
  desktop-practice-chapter-select.png
  desktop-practice-choice-unanswered.png
  desktop-practice-choice-submitted.png
  desktop-practice-big.png
  mobile-practice-choice.png
  mobile-practice-submitted.png

DESKTOP_VISUAL_QA = PASS
TABLET_VISUAL_QA = responsive layout covered by CSS breakpoint review; no standalone tablet capture requested
MOBILE_VISUAL_QA = PASS
AXE_VIOLATIONS = 0 (scoped to .cs408-practice)
CONSOLE_ERRORS = 0

TYPECHECK = PASS
LINT = PASS
UNIT_TESTS = PASS (12 files, 30 tests)
BUILD = PASS
E2E = PASS (3 Playwright scenarios)

BACKEND_FILES_CHANGED = NONE
FRONTEND_F1C2B_COMPLETE = YES
FRONTEND_F1C2C_READY = NOT_STARTED_BY_DESIGN

BLOCKERS = NONE
```

## F1C2B-VR1 Technical Exam Desk

VR1 replaces the thin form treatment with a Technical Exam Desk: the current module is the primary title, chapter context is secondary, and the mode stays a restrained marker. Module and chapter selection now use numbered ledger rows rather than card-like controls. The answer area uses indexed question identity, structural paper rules, exam option rows, inline teacher-style judgement, and separated navigation/submission controls.

Functional behavior, generated API types, route semantics, attempt lifecycle, question identity, grading, wrong-record behavior, and knowledge-status behavior are unchanged. The visual VQA fixtures now capture desktop module selection, chapter selection, unselected/selected/submitted choice, big question, and mobile module/choice/submitted states. Scoped Axe remains zero; console errors remain zero.
