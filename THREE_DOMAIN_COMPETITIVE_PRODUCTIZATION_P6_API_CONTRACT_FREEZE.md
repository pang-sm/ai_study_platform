# P6 API CONTRACT FREEZE — advanced capabilities

Generated: `2026-09-20T12:38:04.207965` · entries: **21** · surface fingerprint: `572d9e68c9bc5138`

> Drift detector, not an OpenAPI copy. A changed fingerprint is a contract change and must be a deliberate, reviewed decision — never a side effect of a frontend or deployment change.

| # | Method | Path | Request | Response | Fingerprint |
|---|--------|------|---------|----------|-------------|
| 1 | `POST` | `/ai/deep-study` | `DeepStudyRequest` | `DeepStudyResponse` | `394bf4761cdf1bf0` |
| 2 | `POST` | `/programming/agent/debug` | `AgentDebugRequest` | `AgentDebugResponse` | `b239b158923a4e1e` |
| 3 | `POST` | `/ai/learning-report` | `LearningReportRequest` | `LearningReportResponse` | `74a8add94e834394` |
| 4 | `POST` | `/wrong-answers/{state_id}/analysis` | `inline` | `WrongAnalysisResponse` | `5ea2402f7739f9dc` |
| 5 | `POST` | `/ai/plan-adjustment` | `PlanScope` | `PlanAdjustmentProposal` | `823e960b029e3d80` |
| 6 | `POST` | `/ai/plan-adjustment/apply` | `PlanApplyRequest` | `PlanApplyResponse` | `865b1971ccba8cac` |
| 7 | `GET` | `/adaptive/practice` | `inline` | `AdaptivePracticeResponse` | `433144f1f90c229d` |
| 8 | `POST` | `/ai/feedback` | `AIFeedbackRequest` | `AIFeedbackResponse` | `c01b537f7dc0ec45` |
| 9 | `GET` | `/ai/feedback/analytics` | `inline` | `FeedbackAnalyticsResponse` | `7f2c5446b572bb8f` |
| 10 | `GET` | `/ai/feedback/availability` | `inline` | `object` | `b333b410e1742529` |
| 11 | `GET` | `/review` | `inline` | `ReviewListResponse` | `15e242ee8a3a30e0` |
| 12 | `GET` | `/review/summary` | `inline` | `ReviewSummaryResponse` | `a7f871d34d67fa3f` |
| 13 | `POST` | `/review/schedule` | `ReviewScheduleRequest` | `ReviewScheduleResponse` | `d2988430f3defb09` |
| 14 | `POST` | `/review/{item_id}/complete` | `ReviewCompleteRequest` | `ReviewCompleteResponse` | `b27ff3b16b7fc517` |
| 15 | `GET` | `/learning/agenda` | `inline` | `AgendaResponse` | `e14bb89baf7aa701` |
| 16 | `GET` | `/learning/agenda/explain` | `inline` | `object` | `eebdd9a33f5af901` |
| 17 | `GET` | `/admin/ai-operations/summary` | `inline` | `AIOperationsSummary` | `d7b1dfb71b3cee36` |
| 18 | `GET` | `/admin/workflow-operations/summary` | `inline` | `WorkflowOperationsSummary` | `10a4cccd400f78b5` |
| 19 | `GET` | `/admin/workflow-operations/agent-runs/{run_id}` | `inline` | `AgentRunDetail` | `ddace2711cf88a84` |
| 20 | `GET` | `/admin/feature-flags` | `inline` | `FeatureFlagList` | `8ae6200ddde36c9e` |
| 21 | `PUT` | `/admin/feature-flags` | `FeatureFlagUpdate` | `FeatureFlagUpdateResult` | `2a5aee93242c433c` |

## Frozen intent per entry

### `POST /ai/deep-study`

- handler: `run_deep_study_ai_deep_study_post`
- request model: `DeepStudyRequest`
- request fields: `chapter_id`, `course_id`, `knowledge_point_id`, `material_ids`, `max_tokens`, `question`, `service_key`, `subject_key`
- response model: `DeepStudyResponse`
- response fields: `answer`, `capability`, `citations`, `context`, `evidence`, `material_refs`, `materials`, `model`, `request_id`, `status`, `usage`
- parameters: —
- frozen intent: grounded strong-reasoning answer + citations + usage
- contract: Run Deep Study

### `POST /programming/agent/debug`

- handler: `run_programming_agent_programming_agent_debug_post`
- request model: `AgentDebugRequest`
- request fields: `exercise_id`, `files`, `goal`, `project_id`
- response model: `AgentDebugResponse`
- response fields: `agent_run_id`, `diagnosis`, `error_category`, `executions_used`, `exercise_id`, `explanation`, `final_code`, `iterations_used`, `language`, `message`, `patch_file`, `patch_summary`, `proposed_patch`, `reason`, `status`, `steps`, `stop_reason`, `tests_after`, `tests_before`, `usage`
- parameters: —
- frozen intent: bounded debug run: code-free step trace + verdict
- contract: Run Programming Agent

### `POST /ai/learning-report`

- handler: `generate_learning_report_ai_learning_report_post`
- request model: `LearningReportRequest`
- request fields: `course_id`, `exam_module_id`, `include_narrative`, `language`, `period_days`, `service_key`
- response model: `LearningReportResponse`
- response fields: `attention_items`, `context`, `data_coverage`, `generated_at`, `highlights`, `narrative`, `narrative_error`, `report_id`, `report_period`, `structured_metrics`
- parameters: —
- frozen intent: deterministic report + optional AI narrative
- contract: Generate Learning Report

### `POST /wrong-answers/{state_id}/analysis`

- handler: `analyze_wrong_answer_wrong_answers__state_id__analysis_post`
- request model: `inline`
- response model: `WrongAnalysisResponse`
- response fields: `analysis`, `analysis_origin`, `analysis_semantics`, `capability`, `fact_origin`, `facts`, `generated_at`, `persistence`, `request_id`, `service_namespace`, `state_id`, `usage`
- parameters: `state_id:path`
- frozen intent: facts / AI reading, explicitly separated
- contract: Analyze Wrong Answer

### `POST /ai/plan-adjustment`

- handler: `propose_plan_adjustment_ai_plan_adjustment_post`
- request model: `PlanScope`
- request fields: `course_id`, `exam_module_id`, `goal`, `language`, `service_key`
- response model: `PlanAdjustmentProposal`
- response fields: `affected_tasks`, `applies_to`, `capability`, `dropped_changes`, `generated_at`, `plan_identity`, `plan_snapshot`, `proposal_id`, `proposed_changes`, `reason`, `request_id`, `service_namespace`, `subject_key`, `usage`
- parameters: —
- frozen intent: plan adjustment PROPOSAL (writes nothing)
- contract: Propose Plan Adjustment

### `POST /ai/plan-adjustment/apply`

- handler: `apply_plan_adjustment_ai_plan_adjustment_apply_post`
- request model: `PlanApplyRequest`
- request fields: `course_id`, `exam_module_id`, `language`, `plan_identity`, `proposal_id`, `proposed_changes`, `service_key`
- response model: `PlanApplyResponse`
- response fields: `applied_at`, `applied_count`, `dropped_changes`, `plan_identity`, `plan_identity_before`, `service_namespace`, `subject_key`
- parameters: —
- frozen intent: apply an accepted proposal (stale → 409)
- contract: Apply Plan Adjustment

### `GET /adaptive/practice`

- handler: `adaptive_practice_adaptive_practice_get`
- request model: `inline`
- response model: `AdaptivePracticeResponse`
- response fields: `candidates`, `context`, `counts_by_reason`, `excluded_count`, `generated_at`, `policy_version`, `reasons`, `selection_id`, `semantics`, `service_namespace`, `total_candidates`
- parameters: `course_id:query?`, `exam_module_id:query?`, `language:query?`, `limit:query?`, `service_key:query?`
- frozen intent: next-practice candidates, each with its factual reason
- contract: Adaptive Practice

### `POST /ai/feedback`

- handler: `submit_ai_feedback_ai_feedback_post`
- request model: `AIFeedbackRequest`
- request fields: `rating`, `reason`, `regenerated`, `request_id`, `switched_model`, `workflow_id`
- response model: `AIFeedbackResponse`
- response fields: `actual_credits`, `capability`, `context`, `created_at`, `estimated_credits`, `latency_ms`, `model`, `provider`, `rating`, `reason`, `reason_taxonomy`, `regenerated`, `request_id`, `router_reason`, `service_namespace`, `status`, `submitted_at`, `switched_model`, `tier`, `trains_router_online`, `workflow_id`
- parameters: —
- frozen intent: rate one of the caller's own AI responses
- contract: Submit Ai Feedback

### `GET /ai/feedback/analytics`

- handler: `feedback_analytics_ai_feedback_analytics_get`
- request model: `inline`
- response model: `FeedbackAnalyticsResponse`
- response fields: `by_capability`, `by_model`, `by_provider`, `by_reason`, `by_workflow`, `generated_at`, `per_capability_model`, `router_mutation`, `scope`, `semantics`, `totals`, `window_days`
- parameters: `scope:query?`, `window_days:query?`
- frozen intent: mine | admin-only platform aggregate of ratings
- contract: Feedback Analytics

### `GET /ai/feedback/availability`

- handler: `model_availability_ai_feedback_availability_get`
- request model: `inline`
- response model: `object`
- parameters: —
- frozen intent: router availability WITH its process-local scope
- contract: Model Availability

### `GET /review`

- handler: `list_review_items_review_get`
- request model: `inline`
- response model: `ReviewListResponse`
- response fields: `buckets`, `items`, `limit`, `offset`, `semantics`, `total`
- parameters: `course_id:query?`, `exam_module_id:query?`, `language:query?`, `limit:query?`, `offset:query?`, `service_namespace:query?`, `status:query?`
- frozen intent: outstanding review work (due / needs_attention / scheduled)
- contract: List Review Items

### `GET /review/summary`

- handler: `review_summary_review_summary_get`
- request model: `inline`
- response model: `ReviewSummaryResponse`
- response fields: `by_namespace`, `by_source`, `by_status`, `has_stored_due_dates`, `semantics`, `service_namespace`, `total`
- parameters: `service_namespace:query?`
- frozen intent: counts over the SAME projection the list serves
- contract: Review Summary

### `POST /review/schedule`

- handler: `schedule_reviews_review_schedule_post`
- request model: `ReviewScheduleRequest`
- request fields: `include_all`, `item_ids`
- response model: `ReviewScheduleResponse`
- response fields: `count`, `generated_at`, `policy_version`, `scheduled`, `semantics`
- parameters: —
- frozen intent: record the next review date from stored facts
- contract: Schedule Reviews

### `POST /review/{item_id}/complete`

- handler: `complete_review_review__item_id__complete_post`
- request model: `ReviewCompleteRequest`
- request fields: `result`
- response model: `ReviewCompleteResponse`
- response fields: `due_at`, `interval_days`, `item_id`, `policy_version`, `previous_review_result`, `reason`, `result`, `scheduled_at`, `semantics`, `source_facts`
- parameters: `item_id:path`
- frozen intent: record a real review result and reschedule
- contract: Complete Review

### `GET /learning/agenda`

- handler: `get_learning_agenda_learning_agenda_get`
- request model: `inline`
- response model: `AgendaResponse`
- response fields: `by_namespace`, `by_reason`, `filters`, `generated_at`, `items`, `policy_version`, `priority_order`, `semantics`, `source_summary`, `total_items`
- parameters: `course_id:query?`, `exam_module_id:query?`, `language:query?`, `limit:query?`, `service_key:query?`
- frozen intent: the daily learning agenda projection
- contract: Get Learning Agenda

### `GET /learning/agenda/explain`

- handler: `explain_learning_agenda_learning_agenda_explain_get`
- request model: `inline`
- response model: `object`
- parameters: `course_id:query?`, `exam_module_id:query?`, `language:query?`, `limit:query?`, `service_key:query?`
- frozen intent: why an agenda entry is where it is
- contract: Explain Learning Agenda

### `GET /admin/ai-operations/summary`

- handler: `ai_operations_summary_admin_ai_operations_summary_get`
- request model: `inline`
- response model: `AIOperationsSummary`
- response fields: `availability`, `bounded`, `by_capability`, `by_model`, `by_provider`, `by_service_namespace`, `by_tier`, `credits`, `feedback`, `generated_at`, `latency`, `privacy`, `requests`, `router`, `scope`, `window_days`, `window_start`
- parameters: `window_days:query?`
- frozen intent: admin-only AI accounting aggregate
- contract: Ai Operations Summary

### `GET /admin/workflow-operations/summary`

- handler: `workflow_operations_summary_admin_workflow_operations_summary_get`
- request model: `inline`
- response model: `WorkflowOperationsSummary`
- response fields: `generated_at`, `privacy`, `scope`, `window_days`, `window_start`, `workflows`
- parameters: `window_days:query?`
- frozen intent: admin-only per-workflow aggregate
- contract: Workflow Operations Summary

### `GET /admin/workflow-operations/agent-runs/{run_id}`

- handler: `agent_run_detail_admin_workflow_operations_agent_runs__run_id__get`
- request model: `inline`
- response model: `AgentRunDetail`
- response fields: `agent_run_id`, `durable_sources`, `exercise_id`, `found`, `language`, `model_steps`, `privacy`, `run_status`, `steps`, `stopped_reason`, `trace`
- parameters: `run_id:path`
- frozen intent: admin-only run trace (code-free)
- contract: Agent Run Detail

### `GET /admin/feature-flags`

- handler: `list_feature_flags_admin_feature_flags_get`
- request model: `inline`
- response model: `FeatureFlagList`
- response fields: `default_mode`, `items`, `modes`, `never_changes`, `semantics`
- parameters: —
- frozen intent: the seven advanced-workflow kill switches
- contract: List Feature Flags

### `PUT /admin/feature-flags`

- handler: `update_feature_flags_admin_feature_flags_put`
- request model: `FeatureFlagUpdate`
- request fields: `flags`
- response model: `FeatureFlagUpdateResult`
- response fields: `modes`, `previous`, `updated`
- parameters: —
- frozen intent: set a flag mode (OFF/INTERNAL/TIER/ALL)
- contract: Update Feature Flags

