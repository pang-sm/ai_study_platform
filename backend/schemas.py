from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    grade: str
    major: str


class UserLogin(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str
    course: str
    grade: str
    major: str
    username: str | None = None
    session_id: int | None = None
