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
