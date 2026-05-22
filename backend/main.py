from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from openai import OpenAI
from dotenv import load_dotenv

from database import Base, engine, get_db, update_conversation_title
from models  import ChatMessage
from auth import hash_password, verify_password
from pydantic import BaseModel

import models
import os

import schemas

load_dotenv()

app = FastAPI()


# 创建数据库表
Base.metadata.create_all(bind=engine)

# 允许前端访问后端
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


@app.get("/")
def root():
    return {"message": "AI Study Platform Backend is running"}

@app.get("/health")
def health():
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



class ChatRequest(BaseModel):
    message: str
    username: str | None = None

class MeRequest(BaseModel):
    username: str


class RenameConversationRequest(BaseModel):
    title: str



@app.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    username = user.username.strip()
    password = user.password.strip()
    grade = user.grade.strip()
    major = user.major.strip()

    if not username:
        raise HTTPException(status_code=400, detail="账号不能为空")

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 位")

    if not grade:
        raise HTTPException(status_code=400, detail="年级不能为空")

    if not major:
        raise HTTPException(status_code=400, detail="专业不能为空")

    existing_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="账号已存在")

    new_user = models.User(
        username=user.username,
        hashed_password=hash_password(user.password),
        grade=user.grade,
        major=user.major
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "注册成功",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "grade": new_user.grade,
            "major": new_user.major
        }
    }

@app.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    username = user.username.strip()
    password = user.password.strip()

    if not username:
        raise HTTPException(status_code=400, detail="账号不能为空")

    if not password:
        raise HTTPException(status_code=400, detail="密码不能为空")

    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if not db_user:
        raise HTTPException(status_code=400, detail="账号不存在")

    if not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="密码错误")

    return {
        "message": "登录成功",
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "grade": db_user.grade,
            "major": db_user.major
        }
    }

@app.post("/me")
def me(req: MeRequest, db: Session = Depends(get_db)):
    username = req.username.strip()

    if not username:
        raise HTTPException(status_code=400, detail="账号不能为空")

    db_user = db.query(models.User).filter(
        models.User.username == username
    ).first()

    if not db_user:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")

    return {
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "grade": db_user.grade,
            "major": db_user.major
        }
    }



def get_course_prompt(course: str):
    course = course.strip()

    course_prompts = {
        "Python": """
当前课程是 Python。

教学策略：
1. 优先用简单代码解释概念。
2. 每个知识点尽量配一个可运行的小例子。
3. 重点解释语法、变量、函数、列表、字典、类、文件操作等。
4. 对初学者要解释代码每一行在做什么。
5. 不要一开始讲太多底层原理，先让用户能写出来、跑起来。
6. 如果用户问报错，要优先帮他定位错误原因和修改方式。
""",

        "Java": """
当前课程是 Java。

教学策略：
1. 优先从面向对象角度解释问题。
2. 重点关注类、对象、封装、继承、多态、接口、异常、集合等。
3. 讲代码时要解释 public、static、void、class、new 等关键字。
4. 遇到后端相关问题，可以联系 Spring Boot、接口、数据库。
5. 不要只给代码，要解释 Java 为什么这样设计。
6. 如果涉及 JVM，可以只讲大一/大二能理解的核心概念。
""",

        "数据结构": """
当前课程是 数据结构。

教学策略：
1. 优先讲清楚“数据怎么组织”和“操作怎么执行”。
2. 尽量用步骤解释，例如第一步、第二步、第三步。
3. 重点关注数组、链表、栈、队列、树、图、哈希表、堆等结构。
4. 必须说明时间复杂度和空间复杂度，但不要过度数学化。
5. 适合用生活类比帮助理解，例如排队、文件夹、地图路线。
6. 如果涉及算法过程，要给出清晰执行流程。
""",

        "计算机网络": """
当前课程是 计算机网络。

教学策略：
1. 优先从“数据如何从一台电脑到另一台电脑”这个角度解释。
2. 多使用分层思想：应用层、传输层、网络层、数据链路层、物理层。
3. 讲协议时说明它解决什么问题，例如 HTTP、TCP、UDP、IP、DNS。
4. 遇到抽象概念，要用真实上网流程举例。
5. 少写代码，多讲通信过程、封装/解封装、请求/响应、可靠传输。
6. 对比概念时要明确，例如 TCP vs UDP，HTTP vs HTTPS。
""",

        "操作系统": """
当前课程是 操作系统。

教学策略：
1. 优先从“操作系统如何管理计算机资源”角度解释。
2. 重点关注进程、线程、CPU 调度、内存管理、文件系统、死锁等。
3. 多用现实类比，例如食堂窗口类比 CPU 调度，宿舍床位类比内存分配。
4. 讲概念时要说明：它解决什么问题，为什么需要它。
5. 如果涉及算法，例如页面置换、进程调度，要一步步模拟过程。
6. 不要一开始陷入源码或内核细节，先讲机制和思想。
""",

        "数据库": """
当前课程是 数据库。

教学策略：
1. 优先从“数据如何存、如何查、如何保证正确性”角度解释。
2. 重点关注表、字段、主键、外键、SQL、索引、事务、范式等。
3. 多给 SQL 示例。
4. 解释概念时尽量结合用户正在做的登录注册项目。
5. 遇到表设计问题，要说明字段、类型、约束和表之间关系。
6. 对事务、索引等概念要用简单场景解释。
""",

        "前端开发": """
当前课程是 前端开发。

教学策略：
1. 优先从页面结构、样式、交互三个角度解释。
2. 重点关注 HTML、CSS、JavaScript、React、组件、状态、事件。
3. 讲 React 时要解释 state、props、组件渲染、事件绑定。
4. 多给可以直接复制运行的代码片段。
5. 如果用户遇到页面没变化，要优先检查文件路径、import、状态更新、控制台报错。
6. 解释要偏实践，不要过度理论化。
""",

        "后端开发": """
当前课程是 后端开发。

教学策略：
1. 优先从接口、请求、响应、数据库、业务逻辑角度解释。
2. 重点关注 FastAPI、路由、POST/GET、数据库模型、接口测试、错误处理。
3. 多结合用户当前的 AI 学习平台项目。
4. 讲接口时说明：前端传什么，后端收什么，后端返回什么。
5. 遇到 bug 要优先定位是前端问题、后端问题、数据库问题还是网络问题。
6. 代码要尽量简单、可运行。
""",

        "算法": """
当前课程是 算法。

教学策略：
1. 优先讲解题思路，而不是直接给最终代码。
2. 重点关注枚举、递归、排序、二分、贪心、动态规划、图算法等。
3. 每道题按照：题意理解 → 思路 → 步骤 → 代码 → 复杂度 来讲。
4. 对初学者要解释为什么这样做。
5. 如果涉及动态规划，要明确状态定义、状态转移、初始化和答案。
6. 不要一开始给太复杂的优化，先给能理解的版本。
"""
    }

    return course_prompts.get(course, f"""
当前课程是 {course}。

教学策略：
1. 根据该课程特点调整讲解方式。
2. 优先讲核心概念。
3. 多结合用户的年级、专业和学习目标。
4. 回答要清晰、分步骤。
""")


@app.post("/chat")
def chat(req: schemas.ChatRequest, db: Session = Depends(get_db)):
    if not req.username:
        raise HTTPException(status_code=401, detail="请先登录后再使用 AI 聊天")

    user = db.query(models.User).filter(models.User.username == req.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")

    # Reuse an existing session when session_id is provided; otherwise create one.
    if req.session_id is not None:
        chat_session = (
            db.query(models.ChatSession)
            .filter(
                models.ChatSession.id == req.session_id,
                models.ChatSession.user_id == user.id
            )
            .first()
        )

        if not chat_session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        title = req.message.strip()
        if len(title) > 30:
            title = title[:30] + "..."

        chat_session = models.ChatSession(
            user_id=user.id,
            title=title,
            course=req.course
        )

        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)

    # 2. 保存用户消息，并绑定到这次对话
    user_message = models.ChatMessage(
        user_id=user.id,
        session_id=chat_session.id,
        role="user",
        content=req.message
    )

    db.add(user_message)
    db.commit()

    course_prompt = get_course_prompt(req.course)

    system_prompt = f"""
你是一个 AI 学习助手。

用户信息：
- 年级：{req.grade}
- 专业：{req.major}
- 当前选择课程：{req.course}


你的核心任务：
根据用户的年级、专业和当前选择课程，提供适合他的学习解释。

通用回答要求：
1. 用适合该年级学生的方式讲解。
2. 尽量结合用户专业举例。
3. 回答要清晰、分步骤。
4. 如果涉及代码，给出简单可运行示例。
5. 不要一次讲太深，先讲核心概念。
6. 如果用户明显是初学者，要先解释“它是什么、为什么需要它、怎么用”。
7. 如果用户问的是报错或代码问题，优先帮他定位问题，再给修改方案。

下面是当前课程的专属教学策略：

{course_prompt}
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.message}
        ]
    )

    answer = response.choices[0].message.content

    # 3. 保存 AI 回复，并绑定到这次对话
    assistant_message = models.ChatMessage(
        user_id=user.id,
        session_id=chat_session.id,
        role="assistant",
        content=answer
    )

    db.add(assistant_message)
    db.commit()

    return {
        "answer": answer,
        "session": {
            "id": chat_session.id,
            "title": chat_session.title,
            "course": chat_session.course,
            "created_at": chat_session.created_at
        }
    }



@app.get("/chat/history")
def get_chat_history(username: str, db: Session = Depends(get_db)):
    if not username:
        raise HTTPException(status_code=401, detail="请先登录后再查看聊天记录")

    user = db.query(models.User).filter(models.User.username == username).first()

    if not user:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")

    sessions = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.user_id == user.id)
        .order_by(models.ChatSession.created_at.desc())
        .all()
    )

    return {
        "sessions": [
            {
                "id": session.id,
                "title": session.title,
                "course": session.course,
                "created_at": session.created_at
            }
            for session in sessions
        ]
    }




@app.get("/chat/sessions/{session_id}")
def get_chat_session_messages(
    session_id: int,
    username: str,
    db: Session = Depends(get_db)
):
    if not username:
        raise HTTPException(status_code=401, detail="请先登录后再查看聊天记录")

    user = db.query(models.User).filter(models.User.username == username).first()

    if not user:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")

    chat_session = (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.id == session_id,
            models.ChatSession.user_id == user.id
        )
        .first()
    )

    if not chat_session:
        raise HTTPException(status_code=404, detail="聊天记录不存在")

    messages = (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.session_id == session_id,
            models.ChatMessage.user_id == user.id
        )
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )

    return {
        "session": {
            "id": chat_session.id,
            "title": chat_session.title,
            "course": chat_session.course,
            "created_at": chat_session.created_at
        },
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at
            }
            for msg in messages
        ]
    }

@app.delete("/chat/sessions/{session_id}")
def delete_chat_session(
    session_id: int,
    username: str,
    db: Session = Depends(get_db)
):
    if not username:
        raise HTTPException(status_code=401, detail="请先登录后再删除聊天记录")

    user = db.query(models.User).filter(models.User.username == username).first()

    if not user:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")

    chat_session = (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.id == session_id,
            models.ChatSession.user_id == user.id
        )
        .first()
    )

    if not chat_session:
        raise HTTPException(status_code=404, detail="聊天记录不存在")

    # 先删除这次对话下面的所有消息
    db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id,
        models.ChatMessage.user_id == user.id
    ).delete()

    # 再删除这条历史对话
    db.delete(chat_session)
    db.commit()

    return {
        "message": "聊天记录删除成功",
        "deleted_session_id": session_id
    }


@app.put("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    req: RenameConversationRequest,
    username: str,
    db: Session = Depends(get_db)
):
    if not username:
        raise HTTPException(status_code=401, detail="请先登录后再重命名历史对话")

    user = db.query(models.User).filter(models.User.username == username).first()

    if not user:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")

    title = req.title.strip()

    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")

    if len(title) > 50:
        title = title[:50]

    conversation = update_conversation_title(
        db=db,
        user_id=user.id,
        conversation_id=conversation_id,
        title=title
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="历史对话不存在")

    return {
        "message": "重命名成功",
        "title": conversation.title
    }
