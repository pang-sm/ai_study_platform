import os
import re
import secrets
from datetime import datetime
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from pypdf import PdfReader
import pytesseract
from sqlalchemy.orm import Session

import models
import schemas
from auth import hash_password, verify_password
from database import Base, engine, get_db, init_user_profile_schema, update_conversation_title
from rag import reindex_materials, replace_material_chunks, search_relevant_material_chunks, soft_delete_material_chunks

load_dotenv()

app = FastAPI()

Base.metadata.create_all(bind=engine)
init_user_profile_schema()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = BASE_DIR / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
MAX_PDF_CHARS = 12000
MAX_OCR_CHARS = 12000
MAX_HISTORY_EXTRACT_CHARS = 4000
TOP_K_CHUNKS = 4

ALLOWED_UPLOAD_TYPES = {
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
}

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

ALLOWED_AVATARS = {
    "avatar_1",
    "avatar_2",
    "avatar_3",
    "avatar_4",
    "avatar_5",
    "avatar_6",
}

SUBJECT_OPTIONS = [
    "Python",
    "Java",
    "数据结构",
    "计算机网络",
    "操作系统",
    "数据库",
    "前端开发",
    "后端开发",
    "算法",
]


class MeRequest(BaseModel):
    username: str


class RenameConversationRequest(BaseModel):
    title: str


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    grade: str | None = None
    major: str | None = None
    avatar: str | None = None


class AddMaterialFromMessageRequest(BaseModel):
    username: str
    message_id: int
    subject: str


class ReindexMaterialsRequest(BaseModel):
    username: str
    subject: str | None = None
    force: bool = False


def user_profile(user: models.User):
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname or "",
        "grade": user.grade or "",
        "major": user.major or "",
        "avatar": user.avatar or "",
    }


def normalize_subject(subject: str | None = None, course: str | None = None, default: str = "通用学习") -> str:
    normalized = (subject or course or "").strip()
    return normalized or default


def get_user_by_username(username: str, db: Session):
    normalized_username = (username or "").strip()
    if not normalized_username:
        raise HTTPException(status_code=401, detail="请先登录")

    user = db.query(models.User).filter(models.User.username == normalized_username).first()
    if not user:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")

    return user


def get_username_from_upload(username: str | None, authorization: str | None):
    if username and username.strip():
        return username.strip()

    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "", 1).strip()

    return ""


def sanitize_filename(filename: str) -> str:
    original = os.path.basename(filename or "material")
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", original)
    return cleaned[:120] or "material"


def validate_upload(file: UploadFile, file_bytes: bytes):
    suffix = Path(file.filename or "").suffix.lower()
    expected_content_type = ALLOWED_EXTENSIONS.get(suffix)

    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="文件不能超过 10MB")

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 png、jpg、jpeg、webp、pdf 文件")

    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail="文件类型不支持")

    if expected_content_type != file.content_type and not (
        expected_content_type == "image/jpeg" and file.content_type == "image/jpg"
    ):
        raise HTTPException(status_code=400, detail="文件扩展名与类型不匹配")


def save_uploaded_file(username: str, original_filename: str, file_bytes: bytes) -> str:
    user_dir = UPLOAD_ROOT / username
    user_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(original_filename)
    stored_name = f"{secrets.token_hex(8)}_{safe_name}"
    file_path = user_dir / stored_name

    with open(file_path, "wb") as output:
        output.write(file_bytes)

    return str(file_path.relative_to(BASE_DIR)).replace("\\", "/")


def extract_pdf_text(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(file_bytes))
        text_parts: list[str] = []

        for page in reader.pages[:15]:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                text_parts.append(page_text)

            current_text = "\n\n".join(text_parts)
            if len(current_text) >= MAX_PDF_CHARS:
                return current_text[:MAX_PDF_CHARS]

        return "\n\n".join(text_parts)[:MAX_PDF_CHARS].strip()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF 解析失败，请确认文件未损坏") from exc


def extract_image_text(image_bytes: bytes) -> str:
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="图片无法识别，请上传清晰的 PNG、JPG 或 WEBP 图片") from exc

    try:
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise HTTPException(status_code=500, detail="服务器未安装 OCR 组件 tesseract-ocr") from exc
    except pytesseract.TesseractError:
        try:
            text = pytesseract.image_to_string(image, lang="eng")
        except pytesseract.pytesseract.TesseractNotFoundError as exc:
            raise HTTPException(status_code=500, detail="服务器未安装 OCR 组件 tesseract-ocr") from exc
        except pytesseract.TesseractError as exc:
            raise HTTPException(status_code=500, detail="OCR 识别失败，请稍后重试") from exc

    return (text or "").strip()[:MAX_OCR_CHARS]


def build_system_prompt(
    subject: str | None,
    user_profile_data: dict | None = None,
    is_pdf: bool = False,
    rag_chunks: list[dict] | None = None,
):
    normalized_subject = normalize_subject(subject)
    profile = user_profile_data or {}
    grade = profile.get("grade") or "未填写"
    major = profile.get("major") or "未填写"

    subject_roles = {
        "Java": "你是 Java 学习助教，优先给出 Java 代码示例，并解释语法、类、对象、异常和集合。",
        "Python": "你是 Python 学习助教，优先用 Python 示例解释变量、函数、类、模块和调试思路。",
        "数据结构": "你是数据结构助教，重点解释解题思路、复杂度、边界情况和结构设计。",
        "数据库": "你是数据库课程助教，重点给出 SQL 示例、表结构设计和索引/事务解释。",
        "计算机网络": "你是计算机网络助教，重点解释分层、协议作用和真实通信流程。",
        "操作系统": "你是操作系统助教，重点解释进程、线程、调度、内存和文件系统。",
        "前端开发": "你是前端开发助教，重点结合 HTML、CSS、JavaScript 和 React 实践回答。",
        "后端开发": "你是后端开发助教，重点结合接口、数据库、业务逻辑和错误处理回答。",
        "算法": "你是算法助教，按照题意、思路、步骤、代码、复杂度来组织答案。",
    }

    subject_instruction = subject_roles.get(
        normalized_subject,
        f"你是通用 AI 学习助手，当前学科是 {normalized_subject}，请根据问题选择合适的讲解方式。",
    )

    rag_context_text = ""
    if rag_chunks:
        blocks = []
        for index, item in enumerate(rag_chunks, start=1):
            blocks.append(
                f"【资料片段 {index}】\n来源文件：{item['source_filename']}\n内容：{item['chunk_text']}"
            )

        rag_context_text = (
            "\n以下是从用户个人学习资料库中检索到的相关资料片段。"
            "请优先参考这些资料回答，但不要编造资料中不存在的内容。\n\n"
            + "\n\n".join(blocks)
            + "\n\n回答要求：\n"
            + "1. 优先结合资料片段回答。\n"
            + "2. 如果资料中没有直接说明，请明确说“资料中没有直接提到”，然后再用通用知识补充。\n"
            + "3. 回答要适合学生理解，尽量分步骤。\n"
            + "4. 如果使用了资料背景，回答末尾加“参考资料：文件名1、文件名2”。\n"
            + "5. 不要透露系统内部检索逻辑。\n"
            + "6. 不要把所有资料原文重复输出。\n"
        )

    no_material_hint = (
        "\n如果当前学科没有相关资料片段，就正常回答，并可简短提示用户在个人主页上传该学科资料以增强回答。"
    )

    pdf_instruction = ""
    if is_pdf:
        pdf_instruction = (
            "\nPDF 问答要求：必须基于 PDF 提取内容回答。"
            "如果内容中没有答案，要明确说明“PDF 内容中没有找到相关信息”，不要编造。"
        )

    return f"""
你是一个面向大学生的 AI 学习助手。

用户资料：
- 年级：{grade}
- 专业：{major}
- 当前学科：{normalized_subject}

学科身份：
{subject_instruction}

通用回答原则：
- 先给结论，再解释原因。
- 尽量结构化输出，必要时使用标题、列表、代码块。
- 概念先讲人话，再讲术语。
- 不确定时不要编造。
- 如果涉及代码或排错，要说明问题原因、修改建议和测试方法。
{rag_context_text}
{no_material_hint}
{pdf_instruction}
""".strip()


def call_deepseek(messages: list[dict]):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="AI 服务调用失败，请稍后重试") from exc


def summarize_material(subject: str, extracted_text: str):
    preview = extracted_text[:5000]
    prompt = f"""
请为以下学习资料生成一段简短摘要，要求：
1. 使用中文。
2. 80 到 180 字。
3. 说明主题、核心知识点、适合复习的方向。
4. 不要输出标题，不要编造文中没有的信息。

学科：{subject}
资料文本：
{preview}
""".strip()

    return call_deepseek(
        [
            {
                "role": "system",
                "content": "你是学习资料摘要助手，输出简洁、准确、便于复习的中文摘要。",
            },
            {"role": "user", "content": prompt},
        ]
    )


def build_material_question_prompt(file_type: str, extracted_text: str, question: str):
    label = "OCR识别文本" if file_type == "image" else "PDF提取文本"
    default_question = "请根据资料内容做简要讲解和总结。"

    return f"""
用户上传了一份学习资料，以下是提取出的文本：

【{label}开始】
{extracted_text}
【{label}结束】

用户问题：
{question or default_question}

请严格基于以上资料内容回答。
如果资料里没有足够信息，请明确说明“资料内容中没有找到相关信息”。
""".strip()


def serialize_session(chat_session: models.ChatSession):
    session_subject = normalize_subject(chat_session.subject, chat_session.course)
    return {
        "id": chat_session.id,
        "title": chat_session.title,
        "course": chat_session.course or session_subject,
        "subject": session_subject,
        "created_at": chat_session.created_at,
    }


def serialize_message(message: models.ChatMessage):
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "attachment_type": message.attachment_type,
        "attachment_filename": message.attachment_filename,
        "attachment_path": message.attachment_path,
        "extracted_text": message.extracted_text,
        "material_id": message.material_id,
        "created_at": message.created_at,
    }


def serialize_material_list_item(material: models.StudyMaterial):
    return {
        "id": material.id,
        "subject": material.subject,
        "file_type": material.file_type,
        "original_filename": material.original_filename,
        "summary": material.summary,
        "created_at": material.created_at,
        "source_message_id": material.source_message_id,
    }


def serialize_material_detail(material: models.StudyMaterial):
    return {
        "id": material.id,
        "username": material.username,
        "subject": material.subject,
        "file_type": material.file_type,
        "original_filename": material.original_filename,
        "file_path": material.file_path,
        "extracted_text": material.extracted_text,
        "summary": material.summary,
        "source_message_id": material.source_message_id,
        "created_at": material.created_at,
    }


def serialize_chunk_search_item(item: dict):
    return {
        "material_id": item["material_id"],
        "chunk_id": item["chunk_id"],
        "source_filename": item["source_filename"],
        "chunk_text": item["chunk_text"],
        "chunk_summary": item["chunk_summary"],
        "keywords": item["keywords"],
        "score": item["score"],
    }


def get_or_create_chat_session(
    db: Session,
    user_id: int,
    conversation_id: int | None,
    title_source: str,
    subject: str,
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
            raise HTTPException(status_code=404, detail="历史对话不存在")

        if not (chat_session.subject or "").strip():
            chat_session.subject = subject
        if not (chat_session.course or "").strip():
            chat_session.course = subject
        db.commit()
        db.refresh(chat_session)
        return chat_session

    title = (title_source or "").strip() or "资料问答"
    if len(title) > 30:
        title = title[:30] + "..."

    chat_session = models.ChatSession(
        user_id=user_id,
        title=title,
        course=subject,
        subject=subject,
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return chat_session


def create_material_from_message(
    db: Session,
    user: models.User,
    message: models.ChatMessage,
    subject: str,
):
    normalized_subject = normalize_subject(subject)
    if normalized_subject == "通用学习":
        raise HTTPException(status_code=400, detail="加入资料库时必须选择学科")

    if not message.attachment_path or not (message.extracted_text or "").strip():
        raise HTTPException(status_code=400, detail="该消息没有可加入资料库的附件内容")

    existing_material = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.source_message_id == message.id,
            models.StudyMaterial.is_deleted.is_(False),
        )
        .first()
    )
    if existing_material:
        if message.material_id != existing_material.id:
            message.material_id = existing_material.id
            db.commit()
        return existing_material, False

    summary = summarize_material(normalized_subject, message.extracted_text)
    material = models.StudyMaterial(
        username=user.username,
        subject=normalized_subject,
        file_type=message.attachment_type or "image",
        original_filename=message.attachment_filename or "未命名附件",
        file_path=message.attachment_path,
        extracted_text=message.extracted_text or "",
        summary=summary,
        source_message_id=message.id,
        is_deleted=False,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    replace_material_chunks(db, material)

    message.material_id = material.id
    db.commit()
    db.refresh(message)
    return material, True


def create_attachment_user_message_content(subject: str, original_filename: str, file_type: str, question: str, extracted_text: str):
    label = "OCR识别文本" if file_type == "image" else "PDF提取文本"
    content = [
        f"上传资料：{original_filename}",
        f"学科：{subject}",
        f"文件类型：{file_type}",
    ]
    if question:
        content.append(f"问题：{question}")
    content.append(f"{label}：\n{extracted_text[:MAX_HISTORY_EXTRACT_CHARS]}")
    return "\n".join(content)


async def handle_material_upload(
    db: Session,
    username: str,
    subject: str,
    file: UploadFile,
    question: str = "",
    conversation_id: int | None = None,
    save_to_materials: bool = False,
):
    user = get_user_by_username(username, db)
    normalized_subject = normalize_subject(subject)

    if normalized_subject == "通用学习":
        raise HTTPException(status_code=400, detail="上传资料时必须选择学科")

    file_bytes = await file.read()
    validate_upload(file, file_bytes)

    original_filename = file.filename or "未命名文件"
    file_type = ALLOWED_UPLOAD_TYPES[file.content_type]
    extracted_text = extract_image_text(file_bytes) if file_type == "image" else extract_pdf_text(file_bytes)

    if not extracted_text.strip():
        if file_type == "pdf":
            raise HTTPException(status_code=400, detail="未能从 PDF 提取到可读文本，扫描版 PDF 暂未支持")
        raise HTTPException(status_code=400, detail="未能从图片识别到文字，请上传更清晰的图片")

    stored_file_path = save_uploaded_file(user.username, original_filename, file_bytes)
    clean_question = (question or "").strip()

    chat_session = None
    user_message = None
    answer = None
    created_material = None

    if conversation_id is not None or clean_question:
        chat_session = get_or_create_chat_session(
            db=db,
            user_id=user.id,
            conversation_id=conversation_id,
            title_source=clean_question or original_filename,
            subject=normalized_subject,
        )

        user_message = models.ChatMessage(
            user_id=user.id,
            session_id=chat_session.id,
            role="user",
            content=create_attachment_user_message_content(
                subject=normalized_subject,
                original_filename=original_filename,
                file_type=file_type,
                question=clean_question,
                extracted_text=extracted_text,
            ),
            attachment_type=file_type,
            attachment_filename=original_filename,
            attachment_path=stored_file_path,
            extracted_text=extracted_text,
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)

        if clean_question:
            rag_chunks = search_relevant_material_chunks(
                username=user.username,
                subject=normalized_subject,
                question=clean_question,
                top_k=TOP_K_CHUNKS,
            )
            answer = call_deepseek(
                [
                    {
                        "role": "system",
                        "content": build_system_prompt(
                            normalized_subject,
                            user_profile(user),
                            is_pdf=file_type == "pdf",
                            rag_chunks=rag_chunks,
                        ),
                    },
                    {
                        "role": "user",
                        "content": build_material_question_prompt(file_type, extracted_text, clean_question),
                    },
                ]
            )

            db.add(
                models.ChatMessage(
                    user_id=user.id,
                    session_id=chat_session.id,
                    role="assistant",
                    content=answer,
                )
            )
            db.commit()

    if save_to_materials:
        target_message = user_message
        if target_message is None:
            temp_session = get_or_create_chat_session(
                db=db,
                user_id=user.id,
                conversation_id=None,
                title_source=original_filename,
                subject=normalized_subject,
            )
            target_message = models.ChatMessage(
                user_id=user.id,
                session_id=temp_session.id,
                role="user",
                content=create_attachment_user_message_content(
                    subject=normalized_subject,
                    original_filename=original_filename,
                    file_type=file_type,
                    question=clean_question,
                    extracted_text=extracted_text,
                ),
                attachment_type=file_type,
                attachment_filename=original_filename,
                attachment_path=stored_file_path,
                extracted_text=extracted_text,
            )
            db.add(target_message)
            db.commit()
            db.refresh(target_message)
            if chat_session is None:
                chat_session = temp_session

        created_material, _ = create_material_from_message(
            db=db,
            user=user,
            message=target_message,
            subject=normalized_subject,
        )
        user_message = target_message

    return {
        "material": serialize_material_detail(created_material) if created_material else None,
        "answer": answer,
        "session": serialize_session(chat_session) if chat_session else None,
        "message": serialize_message(user_message) if user_message else None,
        "extracted_text_preview": extracted_text[:2000],
    }


@app.get("/")
def root():
    return {"message": "AI Study Platform Backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    username = user.username.strip()
    password = user.password.strip()

    if not username:
        raise HTTPException(status_code=400, detail="账号不能为空")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 位")

    existing_user = db.query(models.User).filter(models.User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="账号已存在")

    new_user = models.User(
        username=username,
        hashed_password=hash_password(password),
        nickname="",
        avatar="",
        grade="",
        major="",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "注册成功", "user": user_profile(new_user)}


@app.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    username = user.username.strip()
    password = user.password.strip()

    if not username:
        raise HTTPException(status_code=400, detail="账号不能为空")
    if not password:
        raise HTTPException(status_code=400, detail="密码不能为空")

    db_user = db.query(models.User).filter(models.User.username == username).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="账号不存在")
    if not verify_password(password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="密码错误")

    return {"message": "登录成功", "user": user_profile(db_user)}


@app.post("/me")
def me(req: MeRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    return {"user": user_profile(user)}


@app.get("/me/profile")
def get_profile(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    return {"profile": user_profile(user)}


@app.put("/me/profile")
def update_profile(req: ProfileUpdateRequest, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)

    nickname = (req.nickname or "").strip()[:30]
    grade = (req.grade or "").strip()[:20]
    major = (req.major or "").strip()[:50]
    avatar = (req.avatar or "").strip()

    if avatar and avatar not in ALLOWED_AVATARS:
        raise HTTPException(status_code=400, detail="头像无效")

    user.nickname = nickname
    user.grade = grade
    user.major = major
    user.avatar = avatar
    db.commit()
    db.refresh(user)

    return {"profile": user_profile(user)}


@app.post("/chat")
def chat(req: schemas.ChatRequest, db: Session = Depends(get_db)):
    if not req.username:
        raise HTTPException(status_code=401, detail="请先登录后再使用 AI 聊天")

    user = get_user_by_username(req.username, db)
    subject = normalize_subject(req.subject, req.course)

    if req.session_id is not None:
        chat_session = (
            db.query(models.ChatSession)
            .filter(
                models.ChatSession.id == req.session_id,
                models.ChatSession.user_id == user.id,
            )
            .first()
        )
        if not chat_session:
            raise HTTPException(status_code=404, detail="Chat session not found")

        if not (chat_session.subject or "").strip():
            chat_session.subject = subject
        if not (chat_session.course or "").strip():
            chat_session.course = subject
        db.commit()
        db.refresh(chat_session)
        subject = normalize_subject(chat_session.subject, chat_session.course)
    else:
        title = req.message.strip() or "新对话"
        if len(title) > 30:
            title = title[:30] + "..."

        chat_session = models.ChatSession(
            user_id=user.id,
            title=title,
            course=subject,
            subject=subject,
        )
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)

    db.add(
        models.ChatMessage(
            user_id=user.id,
            session_id=chat_session.id,
            role="user",
            content=req.message,
        )
    )
    db.commit()

    rag_chunks = []
    if subject and subject != "通用学习":
        rag_chunks = search_relevant_material_chunks(
            username=user.username,
            subject=subject,
            question=req.message,
            top_k=TOP_K_CHUNKS,
        )

    system_prompt = build_system_prompt(
        subject,
        {
            "grade": req.grade or user.grade,
            "major": req.major or user.major,
        },
        rag_chunks=rag_chunks,
    )

    answer = call_deepseek(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.message},
        ]
    )

    db.add(
        models.ChatMessage(
            user_id=user.id,
            session_id=chat_session.id,
            role="assistant",
            content=answer,
        )
    )
    db.commit()

    return {
        "answer": answer,
        "session": serialize_session(chat_session),
        "rag_sources": sorted({item["source_filename"] for item in rag_chunks}),
    }


@app.post("/chat/upload")
async def upload_chat_file(
    file: UploadFile = File(...),
    message: str = Form(""),
    conversation_id: int | None = Form(None),
    course: str = Form(""),
    subject: str = Form(""),
    username: str | None = Form(None),
    save_to_materials: bool = Form(False),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    upload_username = get_username_from_upload(username, authorization)
    if not upload_username:
        raise HTTPException(status_code=401, detail="请先登录后再上传文件")

    return await handle_material_upload(
        db=db,
        username=upload_username,
        subject=normalize_subject(subject, course),
        file=file,
        question=message,
        conversation_id=conversation_id,
        save_to_materials=save_to_materials,
    )


@app.post("/materials/upload")
async def upload_material(
    file: UploadFile = File(...),
    username: str = Form(...),
    subject: str = Form(...),
    question: str = Form(""),
    conversation_id: int | None = Form(None),
    save_to_materials: bool = Form(False),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    upload_username = get_username_from_upload(username, authorization)
    if not upload_username:
        raise HTTPException(status_code=401, detail="请先登录后再上传文件")

    return await handle_material_upload(
        db=db,
        username=upload_username,
        subject=subject,
        file=file,
        question=question,
        conversation_id=conversation_id,
        save_to_materials=save_to_materials,
    )


@app.post("/materials/add-from-message")
def add_material_from_message(req: AddMaterialFromMessageRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    message = (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.id == req.message_id,
            models.ChatMessage.user_id == user.id,
        )
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="聊天消息不存在")

    material, created = create_material_from_message(
        db=db,
        user=user,
        message=message,
        subject=req.subject,
    )

    return {
        "message": "加入资料库成功" if created else "该附件已在资料库中",
        "material_id": material.id,
        "material": serialize_material_list_item(material),
        "created": created,
    }


@app.post("/materials/reindex")
def reindex_user_materials(req: ReindexMaterialsRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)

    try:
        indexed_material_count, indexed_chunk_count = reindex_materials(
            db=db,
            username=user.username,
            subject=(req.subject or "").strip() or None,
            force=req.force,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="资料索引重建失败，请稍后重试") from exc

    return {
        "indexed_material_count": indexed_material_count,
        "indexed_chunk_count": indexed_chunk_count,
    }


@app.get("/materials/search")
def search_materials(username: str, subject: str, q: str, top_k: int = 4, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    normalized_subject = normalize_subject(subject)

    if normalized_subject == "通用学习":
        raise HTTPException(status_code=400, detail="检索资料时必须提供学科")

    results = search_relevant_material_chunks(
        username=user.username,
        subject=normalized_subject,
        question=q,
        top_k=top_k,
    )

    return {"chunks": [serialize_chunk_search_item(item) for item in results]}


@app.get("/materials")
def get_materials(username: str, subject: str | None = None, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    query = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.username == user.username,
        models.StudyMaterial.is_deleted.is_(False),
    )

    normalized_subject = (subject or "").strip()
    if normalized_subject:
        query = query.filter(models.StudyMaterial.subject == normalized_subject)

    materials = query.order_by(models.StudyMaterial.created_at.desc()).all()
    return {"materials": [serialize_material_list_item(material) for material in materials]}


@app.get("/materials/{material_id}")
def get_material_detail(material_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    material = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.id == material_id,
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.is_deleted.is_(False),
        )
        .first()
    )

    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    return {"material": serialize_material_detail(material)}


@app.delete("/materials/{material_id}")
def delete_material(material_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    material = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.id == material_id,
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.is_deleted.is_(False),
        )
        .first()
    )

    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    material.is_deleted = True
    material.deleted_at = datetime.utcnow()
    db.commit()
    soft_delete_material_chunks(db, material.id)

    return {"message": "资料已删除", "material_id": material.id}


@app.get("/chat/history")
def get_chat_history(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)

    sessions = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.user_id == user.id)
        .order_by(models.ChatSession.created_at.desc())
        .all()
    )

    return {"sessions": [serialize_session(session) for session in sessions]}


@app.get("/chat/sessions/{session_id}")
def get_chat_session_messages(session_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)

    chat_session = (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.id == session_id,
            models.ChatSession.user_id == user.id,
        )
        .first()
    )
    if not chat_session:
        raise HTTPException(status_code=404, detail="聊天记录不存在")

    messages = (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.session_id == session_id,
            models.ChatMessage.user_id == user.id,
        )
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )

    return {
        "session": serialize_session(chat_session),
        "messages": [serialize_message(msg) for msg in messages],
    }


@app.delete("/chat/sessions/{session_id}")
def delete_chat_session(session_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)

    chat_session = (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.id == session_id,
            models.ChatSession.user_id == user.id,
        )
        .first()
    )
    if not chat_session:
        raise HTTPException(status_code=404, detail="聊天记录不存在")

    db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id,
        models.ChatMessage.user_id == user.id,
    ).delete()

    db.delete(chat_session)
    db.commit()

    return {
        "message": "聊天记录删除成功",
        "deleted_session_id": session_id,
    }


@app.put("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    req: RenameConversationRequest,
    username: str,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)

    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    if len(title) > 50:
        title = title[:50]

    conversation = update_conversation_title(
        db=db,
        user_id=user.id,
        conversation_id=conversation_id,
        title=title,
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="历史对话不存在")

    return {"message": "重命名成功", "title": conversation.title}
