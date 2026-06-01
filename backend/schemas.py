from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str
    subject: str = ""
    course: str = ""
    grade: str = ""
    major: str = ""
    username: str | None = None
    session_id: int | None = None
    material_ids: list[int] = []
    hidden_instruction: str = ""


class CodeSessionCreate(BaseModel):
    username: str
    course_id: str
    title: str = "未命名练习"
    language: str = "Python"
    code: str = ""
    challenge_id: int | None = None


class CodeSessionUpdate(BaseModel):
    username: str
    course_id: str | None = None
    title: str | None = None
    language: str | None = None
    code: str | None = None


class CodeAnalyzeRequest(BaseModel):
    username: str
    course_id: str = ""
    session_id: int | None = None
    language: str = ""
    code: str = ""
    question: str = ""


class CodeAIMessageCreate(BaseModel):
    username: str
    session_id: int
    role: str
    content: str
    language: str | None = None
    code_snapshot: str | None = None


class CodeAIMessageOut(BaseModel):
    id: int
    username: str
    session_id: int
    role: str
    content: str
    language: str | None = None
    code_snapshot: str | None = None
    created_at: str | None = None


class CodeChallengeGenerateRequest(BaseModel):
    username: str
    course_id: str = ""
    language: str = "Python"
    difficulty: str = "基础"
    focus: str = ""
    diagnosis_summary: str = ""
    source: str = ""
    target_weak_point: str = ""


class CodeChallengeOut(BaseModel):
    id: int
    username: str
    course_id: str | None = None
    language: str
    title: str
    difficulty: str
    knowledge_point: str | None = None
    description: str
    requirements: str | None = None
    input_format: str | None = None
    output_format: str | None = None
    examples: str | None = None
    starter_code: str | None = None
    source: str | None = None
    target_weak_point: str | None = None
    created_at: str | None = None


class CodeChallengeGenerateResponse(BaseModel):
    success: bool
    challenge: CodeChallengeOut | None = None
    session: dict | None = None
    detail: str | None = None


class CodeLearningDiagnosisRequest(BaseModel):
    username: str
    course_id: str = ""
    language: str = ""


class CodeChallengeSubmitRequest(BaseModel):
    username: str
    session_id: int
    code: str = ""
    language: str = ""


class CodeExecuteRequest(BaseModel):
    username: str
    session_id: int = 0
    language: str = "python"
    code: str = ""
    stdin: str = ""


class CodeChallengeRunTestsRequest(BaseModel):
    username: str
    session_id: int
    language: str = "python"
    code: str = ""


class CodeChallengeExplainFailureRequest(BaseModel):
    username: str
    session_id: int
    language: str = ""
    code: str = ""
    test_case: dict = {}
    actual_output: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False


class CodeChallengeGenerateTestsRequest(BaseModel):
    username: str
    language: str = ""


# ── Code Attempt History ──────────────────────────────


class CodeAttemptListRequest(BaseModel):
    username: str
    status: str | None = None
    course_id: str = ""
    language: str | None = None
    limit: int = 30


class CodeAttemptOut(BaseModel):
    id: int
    username: str
    session_id: int
    challenge_id: int
    challenge_title: str | None = None
    language: str | None = None
    difficulty: str | None = None
    knowledge_point: str | None = None
    status: str | None = None
    ai_feedback_summary: str | None = None
    mastered: int = 0
    created_at: str | None = None


class CodeAttemptDetailOut(BaseModel):
    id: int
    username: str
    session_id: int
    challenge_id: int
    language: str | None = None
    code: str
    status: str | None = None
    ai_feedback: str | None = None
    mastered: int = 0
    mastered_at: str | None = None
    note: str | None = None
    created_at: str | None = None
    challenge_title: str | None = None
    challenge_difficulty: str | None = None
    challenge_knowledge_point: str | None = None
    challenge_description: str | None = None
    challenge_reference_solution: str | None = None
    challenge_test_cases: str | None = None


class CodeAttemptMasteredUpdate(BaseModel):
    username: str
    mastered: int = 1


class LearningTaskCreate(BaseModel):
    username: str
    course_id: str = ""
    title: str
    description: str = ""
    task_type: str
    status: str = "todo"
    source: str = "manual"
    priority: str = "medium"
    due_date: str | None = None
    related_session_id: int | None = None
    related_challenge_id: int | None = None
    related_material_id: int | None = None
    knowledge_point_id: int | None = None
    related_question_id: int | None = None


class LearningTaskUpdate(BaseModel):
    username: str
    title: str | None = None
    description: str | None = None
    task_type: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None
    knowledge_point_id: int | None = None
    related_question_id: int | None = None


class LearningTaskOut(BaseModel):
    id: int
    username: str
    course_id: str | None = None
    title: str
    description: str | None = None
    task_type: str
    status: str
    source: str | None = None
    priority: str | None = None
    due_date: str | None = None
    related_session_id: int | None = None
    related_challenge_id: int | None = None
    related_material_id: int | None = None
    knowledge_point_id: int | None = None
    knowledge_point_title: str | None = None
    related_question_id: int | None = None
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class GenerateTasksFromDiagnosisRequest(BaseModel):
    username: str
    course_id: str = ""
    course_name: str = ""
    diagnosis_summary: str
    language: str = ""


class KnowledgePointCreate(BaseModel):
    username: str
    course_id: str
    parent_id: int | None = None
    parent_node_key: str | None = None
    title: str
    description: str = ""
    order_index: int | None = None
    level: int | None = None
    node_key: str | None = None


class KnowledgePointUpdate(BaseModel):
    username: str
    title: str | None = None
    description: str | None = None
    parent_id: int | None = None
    order_index: int | None = None
    level: int | None = None
    node_key: str | None = None


class KnowledgePointOut(BaseModel):
    id: int
    username: str
    course_id: str
    parent_id: int | None = None
    title: str
    description: str | None = None
    order_index: int | None = None
    level: int | None = None
    node_key: str | None = None
    mastery_score: int | None = None
    status: str | None = None
    children: list["KnowledgePointOut"] | None = None
    created_at: str | None = None
    updated_at: str | None = None


class KnowledgeProgressUpdate(BaseModel):
    username: str
    mastery_score: int | None = None
    status: str | None = None


class KnowledgeProgressOut(BaseModel):
    id: int
    username: str
    course_id: str
    knowledge_point_id: int
    mastery_score: int | None = None
    status: str | None = None
    practice_count: int | None = None
    task_count: int | None = None
    last_studied_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


# ── Practice / Question Bank ──────────────────────────────


class QuestionCreate(BaseModel):
    username: str
    course_id: str = ""
    knowledge_point_id: int | None = None
    type: str
    title: str
    content: str
    options: str | None = None
    answer: str | None = None
    explanation: str | None = None
    difficulty: str = "基础"
    source: str = "manual"
    source_style: str | None = None
    imported_from: str | None = None
    original_file_name: str | None = None


class QuestionUpdate(BaseModel):
    username: str
    course_id: str | None = None
    knowledge_point_id: int | None = None
    type: str | None = None
    title: str | None = None
    content: str | None = None
    options: str | None = None
    answer: str | None = None
    explanation: str | None = None
    difficulty: str | None = None


class QuestionOut(BaseModel):
    id: int
    username: str
    course_id: str | None = None
    knowledge_point_id: int | None = None
    knowledge_point_title: str | None = None
    type: str
    title: str
    content: str
    options: str | None = None
    answer: str | None = None
    explanation: str | None = None
    difficulty: str | None = None
    source: str | None = None
    source_style: str | None = None
    imported_from: str | None = None
    original_file_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class QuestionAttemptCreate(BaseModel):
    username: str
    question_id: int
    user_answer: str | None = None


class QuestionAttemptOut(BaseModel):
    id: int
    username: str
    question_id: int
    course_id: str | None = None
    knowledge_point_id: int | None = None
    user_answer: str | None = None
    ai_feedback: str | None = None
    self_result: str | None = None
    created_at: str | None = None


class QuestionFeedbackRequest(BaseModel):
    username: str
    user_answer: str


class GenerateQuestionRequest(BaseModel):
    username: str
    course_id: str = ""
    course_name: str = ""
    knowledge_point_id: int | None = None
    knowledge_point_title: str = ""
    type: str = "choice"
    difficulty: str = "基础"
    count: int = 1
    source_style: str = "mixed"
    require_reasoning: bool = True
    avoid_too_simple: bool = True


class PaperQuestionDraft(BaseModel):
    title: str = ""
    question_text: str = ""
    type: str = "short_answer"
    options: str | None = None
    answer: str | None = None
    explanation: str | None = None
    course_id: str = ""
    knowledge_point_id: int | None = None
    difficulty: str = "中等"
    source: str = "paper_import"
    confidence: float | None = None
    source_style: str | None = None


class PaperImportConfirmRequest(BaseModel):
    username: str
    course_id: str = ""
    original_file_name: str | None = None
    questions: list[PaperQuestionDraft]


# ── AI Knowledge Point Generation ────────────────────────


class KnowledgePointGeneratePreviewRequest(BaseModel):
    username: str
    course_id: str = ""
    course_name: str = ""
    mode: str = "course_name"
    max_top_points: int = 8
    max_children_per_point: int = 6


class KnowledgePointImportRequest(BaseModel):
    username: str
    course_id: str
    items: list
    import_mode: str = "append"


class KnowledgePathGenerateFromMaterialsRequest(BaseModel):
    username: str
    subject: str
    material_ids: list[int]
    overwrite: bool = True


# ── AI Learning Plan ─────────────────────────────────────


class PlanGeneratePreviewRequest(BaseModel):
    username: str
    course_id: str = ""
    plan_type: str = "seven_day"
    days: int = 7
    goal: str = ""
    daily_minutes: int = 60


class PlanImportTasksRequest(BaseModel):
    username: str
    plan_title: str = ""
    items: list


# ── Material-Knowledge Links ─────────────────────────────


class MaterialKnowledgeLinkCreate(BaseModel):
    username: str
    course_id: str = ""
    knowledge_point_id: int
    source: str = "manual"
    confidence: int = 100
    reason: str = ""


class MaterialKnowledgeRecommendRequest(BaseModel):
    username: str
    course_id: str = ""


class MaterialKnowledgeApplyRequest(BaseModel):
    username: str
    course_id: str = ""
    links: list


# ── Admin / Plan ────────────────────────────────────────


class AdminUpdatePlanRequest(BaseModel):
    admin_username: str
    plan: str = "free"
    plan_expires_at: str | None = None


# ── Learning Reports ──────────────────────────────────────


class LearningReportGenerateRequest(BaseModel):
    username: str
    report_type: str  # today / weekly / monthly / course / exam / growth
    course_id: str = ""
    course_name: str = ""
    start_date: str | None = None
    end_date: str | None = None
    goal: str = ""
    save_after_generate: bool = False


class LearningReportSaveRequest(BaseModel):
    username: str
    course_id: str = ""
    course_name: str = ""
    report_type: str
    title: str
    summary: str = ""
    content: str
    metrics: dict | None = None
    suggestions: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None


class LearningReportShareCreateRequest(BaseModel):
    username: str
    report_id: int
