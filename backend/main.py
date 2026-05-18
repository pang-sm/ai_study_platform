from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from database import engine, Base, SessionLocal
from sqlalchemy.orm import Session
import models
import os
import bcrypt
import schemas

load_dotenv()

app = FastAPI()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str):
    password_bytes = password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


Base.metadata.create_all(bind=engine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

class ChatRequest(BaseModel):
    message: str
    course: str = "计算机基础"


@app.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if not user.username.strip():
        raise HTTPException(status_code=400, detail="用户名不能为空")

    if not user.email.strip():
        raise HTTPException(status_code=400, detail="邮箱不能为空")

    if len(user.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 位")

    existing_username = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if existing_username:
        raise HTTPException(status_code=400, detail="用户名已存在")

    existing_email = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_email:
        raise HTTPException(status_code=400, detail="邮箱已存在")

    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "注册成功",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email
        }
    }


@app.get("/")
def root():
    return {"message": "AI Study Platform Backend is running"}

@app.post("/chat")
def chat(req: ChatRequest):
    system_prompt = f"""
你是一个高校计算机课程 AI 学习助手。
当前课程：{req.course}

你的回答要求：
.gitignore. 不要只给答案，要分步骤引导学生理解。
2. 适合大学生学习场景。
3. 如果涉及代码，要解释代码逻辑。
4. 回答要清晰、具体、适合初学者。
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.message}
        ]
    )

    return {
        "answer": response.choices[0].message.content
    }