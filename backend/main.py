from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from openai import OpenAI
from dotenv import load_dotenv

from database import (
    Base,
    engine,
    get_db,
    init_user_profile_schema,
    update_conversation_title,
)
from models  import ChatMessage
from auth import hash_password, verify_password
from pydantic import BaseModel
from pypdf import PdfReader
from PIL import Image, UnidentifiedImageError
import pytesseract

from io import BytesIO
import models
import os

import schemas

load_dotenv()

app = FastAPI()


# 创建数据库表
Base.metadata.create_all(bind=engine)
init_user_profile_schema()

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


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    grade: str | None = None
    major: str | None = None
    avatar: str | None = None


ALLOWED_AVATARS = {
    "avatar_1",
    "avatar_2",
    "avatar_3",
    "avatar_4",
    "avatar_5",
    "avatar_6",
}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
MAX_PDF_CHARS = 12000
MAX_OCR_CHARS = 12000
ALLOWED_UPLOAD_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
}


def user_profile(user: models.User):
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname or "",
        "grade": user.grade or "",
        "major": user.major or "",
        "avatar": user.avatar or "",
    }


def get_user_by_username(username: str, db: Session):
    username = username.strip()

    if not username:
        raise HTTPException(status_code=401, detail="请先登录")

    user = db.query(models.User).filter(models.User.username == username).first()

    if not user:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")

    return user


def get_username_from_upload(username: str | None, authorization: str | None):
    if username:
        return username

    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "", 1).strip()

    return ""


def get_or_create_chat_session(
    db: Session,
    user_id: int,
    conversation_id: int | None,
    title_source: str,
    course: str | None = None,
):
    if conversation_id is not None:
        chat_session = (
            db.query(models.ChatSession)
            .filter(
                models.ChatSession.id == conversation_id,
                models.ChatSession.user_id == user_id,
            )
            .first()
        )

        if not chat_session:
            raise HTTPException(status_code=404, detail="聊天记录不存在")

        return chat_session

    title = title_source.strip() or "文件问答"
    if len(title) > 30:
        title = title[:30] + "..."

    chat_session = models.ChatSession(
        user_id=user_id,
        title=title,
        course=course or "文件问答",
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return chat_session


def save_chat_pair(
    db: Session,
    user_id: int,
    session_id: int,
    user_content: str,
    answer: str,
):
    db.add(
        models.ChatMessage(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=user_content,
        )
    )
    db.add(
        models.ChatMessage(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=answer,
        )
    )
    db.commit()


def extract_pdf_text(file_bytes: bytes):
    try:
        reader = PdfReader(BytesIO(file_bytes))
        text_parts = []

        for page in reader.pages[:10]:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text.strip())

            current_text = "\n\n".join(text_parts)
            if len(current_text) >= MAX_PDF_CHARS:
                return current_text[:MAX_PDF_CHARS]

        return "\n\n".join(text_parts)[:MAX_PDF_CHARS]
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF 无法解析，请换一个文件重试") from exc


def extract_image_text(image_bytes: bytes) -> str:
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=400,
            detail="图片无法识别，请上传清晰的 PNG、JPG 或 WEBP 图片",
        ) from exc

    try:
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="服务器 OCR 组件未安装，请联系管理员安装 tesseract-ocr",
        ) from exc
    except pytesseract.TesseractError:
        try:
            text = pytesseract.image_to_string(image, lang="eng")
        except pytesseract.pytesseract.TesseractNotFoundError as exc:
            raise HTTPException(
                status_code=500,
                detail="服务器 OCR 组件未安装，请联系管理员安装 tesseract-ocr",
            ) from exc
        except pytesseract.TesseractError as exc:
            raise HTTPException(
                status_code=500,
                detail="服务器 OCR 识别失败，请稍后重试",
            ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="图片无法识别，请上传清晰的 PNG、JPG 或 WEBP 图片",
        ) from exc

    return (text or "").strip()[:MAX_OCR_CHARS]


def build_system_prompt(course: str | None, user_profile: dict | None = None, is_pdf: bool = False):
    normalized_course = (course or "").strip()
    profile = user_profile or {}
    grade = profile.get("grade") or "未填写"
    major = profile.get("major") or "未填写"

    course_roles = {
        "Java": """
课程身份：你是 Java 编程助教。
回答重点：
- 多解释 Java 语法、类、对象、封装、继承、多态、异常、集合等。
- 代码示例优先使用 Java。
- 遇到报错时，说明错误原因、修改位置、修改代码、测试方式。
""",
        "Python": """
课程身份：你是 Python 学习助教。
回答重点：
- 代码示例优先使用 Python。
- 多解释变量、函数、类、包、虚拟环境、依赖安装等。
- 遇到代码问题时，给出可运行的小例子。
""",
        "数据结构": """
课程身份：你是数据结构助教。
回答重点：
- 多解释解题思路、时间复杂度、空间复杂度和边界情况。
- 必要时给伪代码，或给 Java/Python 示例。
""",
        "数据库": """
课程身份：你是数据库课程助教。
回答重点：
- 多给 SQL 示例、表结构设计、查询思路和事务/索引解释。
- 讲清楚表、字段、主键、外键、约束之间的关系。
""",
        "软件工程": """
课程身份：你是软件工程助教。
回答重点：
- 多结合需求分析、UML、类图、用例、项目流程解释。
- 遇到项目问题时，说明需求、设计、实现、测试之间的关系。
""",
    }

    course_instruction = course_roles.get(
        normalized_course,
        f"""
课程身份：你是通用 AI 学习助手。
当前课程：{normalized_course or "未选择"}。
回答时根据问题内容选择合适的讲解方式。
""",
    )

    pdf_instruction = """
PDF 问答要求：
- 必须基于 PDF 内容回答。
- 如果 PDF 内容中没有答案，要明确说明“PDF 内容中没有找到相关信息”，不要编造。
- 如果用户要求总结 PDF，按以下结构输出：
  1. 文档主题
  2. 核心知识点
  3. 重点概念
  4. 复习建议
  5. 可能考点
""" if is_pdf else ""

    return f"""
你是一个面向大学生的 AI 学习助手，不是普通闲聊机器人。

用户资料：
- 年级：{grade}
- 专业：{major}
- 当前课程：{normalized_course or "未选择"}

{course_instruction}

通用回答原则：
- 先给结论，再解释原因。
- 用适合大学生理解的语言。
- 遇到专业概念，先讲人话，再讲术语。
- 遇到代码问题，说明应该改哪里、为什么改、如何测试。
- 遇到学习问题，给清晰步骤。
- 不确定时不要编造。
- 回答尽量结构化，使用 Markdown 标题、列表、代码块。

默认结构可以参考：
1. 结论
2. 解释
3. 示例
4. 易错点 / 建议

不要机械套模板。如果用户只是简单问候，可以简短自然回复。

{pdf_instruction}
"""



@app.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    username = user.username.strip()
    password = user.password.strip()

    if not username:
        raise HTTPException(status_code=400, detail="账号不能为空")

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 位")

    existing_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="账号已存在")

    new_user = models.User(
        username=user.username,
        hashed_password=hash_password(user.password),
        nickname="",
        avatar="",
        grade="",
        major=""
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "注册成功",
        "user": user_profile(new_user)
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
        "user": user_profile(db_user)
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
        "user": user_profile(db_user)
    }


@app.get("/me/profile")
def get_profile(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    return {"profile": user_profile(user)}


@app.put("/me/profile")
def update_profile(
    req: ProfileUpdateRequest,
    username: str,
    db: Session = Depends(get_db)
):
    user = get_user_by_username(username, db)

    nickname = (req.nickname or "").strip()
    grade = (req.grade or "").strip()
    major = (req.major or "").strip()
    avatar = (req.avatar or "").strip()

    if len(nickname) > 30:
        nickname = nickname[:30]

    if len(grade) > 20:
        grade = grade[:20]

    if len(major) > 50:
        major = major[:50]

    if avatar and avatar not in ALLOWED_AVATARS:
        raise HTTPException(status_code=400, detail="头像无效")

    user.nickname = nickname
    user.grade = grade
    user.major = major
    user.avatar = avatar

    db.commit()
    db.refresh(user)

    return {"profile": user_profile(user)}



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

    system_prompt = build_system_prompt(
        course=req.course,
        user_profile={
            "grade": req.grade,
            "major": req.major,
        },
    )

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


@app.post("/chat/upload")
async def upload_chat_file(
    file: UploadFile = File(...),
    message: str = Form(""),
    conversation_id: int | None = Form(None),
    course: str = Form(""),
    username: str | None = Form(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    upload_username = get_username_from_upload(username, authorization)

    if not upload_username:
        raise HTTPException(status_code=401, detail="请先登录后再上传文件")

    user = db.query(models.User).filter(models.User.username == upload_username).first()

    if not user:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")

    file_bytes = await file.read()

    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="文件不能超过 10MB")

    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail="文件类型不支持")

    clean_message = message.strip()
    selected_course = course.strip()
    file_name = file.filename or "未命名文件"
    user_content = f"上传文件：{file_name}"
    if clean_message:
        user_content += f"\n问题：{clean_message}"

    chat_session = get_or_create_chat_session(
        db=db,
        user_id=user.id,
        conversation_id=conversation_id,
        title_source=clean_message or file_name or "文件问答",
        course=selected_course or "文件问答",
    )

    if file.content_type.startswith("image/"):
        ocr_text = extract_image_text(file_bytes)

        if not ocr_text.strip():
            answer = "这张图片没有识别到清晰文字，可能是图片太模糊、手写内容较多，或不是文字型图片。请尝试上传更清晰的截图。"
            save_chat_pair(db, user.id, chat_session.id, user_content, answer)
            return {
                "answer": answer,
                "session": {
                    "id": chat_session.id,
                    "title": chat_session.title,
                    "course": chat_session.course,
                    "created_at": chat_session.created_at,
                },
            }

        image_user_content = (
            f"{user_content}\nOCR识别内容：\n{ocr_text[:2000]}"
        )
        image_prompt = f"""
用户上传了一张图片，以下是 OCR 从图片中识别到的文字内容：

【图片 OCR 内容开始】
{ocr_text}
【图片 OCR 内容结束】

用户问题：
{clean_message or "请根据图片中识别出的文字进行讲解。"}

请基于图片中识别出的文字回答。
如果图片文字中没有足够信息，请明确说明。
如果图片内容像题目，请按“答案、思路、易错点”解释。
如果图片内容像代码或报错，请按“问题原因、修改建议、示例代码、测试方法”解释。
不要编造图片中没有的信息。
"""

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": build_system_prompt(
                            course=selected_course,
                            user_profile=user_profile(user),
                        ),
                    },
                    {"role": "user", "content": image_prompt},
                ],
            )
            answer = response.choices[0].message.content
        except Exception as exc:
            raise HTTPException(status_code=500, detail="后端处理图片失败，请稍后重试") from exc

        save_chat_pair(db, user.id, chat_session.id, image_user_content, answer)
        return {
            "answer": answer,
            "session": {
                "id": chat_session.id,
                "title": chat_session.title,
                "course": chat_session.course,
                "created_at": chat_session.created_at,
            },
        }

    pdf_text = extract_pdf_text(file_bytes)

    if not pdf_text.strip():
        answer = "这个 PDF 没有提取到可读文本，可能是扫描件或图片型 PDF。"
        save_chat_pair(db, user.id, chat_session.id, user_content, answer)
        return {
            "answer": answer,
            "session": {
                "id": chat_session.id,
                "title": chat_session.title,
                "course": chat_session.course,
                "created_at": chat_session.created_at,
            },
        }

    prompt = f"""
用户上传了一个 PDF 文件，以下是从文件中提取的内容：

【PDF 内容开始】
{pdf_text}
【PDF 内容结束】

用户问题：
{clean_message or "请总结这个 PDF 的主要内容。"}

请基于 PDF 内容回答。如果 PDF 内容中没有答案，请明确说明，不要编造。
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": build_system_prompt(
                        course=selected_course,
                        user_profile=user_profile(user),
                        is_pdf=True,
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        answer = response.choices[0].message.content
    except Exception as exc:
        raise HTTPException(status_code=500, detail="后端处理文件失败，请稍后重试") from exc

    save_chat_pair(db, user.id, chat_session.id, user_content, answer)

    return {
        "answer": answer,
        "session": {
            "id": chat_session.id,
            "title": chat_session.title,
            "course": chat_session.course,
            "created_at": chat_session.created_at,
        },
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
