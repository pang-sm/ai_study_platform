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


class CodeSessionCreate(BaseModel):
    username: str
    course_id: str
    title: str = "未命名练习"
    language: str = "Python"
    code: str = ""


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
    title: str
    description: str = ""
    order_index: int | None = None
    level: int | None = None


class KnowledgePointUpdate(BaseModel):
    username: str
    title: str | None = None
    description: str | None = None
    parent_id: int | None = None
    order_index: int | None = None
    level: int | None = None


class KnowledgePointOut(BaseModel):
    id: int
    username: str
    course_id: str
    parent_id: int | None = None
    title: str
    description: str | None = None
    order_index: int | None = None
    level: int | None = None
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
