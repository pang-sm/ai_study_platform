import json
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
from sqlalchemy import or_
from sqlalchemy.orm import Session

from course_workbench import (
    COURSE_PROGRESS_STATUSES,
    build_course_progress,
    calculate_progress_percent,
    get_course_roadmap,
    normalize_progress_status,
)
import models
import schemas
from auth import hash_password, verify_password
from database import Base, engine, get_db, init_user_profile_schema, update_conversation_title
from prompts import build_system_prompt
from rag import reindex_materials, replace_material_chunks, search_relevant_material_chunks, soft_delete_material_chunks
from subjects import normalize_subject

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

ALLOWED_RECORD_TYPES = {
    "wrong_question",
    "important",
    "review",
}

ALLOWED_REVIEW_STATUSES = {
    "pending",
    "reviewed",
}


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


class CreateLearningRecordRequest(BaseModel):
    username: str
    subject: str
    session_id: int | None = None
    message_id: int | None = None
    record_type: str
    question: str
    answer: str
    references: list[dict] | None = None
    note: str | None = None
    tags: list[str] | None = None


class UpdateLearningRecordRequest(BaseModel):
    note: str | None = None
    tags: list[str] | None = None
    review_status: str | None = None


class CourseProgressUpdateRequest(BaseModel):
    username: str
    course: str
    knowledge_point: str
    status: str


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
    references = []
    if message.reference_payload:
        try:
            references = json.loads(message.reference_payload)
        except json.JSONDecodeError:
            references = []

    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "attachment_type": message.attachment_type,
        "attachment_filename": message.attachment_filename,
        "attachment_path": message.attachment_path,
        "extracted_text": message.extracted_text,
        "material_id": message.material_id,
        "references": references,
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
        "filename": item.get("source_filename") or "",
        "subject": item.get("subject") or "",
        "file_type": item.get("file_type") or "",
        "snippet": item.get("chunk_text") or "",
        "chunk_summary": item.get("chunk_summary") or "",
        "keywords": item.get("keywords") or "",
        "score": item.get("score") or 0,
        "created_at": item.get("created_at"),
    }


def serialize_reference_item(item: dict):
    snippet = (item.get("chunk_text") or item.get("chunk_summary") or "").strip()
    if len(snippet) > 220:
        snippet = snippet[:220].rstrip() + "..."

    return {
        "material_id": item["material_id"],
        "filename": item.get("source_filename") or "",
        "subject": item.get("subject") or "",
        "file_type": item.get("file_type") or "",
        "snippet": snippet,
        "score": round(float(item.get("score") or 0), 4),
        "created_at": item.get("created_at"),
    }


def normalize_record_type(record_type: str) -> str:
    normalized = (record_type or "").strip()
    if normalized not in ALLOWED_RECORD_TYPES:
        raise HTTPException(status_code=400, detail="学习记录类型无效")
    return normalized


def normalize_review_status(review_status: str | None, default: str = "pending") -> str:
    normalized = (review_status or "").strip() or default
    if normalized not in ALLOWED_REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail="复习状态无效")
    return normalized


def normalize_learning_record_tags(tags: list[str] | None) -> list[str]:
    normalized_tags: list[str] = []
    for tag in tags or []:
        clean_tag = (tag or "").strip()
        if clean_tag and clean_tag not in normalized_tags:
            normalized_tags.append(clean_tag[:30])
    return normalized_tags[:12]


def serialize_learning_record(record: models.LearningRecord):
    references = []
    tags = []

    if record.references_json:
        try:
            references = json.loads(record.references_json)
        except json.JSONDecodeError:
            references = []

    if record.tags:
        try:
            tags = json.loads(record.tags)
        except json.JSONDecodeError:
            tags = [item.strip() for item in record.tags.split(",") if item.strip()]

    return {
        "id": record.id,
        "user_id": record.user_id,
        "subject": record.subject,
        "session_id": record.session_id,
        "message_id": record.message_id,
        "record_type": record.record_type,
        "question": record.question,
        "answer": record.answer,
        "references": references,
        "note": record.note or "",
        "tags": tags,
        "review_status": record.review_status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "reviewed_at": record.reviewed_at,
    }


def serialize_course_progress(record: models.CourseProgress):
    return {
        "id": record.id,
        "course": record.course,
        "knowledge_point": record.knowledge_point,
        "status": record.status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def get_saved_course_progress_map(db: Session, username: str, course: str):
    records = (
        db.query(models.CourseProgress)
        .filter(
            models.CourseProgress.username == username,
            models.CourseProgress.course == course,
        )
        .order_by(models.CourseProgress.updated_at.desc(), models.CourseProgress.id.desc())
        .all()
    )

    saved_statuses: dict[str, str] = {}
    for record in records:
        if record.knowledge_point not in saved_statuses:
            saved_statuses[record.knowledge_point] = normalize_progress_status(record.status)
    return saved_statuses


def build_course_dashboard_payload(db: Session, user: models.User, course: str):
    normalized_course = normalize_subject(course)

    material_query = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.username == user.username,
        models.StudyMaterial.subject == normalized_course,
        models.StudyMaterial.is_deleted.is_(False),
    )
    materials_count = material_query.count()
    pdf_count = material_query.filter(models.StudyMaterial.file_type == "pdf").count()
    image_count = material_query.filter(models.StudyMaterial.file_type == "image").count()
    recent_materials = (
        material_query.order_by(models.StudyMaterial.created_at.desc()).limit(3).all()
    )

    chat_query = db.query(models.ChatSession).filter(
        models.ChatSession.user_id == user.id,
        or_(
            models.ChatSession.subject == normalized_course,
            models.ChatSession.course == normalized_course,
        ),
    )
    chat_count = chat_query.count()
    recent_chats = chat_query.order_by(models.ChatSession.created_at.desc()).limit(5).all()

    pending_review_count = 0
    recent_record_at = None
    try:
        pending_review_count = (
            db.query(models.LearningRecord)
            .filter(
                models.LearningRecord.user_id == user.id,
                models.LearningRecord.subject == normalized_course,
                models.LearningRecord.is_deleted.is_(False),
                models.LearningRecord.review_status == "pending",
            )
            .count()
        )
        recent_record = (
            db.query(models.LearningRecord)
            .filter(
                models.LearningRecord.user_id == user.id,
                models.LearningRecord.subject == normalized_course,
                models.LearningRecord.is_deleted.is_(False),
            )
            .order_by(models.LearningRecord.updated_at.desc(), models.LearningRecord.created_at.desc())
            .first()
        )
        recent_record_at = (
            recent_record.updated_at if recent_record and recent_record.updated_at else recent_record.created_at if recent_record else None
        )
    except Exception:
        pending_review_count = 0
        recent_record_at = None

    saved_progress_map = get_saved_course_progress_map(db, user.username, normalized_course)
    progress = build_course_progress(normalized_course, saved_progress_map)
    progress_percent = calculate_progress_percent(progress)

    latest_progress = (
        db.query(models.CourseProgress)
        .filter(
            models.CourseProgress.username == user.username,
            models.CourseProgress.course == normalized_course,
        )
        .order_by(models.CourseProgress.updated_at.desc(), models.CourseProgress.created_at.desc())
        .first()
    )

    latest_candidates = [
        recent_materials[0].created_at if recent_materials else None,
        recent_chats[0].created_at if recent_chats else None,
        recent_record_at,
        latest_progress.updated_at if latest_progress else None,
    ]
    recent_learning_at = max((item for item in latest_candidates if item is not None), default=None)

    if materials_count == 0:
        suggestion = "建议先上传课程资料，方便 AI 结合你的个人资料回答。"
    elif chat_count == 0:
        suggestion = "建议先从一个基础问题开始提问，建立这门课的学习上下文。"
    elif pending_review_count > 0:
        suggestion = "建议优先复习待复习内容，再继续围绕薄弱点提问。"
    else:
        suggestion = "建议继续围绕薄弱知识点提问，并结合资料库做针对性复习。"

    return {
        "success": True,
        "course": normalized_course,
        "stats": {
            "materials_count": materials_count,
            "pdf_count": pdf_count,
            "image_count": image_count,
            "chat_count": chat_count,
            "pending_review_count": pending_review_count,
            "progress_percent": progress_percent,
        },
        "recent_learning_at": recent_learning_at,
        "recent_materials": [serialize_material_list_item(item) for item in recent_materials],
        "recent_chats": [serialize_session(item) for item in recent_chats],
        "progress": progress,
        "roadmap": get_course_roadmap(normalized_course),
        "suggestion": suggestion,
        "progress_status_options": list(COURSE_PROGRESS_STATUSES),
    }


def find_duplicate_learning_record(
    db: Session,
    user_id: int,
    message_id: int | None,
    record_type: str,
    question: str,
    answer: str,
    session_id: int | None = None,
):
    query = db.query(models.LearningRecord).filter(
        models.LearningRecord.user_id == user_id,
        models.LearningRecord.record_type == record_type,
        models.LearningRecord.is_deleted.is_(False),
    )

    if message_id is not None:
        return query.filter(models.LearningRecord.message_id == message_id).first()

    compact_question = question.strip()
    compact_answer = answer.strip()
    if not compact_question or not compact_answer:
        return None

    return query.filter(
        models.LearningRecord.session_id == session_id,
        models.LearningRecord.question == compact_question,
        models.LearningRecord.answer == compact_answer,
    ).first()


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
    references: list[dict] = []
    assistant_message = None

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
            references = [serialize_reference_item(item) for item in rag_chunks]
            answer = call_deepseek(
                [
                    {
                        "role": "system",
                        "content": build_system_prompt(
                            normalized_subject,
                            clean_question,
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

            assistant_message = models.ChatMessage(
                user_id=user.id,
                session_id=chat_session.id,
                role="assistant",
                content=answer,
                reference_payload=json.dumps(references, ensure_ascii=False)
                if references
                else None,
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)

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
        "references": references,
        "assistant_message_id": assistant_message.id if assistant_message else None,
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

    user_message = models.ChatMessage(
        user_id=user.id,
        session_id=chat_session.id,
        role="user",
        content=req.message,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    rag_chunks = []
    if subject:
        rag_chunks = search_relevant_material_chunks(
            username=user.username,
            subject=subject,
            question=req.message,
            top_k=TOP_K_CHUNKS,
        )

    system_prompt = build_system_prompt(
        subject,
        req.message,
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
    references = [serialize_reference_item(item) for item in rag_chunks]

    assistant_message = models.ChatMessage(
        user_id=user.id,
        session_id=chat_session.id,
        role="assistant",
        content=answer,
        reference_payload=json.dumps(references, ensure_ascii=False) if references else None,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return {
        "answer": answer,
        "references": references,
        "assistant_message_id": assistant_message.id,
        "user_message_id": user_message.id,
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
            subject=normalize_subject(req.subject, default="") or None,
            force=req.force,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="资料索引重建失败，请稍后重试") from exc

    return {
        "indexed_material_count": indexed_material_count,
        "indexed_chunk_count": indexed_chunk_count,
    }


@app.get("/materials/search")
def search_materials(
    username: str,
    q: str,
    subject: str = "",
    top_k: int = 8,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    keyword = (q or "").strip()
    normalized_subject = normalize_subject(subject, default="")

    if not keyword:
        return {"chunks": []}

    results = search_relevant_material_chunks(
        username=user.username,
        subject=normalized_subject or None,
        question=keyword,
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

    normalized_subject = normalize_subject(subject, default="")
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


@app.post("/learning-records")
def create_learning_record(req: CreateLearningRecordRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    normalized_subject = normalize_subject(req.subject)
    record_type = normalize_record_type(req.record_type)
    question = (req.question or "").strip()
    answer = (req.answer or "").strip()
    tags = normalize_learning_record_tags(req.tags)

    if not question:
        raise HTTPException(status_code=400, detail="问题内容不能为空")
    if not answer:
        raise HTTPException(status_code=400, detail="回答内容不能为空")

    duplicate_record = find_duplicate_learning_record(
        db=db,
        user_id=user.id,
        message_id=req.message_id,
        record_type=record_type,
        question=question,
        answer=answer,
        session_id=req.session_id,
    )
    if duplicate_record:
        return {
            "success": True,
            "duplicated": True,
            "message": "已添加过",
            "record": serialize_learning_record(duplicate_record),
        }

    note = (req.note or "").strip()
    review_status = "pending"
    reviewed_at = None

    learning_record = models.LearningRecord(
        user_id=user.id,
        subject=normalized_subject,
        session_id=req.session_id,
        message_id=req.message_id,
        record_type=record_type,
        question=question,
        answer=answer,
        references_json=json.dumps(req.references or [], ensure_ascii=False)
        if req.references is not None
        else None,
        note=note,
        tags=json.dumps(tags, ensure_ascii=False) if tags else None,
        review_status=review_status,
        reviewed_at=reviewed_at,
        is_deleted=False,
    )
    db.add(learning_record)
    db.commit()
    db.refresh(learning_record)

    return {
        "success": True,
        "duplicated": False,
        "message": "学习记录已保存",
        "record": serialize_learning_record(learning_record),
    }


@app.get("/learning-records")
def get_learning_records(
    username: str,
    subject: str = "",
    record_type: str = "",
    review_status: str = "",
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    query = db.query(models.LearningRecord).filter(
        models.LearningRecord.user_id == user.id,
        models.LearningRecord.is_deleted.is_(False),
    )

    normalized_subject = normalize_subject(subject, default="")
    normalized_record_type = (record_type or "").strip()
    normalized_review_status = (review_status or "").strip()

    if normalized_subject:
        query = query.filter(models.LearningRecord.subject == normalized_subject)
    if normalized_record_type:
        query = query.filter(models.LearningRecord.record_type == normalize_record_type(normalized_record_type))
    if normalized_review_status:
        query = query.filter(
            models.LearningRecord.review_status == normalize_review_status(normalized_review_status)
        )

    records = query.order_by(models.LearningRecord.created_at.desc()).all()
    return {"records": [serialize_learning_record(record) for record in records]}


@app.get("/learning-records/stats")
def get_learning_record_stats(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    records = (
        db.query(models.LearningRecord)
        .filter(
            models.LearningRecord.user_id == user.id,
            models.LearningRecord.is_deleted.is_(False),
        )
        .order_by(models.LearningRecord.created_at.desc())
        .all()
    )

    subject_counts: dict[str, int] = {}
    wrong_question_count = 0
    important_count = 0
    review_count = 0
    reviewed_count = 0

    for record in records:
        subject_counts[record.subject] = subject_counts.get(record.subject, 0) + 1
        if record.record_type == "wrong_question":
            wrong_question_count += 1
        elif record.record_type == "important":
            important_count += 1
        elif record.record_type == "review":
            review_count += 1

        if record.review_status == "reviewed":
            reviewed_count += 1

    return {
        "wrong_question_count": wrong_question_count,
        "important_count": important_count,
        "review_count": review_count,
        "reviewed_count": reviewed_count,
        "pending_review_count": len(records) - reviewed_count,
        "subject_counts": subject_counts,
    }


@app.patch("/learning-records/{record_id}")
def update_learning_record(
    record_id: int,
    req: UpdateLearningRecordRequest,
    username: str,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    record = (
        db.query(models.LearningRecord)
        .filter(
            models.LearningRecord.id == record_id,
            models.LearningRecord.user_id == user.id,
            models.LearningRecord.is_deleted.is_(False),
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="学习记录不存在")

    if req.note is not None:
        record.note = (req.note or "").strip()
    if req.tags is not None:
        tags = normalize_learning_record_tags(req.tags)
        record.tags = json.dumps(tags, ensure_ascii=False) if tags else None
    if req.review_status is not None:
        next_status = normalize_review_status(req.review_status)
        record.review_status = next_status
        record.reviewed_at = datetime.utcnow() if next_status == "reviewed" else None

    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)

    return {"success": True, "record": serialize_learning_record(record)}


@app.delete("/learning-records/{record_id}")
def delete_learning_record(record_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    record = (
        db.query(models.LearningRecord)
        .filter(
            models.LearningRecord.id == record_id,
            models.LearningRecord.user_id == user.id,
            models.LearningRecord.is_deleted.is_(False),
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="学习记录不存在")

    record.is_deleted = True
    record.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "学习记录已删除", "record_id": record.id}


@app.get("/course-progress")
def get_course_progress(username: str, course: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    normalized_course = normalize_subject(course)
    progress = build_course_progress(
        normalized_course,
        get_saved_course_progress_map(db, user.username, normalized_course),
    )
    return {
        "success": True,
        "course": normalized_course,
        "progress": progress,
        "progress_percent": calculate_progress_percent(progress),
        "status_options": list(COURSE_PROGRESS_STATUSES),
    }


@app.patch("/course-progress")
def update_course_progress(req: CourseProgressUpdateRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    normalized_course = normalize_subject(req.course)
    knowledge_point = (req.knowledge_point or "").strip()
    raw_status = (req.status or "").strip()
    roadmap = get_course_roadmap(normalized_course)

    if knowledge_point not in roadmap:
        raise HTTPException(status_code=400, detail="知识点不属于当前课程")
    if raw_status not in COURSE_PROGRESS_STATUSES:
        raise HTTPException(status_code=400, detail="知识点状态无效")

    next_status = normalize_progress_status(raw_status)

    record = (
        db.query(models.CourseProgress)
        .filter(
            models.CourseProgress.username == user.username,
            models.CourseProgress.course == normalized_course,
            models.CourseProgress.knowledge_point == knowledge_point,
        )
        .first()
    )

    if record:
        record.status = next_status
        record.updated_at = datetime.utcnow()
    else:
        record = models.CourseProgress(
            username=user.username,
            course=normalized_course,
            knowledge_point=knowledge_point,
            status=next_status,
        )
        db.add(record)

    db.commit()
    db.refresh(record)

    progress = build_course_progress(
        normalized_course,
        get_saved_course_progress_map(db, user.username, normalized_course),
    )
    return {
        "success": True,
        "item": serialize_course_progress(record),
        "progress": progress,
        "progress_percent": calculate_progress_percent(progress),
    }


@app.get("/course-dashboard")
def get_course_dashboard(username: str, course: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    return build_course_dashboard_payload(db, user, course)


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
