from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

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