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
