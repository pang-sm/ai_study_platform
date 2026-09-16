# Next Data-Producer Readiness Audit

> **权威层级**：唯一最高权威是仓库根目录 `ZHIXUE_AI_PRODUCT_REDESIGN_SSOT.md`。
> 本文档是一份**就绪度审计（readiness audit）**，从属于 SSOT；冲突时 SSOT wins。
> 其中「Recommended」不等于已批准或已实施；任何 component 的产品化仍需通过 SSOT §35 的
> Productization Gate。当前全部 13 个组件状态为 `RUNTIME_ONLY`。

Audit of the remaining 12 components after the StudentTwin DATA_PRODUCER go-live.
Principle (§27): prioritize components whose input is product-native, whose scientific
semantics remain valid, and which need no ontology fabrication — not simply because a
model was "recovered".

Eligibility semantics (§28): `READY+SUPPORTED = ELIGIBLE`; `PARTIAL/ONTOLOGY_MISMATCH/
BLOCKED/NOT_APPLICABLE = INELIGIBLE`. No component is force-run.

## Readiness matrix (remaining 12)

| Component | Current blocker | Product-native preprocessing? | Ontology mapping? | New data collection? | Est. cost | Scientific risk | Recommended |
|-----------|-----------------|-------------------------------|-------------------|----------------------|-----------|-----------------|-------------|
| domestic_registry | NOT_APPLICABLE (metadata, no inference) | n/a | n/a | no | — | none | No (not an inference component) |
| execution_router | NOT_APPLICABLE (registry routing, no product inference) | n/a | n/a | no | — | none | No |
| difficulty_prior | BLOCKED: 1024-d BGE-M3 embedding missing | **Yes** — question_text (FULL snapshot) → embedding | No (BGE-M3 is text-based) | No | Medium (add BGE-M3 embedding capability) | Low–Medium | **#1** |
| memory | BLOCKED: review-history features (log_dt, hist_len, mean_interval, mean_rating, last_rating, lapses) | Partial — has occurred_at+correct; lacks rating/interval/lapse semantics | No | **Yes** (review events ≠ ordinary answer events) | Medium | Medium | #3 (only after real review data exists) |
| evidence_reliability | PARTIAL: hint_count, log_rt, b_s, opportunity missing | Partial — correct present; response_time_ms currently NULL in emitter; hints not recorded | No | **Yes** (hints, response time, opportunity) | Medium | Medium | #2 (only after capturing real features) |
| irt | BLOCKED: ONTOLOGY_MISMATCH (Junyi item IDs) | No | **Yes** (Junyi item parameters) | No | High | High | No |
| tutor_guard | BLOCKED: DEPENDENCY_NOT_AVAILABLE (candidate pool + ActionRecognizer) | No | Partial (4-action ontology) | Yes | High | High | No |
| planner | BLOCKED: ONTOLOGY_MISMATCH (research Junyi graph) | No | **Yes** (prerequisite graph) | No | High | High | No |
| concept_verifier | PARTIAL: ONTOLOGY_MISMATCH (Eedi English math) | Partial (question+concept present) | **Yes** (Eedi concept ids ≠ product KP) | No | High | High | No |
| tutor_policy | BLOCKED: MISSING_INPUT (FULL_STATE) | No | Partial (4-action ontology) | Yes | High | High | No |
| misconception_v2 | BLOCKED: ONTOLOGY_MISMATCH (Eedi 2587 misconceptions) | Partial (question+answer present) | **Yes** (misconception taxonomy) | No | High | High | No |
| learner_state | PARTIAL: ONTOLOGY_MISMATCH (ASSISTments+Junyi) | Partial (interaction sequence present) | **Yes** (concept graph) | No | High | High | No |

## Special assessments (§29–31)

### difficulty_prior — worth a controlled preprocessing capability?
Verdict: **conditional yes, not this sprint.**

The input is a 1024-d BGE-M3 embedding over question text, and the output is a Ridge
difficulty prediction. BGE-M3 is text-agnostic (no product ontology involved), and the
product already stores `question_text` in the FULL LearningEvent snapshot. This makes it
the least ontology-blocked candidate. However it requires a new **Scientific Runtime
embedding capability** (a self-contained transformer, ~hundreds of MB, CPU-inferable) —
that is a real deployment-weight decision, so it is flagged for a separate
science/engineering decision rather than auto-implemented now.

### memory — is real review history available?
Verdict: **insufficient → keep BLOCKED.**

The scientific `memory` (MemNet + Platt) consumes spaced-repetition review-history features
(`log_dt`, `hist_len`, `mean_interval`, `mean_rating`, `last_rating`, `lapses`). The product
course_practice events provide `occurred_at` + `correct` but do not yet carry a genuine
review schedule, rating, or lapse semantics. Fabricating a review history from ordinary
answer events would violate the no-fabrication rule — keep BLOCKED until real review data
is collected.

### evidence_reliability — feature availability mapping
| Feature | Status |
|---------|--------|
| hint_count | MISSING (hints not recorded by emitter) |
| log_rt (response time) | MISSING (response_time_ms emitted as NULL) |
| b_s / opportunity (ASSISTments skill sequence) | MISSING |
| correctness | AVAILABLE |

Verdict: **keep PARTIAL/INELIGIBLE.** The reliability weight `w` cannot be computed from
only `correct`; the missing features would require recording hints + response time + a
skill-attempt sequence. Do not fill unknown features with 0.

## Recommended next components (strict order)

1. **difficulty_prior** — only after a deliberate decision to add a BGE-M3 embedding
   capability to the Scientific Runtime (separate approval; not auto).
2. **evidence_reliability** — only after the emitter starts recording `response_time_ms`
   and `hints` (real features, not defaults).
3. **memory** — only after genuine review-history data exists in the product.

All ontology-mismatched components (irt, planner, concept_verifier, tutor_policy,
misconception_v2, learner_state, tutor_guard) are **not recommended** until the underlying
ontology/domain mapping is resolved by product data work — do not paper over them with
engineering hacks.

## Historical backfill

`--apply = NO` (unchanged).
