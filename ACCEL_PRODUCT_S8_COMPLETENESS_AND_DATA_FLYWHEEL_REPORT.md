# ACCEL_PRODUCT_S8 — CS408 PRODUCT COMPLETENESS + SCIENTIFIC DATA COLLECTION V1

```text
ACCEL_PRODUCT_S8_COMPLETE

CS408_CORE_LOOP        = COMPLETE — 8/8 surfaces, ONE BLOCKING DEFECT FOUND AND FIXED
                         (computer_network had 0 of 28 leaves and 0 of 920 questions
                          reachable from the Knowledge workspace)
CROSS_WORKSPACE_LINKS  = 6/6 established or verified; 3 links deliberately NOT built
                         where the contract carries no canonical identity

STUDENT_TWIN           = USER_VISIBLE_PREVIEW   (authority unchanged)
EVIDENCE_RELIABILITY   = SHADOW_NOT_USER_VISIBLE / collecting
CS408_NATIVE_KT        = DATA_COLLECTION / NOT_TRAINED (gate FAIL)
TUTOR_POLICY           = SHADOW / DATA_COLLECTION (no action ontology in the running tutor)

LEGACY_LEARNER_STATE   = RESEARCH_ONLY / ontology mismatch
MISCONCEPTION_V2       = RESEARCH_ONLY / ontology mismatch

CONCEPT_COVERAGE_BEFORE = 5094 / 9333 (54.58%)   [active: 3330 / 4375 = 76.11%]
CONCEPT_COVERAGE_AFTER  = 5714 / 9333 (61.22%)   [active: 3950 / 4375 = 90.29%]
                          +620 resolved, 0 rule disagreements, 7 collisions refused

DATA_COLLECTION_ACTIVE = YES
DATASET_TRAINING_READY = NO  (pre-registered gate FAIL, re-measured)

SCIENTIFIC_ADMIN_DIAGNOSTICS       = GET /science/status  (ADMIN_ONLY, 401/403 enforced)
USER_VISIBLE_SCIENTIFIC_COMPONENTS = 1   (student_twin)
SHADOW_COMPONENTS                  = 2   (evidence_reliability, tutor_policy)
                                         + 1 product-native (cs408_native_kt)
RESEARCH_ONLY_COMPONENTS           = 5   (learner_state, misconception_v2, memory, irt,
                                          concept_verifier)

PLAN_UPGRADE_LINK      = NOT_ADDED — no membership/upgrade route exists in the app
ACCESSIBILITY_DEBT     = RESOLVED — past-paper small danger text 3.83:1 → 6.59:1

FULL_BACKEND_TESTS     = 1516 passed / 2 skipped / 0 failed
FRONTEND_TESTS         = 94 passed (25 files); typecheck + lint + build PASS

REAL_APP_DB_MUTATED    = NO
```

---

## 0. WHAT SHIPPED

Three commits, one push:

| Commit | Content |
|---|---|
| `569dbe87` | **S7** — product-native model pipeline + evidence_reliability forensic closure |
| `01814ed7` | **Frontend S3** — CS408 scientific state workspace |
| `19f132a7` | **S8** — this sprint |

43 files, +5963 / −737. No `.env`, no database file, no build artifact, no scratch
directory is in the payload — every file was added by explicit path, and the working tree's
scratch directories (`.bc7tmp/`, `.bc8tmp/`, `.bc8r1tmp/`, `.f1c5qa/`, `.f1c6tmp/`,
`frontend/.f1c5qa/`, `frontend/.f1c6tmp/`, `test-results/`, `backend/file`) were left
untracked and uncommitted.

---

## 1. THE FINDING THAT MATTERS MOST: `computer_network` WAS UNREACHABLE

PART 1 asked whether the CS408 learner journey is coherent between its surfaces. Auditing
the links found that one entire module's practice path was **not merely awkward — it was
empty**.

The knowledge map publishes canonical leaf codes (`3.6`). The question bank for
`computer_network` stores its identity column as `"3.6 局域网"` — the canonical code
concatenated with its own title. The chapter-practice matcher compared those two strings
for equality:

```text
"_chapter_question_matches_kp('3.6 局域网', '3.6')"  ->  False
```

Measured against the shipped bank, before the fix:

| module | canonical leaves | leaves reachable | questions reachable |
|---|---|---|---|
| data_structure | 32 | 31 | 1010 / 1010 |
| computer_organization | 28 | 28 | 1200 / 1265 |
| operating_system | 18 | 18 | 1120 / 1180 |
| **computer_network** | **28** | **0** | **0 / 920** |

A learner could open the computer_network knowledge tree, click any of its 28 leaves, and
be served nothing. After the fix: **21 leaves, 620 of 920 questions** — the remainder are
the chapter-4 collisions the resolver refuses (see §2) and the 45 past-paper rows that
carry no concept at all.

---

## 2. CONCEPT COVERAGE — THE NORMALIZATION, AND THE COLLISION IT REFUSES

### 2.1 The rule is exact equality against a string the seed itself publishes

`cs408-concept-normalization-v1` recognises three spellings, and nothing else:

| rule | what it matches |
|---|---|
| `canonical_leaf_code` | the stored id **equals** a canonical leaf code (S6's rule, unchanged) |
| `canonical_leaf_title_echo` | the stored id **equals** the leaf's own `title` field, verbatim |
| `source_ref_chapter_leaf` | `source_ref` is the fixed grammar `chapter:<n>:<code>` where `<code>` is a canonical leaf of chapter `<n>` **and** the stored code is **strictly deeper** than it |

No model. No fuzzy match. No stemming, truncation or scoring. `exam_question_bank` is a
preservation-critical content table and **not one row was modified** — the resolver is
read-time, so every row past and future resolves under one versioned rule.

### 2.2 The refusal that makes it safe

`computer_network`'s chapter 4 was ingested from a source whose own section numbering runs
`4.1`…`4.40`, in the **same numeric slots** as the canonical leaves, meaning something else:

```text
stored '4.2 路由与转发'      canonical 4.2 = '4.2 IPv4'
stored '4.3 虚电路服务'      canonical 4.3 = '4.3 IPv6'
stored '4.6 拥塞控制'        canonical 4.6 = '4.6 移动IP'
```

All seven such collisions (**35 rows**) are refused, by two independent mechanisms: the
title rule rejects them because the titles differ, and the source-ref rule rejects them
because it demands strict descent. They are **listed in the report** rather than dropped —
this is where a laxer rule would have produced 35 fabricated concept links.

### 2.3 Exact before / after

```text
ALL 9333 QUESTIONS
  before   concept 5094 (54.58%)   chapter 4003   module_only  236
  after    concept 5714 (61.22%)   chapter 3383   module_only  236
  recovered 620 = 205 (title echo) + 415 (source-ref descendant)

ACTIVE 4375 QUESTIONS
  before   concept 3330 (76.11%)
  after    concept 3950 (90.29%)

CORROBORATION (the proof it is a resolution and not a guess)
  rules_disagreed                          = 0
  chapter segments agreed / compared       = 620 / 620
```

`chapter segments agreed` is the independent check: the chapter read from `source_ref` and
the chapter read from the stored id's own leading segment are **two different columns**, and
a row where they disagreed would mean the rule resolved across chapter lines.

Reproducible against any read-only snapshot:

```bash
./backend/.venv/Scripts/python.exe -X utf8 scripts/audit_concept_coverage.py --db <snapshot.db>
```

---

## 3. CROSS-WORKSPACE LINKS (PART 2)

Established or verified, each built only from a canonical identity the source carries:

| link | target | identity used |
|---|---|---|
| Knowledge → Practice | `/exam/cs408/practice?module&chapter` | `chapter.code` (already existed; now works for every module) |
| **Practice result → Wrong Answers** | `/exam/cs408/wrong?module&status=active` | appears only when the session actually produced wrong answers |
| Wrong Answer → original context | `/exam/cs408/past-papers?module&year&question` | `year` + `question_number`; now opens **at that question** |
| Study Plan → action target | `/exam/cs408/knowledge` or `/practice` | `action_target` + `subject_key` (already existed) |
| **Learning Record → source** | `/exam/cs408/practice?attempt=` / `/past-papers?attempt=` | `source.type` + `source.id` |
| Learning State → Records | `/exam/cs408/records?module` | `module` (already existed) |

### Deliberately NOT built

- **Wrong Answer (chapter practice) → its chapter.** The record carries
  `knowledge_point_id` and `knowledge_point_path` — and **neither is a chapter code** the
  practice route accepts. Deriving one from the path's leading title would be guessing a URL
  from a title, so the link stops at the module.
- **Study Plan → knowledge node.** `ExamStudyPlanTaskItem` carries `knowledge_point_name`
  (a display string) and **no** code. A node-level link would have to be guessed from a
  title, so none is built. The test pins the absence so a contract change is what unlocks
  it.
- **Plan locked state → upgrade.** See §5.

Two latent traps were also closed: a `?attempt=` without its parent selector now renders as
a complete entry point (previously the desk rendered beside a chapter selector, or nothing
at all for past papers, which required a `year` the attempt itself already carries).

---

## 4. STUDENT TWIN — END-TO-END, AUTHORITY UNCHANGED

`STUDENT_TWIN = USER_VISIBLE_PREVIEW`, and this sprint **did not increase its authority**.

The production flow is verified end to end against real facts: a real chapter-practice
submission produces a canonical `question_answered` fact, the fact reaches the StudentTwin
evidence window, and `GET /exam/prep/scientific/student-twin` returns the experiment state
view. Writes nothing: `controls_product_decision = false`, `writes_learner_fact = false`.
The frontend requests the preview **only** when the capabilities contract reports
`component === "student_twin"` with `user_visible === true`.

---

## 5. THE LOCKED PLAN HAS NO UPGRADE LINK, AND THAT IS THE ANSWER (PART 13)

F1C5 recorded that the locked Study Plan state has no route to membership/upgrade. The
sprint's condition was "if a real membership route now exists".

**It does not.** The app's entire route table is `home` + `exam/*`. `GET
/membership/entitlements` returns a real `required_plan`, but there is no page to act on it,
and the brief forbids inventing a payment flow.

So no navigation target was added. What changed is the copy: it now states the requirement
(`学习计划需要开通对应的备考方案，当前账号尚未开通。`) instead of promising `升级…后即可使用`,
which described an action the app cannot perform. A test asserts the locked state renders
**no link at all**, so the day a route exists the test is what has to change.

```text
PLAN_UPGRADE_LINK = NOT_ADDED — no real membership route exists
```

---

## 6. ACCESSIBILITY DEBT (PART 14)

F1C5 recorded `.past-paper__error` using `--color-danger` at `--text-metadata` size. The
exam shell renders on `--color-lab-paper` (`#e8e5da`), and the measured ratio there is:

```text
--color-danger     #dc2626  on #e8e5da = 3.83:1   FAILS WCAG AA (4.5:1 floor)
--color-danger-ink #991b1b  on #e8e5da = 6.59:1   PASSES
```

A text-safe sibling token was added, mirroring the existing `--color-success-ink`
precedent, and **the base token was not touched** — so no frozen fill, dot or inset accent
moved. The same defect existed in `.practice-error` (identical token, identical size) and
was fixed with the same token.

```text
ACCESSIBILITY_DEBT = RESOLVED
```

---

## 7. MODEL STATUS REGISTRY (PART 9)

Four frozen categories, and the thirteen placed in them:

```text
USER_VISIBLE                 1   student_twin
SHADOW_COLLECTING_DATA       2   evidence_reliability, tutor_policy
RESEARCH_ONLY                5   learner_state, misconception_v2, memory, irt, concept_verifier
RETIRED_FROM_PRODUCT_ROADMAP 5   difficulty_prior, planner, tutor_guard, execution_router,
                                 domestic_registry
```

`cs408_native_kt` — the model the product will train on its **own** concept space — is
reported in a separate `product_native_capabilities` block, deliberately **not** a
fourteenth member of the SSOT §36 thirteen. Its `artifact` is `null` and its blocker is
`DATA_READINESS_GATE`, because no model exists.

A real defect was found and fixed while doing this: the S5 readiness dimensions
(`runtime_available`, `scientifically_compatible`, `product_input_ready`) were computed and
emitted by `summary()` but **never declared on the response model**, so FastAPI silently
dropped them and no HTTP client had ever seen them.

---

## 8. ADMIN-ONLY SCIENTIFIC DIAGNOSTICS (PARTS 10/11)

```text
GET /science/status      anonymous → 401 · ordinary learner → 403 · admin → 200
```

It carries, per retained self-developed model: model family, provenance digests, the
logical runtime route (`POST /v1/inference/<component>`), the test that actually executes
it, the product mode, and the blocker if it is not visible.

| component | learned | family | product mode | category |
|---|---|---|---|---|
| student_twin | **no** | deterministic rule-based state engine | PREVIEW | USER_VISIBLE |
| learner_state | yes | knowledge-tracing panel (DKT/SimpleKT/AKT/CGKT/CGKT_v2) | SHADOW_NOT_USER_VISIBLE | RESEARCH_ONLY |
| evidence_reliability | yes | ReliabilityNet variant panel (5 checkpoints, 4 source digests) | SHADOW_NOT_USER_VISIBLE | SHADOW_COLLECTING_DATA |
| misconception_v2 | yes | dual-encoder retrieval (BGE-M3 + FAISS) | SHADOW_NOT_USER_VISIBLE | RESEARCH_ONLY |
| tutor_policy | yes | encoder 4-way action classifier | SHADOW | SHADOW_COLLECTING_DATA |

`student_twin` is reported as `learned_model: false` rather than omitted — the one
user-visible scientific capability carries **no checkpoint at all**, and a reader must be
able to see that.

Deliberately absent, and asserted by test: no raw prompt, no per-user field, no filesystem
path, no secret. A runtime is named by its **logical route**, never by host or install
location; the configured base URL is deployment configuration and is not exposed. An
unprobed runtime reports `reachable: null`, which is a different answer from `false` and is
never conflated with it.

---

## 9. DATA COLLECTION (PARTS 4/5/7/8)

**Versioning.** Every collected field now travels with its own `unit`, `null_semantics` and
`source_of_truth`, plus the schema version and collection start — so a future training run
can tell **"never collected"** from **"observed zero"**. The historical boundary is a field,
not a footnote.

**CS408 native KT.** Every authoritative interaction supplies: an opaque learner reference
(fixed-domain digest), a stable event/attempt id, a timestamp, module identity, item
identity, native concept identity where honestly available, and an authoritative
correctness boolean. **No training happened** — the gate registered in S7 is re-measured at
`FAIL` and the trainer is a contract that refuses.

**Tutor data collection.** Only fields the product already owns:

```text
dialogue_turn_ref         COLLECTED       (ai_requests.id, carried onto the learning event)
question_context          COLLECTED       (LearningContext on the event envelope)
student_submitted_answer  OWNED_NOT_READ  (canonical practice_attempts; not copied onto AI events)
pedagogical_action        NOT_OWNED       <-- the running tutor selects NO action
confusion                 NOT_OWNED       (research-dataset field, no product source)
previous_action           NOT_OWNED       (no action ledger exists)
```

`explicit_action_ontology_in_running_tutor = ABSENT`, reported rather than worked around.
The orchestrator chooses a capability and a model; neither is a member of the frozen
`focus / generic / probing / telling` ontology, so logging one would be logging an invented
label. Nothing is written for it.

---

## 10. TESTS (PART 16)

```text
backend/tests/test_s8_concept_identity.py            14 tests (2 require the shipped bank)
backend/tests/test_s8_completeness_and_status.py     21 tests
frontend cs408-s8-cross-workspace.test.tsx            9 tests
```

Covering: the strict S6 rule still behaves as S6 defined it · the normalization recovers
only exact-equality forms · the chapter-4 collision is refused **and listed** · the resolver
never writes to the question bank · knowledge→practice reachability, positive **and**
negative · practice→wrong · records→source (including a record with no source id rendering
no link) · plan→action_target, with the absent node identity pinned · state→records scope
agreement · per-field telemetry contract · tutor collection contract · the frozen four-way
category registry · an unknown category refused rather than silently created · the native-KT
entry is not a fourteenth component · admin authorization (401/403/200) · no path, prompt,
secret or PII leak · **no per-user field** · migration chain linear with exactly one head ·
no destructive migration operation anywhere in the chain · the suite never opens the
shipped `app.db`.

```text
FULL_BACKEND_TESTS = 1516 passed / 2 skipped / 0 failed   (562 s)
FRONTEND           = typecheck PASS · lint PASS · 94 unit (25 files) PASS · build PASS
```

---

## 11. PRODUCTION (PART 15/17)

**Production safety.** No schema change this sprint, so no new migration. The procedure was
rehearsed on a **temporary copy** — the real `backend/app.db` was never opened for write:

```text
copy backend/app.db -> temp
alembic upgrade head    -> 20260919_0010 (head)   [10 revisions, all applied]
PRAGMA integrity_check  -> ok
content preserved       -> exam_question_bank 9333 rows, 0 users, 0 learning_events
schema preflight        -> AT_HEAD, 85 tables, missing_required_columns []
authenticated smoke     -> 11 endpoints 200, 0 × 5xx
   CN leaf 3.6 -> 50 questions (was 0)
   CN leaf 4.2 -> 0  (the refused collision, still refused)
   /science/status -> 403 ordinary user, 401 anonymous
```

**Live deployment.** Pushed `19f132a7`; the pipeline executes, in this order:

```text
stop writers -> backup -> integrity_check ok -> alembic upgrade head
             -> post-migration integrity_check -> schema preflight -> restart backend
             -> frontend -> public HTTPS verification
```

Migration strictly precedes the new backend's start, which is what the sprint requires.

**Deployment result — SUCCEEDED.**

```text
commit                19f132a716a50bdb164c5d35b7fd34a6da36128a
                      (with 01814ed7 and 569dbe87 as its two predecessors)
workflow run          35480304704    status=completed  conclusion=success

backup                app.db.before-catalog-reform.20260920_090316.db   (39M)
pre-migration check   [deploy] Persistent database integrity_check: ok
=== alembic upgrade head ===
post-migration check  [deploy] Post-migration integrity_check: ok
schema preflight      [schema-check] OK: AT_HEAD revision=20260919_0010
PRODUCTION MIGRATION REVISION = 20260919_0010   (AT_HEAD)
backend               [deploy] backend health ok
runtime               [deploy] zhixue-runtime health ok
https                 [deploy] HTTPS health ok · HTTP redirect verified: 308 -> https://…
```

**Public acceptance, run against `https://101.32.190.42` after the deploy:**

| probe | result |
|---|---|
| `GET /api/health` | 200 `{"status":"ok"}` |
| `GET /api/exam/prep/catalog` | 200 — `catalog_version=v2`, `active_subject_ids=["cs_408"]`, 14 subjects |
| `GET /api/exam/prep/subjects/cs_408/content-status` | 200 |
| **`GET /api/science/status`** | **401** — this route did not exist before this deploy (it would have been 404), so the new build is provably live *and* its admin gate answers correctly |
| frontend bundle | production serves `index-BbingS8D.js` / `index-6g9zWxY9.css` — **byte-identical asset hashes to the locally built and locally tested bundle** |

**What the public probe deliberately does not do.** The authenticated CS408 flow — including
the `computer_network` fix — was verified against a migrated copy with a real session (see
above: leaf `3.6` → 50 questions, leaf `4.2` → 0). It is **not** re-verified on production by
creating a throwaway account there, because that would write a real user row and, with SMTP
configured, send a real email. The production evidence for that path is the identical
artifact (same commit, same bundle hashes) plus the deploy's own health checks.

---

## BLOCKERS

1. **`DATA_READINESS_GATE = FAIL`.** The product holds 0 users and 0 learning events. The
   gate was registered before the measurement and was not lowered.
2. **Chapter-practice facts carry module identity but not concept identity.** The frontend
   calls `POST /exam/11408/{subject}/chapter-practice/attempts` with `question_ids` only
   (`frontend/src/features/exam/api/chapter-practice.ts:41`) and never sends
   `knowledge_point_id`, so the attempt row's concept column is NULL and every chapter
   practice fact lands at module granularity. The backend accepts the field; the flow does
   not supply it. **This is the single largest blocker to a concept-level CS408 KT model**,
   and it is now measured and reproducible. It was NOT changed this sprint: it alters what
   a frozen STEP7D adapter records, which is a product decision rather than a bug fix.
3. **220 `computer_network` questions remain chapter-level only** — chapter 4's own
   `4.1`…`4.40` numbering cannot be mapped onto the canonical leaves without an inference
   this sprint refuses to make. A content re-key is the fix, and it is a content decision.
4. **`response_time_ms` still has no producer**, and no surface records a per-item serve
   boundary. `hint_count` remains `NOT_AVAILABLE` — no hint mechanism exists.
5. **`tutor_policy` has no turn state** because the running tutor selects no pedagogical
   action. Recording one would fabricate the model's dominant input signal.
6. **No membership/upgrade route exists**, so the locked Study Plan state has no canonical
   navigation target.
7. **Prior-sprint scratch directories remain uncommitted** (`.bc7tmp/`, `.bc8tmp/`,
   `.bc8r1tmp/`, `.f1c5qa/`, `.f1c6tmp/`, `frontend/.f1c5qa/`, `frontend/.f1c6tmp/`,
   `test-results/`, `backend/file`). They are not in the repository; they should be removed
   from the working tree when convenient.
8. **A stale claim in `.claude/rules/frontend-ui.md`** still states that all 13 scientific
   components are `RUNTIME_ONLY` with `SHADOW = 0 / ADVISORY = 0 / ACTIVE = 0` and that
   *"前端不得暴露任何 scientific component"*. That is no longer true — `student_twin` has
   been `USER_VISIBLE_PREVIEW` since S2 and the frontend deliberately renders its experiment
   view. Reported rather than edited, because it is a governance file and the correction is
   the user's to make. (`CLAUDE.md`'s `MIGRATION_HEAD = 20260917_0008` and the
   `DIVERGED` git warning in §37.1/§68.1 are likewise stale: HEAD is `20260919_0010` and
   local `main` again equals `origin/main`.)
