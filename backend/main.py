import json
import logging
import os
import re
import secrets
import subprocess
import tempfile
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import fitz
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
from database import Base, SessionLocal, engine, get_db, init_user_profile_schema, update_conversation_title
from prompts import build_system_prompt
from qwen_parser import (
    SCANNED_PDF_PAGE_PROMPT,
    get_qwen_pdf_ocr_model,
    get_qwen_parse_max_pages,
    get_qwen_status_payload,
    parse_image_with_qwen,
)
from rag import (
    reindex_materials,
    replace_material_chunks,
    retrieve_chunks_for_materials,
    search_relevant_material_chunks,
    soft_delete_material_chunks,
)
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

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = BASE_DIR / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
MATERIAL_UPLOAD_ROOT = UPLOAD_ROOT / "materials"
MATERIAL_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
MAX_PDF_CHARS = 12000
MAX_OCR_CHARS = 12000
MAX_HISTORY_EXTRACT_CHARS = 4000
TOP_K_CHUNKS = 4
MIN_QWEN_CHINESE_CHARS = 30
MIN_QWEN_ALNUM_CHARS = 80
MIN_PDF_AVG_PAGE_CHARS = 120
DEFAULT_LOCAL_PDF_SYNC_MAX_PAGES = 200
DEFAULT_PDF_OCR_RENDER_DPI = 150
DEFAULT_PDF_OCR_IMAGE_FORMAT = "jpeg"
DEFAULT_PDF_OCR_JPEG_QUALITY = 80
DEFAULT_PDF_OCR_MAX_IMAGE_SIDE = 1600
DEFAULT_PDF_OCR_CONCURRENCY = 2
DEFAULT_PDF_OCR_PAGE_TIMEOUT_SECONDS = 45

ALLOWED_UPLOAD_TYPES = {
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "text",
    "text/markdown": "text",
    "text/x-python": "code",
    "text/x-java": "code",
    "text/x-c": "code",
    "text/x-c++": "code",
    "text/javascript": "code",
    "text/html": "code",
    "text/css": "code",
    "application/json": "code",
    "text/xml": "code",
    "application/xml": "code",
    "text/x-sh": "code",
    "text/x-sql": "code",
    "application/x-yaml": "code",
    "text/yaml": "code",
    "text/x-go": "code",
    "text/x-php": "code",
    "text/x-ruby": "code",
}

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".py": "text/x-python",
    ".java": "text/x-java",
    ".c": "text/x-c",
    ".cpp": "text/x-c++",
    ".h": "text/x-c",
    ".hpp": "text/x-c++",
    ".js": "text/javascript",
    ".jsx": "text/javascript",
    ".ts": "text/javascript",
    ".tsx": "text/javascript",
    ".html": "text/html",
    ".htm": "text/html",
    ".css": "text/css",
    ".json": "application/json",
    ".xml": "application/xml",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
    ".sql": "text/x-sql",
    ".sh": "text/x-sh",
    ".bash": "text/x-sh",
    ".go": "text/x-go",
    ".rs": "text/x-rust",
    ".php": "text/x-php",
    ".rb": "text/x-ruby",
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
    learning_goals: list[dict] | None = None
    onboarding_completed: bool | None = None


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


AVATAR_UPLOAD_ROOT = UPLOAD_ROOT / "avatars"
AVATAR_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_AVATAR_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

MAX_AVATAR_SIZE = 3 * 1024 * 1024


def user_profile(user: models.User):
    avatar_id = (user.avatar or "").strip()
    avatar_url = None
    if avatar_id:
        if avatar_id in ALLOWED_AVATARS:
            avatar_url = avatar_id
        else:
            avatar_url = f"/me/avatar/{avatar_id}"

    learning_goals = []
    if user.learning_goals:
        try:
            learning_goals = json.loads(user.learning_goals)
        except (json.JSONDecodeError, TypeError):
            learning_goals = []

    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname or "",
        "grade": user.grade or "",
        "major": user.major or "",
        "avatar": user.avatar or "",
        "avatar_url": avatar_url,
        "onboarding_completed": bool(user.onboarding_completed),
        "learning_goals": learning_goals,
        "is_admin": bool(user.is_admin),
        "plan": user.plan or "free",
    }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_datetime(value):
    if not value:
        return None
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return None
        if text_value.endswith("Z") or re.search(r"[+-]\d{2}:\d{2}$", text_value):
            return text_value
        return f"{text_value}Z"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def parse_optional_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d")
            except ValueError:
                return None
    return None


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
    from document_parser import detect_material_type, MAX_NEW_TYPE_SIZE, LEGACY_EXTENSIONS

    suffix = Path(file.filename or "").suffix.lower()
    expected_content_type = ALLOWED_EXTENSIONS.get(suffix)
    material_type = detect_material_type(file.filename or "", file.content_type)

    if suffix in LEGACY_EXTENSIONS:
        raise HTTPException(status_code=400, detail=LEGACY_EXTENSIONS[suffix])

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="不支持该文件格式，仅支持 PDF、图片、Word(docx)、PPT(pptx)、TXT、Markdown 和常见代码文件。",
        )

    if material_type in ("DOCX", "PPTX", "TEXT", "CODE"):
        size_limit = MAX_NEW_TYPE_SIZE
    else:
        size_limit = MAX_UPLOAD_SIZE

    if len(file_bytes) > size_limit:
        limit_mb = size_limit // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"文件过大，当前类型最大支持 {limit_mb}MB，请压缩或拆分后上传。")

    if material_type in ("TEXT", "CODE") and suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".docx", ".pptx"}:
        return

    if file.content_type not in ALLOWED_UPLOAD_TYPES and not (
        material_type in ("TEXT", "CODE")
    ):
        if material_type not in ("PDF", "IMAGE", "DOCX", "PPTX"):
            raise HTTPException(status_code=400, detail="文件类型不支持")

    if expected_content_type and expected_content_type != file.content_type and not (
        expected_content_type == "image/jpeg" and file.content_type == "image/jpg"
    ):
        if material_type not in ("TEXT", "CODE", "DOCX", "PPTX"):
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


def calculate_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def safe_file_extension(filename: str) -> str:
    suffix = Path(os.path.basename(filename or "")).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="文件扩展名不支持")
    return suffix


def save_material_file(file_bytes: bytes, original_filename: str, file_hash: str) -> str:
    suffix = safe_file_extension(original_filename)
    safe_hash = re.sub(r"[^a-fA-F0-9]", "", file_hash or "").lower()
    if len(safe_hash) != 64:
        raise HTTPException(status_code=400, detail="文件哈希无效")

    MATERIAL_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    file_path = MATERIAL_UPLOAD_ROOT / f"{safe_hash}{suffix}"
    if not file_path.exists():
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


def get_pdf_total_pages(file_bytes: bytes) -> int:
    try:
        reader = PdfReader(BytesIO(file_bytes))
        return len(reader.pages)
    except Exception:
        return 0


def extract_pdf_pages(file_bytes: bytes) -> tuple[int, list[dict]]:
    fitz_error = None
    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
        page_texts: list[dict] = []
        total_pages = len(document)
        for page_index in range(total_pages):
            try:
                page_text = (document.load_page(page_index).get_text("text") or "").strip()
            except Exception:
                page_text = ""
            if page_text:
                page_texts.append({"page": page_index + 1, "text": page_text})
        document.close()
        if page_texts:
            return total_pages, page_texts
    except Exception as exc:
        fitz_error = exc
        try:
            document.close()
        except Exception:
            pass

    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF 解析失败，请确认文件未损坏") from (fitz_error or exc)

    page_texts: list[dict] = []
    total_pages = len(reader.pages)
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            page_text = (page.extract_text() or "").strip()
        except Exception:
            page_text = ""
        if page_text:
            page_texts.append({"page": page_index, "text": page_text})
    return total_pages, page_texts


def build_pdf_text_from_pages(page_texts: list[dict]) -> str:
    text_parts = []
    for page_item in page_texts:
        page_number = page_item.get("page")
        page_text = (page_item.get("text") or "").strip()
        if page_text:
            text_parts.append(f"【第 {page_number} 页】\n{page_text}")
    return "\n\n".join(text_parts).strip()


def should_use_qwen_for_pdf(extracted_text: str, total_pages: int) -> bool:
    cleaned = (extracted_text or "").strip()
    if not cleaned:
        return True

    if total_pages > 0:
        return len(cleaned) / total_pages < MIN_PDF_AVG_PAGE_CHARS

    return False


def render_pdf_pages_to_images(file_bytes: bytes, max_pages: int) -> list[str]:
    image_paths: list[str] = []
    document = None
    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = min(len(document), max_pages)
        for page_index in range(page_count):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            temp_file = tempfile.NamedTemporaryFile(
                suffix=f"_page_{page_index + 1}.png",
                delete=False,
            )
            temp_path = temp_file.name
            temp_file.close()
            pixmap.save(temp_path)
            image_paths.append(temp_path)
    except Exception as exc:
        logger.warning("[QWEN] PDF render failed, error=%s", str(exc)[:120])
        for image_path in image_paths:
            try:
                Path(image_path).unlink(missing_ok=True)
            except OSError:
                pass
        return []
    finally:
        if document is not None:
            document.close()

    return image_paths


def parse_scanned_pdf_with_qwen(file_bytes: bytes) -> dict:
    max_pages = get_qwen_parse_max_pages()
    image_paths = render_pdf_pages_to_images(file_bytes, max_pages)
    page_texts: dict[int, str] = {}
    errors: list[str] = []
    success_pages = 0
    failed_pages = 0

    try:
        for page_index, image_path in enumerate(image_paths, start=1):
            result = parse_image_with_qwen(
                image_path,
                prompt=SCANNED_PDF_PAGE_PROMPT,
            )
            page_text = (result.get("extracted_text") or "").strip()
            if result.get("success") and page_text:
                success_pages += 1
                page_texts.append(f"第 {page_index} 页：\n{page_text}")
            else:
                failed_pages += 1
                errors.append(f"第 {page_index} 页解析失败：{result.get('error') or '未知错误'}")
    finally:
        for image_path in image_paths:
            try:
                Path(image_path).unlink(missing_ok=True)
            except OSError:
                pass

    return {
        "text": "\n\n".join(page_texts).strip()[:MAX_PDF_CHARS],
        "success_pages": success_pages,
        "failed_pages": failed_pages,
        "max_pages": max_pages,
        "rendered_pages": len(image_paths),
        "errors": errors,
    }


def merge_pdf_extracted_text(local_pdf_text: str, qwen_pdf_text: str) -> str:
    cleaned_local = (local_pdf_text or "").strip()
    cleaned_qwen = (qwen_pdf_text or "").strip()

    if not cleaned_local:
        return cleaned_qwen[:MAX_PDF_CHARS]
    if not cleaned_qwen:
        return cleaned_local[:MAX_PDF_CHARS]
    if cleaned_qwen in cleaned_local:
        return cleaned_local[:MAX_PDF_CHARS]
    if cleaned_local in cleaned_qwen:
        return cleaned_qwen[:MAX_PDF_CHARS]

    merged = f"{cleaned_local}\n\nQwen 视觉解析补充：\n{cleaned_qwen}"
    return merged[:MAX_PDF_CHARS]


def build_pdf_qwen_parse_error(pdf_result: dict, total_pages: int) -> str | None:
    notes: list[str] = []
    max_pages = pdf_result.get("max_pages") or get_qwen_parse_max_pages()
    if total_pages > max_pages:
        notes.append(f"扫描版 PDF 仅解析前 {max_pages} 页")

    failed_pages = int(pdf_result.get("failed_pages") or 0)
    if failed_pages:
        notes.append(f"失败页数：{failed_pages}")

    errors = pdf_result.get("errors") or []
    if errors:
        notes.append("; ".join(errors[:3]))

    return "；".join(notes) if notes else None


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


def count_chinese_characters(text_value: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text_value or ""))


def count_alnum_characters(text_value: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]", text_value or ""))


def should_use_qwen_for_image(local_ocr_text: str) -> bool:
    cleaned = (local_ocr_text or "").strip()
    if not cleaned:
        return True

    chinese_count = count_chinese_characters(cleaned)
    alnum_count = count_alnum_characters(cleaned)
    return chinese_count < MIN_QWEN_CHINESE_CHARS and alnum_count < MIN_QWEN_ALNUM_CHARS


def merge_image_extracted_text(local_ocr_text: str, qwen_text: str) -> str:
    cleaned_local = (local_ocr_text or "").strip()
    cleaned_qwen = (qwen_text or "").strip()

    if not cleaned_local:
        return cleaned_qwen[:MAX_OCR_CHARS]
    if not cleaned_qwen:
        return cleaned_local[:MAX_OCR_CHARS]
    if cleaned_qwen in cleaned_local:
        return cleaned_local[:MAX_OCR_CHARS]
    if cleaned_local in cleaned_qwen:
        return cleaned_qwen[:MAX_OCR_CHARS]

    merged = f"{cleaned_qwen}\n\n本地 OCR 补充：\n{cleaned_local}"
    return merged[:MAX_OCR_CHARS]


def get_default_parse_metadata():
    return {
        "extract_method": "local",
        "parse_status": "success",
        "parse_error": None,
        "qwen_used": False,
        "parsed_at": utc_now(),
    }


def resolve_stored_file_path(stored_file_path: str) -> Path:
    resolved_path = (BASE_DIR / (stored_file_path or "")).resolve()
    upload_root = UPLOAD_ROOT.resolve()
    if resolved_path != upload_root and upload_root not in resolved_path.parents:
        raise HTTPException(status_code=400, detail="文件存储路径无效")
    return resolved_path


def get_material_file_path(material: models.StudyMaterial) -> Path | None:
    if not (material.file_path or "").strip():
        return None

    try:
        file_path = resolve_stored_file_path(material.file_path)
    except HTTPException:
        return None

    if not file_path.exists() or not file_path.is_file():
        return None
    return file_path


def get_material_download_metadata(material: models.StudyMaterial):
    file_path = get_material_file_path(material)
    return {
        "can_download": file_path is not None,
        "download_url": f"/materials/{material.id}/download" if file_path else None,
    }


PREVIEWABLE_FILE_TYPES = frozenset({"pdf", "image", "txt", "text", "markdown", "code"})


def get_material_preview_metadata(material: models.StudyMaterial):
    file_path = get_material_file_path(material)
    file_type = (material.file_type or "").lower().strip()
    can_preview = file_path is not None and file_type in PREVIEWABLE_FILE_TYPES
    return {
        "can_preview": can_preview,
        "preview_url": f"/materials/{material.id}/preview" if can_preview else None,
    }


def call_deepseek(messages: list[dict]):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="AI 服务调用失败，请稍后重试") from exc


# ── Quota / Plan System ─────────────────────────────────

PLAN_LIMITS = {
    "free": {
        "chat": 30,
        "code_analyze": 10,
        "challenge_generate": 5,
        "learning_diagnosis": 3,
        "knowledge_generate": 3,
        "learning_plan_generate": 3,
        "material_link_recommend": 5,
        "question_generate": 10,
        "question_feedback": 10,
        "learning_report_generate": 3,
        "material_upload_count": 30,
        "single_file_size_mb": 20,
    },
    "pro": {
        "chat": 300,
        "code_analyze": 100,
        "challenge_generate": 50,
        "learning_diagnosis": 20,
        "knowledge_generate": 20,
        "learning_plan_generate": 20,
        "material_link_recommend": 50,
        "question_generate": 100,
        "question_feedback": 100,
        "learning_report_generate": 30,
        "material_upload_count": 500,
        "single_file_size_mb": 100,
    },
    "admin": {
        "chat": 999999,
        "code_analyze": 999999,
        "challenge_generate": 999999,
        "learning_diagnosis": 999999,
        "knowledge_generate": 999999,
        "learning_plan_generate": 999999,
        "material_link_recommend": 999999,
        "question_generate": 999999,
        "question_feedback": 999999,
        "learning_report_generate": 999999,
        "material_upload_count": 999999,
        "single_file_size_mb": 500,
    },
}

ALL_FEATURES = [
    "chat", "code_analyze", "challenge_generate", "learning_diagnosis",
    "knowledge_generate", "learning_plan_generate", "material_link_recommend",
    "question_generate", "question_feedback", "learning_report_generate",
]


def get_user_plan(username: str, db: Session):
    user = get_user_by_username(username, db)
    plan = (user.plan or "free").strip().lower()
    if plan not in ("free", "pro", "admin"):
        plan = "free"
    is_admin = bool(user.is_admin)
    if is_admin:
        plan = "admin"
    if plan == "pro" and user.plan_expire_at:
        from datetime import datetime, timezone
        if user.plan_expire_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            plan = "free"
    return {
        "plan": plan,
        "is_admin": is_admin,
        "plan_expire_at": serialize_datetime(user.plan_expire_at) if user.plan_expire_at else None,
    }


def get_plan_limits(plan: str):
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])


def get_today_usage(username: str, feature: str, db: Session):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    count = (
        db.query(models.AiUsageLog)
        .filter(
            models.AiUsageLog.username == username,
            models.AiUsageLog.feature == feature,
            models.AiUsageLog.status == "success",
            models.AiUsageLog.created_at >= today_start,
        )
        .count()
    )
    return count


def check_usage_limit(username: str, feature: str, db: Session):
    plan_info = get_user_plan(username, db)
    plan = plan_info["plan"]
    limits = get_plan_limits(plan)
    limit = limits.get(feature, 999999)
    used = get_today_usage(username, feature, db)
    remaining = max(0, limit - used)
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"今日 {feature} 使用次数已达上限（{used}/{limit}），请明天再试或升级会员。",
        )
    return {
        "allowed": True,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "plan": plan,
    }


def record_ai_usage(username: str, feature: str, db: Session, model: str = None,
                    estimated_tokens: int = 0, status: str = "success",
                    error_message: str = None):
    try:
        log = models.AiUsageLog(
            username=username,
            feature=feature,
            model=model or "deepseek-chat",
            estimated_tokens=estimated_tokens,
            estimated_cost=round(estimated_tokens * 0.000001, 6),
            status=status,
            error_message=error_message or "",
        )
        db.add(log)
        db.commit()
    except Exception:
        logger.warning(f"Failed to record AI usage for {username}/{feature}")


def estimate_tokens_from_text(text: str):
    if not text:
        return 0
    return max(1, len(text) // 2)


# ── Markdown post-processing: collapse stray single-term fenced code blocks ──

_COLLAPSIBLE_LANGS = frozenset({"", "text", "txt", "plain", "none", "nohighlight", "plaintext"})

_PRESERVED_LANGS = frozenset({
    "java", "python", "py", "c", "cpp", "c++", "bash", "sh", "zsh",
    "javascript", "js", "typescript", "ts", "json", "sql", "html", "css",
    "latex", "tex", "yaml", "yml", "xml", "rust", "rs", "go", "golang",
    "php", "ruby", "rb", "shell", "powershell", "ps1", "dockerfile",
    "toml", "ini", "conf", "makefile", "perl", "swift", "kotlin", "scala",
    "r", "matlab", "lua", "dart", "groovy", "haskell", "hs", "elixir",
    "clojure", "erlang", "markdown", "md", "diff", "patch", "nginx",
})

_CLI_COMMANDS = frozenset({
    "npm", "npx", "yarn", "pnpm", "git", "sudo", "pip", "pip3", "apt",
    "apt-get", "yum", "dnf", "brew", "docker", "kubectl", "systemctl",
    "journalctl", "curl", "wget", "ssh", "scp", "rsync", "make", "cmake",
    "gcc", "g++", "clang", "clang++", "node", "python", "python3",
    "java", "javac", "mvn", "gradle", "cargo", "rustc", "go",
})

_CODE_LINE_PATTERNS = [
    r"\bimport\s",
    r"\bclass\s",
    r"\bdef\s",
    r"\bfunction\s",
    r"\breturn\s",
    r"\bpublic\s",
    r"\bprivate\s",
    r"\bprotected\s",
    r"\bconst\s",
    r"\blet\s",
    r"\bvar\s",
    r"\bexport\s",
    r"\bpackage\s",
    r"#include",
    r"\brequire\s",
    r"\bfor\s*\(",
    r"\bwhile\s*\(",
    r"\bif\s*\(",
    r"\bswitch\s*\(",
    r"&&",
    r"\|\|",
    r"\bprint\s*\(",
    r"\becho\s",
    r"\bthrow\s",
    r"\bcatch\s*\(",
    r"\bnew\s+\w+\s*\(",
]

_CODE_LINE_RE = re.compile("|".join(_CODE_LINE_PATTERNS), re.IGNORECASE)

_FENCE_RE = re.compile(r"```(\w*)[ \t]*\r?\n(.*?)\r?\n[ \t]*```", re.DOTALL)


def _should_collapse(lang: str, content: str) -> bool:
    lang = lang.strip().lower()
    if lang in _PRESERVED_LANGS:
        return False
    if lang not in _COLLAPSIBLE_LANGS:
        return False

    stripped = content.strip()
    if not stripped:
        return False
    if "\n" in stripped:
        return False
    if len(stripped) > 40:
        return False
    if ";" in stripped or "{" in stripped or "}" in stripped:
        return False

    words = stripped.split()
    if len(words) >= 2 and words[0].lower() in _CLI_COMMANDS:
        return False

    if _CODE_LINE_RE.search(stripped):
        return False

    return True


def normalize_assistant_markdown(text: str) -> str:
    if not text:
        return text

    def _replace(match: re.Match) -> str:
        lang = match.group(1) or ""
        content = match.group(2)
        if _should_collapse(lang, content):
            return f"`{content.strip()}`"
        return match.group(0)

    return _FENCE_RE.sub(_replace, text)


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


FILE_TYPE_LABELS = {
    "image": "OCR识别文本",
    "pdf": "PDF提取文本",
    "docx": "Word文档提取文本",
    "pptx": "PPT提取文本",
    "text": "文本文件内容",
    "code": "代码文件内容",
}

TASK_TYPE_LABELS = {
    "read_material": "阅读资料",
    "ask_ai": "AI 问答",
    "code_practice": "代码练习",
    "challenge": "AI 出题练习",
    "review": "复习巩固",
    "custom": "自定义任务",
}

ALLOWED_TASK_TYPES = set(TASK_TYPE_LABELS.keys())
ALLOWED_TASK_STATUSES = {"todo", "doing", "done"}
ALLOWED_TASK_SOURCES = {"manual", "code_diagnosis", "course_plan", "system"}
ALLOWED_TASK_PRIORITIES = {"low", "medium", "high"}


def build_material_question_prompt(file_type: str, extracted_text: str, question: str):
    label = FILE_TYPE_LABELS.get(file_type, "资料提取文本")
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
    download_metadata = get_material_download_metadata(material)
    preview_metadata = get_material_preview_metadata(material)
    return {
        "id": material.id,
        "subject": material.subject,
        "file_type": material.file_type,
        "file_name": material.original_filename,
        "original_filename": material.original_filename,
        "mime_type": material.mime_type,
        "file_size": material.file_size or 0,
        "summary": material.summary,
        "extract_method": material.extract_method or "local",
        "parse_status": material.parse_status or "success",
        "parse_error": material.parse_error,
        "qwen_used": bool(material.qwen_used),
        "parse_progress": material.parse_progress or 0,
        "total_pages": material.total_pages or 0,
        "parsed_pages": material.parsed_pages or 0,
        "chunk_count": material.chunk_count or 0,
        "parsed_at": serialize_datetime(material.parsed_at),
        "parse_started_at": serialize_datetime(material.parse_started_at),
        "parse_completed_at": serialize_datetime(material.parse_completed_at),
        "created_at": serialize_datetime(material.created_at),
        "updated_at": serialize_datetime(material.updated_at),
        "source_message_id": material.source_message_id,
        **download_metadata,
        **preview_metadata,
    }


def serialize_material_detail(material: models.StudyMaterial):
    download_metadata = get_material_download_metadata(material)
    preview_metadata = get_material_preview_metadata(material)
    return {
        "id": material.id,
        "username": material.username,
        "subject": material.subject,
        "file_type": material.file_type,
        "file_name": material.original_filename,
        "original_filename": material.original_filename,
        "mime_type": material.mime_type,
        "file_size": material.file_size or 0,
        "extracted_text": material.extracted_text,
        "summary": material.summary,
        "extract_method": material.extract_method or "local",
        "parse_status": material.parse_status or "success",
        "parse_error": material.parse_error,
        "qwen_used": bool(material.qwen_used),
        "parse_progress": material.parse_progress or 0,
        "total_pages": material.total_pages or 0,
        "parsed_pages": material.parsed_pages or 0,
        "chunk_count": material.chunk_count or 0,
        "parsed_at": serialize_datetime(material.parsed_at),
        "parse_started_at": serialize_datetime(material.parse_started_at),
        "parse_completed_at": serialize_datetime(material.parse_completed_at),
        "source_message_id": material.source_message_id,
        "created_at": serialize_datetime(material.created_at),
        "updated_at": serialize_datetime(material.updated_at),
        **download_metadata,
        **preview_metadata,
    }


def serialize_material_status(material: models.StudyMaterial):
    return {
        "success": True,
        "material_id": material.id,
        "filename": material.original_filename,
        "file_type": material.file_type,
        "parse_status": material.parse_status or "success",
        "parse_progress": material.parse_progress or 0,
        "chunk_count": material.chunk_count or 0,
        "parse_error": material.parse_error,
        "total_pages": material.total_pages or 0,
        "parsed_pages": material.parsed_pages or 0,
        **get_material_download_metadata(material),
        **get_material_preview_metadata(material),
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
        "created_at": serialize_datetime(item.get("created_at")),
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


def make_json_safe(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return serialize_datetime(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


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

    code_query = db.query(models.CodeSession).filter(
        models.CodeSession.username == user.username,
        models.CodeSession.course_id == normalized_course,
    )
    code_sessions = code_query.order_by(models.CodeSession.updated_at.desc()).all()
    code_language_counts: dict[str, int] = {}
    challenge_count = 0
    for cs in code_sessions:
        code_language_counts[cs.language] = code_language_counts.get(cs.language, 0) + 1
        st = getattr(cs, "session_type", None)
        if st == "challenge":
            challenge_count += 1
    latest_code = code_sessions[0] if code_sessions else None
    latest_challenge_sessions = [cs for cs in code_sessions if getattr(cs, "session_type", None) == "challenge"][:1]

    # Count diagnosis-driven challenges
    challenge_ids = [
        getattr(cs, "challenge_id", None)
        for cs in code_sessions
        if getattr(cs, "session_type", None) == "challenge" and getattr(cs, "challenge_id", None)
    ]
    diagnosis_challenge_count = 0
    if challenge_ids:
        diagnosis_challenge_count = (
            db.query(models.CodeChallenge)
            .filter(
                models.CodeChallenge.id.in_(challenge_ids),
                models.CodeChallenge.source == "diagnosis",
            )
            .count()
        )

    code_progress = {
        "total": len(code_sessions),
        "language_counts": code_language_counts,
        "recent_title": latest_code.title if latest_code else None,
        "recent_language": latest_code.language if latest_code else None,
        "recent_updated_at": latest_code.updated_at if latest_code else None,
        "challenge_count": challenge_count,
        "recent_challenge_title": latest_challenge_sessions[0].title if latest_challenge_sessions else None,
        "diagnosis_challenge_count": diagnosis_challenge_count,
    }

    # Build task summary for this course
    task_query = db.query(models.LearningTask).filter(
        models.LearningTask.username == user.username,
        models.LearningTask.course_id == normalized_course,
    )
    task_total = task_query.count()
    task_todo = task_query.filter(models.LearningTask.status == "todo").count()
    task_doing = task_query.filter(models.LearningTask.status == "doing").count()
    task_done = task_query.filter(models.LearningTask.status == "done").count()
    recent_tasks = task_query.order_by(models.LearningTask.updated_at.desc()).limit(5).all()
    task_kp_ids = [getattr(t, "knowledge_point_id", None) for t in recent_tasks if getattr(t, "knowledge_point_id", None)]
    task_kp_map: dict[int, str] = {}
    if task_kp_ids:
        task_kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(task_kp_ids)).all()
        for kp in task_kps:
            task_kp_map[kp.id] = kp.title
    task_summary = {
        "total": task_total,
        "todo_count": task_todo,
        "doing_count": task_doing,
        "done_count": task_done,
        "recent_tasks": [serialize_learning_task(t, knowledge_point_title=task_kp_map.get(getattr(t, "knowledge_point_id", None))) for t in recent_tasks],
    }

    # Knowledge points summary
    kp_query = db.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == user.username,
        models.KnowledgePoint.course_id == normalized_course,
    )
    kp_total = kp_query.count()
    kp_progresses = db.query(models.UserKnowledgeProgress).filter(
        models.UserKnowledgeProgress.username == user.username,
        models.UserKnowledgeProgress.course_id == normalized_course,
    ).all()
    kp_progress_map = {p.knowledge_point_id: p for p in kp_progresses}
    kp_mastered = sum(1 for p in kp_progresses if (p.mastery_score or 0) >= 80)
    kp_learning = sum(1 for p in kp_progresses if p.status == "learning" or p.status == "doing")
    kp_scores = [p.mastery_score for p in kp_progresses if p.mastery_score is not None]
    kp_avg_mastery = round(sum(kp_scores) / len(kp_scores), 1) if kp_scores else 0
    knowledge_summary = {
        "total_points": kp_total,
        "mastered_count": kp_mastered,
        "learning_count": kp_learning,
        "average_mastery": kp_avg_mastery,
    }

    # Practice summary
    q_query = db.query(models.Question).filter(
        models.Question.username == user.username,
        models.Question.course_id == normalized_course,
    )
    q_total = q_query.count()
    q_choice = q_query.filter(models.Question.type == "choice").count()
    q_short = q_query.filter(models.Question.type == "short_answer").count()
    q_prog = q_query.filter(models.Question.type == "programming").count()
    a_query = db.query(models.QuestionAttempt).filter(
        models.QuestionAttempt.username == user.username,
        models.QuestionAttempt.course_id == normalized_course,
    )
    a_total = a_query.count()
    a_correct = a_query.filter(models.QuestionAttempt.self_result == "correct").count()
    recent_attempts = a_query.order_by(models.QuestionAttempt.created_at.desc()).limit(5).all()
    practice_summary = {
        "total_questions": q_total,
        "total_attempts": a_total,
        "choice_count": q_choice,
        "short_answer_count": q_short,
        "programming_count": q_prog,
        "correct_count": a_correct,
        "recent_attempts": [],
    }
    if recent_attempts:
        a_q_ids = [a.question_id for a in recent_attempts]
        a_q_map = {}
        if a_q_ids:
            a_qs = db.query(models.Question).filter(models.Question.id.in_(a_q_ids)).all()
            for q in a_qs:
                a_q_map[q.id] = q.title
        practice_summary["recent_attempts"] = [
            {
                "id": a.id,
                "question_id": a.question_id,
                "question_title": a_q_map.get(a.question_id, ""),
                "self_result": a.self_result,
                "created_at": serialize_datetime(a.created_at) if a.created_at else None,
            }
            for a in recent_attempts
        ]

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
        "code_progress": code_progress,
        "task_summary": task_summary,
        "knowledge_summary": knowledge_summary,
        "practice_summary": practice_summary,
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


def get_material_by_file_hash(db: Session, username: str, file_hash: str):
    normalized_username = (username or "").strip()
    normalized_hash = (file_hash or "").strip().lower()
    if not normalized_username or not normalized_hash:
        return None

    return (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.username == normalized_username,
            models.StudyMaterial.file_hash == normalized_hash,
            models.StudyMaterial.is_deleted.is_(False),
        )
        .order_by(models.StudyMaterial.created_at.desc())
        .first()
    )


def ensure_material_original_file(
    db: Session,
    material: models.StudyMaterial,
    file_bytes: bytes,
    original_filename: str,
    file_hash: str,
    mime_type: str | None,
):
    if get_material_file_path(material):
        return material

    stored_file_path = save_material_file(file_bytes, original_filename, file_hash)
    material.file_path = stored_file_path
    material.file_hash = (file_hash or "").strip().lower()
    material.mime_type = mime_type
    material.file_size = max(0, len(file_bytes or b""))
    db.commit()
    db.refresh(material)
    return material


def get_material_for_parsing(db: Session, material_id: int):
    return (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.id == material_id,
            models.StudyMaterial.is_deleted.is_(False),
        )
        .first()
    )


def create_pending_material(
    db: Session,
    username: str,
    subject: str,
    file_type: str,
    original_filename: str,
    file_path: str,
    file_hash: str,
    mime_type: str | None = None,
    file_size: int = 0,
    total_pages: int = 0,
    source_message_id: int | None = None,
):
    material = models.StudyMaterial(
        username=(username or "").strip(),
        subject=normalize_subject(subject),
        file_type=file_type,
        original_filename=os.path.basename(original_filename or "未命名文件"),
        mime_type=mime_type,
        file_size=max(0, int(file_size or 0)),
        file_hash=(file_hash or "").strip().lower(),
        file_path=file_path,
        extracted_text="",
        summary="资料已上传，等待后台解析。",
        source_message_id=source_message_id,
        extract_method=None,
        parse_status="pending",
        parse_error=None,
        qwen_used=False,
        parsed_at=None,
        total_pages=max(0, int(total_pages or 0)),
        parsed_pages=0,
        chunk_count=0,
        ocr_required=0,
        parse_progress=0,
        parse_started_at=None,
        parse_completed_at=None,
        is_deleted=False,
        created_at=utc_now(),
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def update_material_parse_state(db: Session, material_id: int, **updates):
    material = get_material_for_parsing(db, material_id)
    if not material:
        return None

    allowed_fields = {
        "file_path",
        "file_hash",
        "mime_type",
        "file_size",
        "parse_status",
        "parse_progress",
        "total_pages",
        "parsed_pages",
        "chunk_count",
        "ocr_required",
        "parse_error",
        "qwen_used",
        "extract_method",
        "parsed_at",
        "parse_started_at",
        "parse_completed_at",
        "extracted_text",
        "summary",
    }
    for field_name, field_value in updates.items():
        if field_name in allowed_fields:
            setattr(material, field_name, field_value)

    db.commit()
    db.refresh(material)
    return material


def is_pdf_text_usable(extracted_text: str, total_pages: int) -> bool:
    cleaned = (extracted_text or "").strip()
    if not cleaned:
        return False

    checked_pages = max(1, min(total_pages or 1, 15))
    return len(cleaned) / checked_pages >= MIN_PDF_AVG_PAGE_CHARS


def get_pdf_ocr_max_pages() -> int:
    raw_value = (os.getenv("PDF_OCR_MAX_PAGES") or "0").strip()
    try:
        value = int(raw_value)
        return value if value > 0 else 0
    except (TypeError, ValueError):
        return 0


def get_local_pdf_sync_max_pages() -> int:
    raw_value = (os.getenv("LOCAL_PDF_SYNC_MAX_PAGES") or str(DEFAULT_LOCAL_PDF_SYNC_MAX_PAGES)).strip()
    try:
        value = int(raw_value)
        return value if value > 0 else DEFAULT_LOCAL_PDF_SYNC_MAX_PAGES
    except (TypeError, ValueError):
        return DEFAULT_LOCAL_PDF_SYNC_MAX_PAGES


def get_int_env(name: str, default_value: int, min_value: int = 1) -> int:
    raw_value = (os.getenv(name) or str(default_value)).strip()
    try:
        value = int(raw_value)
        return value if value >= min_value else default_value
    except (TypeError, ValueError):
        return default_value


def get_pdf_ocr_render_dpi() -> int:
    return get_int_env("PDF_OCR_RENDER_DPI", DEFAULT_PDF_OCR_RENDER_DPI, min_value=72)


def get_pdf_ocr_image_format() -> str:
    image_format = (os.getenv("PDF_OCR_IMAGE_FORMAT") or DEFAULT_PDF_OCR_IMAGE_FORMAT).strip().lower()
    if image_format in {"jpg", "jpeg"}:
        return "jpeg"
    if image_format == "webp":
        return "webp"
    if image_format == "png":
        return "png"
    return DEFAULT_PDF_OCR_IMAGE_FORMAT


def get_pdf_ocr_jpeg_quality() -> int:
    return max(40, min(get_int_env("PDF_OCR_JPEG_QUALITY", DEFAULT_PDF_OCR_JPEG_QUALITY, min_value=1), 95))


def get_pdf_ocr_max_image_side() -> int:
    return get_int_env("PDF_OCR_MAX_IMAGE_SIDE", DEFAULT_PDF_OCR_MAX_IMAGE_SIDE, min_value=800)


def get_pdf_ocr_concurrency() -> int:
    return max(1, min(get_int_env("PDF_OCR_CONCURRENCY", DEFAULT_PDF_OCR_CONCURRENCY, min_value=1), 6))


def get_pdf_ocr_page_timeout_seconds() -> int:
    return get_int_env("PDF_OCR_PAGE_TIMEOUT_SECONDS", DEFAULT_PDF_OCR_PAGE_TIMEOUT_SECONDS, min_value=5)


def complete_material_with_local_pdf_text(
    db: Session,
    material: models.StudyMaterial,
    extracted_text: str,
    total_pages: int,
):
    now = utc_now()
    material = update_material_parse_state(
        db,
        material.id,
        extracted_text=extracted_text,
        summary=(extracted_text or "").strip()[:300] or "资料解析完成。",
        parse_status="parsing",
        parse_progress=80,
        total_pages=total_pages,
        parsed_pages=total_pages,
        ocr_required=0,
        qwen_used=False,
        extract_method="local",
        parse_started_at=serialize_datetime(now),
    )
    if not material:
        return None, 0

    chunk_count = replace_material_chunks(db, material)
    material = update_material_parse_state(
        db,
        material.id,
        parse_status="success",
        parse_progress=100,
        chunk_count=chunk_count,
        total_pages=total_pages,
        parsed_pages=total_pages,
        parse_error=None,
        ocr_required=0,
        qwen_used=False,
        extract_method="local",
        parsed_at=now,
        parse_completed_at=serialize_datetime(now),
    )
    return material, chunk_count


def render_pdf_page_to_temp_image(
    document,
    page_index: int,
    render_dpi: int,
    image_format: str,
    jpeg_quality: int,
    max_image_side: int,
) -> dict:
    render_started_at = time.perf_counter()
    zoom = render_dpi / 72
    page = document.load_page(page_index)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = Image.open(BytesIO(pixmap.tobytes("png")))
    image.load()
    width, height = image.size
    largest_side = max(width, height)
    if largest_side > max_image_side:
        scale = max_image_side / largest_side
        width = max(1, int(width * scale))
        height = max(1, int(height * scale))
        image = image.resize((width, height), Image.Resampling.LANCZOS)

    suffix = ".jpg" if image_format == "jpeg" else f".{image_format}"
    temp_file = tempfile.NamedTemporaryFile(
        suffix=f"_material_page_{page_index + 1}{suffix}",
        delete=False,
    )
    temp_path = temp_file.name
    temp_file.close()
    save_kwargs = {}
    if image_format == "jpeg":
        image = image.convert("RGB")
        save_kwargs = {"quality": jpeg_quality, "optimize": True}
        pil_format = "JPEG"
    elif image_format == "webp":
        image = image.convert("RGB")
        save_kwargs = {"quality": jpeg_quality, "method": 4}
        pil_format = "WEBP"
    else:
        pil_format = "PNG"
    image.save(temp_path, pil_format, **save_kwargs)
    image_size_bytes = Path(temp_path).stat().st_size
    return {
        "image_path": temp_path,
        "render_seconds": time.perf_counter() - render_started_at,
        "image_size_bytes": image_size_bytes,
        "image_width": width,
        "image_height": height,
    }


def build_pdf_ocr_parse_error(
    failed_pages: list[int],
    total_pages: int,
    ocr_page_count: int,
    max_pages: int,
) -> str | None:
    notes: list[str] = []
    if max_pages > 0 and total_pages > ocr_page_count:
        notes.append(f"已按配置仅 OCR 前 {ocr_page_count} 页，未覆盖全文。")
    if failed_pages:
        failed_preview = "、".join(str(page) for page in failed_pages[:8])
        suffix = "等" if len(failed_pages) > 8 else ""
        notes.append(f"部分页面 OCR 失败：第 {failed_preview}{suffix} 页。")
    return " ".join(notes) if notes else None


def ocr_pdf_page_worker(
    material_id: int,
    file_bytes: bytes,
    page_index: int,
    total_pages: int,
    render_dpi: int,
    image_format: str,
    jpeg_quality: int,
    max_image_side: int,
    model_name: str,
    timeout_seconds: int,
) -> dict:
    page_started_at = time.perf_counter()
    page_number = page_index + 1
    document = None
    image_path = ""
    render_info = {
        "render_seconds": 0,
        "image_size_bytes": 0,
        "image_width": 0,
        "image_height": 0,
    }
    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
        render_info = render_pdf_page_to_temp_image(
            document,
            page_index,
            render_dpi,
            image_format,
            jpeg_quality,
            max_image_side,
        )
        image_path = render_info["image_path"]
        result = parse_image_with_qwen(
            image_path,
            prompt=SCANNED_PDF_PAGE_PROMPT,
            model=model_name,
            timeout_seconds=timeout_seconds,
        )
        page_text = (result.get("extracted_text") or "").strip()
        success = bool(result.get("success") and page_text)
        error = None if success else (result.get("error") or "未识别到有效文本")
        return {
            "page_number": page_number,
            "total_pages": total_pages,
            "success": success,
            "text": page_text,
            "error": error,
            "model": result.get("model") or model_name,
            "render_seconds": float(render_info.get("render_seconds") or 0),
            "image_size_bytes": int(render_info.get("image_size_bytes") or 0),
            "image_width": int(render_info.get("image_width") or 0),
            "image_height": int(render_info.get("image_height") or 0),
            "encode_seconds": float(result.get("encode_seconds") or 0),
            "qwen_seconds": float(result.get("qwen_seconds") or 0),
            "total_page_seconds": time.perf_counter() - page_started_at,
        }
    except Exception as exc:
        return {
            "page_number": page_number,
            "total_pages": total_pages,
            "success": False,
            "text": "",
            "error": str(exc)[:120],
            "model": model_name,
            "render_seconds": float(render_info.get("render_seconds") or 0),
            "image_size_bytes": int(render_info.get("image_size_bytes") or 0),
            "image_width": int(render_info.get("image_width") or 0),
            "image_height": int(render_info.get("image_height") or 0),
            "encode_seconds": 0,
            "qwen_seconds": 0,
            "total_page_seconds": time.perf_counter() - page_started_at,
        }
    finally:
        if image_path:
            try:
                Path(image_path).unlink(missing_ok=True)
            except OSError:
                pass
        if document is not None:
            document.close()


def parse_scanned_pdf_in_background(
    db: Session,
    material: models.StudyMaterial,
    file_bytes: bytes,
    local_pdf_text: str = "",
):
    document = None
    page_texts: dict[int, str] = {}
    failed_pages: list[int] = []
    errors: list[str] = []
    max_pages = get_pdf_ocr_max_pages()

    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
        total_pages = len(document)
        ocr_page_count = total_pages if max_pages == 0 else min(total_pages, max_pages)

        if ocr_page_count <= 0:
            update_material_parse_state(
                db,
                material.id,
                parse_status="failed",
                parse_error="扫描版 PDF OCR 解析失败，请稍后重试或上传更清晰的文件。",
                parse_progress=0,
                total_pages=total_pages,
                parsed_pages=0,
                chunk_count=0,
                ocr_required=1,
                qwen_used=True,
                extract_method="failed",
                parse_completed_at=serialize_datetime(utc_now()),
            )
            return

        update_material_parse_state(
            db,
            material.id,
            parse_status="parsing",
            parse_progress=1,
            total_pages=total_pages,
            parsed_pages=0,
            chunk_count=0,
            ocr_required=1,
            qwen_used=True,
            extract_method="qwen" if not (local_pdf_text or "").strip() else "mixed",
        )

        render_dpi = get_pdf_ocr_render_dpi()
        image_format = get_pdf_ocr_image_format()
        jpeg_quality = get_pdf_ocr_jpeg_quality()
        max_image_side = get_pdf_ocr_max_image_side()
        concurrency = min(get_pdf_ocr_concurrency(), ocr_page_count)
        timeout_seconds = get_pdf_ocr_page_timeout_seconds()
        model_name = get_qwen_pdf_ocr_model()
        ocr_started_at = time.perf_counter()
        completed_pages = 0
        page_results: list[dict] = []

        logger.info(
            "[PDF_OCR_START] material_id=%s total_pages=%s ocr_max_pages=%s concurrency=%s dpi=%s format=%s quality=%s max_side=%s model=%s",
            material.id,
            total_pages,
            max_pages,
            concurrency,
            render_dpi,
            image_format,
            jpeg_quality,
            max_image_side,
            model_name,
        )

        if document is not None:
            document.close()
            document = None

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_map = {
                executor.submit(
                    ocr_pdf_page_worker,
                    material.id,
                    file_bytes,
                    page_index,
                    total_pages,
                    render_dpi,
                    image_format,
                    jpeg_quality,
                    max_image_side,
                    model_name,
                    timeout_seconds,
                ): page_index + 1
                for page_index in range(ocr_page_count)
            }

            for future in as_completed(future_map):
                result = future.result()
                page_results.append(result)
                completed_pages += 1
                page_number = int(result.get("page_number") or future_map[future])
                page_text = (result.get("text") or "").strip()
                db_update_started_at = time.perf_counter()
                if result.get("success") and page_text:
                    page_texts[page_number] = f"【第 {page_number} 页】\n{page_text}"
                else:
                    failed_pages.append(page_number)
                    errors.append(f"第 {page_number} 页：{result.get('error') or '未识别到有效文本'}")

                parse_progress = round((completed_pages / max(total_pages, 1)) * 100, 2)
                update_material_parse_state(
                    db,
                    material.id,
                    parse_status="parsing",
                    parse_progress=min(parse_progress, 99 if completed_pages < total_pages else parse_progress),
                    parsed_pages=completed_pages,
                    total_pages=total_pages,
                    chunk_count=len(page_texts),
                    parse_error="; ".join(errors[:3]) if errors else None,
                )
                db_update_seconds = time.perf_counter() - db_update_started_at
                logger.info(
                    "[PDF_OCR_PAGE] material_id=%s page=%s/%s render=%.2fs image=%sKB size=%sx%s encode=%.2fs qwen=%.2fs db=%.2fs total=%.2fs model=%s success=%s error=%s",
                    material.id,
                    page_number,
                    total_pages,
                    float(result.get("render_seconds") or 0),
                    int((int(result.get("image_size_bytes") or 0) + 1023) / 1024),
                    int(result.get("image_width") or 0),
                    int(result.get("image_height") or 0),
                    float(result.get("encode_seconds") or 0),
                    float(result.get("qwen_seconds") or 0),
                    db_update_seconds,
                    float(result.get("total_page_seconds") or 0) + db_update_seconds,
                    result.get("model") or model_name,
                    bool(result.get("success")),
                    (result.get("error") or "")[:80],
                )

        sorted_page_texts = [text for _, text in sorted(page_texts.items(), key=lambda item: item[0])]

        if not page_texts:
            update_material_parse_state(
                db,
                material.id,
                parse_status="failed",
                parse_error="扫描版 PDF OCR 解析失败，请稍后重试或上传更清晰的文件。",
                parse_progress=100,
                total_pages=total_pages,
                parsed_pages=ocr_page_count,
                chunk_count=0,
                ocr_required=1,
                qwen_used=True,
                extract_method="failed",
                parsed_at=utc_now(),
                parse_completed_at=serialize_datetime(utc_now()),
            )
            return

        text_parts: list[str] = []
        if (local_pdf_text or "").strip():
            text_parts.append(f"本地文本提取补充：\n{local_pdf_text.strip()}")
        text_parts.extend(sorted_page_texts)
        extracted_text = "\n\n".join(text_parts).strip()
        material = update_material_parse_state(
            db,
            material.id,
            extracted_text=extracted_text,
            summary=extracted_text[:300] or "扫描版 PDF OCR 解析完成。",
            parse_progress=95,
            total_pages=total_pages,
            parsed_pages=ocr_page_count,
            ocr_required=1,
            qwen_used=True,
            extract_method="qwen" if not (local_pdf_text or "").strip() else "mixed",
        )
        if not material:
            return

        chunk_count = replace_material_chunks(db, material)
        parse_error = build_pdf_ocr_parse_error(failed_pages, total_pages, ocr_page_count, max_pages)
        reached_page_limit = max_pages > 0 and total_pages > ocr_page_count
        parse_status = "partial" if failed_pages or reached_page_limit else "success"
        update_material_parse_state(
            db,
            material.id,
            parse_status=parse_status,
            parse_progress=100,
            total_pages=total_pages,
            parsed_pages=ocr_page_count if reached_page_limit else total_pages,
            chunk_count=chunk_count,
            parse_error=parse_error,
            ocr_required=1,
            qwen_used=True,
            extract_method="qwen" if not (local_pdf_text or "").strip() else "mixed",
            parsed_at=utc_now(),
            parse_completed_at=serialize_datetime(utc_now()),
        )
        total_ocr_seconds = time.perf_counter() - ocr_started_at
        average_page_seconds = (
            sum(float(item.get("total_page_seconds") or 0) for item in page_results) / max(len(page_results), 1)
        )
        pages_per_minute = (len(page_results) / total_ocr_seconds * 60) if total_ocr_seconds > 0 else 0
        logger.info(
            "[PDF_OCR_DONE] material_id=%s pages=%s/%s ocr_max_pages=%s concurrency=%s dpi=%s format=%s total=%.2fs avg=%.2fs ppm=%.2f chunk_count=%s status=%s",
            material.id,
            len(page_results),
            total_pages,
            max_pages,
            concurrency,
            render_dpi,
            image_format,
            total_ocr_seconds,
            average_page_seconds,
            pages_per_minute,
            chunk_count,
            parse_status,
        )
    except Exception as exc:
        logger.warning("[MATERIAL_PARSE] material_id=%s scanned pdf OCR failed: %s", material.id, str(exc)[:160])
        update_material_parse_state(
            db,
            material.id,
            parse_status="failed",
            parse_error="扫描版 PDF OCR 解析失败，请稍后重试或上传更清晰的文件。",
            parse_progress=0,
            ocr_required=1,
            qwen_used=True,
            extract_method="failed",
            parse_completed_at=serialize_datetime(utc_now()),
        )
    finally:
        if document is not None:
            document.close()


def parse_material_in_background(material_id: int):
    db = SessionLocal()
    try:
        material = get_material_for_parsing(db, material_id)
        if not material:
            return

        now_text = serialize_datetime(utc_now())
        update_material_parse_state(
            db,
            material_id,
            parse_status="parsing",
            parse_progress=1,
            parse_started_at=now_text,
            parse_error=None,
        )
        material = get_material_for_parsing(db, material_id)
        if not material:
            return

        file_path = resolve_stored_file_path(material.file_path)
        if not file_path.exists() or not file_path.is_file():
            update_material_parse_state(
                db,
                material_id,
                parse_status="failed",
                parse_error="上传文件不存在，无法后台解析。",
                parse_progress=0,
            )
            return

        file_bytes = file_path.read_bytes()
        total_pages = get_pdf_total_pages(file_bytes) if material.file_type == "pdf" else 0

        if material.file_type == "pdf":
            total_pages, page_texts = extract_pdf_pages(file_bytes)
            extracted_text = build_pdf_text_from_pages(page_texts)
            if not is_pdf_text_usable(extracted_text, total_pages):
                # TODO: Qwen PDF fallback logic is duplicated between
                # parse_material_in_background (via parse_scanned_pdf_in_background)
                # and handle_material_upload (~L2088).
                # Extract a shared _qwen_fallback_for_pdf() helper in a future refactor.
                parse_scanned_pdf_in_background(db, material, file_bytes, extracted_text)
                return
        elif material.file_type == "image":
            extracted_text = extract_image_text(file_bytes)
            if not (extracted_text or "").strip():
                update_material_parse_state(
                    db,
                    material_id,
                    parse_status="failed",
                    parse_error="图片已上传，后台视觉解析将在下一阶段接入。",
                    parse_progress=0,
                    extract_method="local",
                    qwen_used=False,
                )
                return
        elif material.file_type in ("docx", "pptx", "text", "code"):
            from document_parser import extract_supported_file_text
            try:
                result = extract_supported_file_text(file_bytes, material.original_filename)
                extracted_text = result["text"]
            except ValueError as exc:
                update_material_parse_state(
                    db,
                    material_id,
                    parse_status="failed",
                    parse_error=str(exc),
                    parse_progress=0,
                )
                return
            if not (extracted_text or "").strip():
                update_material_parse_state(
                    db,
                    material_id,
                    parse_status="failed",
                    parse_error="文件内容为空，无法解析。",
                    parse_progress=0,
                )
                return
        else:
            update_material_parse_state(
                db,
                material_id,
                parse_status="failed",
                parse_error="暂不支持该文件类型的后台解析。",
                parse_progress=0,
            )
            return

        material, chunk_count = complete_material_with_local_pdf_text(db, material, extracted_text, total_pages)
        if not material:
            return
        logger.info(
            "[MATERIAL_PARSE] material_id=%s file_type=%s total_pages=%s chunk_count=%s status=success",
            material_id,
            material.file_type,
            total_pages,
            chunk_count,
        )
    except Exception as exc:
        logger.warning("[MATERIAL_PARSE] material_id=%s failed: %s", material_id, str(exc)[:160])
        try:
            update_material_parse_state(
                db,
                material_id,
                parse_status="failed",
                parse_error=f"后台解析失败：{str(exc)[:120]}",
                parse_progress=0,
                parse_completed_at=serialize_datetime(utc_now()),
            )
        except Exception as update_exc:
            logger.warning(
                "[MATERIAL_PARSE] material_id=%s failed to update error state: %s",
                material_id,
                str(update_exc)[:160],
            )
    finally:
        db.close()


def create_material_from_message(
    db: Session,
    user: models.User,
    message: models.ChatMessage,
    subject: str,
    parse_metadata: dict | None = None,
):
    normalized_subject = normalize_subject(subject)

    if not message.attachment_path:
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

    final_parse_metadata = {
        **get_default_parse_metadata(),
        **(parse_metadata or {}),
    }

    if (message.extracted_text or "").strip():
        summary = summarize_material(normalized_subject, message.extracted_text)
    else:
        summary = final_parse_metadata.get("parse_error") or "该资料解析失败，暂未提取到可用于检索的文本内容。"
    material = models.StudyMaterial(
        username=user.username,
        subject=normalized_subject,
        file_type=message.attachment_type or "image",
        original_filename=message.attachment_filename or "未命名附件",
        file_path=message.attachment_path,
        extracted_text=message.extracted_text or "",
        summary=summary,
        source_message_id=message.id,
        extract_method=final_parse_metadata.get("extract_method"),
        parse_status=final_parse_metadata.get("parse_status"),
        parse_error=final_parse_metadata.get("parse_error"),
        qwen_used=bool(final_parse_metadata.get("qwen_used")),
        parsed_at=final_parse_metadata.get("parsed_at"),
        is_deleted=False,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    if (material.extracted_text or "").strip():
        replace_material_chunks(db, material)

    message.material_id = material.id
    db.commit()
    db.refresh(message)
    return material, True


def create_attachment_user_message_content(subject: str, original_filename: str, file_type: str, question: str, extracted_text: str):
    label = FILE_TYPE_LABELS.get(file_type, "资料提取文本")
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
    from document_parser import detect_material_type, extract_supported_file_text

    material_type = detect_material_type(original_filename, file.content_type)
    file_type = ALLOWED_UPLOAD_TYPES.get(file.content_type, material_type.lower())
    parse_metadata = get_default_parse_metadata()
    clean_question = (question or "").strip()

    if material_type in ("DOCX", "PPTX", "TEXT", "CODE"):
        try:
            result = extract_supported_file_text(file_bytes, original_filename, file.content_type)
            extracted_text = result["text"]
            file_type = result["material_type"].lower()
            parse_metadata["parse_status"] = "success"
        except ValueError as exc:
            file_hash = calculate_file_hash(file_bytes)
            stored_path = save_material_file(file_bytes, original_filename, file_hash)
            material = create_pending_material(
                db=db,
                username=user.username,
                subject=normalized_subject,
                file_type=file_type,
                original_filename=original_filename,
                file_path=stored_path,
                file_hash=file_hash,
                mime_type=file.content_type,
                file_size=len(file_bytes),
            )
            update_material_parse_state(
                db,
                material.id,
                parse_status="failed",
                parse_error=str(exc),
                parse_progress=0,
                parse_completed_at=serialize_datetime(utc_now()),
            )
            return {
                "success": True,
                "material_id": material.id,
                "filename": original_filename,
                "parse_status": "failed",
                "parse_progress": 0,
                "message": "原文件已保存，但解析失败，AI 暂时无法基于该文件问答。",
                "material": serialize_material_detail(material),
            }

        if not extracted_text or not extracted_text.strip():
            raise HTTPException(status_code=400, detail="文件内容为空，请检查后重试。")

        stored_file_path = save_uploaded_file(user.username, original_filename, file_bytes)

    elif file_type == "image":
        # TODO: Qwen fallback logic for images is duplicated between
        # handle_material_upload (~L2046) and parse_material_in_background (~L1883).
        # Extract a shared _qwen_fallback_for_image() helper in a future refactor.
        local_ocr_text = extract_image_text(file_bytes)
        extracted_text = local_ocr_text
        stored_file_path = save_uploaded_file(user.username, original_filename, file_bytes)

        if should_use_qwen_for_image(local_ocr_text):
            logger.info(
                "[QWEN] image fallback triggered, local_text_len=%s",
                len(local_ocr_text or ""),
            )
            qwen_result = parse_image_with_qwen(str(resolve_stored_file_path(stored_file_path)))
            qwen_text = (qwen_result.get("extracted_text") or "").strip()
            qwen_success = bool(qwen_result.get("success") and qwen_text)

            if qwen_success:
                extracted_text = merge_image_extracted_text(local_ocr_text, qwen_text)
                parse_metadata["extract_method"] = "mixed" if (local_ocr_text or "").strip() else "qwen"
                parse_metadata["parse_status"] = "success"
                parse_metadata["parse_error"] = None
                parse_metadata["qwen_used"] = True
                logger.info(
                    "[QWEN] image fallback success, extracted_text_len=%s",
                    len(extracted_text or ""),
                )
            else:
                parse_metadata["parse_error"] = qwen_result.get("error") or "图片解析失败，请稍后重试"
                parse_metadata["parse_status"] = "partial" if (local_ocr_text or "").strip() else "failed"
                logger.warning(
                    "[QWEN] image fallback failed, qwen_success=%s, final_text_len=%s",
                    qwen_success,
                    len(extracted_text or ""),
                )
    else:
        extracted_text = extract_pdf_text(file_bytes)
        total_pages = get_pdf_total_pages(file_bytes)
        should_fallback = should_use_qwen_for_pdf(extracted_text, total_pages)
        logger.info(
            "[QWEN] PDF local parse checked, total_pages=%s, local_text_len=%s, qwen_fallback=%s",
            total_pages,
            len(extracted_text or ""),
            should_fallback,
        )
        if should_fallback:
            pdf_qwen_result = parse_scanned_pdf_with_qwen(file_bytes)
            qwen_pdf_text = (pdf_qwen_result.get("text") or "").strip()
            success_pages = int(pdf_qwen_result.get("success_pages") or 0)
            failed_pages = int(pdf_qwen_result.get("failed_pages") or 0)
            logger.info(
                "[QWEN] PDF fallback finished, success_pages=%s, failed_pages=%s, final_text_len=%s",
                success_pages,
                failed_pages,
                len(qwen_pdf_text or ""),
            )

            if qwen_pdf_text:
                had_local_text = bool((extracted_text or "").strip())
                extracted_text = merge_pdf_extracted_text(extracted_text, qwen_pdf_text)
                parse_metadata["extract_method"] = "mixed" if had_local_text else "qwen"
                parse_metadata["parse_status"] = "partial" if failed_pages else "success"
                parse_metadata["parse_error"] = build_pdf_qwen_parse_error(pdf_qwen_result, total_pages)
                parse_metadata["qwen_used"] = True
            else:
                parse_metadata["parse_error"] = (
                    "无法从 PDF 提取文字，Qwen 扫描解析也失败："
                    + "; ".join((pdf_qwen_result.get("errors") or [])[:3])
                )
                parse_metadata["parse_status"] = "partial" if (extracted_text or "").strip() else "failed"
                parse_metadata["extract_method"] = "local" if (extracted_text or "").strip() else "failed"
                parse_metadata["qwen_used"] = True
        stored_file_path = save_uploaded_file(user.username, original_filename, file_bytes)

    if not extracted_text.strip():
        if file_type == "pdf":
            raise HTTPException(
                status_code=400,
                detail="这个 PDF 可能是扫描件，但视觉解析失败，请稍后重试或上传更清晰的文件。",
            )
        raise HTTPException(status_code=400, detail="未能从文件中提取到文字内容，请检查文件是否为空或已损坏。")


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
                            has_attachment=(file_type == "pdf"),
                            rag_chunks=rag_chunks,
                        ),
                    },
                    {
                        "role": "user",
                        "content": build_material_question_prompt(file_type, extracted_text, clean_question),
                    },
                ]
            )

            answer = normalize_assistant_markdown(answer)

            safe_references = make_json_safe(references)
            assistant_message = models.ChatMessage(
                user_id=user.id,
                session_id=chat_session.id,
                role="assistant",
                content=answer,
                reference_payload=json.dumps(safe_references, ensure_ascii=False) if safe_references else None,
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
            parse_metadata=parse_metadata,
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


@app.get("/debug/qwen-status")
def get_qwen_status():
    return get_qwen_status_payload()


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
        onboarding_completed=False,
        learning_goals=None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "注册成功", "user": user_profile(new_user), "profile": user_profile(new_user)}


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

    return {"message": "登录成功", "user": user_profile(db_user), "profile": user_profile(db_user)}


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

    if avatar and avatar not in ALLOWED_AVATARS and not avatar.startswith("/"):
        raise HTTPException(status_code=400, detail="头像无效")

    user.nickname = nickname
    user.grade = grade
    user.major = major
    user.avatar = avatar

    if req.learning_goals is not None:
        validated_goals = []
        for goal_item in req.learning_goals:
            if not isinstance(goal_item, dict):
                continue
            subject_name = (goal_item.get("subject") or "").strip()
            if not subject_name:
                continue
            target_level = (goal_item.get("target_level") or "").strip()
            if not target_level:
                continue
            note = (goal_item.get("note") or "").strip()[:200]
            validated_goals.append({
                "subject": subject_name,
                "target_level": target_level,
                "note": note,
            })
        user.learning_goals = json.dumps(validated_goals, ensure_ascii=False) if validated_goals else None

    if req.onboarding_completed is not None:
        user.onboarding_completed = bool(req.onboarding_completed)

    db.commit()
    db.refresh(user)

    return {"profile": user_profile(user)}


@app.get("/me/quota")
def get_my_quota(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    plan_info = get_user_plan(user.username, db)
    limits = get_plan_limits(plan_info["plan"])

    usage = {}
    for feature in ALL_FEATURES:
        usage[feature] = get_today_usage(user.username, feature, db)

    feature_limits = {}
    for feature in ALL_FEATURES:
        limit = limits.get(feature, 0)
        used = usage.get(feature, 0)
        feature_limits[feature] = {
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
        }

    upload_limits = {
        "material_upload_count": {
            "used": db.query(models.StudyMaterial)
                .filter(models.StudyMaterial.username == user.username, models.StudyMaterial.is_deleted.is_(False))
                .count(),
            "limit": limits.get("material_upload_count", 30),
        },
        "single_file_size_mb": limits.get("single_file_size_mb", 20),
    }

    return {
        "plan": plan_info,
        "feature_limits": feature_limits,
        "upload_limits": upload_limits,
        "all_features": ALL_FEATURES,
    }


@app.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    username: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)

    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="头像仅支持 JPG、PNG、WebP 或 GIF 格式")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="头像文件不能超过 3MB")

    suffix = Path(file.filename or "avatar.png").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise HTTPException(status_code=400, detail="头像仅支持 JPG、PNG、WebP 或 GIF 格式")

    avatar_filename = f"{secrets.token_hex(16)}{suffix}"
    AVATAR_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    avatar_path = AVATAR_UPLOAD_ROOT / avatar_filename

    with open(avatar_path, "wb") as output:
        output.write(file_bytes)

    user.avatar = avatar_filename
    db.commit()
    db.refresh(user)

    return {"avatar_url": f"/me/avatar/{avatar_filename}", "profile": user_profile(user)}


@app.get("/me/avatar/{filename}")
def serve_avatar(filename: str):
    safe_name = os.path.basename(filename)
    if not safe_name or safe_name != filename:
        raise HTTPException(status_code=400, detail="头像路径无效")

    avatar_path = (AVATAR_UPLOAD_ROOT / safe_name).resolve()
    if AVATAR_UPLOAD_ROOT.resolve() not in avatar_path.parents and avatar_path != AVATAR_UPLOAD_ROOT.resolve():
        raise HTTPException(status_code=400, detail="头像路径无效")

    if not avatar_path.exists() or not avatar_path.is_file():
        raise HTTPException(status_code=404, detail="头像文件不存在")

    ext = avatar_path.suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
    media_type = media_map.get(ext, "image/png")

    return FileResponse(avatar_path, media_type=media_type)


def generate_answer_summary(answer: str, max_chars: int = 200) -> str:
    if not answer:
        return ""
    cleaned = re.sub(r"```[\s\S]*?```", "", answer)
    cleaned = re.sub(r"^#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars]
    last_period = max(truncated.rfind("。"), truncated.rfind(". "), truncated.rfind("\n"))
    if last_period > max_chars // 2:
        return truncated[: last_period + 1]
    return truncated.rsplit(" ", 1)[0] if " " in truncated else truncated


_IGNORE_WORDS = frozenset({
    "什么", "如何", "怎么", "为什么", "请问", "是什么", "请",
    "的", "吗", "呢", "吧", "啊", "是", "在", "有", "和", "与", "或",
    "可以", "这个", "那个", "一下", "一个", "一些", "the", "a", "an",
    "is", "are", "of", "in", "to", "for", "and", "or",
})


def extract_knowledge_points(question: str, answer: str, subject: str) -> list[str]:
    points: list[str] = []

    bold_matches = re.findall(r"\*\*(.+?)\*\*", answer or "")
    for match in bold_matches:
        clean = match.strip()
        if 2 <= len(clean) <= 20 and clean.lower() not in _IGNORE_WORDS and clean not in points:
            points.append(clean)

    question_words = re.findall(r"[一-鿿\w]+", question or "")
    for word in question_words:
        clean = word.strip()
        if (
            len(clean) >= 2
            and clean.lower() not in _IGNORE_WORDS
            and clean not in points
        ):
            points.append(clean)

    if not points and subject:
        points.append(subject)

    return points[:8]


def auto_create_learning_record(
    db: Session,
    user: models.User,
    subject: str,
    session_id: int,
    message_id: int,
    question: str,
    answer: str,
    rag_chunks: list[dict],
):
    existing = (
        db.query(models.LearningRecord)
        .filter(
            models.LearningRecord.user_id == user.id,
            models.LearningRecord.message_id == message_id,
            models.LearningRecord.record_type == "review",
            models.LearningRecord.is_deleted.is_(False),
        )
        .first()
    )
    if existing:
        return existing, False

    summary = generate_answer_summary(answer)
    knowledge_points = extract_knowledge_points(question, answer, subject)
    review_suggestion = "建议复习本次问题涉及的核心概念，并结合课程资料做 1-2 道相关练习。"

    source_filenames: list[str] = list(dict.fromkeys(
        item.get("source_filename", "") for item in (rag_chunks or []) if item.get("source_filename")
    ))

    note_parts: list[str] = []
    if summary:
        note_parts.append(f"回答摘要：{summary}")
    note_parts.append(f"复习建议：{review_suggestion}")
    note = "\n\n".join(note_parts)

    references = [
        {"filename": fn, "material_id": item.get("material_id")}
        for item in (rag_chunks or [])
        for fn in [item.get("source_filename", "")]
        if fn
    ]

    record = models.LearningRecord(
        user_id=user.id,
        subject=normalize_subject(subject),
        session_id=session_id,
        message_id=message_id,
        record_type="review",
        question=question,
        answer=answer,
        references_json=json.dumps(references, ensure_ascii=False) if references else None,
        note=note,
        tags=json.dumps(knowledge_points, ensure_ascii=False) if knowledge_points else None,
        review_status="pending",
        is_deleted=False,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, True


def build_knowledge_context(username: str, course_id: str, db: Session) -> str:
    if not username or not course_id:
        return ""

    rows = (
        db.query(models.UserKnowledgeProgress, models.KnowledgePoint.title)
        .join(models.KnowledgePoint, models.UserKnowledgeProgress.knowledge_point_id == models.KnowledgePoint.id)
        .filter(
            models.UserKnowledgeProgress.username == username,
            models.UserKnowledgeProgress.course_id == course_id,
        )
        .all()
    )

    if not rows:
        return ""

    mastered: list[str] = []
    learning: list[str] = []
    weak: list[str] = []
    reviewing: list[str] = []
    not_started: list[str] = []

    for progress, title in rows:
        if not title:
            continue
        score = progress.mastery_score or 0
        status = progress.status or ""

        if status == "mastered" or score >= 80:
            mastered.append(title)
        elif status == "reviewing":
            reviewing.append(title)
        elif status == "learning":
            learning.append(title)
        elif status == "not_started":
            not_started.append(title)
        elif 0 < score < 40:
            weak.append(title)
        elif 40 <= score < 80:
            learning.append(title)
        else:
            not_started.append(title)

    MAX_PER = 5
    mastered = mastered[:MAX_PER]
    learning = learning[:MAX_PER]
    weak = weak[:MAX_PER]
    reviewing = reviewing[:MAX_PER]
    not_started = not_started[:MAX_PER]

    lines = ["当前课程知识点掌握情况："]
    if mastered:
        lines.append(f"- 已掌握：{'、'.join(mastered)}")
    if learning:
        lines.append(f"- 学习中：{'、'.join(learning)}")
    if reviewing:
        lines.append(f"- 复习中：{'、'.join(reviewing)}")
    if weak:
        lines.append(f"- 掌握度较低：{'、'.join(weak)}")
    if not_started:
        lines.append(f"- 未开始：{'、'.join(not_started)}")

    if len(lines) == 1:
        return ""

    result = "\n".join(lines)
    if len(result) > 800:
        result = result[:797] + "..."

    result += "\n\n请仅将以上信息作为学习背景参考，回答时以用户当前问题和提供的资料为准。"
    return result


def get_weak_knowledge_points(username: str, course_id: str, db: Session, limit: int = 5):
    """Return weak/not-started/learning/reviewing knowledge points for a course.

    Sorted by mastery_score ascending, then by last_studied_at (older first).
    Returns list of dicts with id, title, status, mastery_score.
    """
    if not username or not course_id:
        return []

    rows = (
        db.query(models.UserKnowledgeProgress, models.KnowledgePoint.title, models.KnowledgePoint.id)
        .join(models.KnowledgePoint, models.UserKnowledgeProgress.knowledge_point_id == models.KnowledgePoint.id)
        .filter(
            models.UserKnowledgeProgress.username == username,
            models.UserKnowledgeProgress.course_id == course_id,
            models.UserKnowledgeProgress.status.in_(["not_started", "learning", "reviewing"]),
        )
        .all()
    )

    if not rows:
        # Fallback: any knowledge points with low mastery score
        rows = (
            db.query(models.UserKnowledgeProgress, models.KnowledgePoint.title, models.KnowledgePoint.id)
            .join(models.KnowledgePoint, models.UserKnowledgeProgress.knowledge_point_id == models.KnowledgePoint.id)
            .filter(
                models.UserKnowledgeProgress.username == username,
                models.UserKnowledgeProgress.course_id == course_id,
                models.UserKnowledgeProgress.mastery_score < 40,
            )
            .all()
        )

    if not rows:
        return []

    result: list[dict] = []
    for progress, title, kp_id in rows:
        if not title:
            continue
        result.append({
            "id": kp_id,
            "title": title,
            "status": progress.status or "not_started",
            "mastery_score": progress.mastery_score or 0,
            "last_studied_at": progress.last_studied_at,
        })

    result.sort(key=lambda x: (
        x["mastery_score"],
        0 if x["last_studied_at"] else 0,
    ))

    return result[:limit]


def apply_knowledge_progress_event(
    username: str,
    course_id: str,
    knowledge_point_id: int,
    event_type: str,
    delta: int,
    reason: str = "",
    source_type: str | None = None,
    source_id: int | None = None,
    db: Session | None = None,
):
    if not db or not username or not course_id or not knowledge_point_id:
        return

    try:
        # Validate knowledge point belongs to user + course
        point = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.id == knowledge_point_id,
                models.KnowledgePoint.username == username,
                models.KnowledgePoint.course_id == course_id,
            )
            .first()
        )
        if not point:
            return

        now = utc_now()

        # Write event
        event = models.KnowledgeProgressEvent(
            username=username,
            course_id=course_id,
            knowledge_point_id=knowledge_point_id,
            event_type=event_type,
            delta=delta,
            reason=reason or None,
            source_type=source_type,
            source_id=source_id,
            created_at=now,
        )
        db.add(event)

        # Get or create progress
        progress = (
            db.query(models.UserKnowledgeProgress)
            .filter(
                models.UserKnowledgeProgress.username == username,
                models.UserKnowledgeProgress.course_id == course_id,
                models.UserKnowledgeProgress.knowledge_point_id == knowledge_point_id,
            )
            .first()
        )
        if not progress:
            progress = models.UserKnowledgeProgress(
                username=username,
                course_id=course_id,
                knowledge_point_id=knowledge_point_id,
                mastery_score=0,
                status="not_started",
                practice_count=0,
                task_count=0,
            )
            db.add(progress)
            db.flush()

        # Update mastery_score (clamp 0-100)
        old_score = progress.mastery_score or 0
        new_score = max(0, min(100, old_score + delta))
        progress.mastery_score = new_score

        # Auto-update status
        if new_score == 0:
            progress.status = "not_started"
        elif new_score < 40:
            progress.status = "learning"
        elif new_score < 80:
            progress.status = "reviewing"
        else:
            progress.status = "mastered"

        # Update practice/task counts
        if event_type == "task_done":
            progress.task_count = (progress.task_count or 0) + 1
        elif event_type in ("question_correct", "question_incorrect", "question_attempt"):
            progress.practice_count = (progress.practice_count or 0) + 1

        if delta > 0:
            progress.last_studied_at = now
        progress.updated_at = now

        db.flush()
    except Exception:
        db.rollback()
        logging.exception("apply_knowledge_progress_event failed")


@app.post("/chat")
def chat(req: schemas.ChatRequest, db: Session = Depends(get_db)):
    if not req.username:
        raise HTTPException(status_code=401, detail="请先登录后再使用 AI 聊天")

    user = get_user_by_username(req.username, db)
    subject = normalize_subject(req.subject, req.course)
    material_ids = sorted({int(item) for item in (req.material_ids or []) if int(item) > 0})
    selected_materials: list[models.StudyMaterial] = []

    if material_ids:
        selected_materials = (
            db.query(models.StudyMaterial)
            .filter(
                models.StudyMaterial.id.in_(material_ids),
                models.StudyMaterial.username == user.username,
                models.StudyMaterial.is_deleted.is_(False),
            )
            .all()
        )
        material_map = {material.id: material for material in selected_materials}
        if len(material_map) != len(material_ids):
            raise HTTPException(status_code=404, detail="指定资料不存在或不属于当前用户")

        blocked_materials = [
            material
            for material in selected_materials
            if (material.parse_status or "success") != "success" or (material.chunk_count or 0) <= 0
        ]
        if blocked_materials:
            raise HTTPException(status_code=400, detail="资料仍在解析中，解析完成后才能提问。")

        selected_materials = [material_map[material_id] for material_id in material_ids]

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

    primary_material = selected_materials[0] if selected_materials else None
    user_message = models.ChatMessage(
        user_id=user.id,
        session_id=chat_session.id,
        role="user",
        content=req.message,
        attachment_type=primary_material.file_type if primary_material else None,
        attachment_filename=primary_material.original_filename if primary_material else None,
        material_id=primary_material.id if primary_material else None,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    rag_chunks = []
    if material_ids:
        rag_chunks = retrieve_chunks_for_materials(
            username=user.username,
            subject=subject,
            question=req.message,
            material_ids=material_ids,
            top_k=TOP_K_CHUNKS,
        )
    elif subject:
        rag_chunks = search_relevant_material_chunks(
            username=user.username,
            subject=subject,
            question=req.message,
            top_k=TOP_K_CHUNKS,
        )

    knowledge_context = build_knowledge_context(user.username, subject, db)

    system_prompt = build_system_prompt(
        subject,
        req.message,
        {
            "grade": req.grade or user.grade,
            "major": req.major or user.major,
        },
        has_attachment=bool(material_ids),
        rag_chunks=rag_chunks,
        knowledge_context=knowledge_context,
    )

    user_content = req.message
    if material_ids and selected_materials:
        file_names = "、".join(m.original_filename for m in selected_materials)
        user_content = f"【用户本轮上传文件：{file_names}】\n{req.message}"

    check_usage_limit(user.username, "chat", db)

    answer = call_deepseek(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
    )

    record_ai_usage(user.username, "chat", db, estimated_tokens=estimate_tokens_from_text(answer), status="success")

    answer = normalize_assistant_markdown(answer)

    references = [serialize_reference_item(item) for item in rag_chunks]
    safe_references = make_json_safe(references)

    assistant_message = models.ChatMessage(
        user_id=user.id,
        session_id=chat_session.id,
        role="assistant",
        content=answer,
        reference_payload=json.dumps(safe_references, ensure_ascii=False) if safe_references else None,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    auto_create_learning_record(
        db=db,
        user=user,
        subject=subject,
        session_id=chat_session.id,
        message_id=assistant_message.id,
        question=req.message,
        answer=answer,
        rag_chunks=rag_chunks,
    )

    return {
        "answer": answer,
        "references": safe_references,
        "assistant_message_id": assistant_message.id,
        "user_message_id": user_message.id,
        "session": serialize_session(chat_session),
        "rag_sources": sorted({item["source_filename"] for item in rag_chunks}),
    }


# ── LEGACY: /chat/upload ──────────────────────────────────────────────
# This endpoint is preserved for backward compatibility only.
# The current primary flow is: POST /materials/upload → poll status → POST /chat (with material_ids).
# The frontend no longer calls this endpoint; do NOT add new frontend integrations.
# If this endpoint is confirmed unused by any external client, it can be removed in a future cleanup.
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
    background_tasks: BackgroundTasks,
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

    user = get_user_by_username(upload_username, db)

    # Upload quota checks
    plan_info = get_user_plan(user.username, db)
    plan_limits = get_plan_limits(plan_info["plan"])
    max_file_size_mb = plan_limits.get("single_file_size_mb", 20)
    max_material_count = plan_limits.get("material_upload_count", 30)

    # Check file size before reading
    if file.size and file.size > max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过限制（{max_file_size_mb}MB），当前套餐最大支持 {max_file_size_mb}MB 的文件。",
        )

    # Check total material count
    material_count = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.is_deleted.is_(False),
        )
        .count()
    )
    if material_count >= max_material_count:
        raise HTTPException(
            status_code=429,
            detail=f"资料数量已达上限（{material_count}/{max_material_count}），请清理旧资料或升级会员。",
        )

    normalized_subject = normalize_subject(subject)
    file_bytes = await file.read()
    validate_upload(file, file_bytes)

    original_filename = file.filename or "未命名文件"
    from document_parser import detect_material_type
    material_type = detect_material_type(original_filename, file.content_type)
    file_type = ALLOWED_UPLOAD_TYPES.get(file.content_type, material_type.lower())
    file_hash = calculate_file_hash(file_bytes)
    existing_material = get_material_by_file_hash(db, user.username, file_hash)
    if existing_material and (existing_material.parse_status or "").strip() == "success":
        existing_material = ensure_material_original_file(
            db,
            existing_material,
            file_bytes,
            original_filename,
            file_hash,
            file.content_type,
        )
        return {
            "success": True,
            "material_id": existing_material.id,
            "filename": existing_material.original_filename,
            "parse_status": existing_material.parse_status,
            "parse_progress": existing_material.parse_progress or 100,
            "message": "该资料已上传并解析完成，可直接使用。",
            "material": serialize_material_detail(existing_material),
        }

    if existing_material and (existing_material.parse_status or "").strip() in {"pending", "parsing"}:
        existing_material = ensure_material_original_file(
            db,
            existing_material,
            file_bytes,
            original_filename,
            file_hash,
            file.content_type,
        )
        return {
            "success": True,
            "material_id": existing_material.id,
            "filename": existing_material.original_filename,
            "parse_status": existing_material.parse_status,
            "parse_progress": existing_material.parse_progress or 0,
            "message": "该资料已上传，正在后台解析。",
            "material": serialize_material_detail(existing_material),
        }

    stored_file_path = save_material_file(file_bytes, original_filename, file_hash)
    material = create_pending_material(
        db=db,
        username=user.username,
        subject=normalized_subject,
        file_type=file_type,
        original_filename=original_filename,
        file_path=stored_file_path,
        file_hash=file_hash,
        mime_type=file.content_type,
        file_size=len(file_bytes),
    )

    total_pages = 0
    extracted_text = ""
    is_text_pdf = False
    if file_type == "pdf":
        try:
            total_pages, page_texts = extract_pdf_pages(file_bytes)
            extracted_text = build_pdf_text_from_pages(page_texts)
            is_text_pdf = is_pdf_text_usable(extracted_text, total_pages)
            material = update_material_parse_state(db, material.id, total_pages=total_pages) or material
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            material = update_material_parse_state(
                db,
                material.id,
                parse_status="failed",
                parse_error=str(detail),
                parse_progress=0,
                parse_completed_at=serialize_datetime(utc_now()),
            ) or material
            return {
                "success": True,
                "material_id": material.id,
                "filename": original_filename,
                "parse_status": "failed",
                "parse_progress": 0,
                "message": "原文件已保存，但解析失败，AI 暂时无法基于该文件问答。",
                "material": serialize_material_detail(material),
            }

    if file_type in ("docx", "pptx", "text", "code"):
        from document_parser import extract_supported_file_text
        try:
            result = extract_supported_file_text(file_bytes, original_filename, file.content_type)
            sync_text = result["text"]
        except ValueError as exc:
            material = update_material_parse_state(
                db,
                material.id,
                parse_status="failed",
                parse_error=str(exc),
                parse_progress=0,
                parse_completed_at=serialize_datetime(utc_now()),
            ) or material
            return {
                "success": True,
                "material_id": material.id,
                "filename": original_filename,
                "parse_status": "failed",
                "parse_progress": 0,
                "message": "原文件已保存，但解析失败，AI 暂时无法基于该文件问答。",
                "material": serialize_material_detail(material),
            }

        if not (sync_text or "").strip():
            material = update_material_parse_state(
                db,
                material.id,
                parse_status="failed",
                parse_error="文件内容为空，无法生成 AI 知识索引。",
                parse_progress=0,
                parse_completed_at=serialize_datetime(utc_now()),
            ) or material
            return {
                "success": True,
                "material_id": material.id,
                "filename": original_filename,
                "parse_status": "failed",
                "parse_progress": 0,
                "message": "原文件已保存，但解析失败，AI 暂时无法基于该文件问答。",
                "material": serialize_material_detail(material),
            }
            raise HTTPException(status_code=400, detail="文件内容为空，请检查后重试。")

        material, chunk_count = complete_material_with_local_pdf_text(
            db, material, sync_text, 0,
        )
        return {
            "success": True,
            "material_id": material.id,
            "filename": original_filename,
            "parse_status": "success",
            "parse_progress": 100,
            "message": "资料已解析完成，可直接基于全文问答。",
            "chunk_count": chunk_count,
            "material": serialize_material_detail(material),
        }

    if file_type == "pdf" and is_text_pdf:
        sync_max_pages = get_local_pdf_sync_max_pages()
        if total_pages <= sync_max_pages:
            material, chunk_count = complete_material_with_local_pdf_text(
                db,
                material,
                extracted_text,
                total_pages,
            )
            return {
                "success": True,
                "material_id": material.id,
                "filename": original_filename,
                "parse_status": "success",
                "parse_progress": 100,
                "message": "资料已解析完成，可直接基于全文问答。",
                "chunk_count": chunk_count,
                "material": serialize_material_detail(material),
            }

        background_tasks.add_task(parse_material_in_background, material.id)
        return {
            "success": True,
            "material_id": material.id,
            "filename": original_filename,
            "parse_status": "pending",
            "parse_progress": 0,
            "message": "资料页数较多，正在后台解析，完成后可基于全文问答。",
            "material": serialize_material_detail(material),
        }

    background_tasks.add_task(parse_material_in_background, material.id)
    pending_message = (
        "资料已上传，正在后台 OCR 解析。解析完成后可基于全文问答。"
        if file_type == "pdf"
        else "资料已上传，正在后台解析。解析完成后可基于全文问答。"
    )

    return {
        "success": True,
        "material_id": material.id,
        "filename": original_filename,
        "parse_status": "pending",
        "parse_progress": 0,
        "message": pending_message,
        "material": serialize_material_detail(material),
    }


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


@app.get("/materials/{material_id}/download")
def download_material_file(material_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    material = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.id == material_id,
            models.StudyMaterial.is_deleted.is_(False),
        )
        .first()
    )

    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    if material.username != user.username:
        raise HTTPException(status_code=403, detail="没有权限下载该资料")

    file_path = get_material_file_path(material)
    if not file_path:
        raise HTTPException(status_code=404, detail="原文件不存在，无法下载")

    download_filename = os.path.basename(material.original_filename or file_path.name)
    quoted_filename = quote(download_filename)
    fallback_filename = sanitize_filename(download_filename)
    return FileResponse(
        path=file_path,
        media_type=material.mime_type or "application/octet-stream",
        filename=download_filename,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{fallback_filename}\"; "
                f"filename*=UTF-8''{quoted_filename}"
            )
        },
    )


@app.get("/materials/{material_id}/preview")
def preview_material_file(material_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    material = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.id == material_id,
            models.StudyMaterial.is_deleted.is_(False),
        )
        .first()
    )

    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    if material.username != user.username:
        raise HTTPException(status_code=403, detail="没有权限查看该资料")

    file_path = get_material_file_path(material)
    if not file_path:
        raise HTTPException(status_code=404, detail="原文件不存在，无法预览")

    preview_filename = os.path.basename(material.original_filename or file_path.name)
    quoted_filename = quote(preview_filename)
    fallback_filename = sanitize_filename(preview_filename)

    file_type = (material.file_type or "").lower().strip()
    if file_type == "pdf":
        media_type = "application/pdf"
    elif file_type == "image":
        ext = Path(file_path.name).suffix.lower()
        media_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        media_type = media_map.get(ext, material.mime_type or "image/png")
    elif file_type in ("txt", "text", "markdown", "code"):
        ext = Path(file_path.name).suffix.lower()
        text_type_map = {".md": "text/markdown; charset=utf-8", ".markdown": "text/markdown; charset=utf-8"}
        media_type = text_type_map.get(ext, "text/plain; charset=utf-8")
    else:
        raise HTTPException(status_code=400, detail="此文件类型暂不支持网页内预览")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=preview_filename,
        headers={
            "Content-Disposition": (
                f"inline; filename=\"{fallback_filename}\"; "
                f"filename*=UTF-8''{quoted_filename}"
            )
        },
    )


@app.get("/materials/{material_id}/status")
def get_material_status(material_id: int, username: str, db: Session = Depends(get_db)):
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

    return serialize_material_status(material)


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
    material.deleted_at = utc_now()
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


@app.post("/learning-records/{record_id}/reviewed")
def mark_learning_record_reviewed(record_id: int, username: str, db: Session = Depends(get_db)):
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

    record.review_status = "reviewed"
    record.reviewed_at = utc_now()
    record.updated_at = utc_now()
    db.commit()
    db.refresh(record)

    return {"success": True, "message": "已标记为已复习", "record": serialize_learning_record(record)}


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
        record.reviewed_at = utc_now() if next_status == "reviewed" else None

    record.updated_at = utc_now()
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
    record.updated_at = utc_now()
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
        record.updated_at = utc_now()
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


# ── Code Sessions ─────────────────────────────────────────────────────────


def serialize_code_session(session: models.CodeSession):
    return {
        "id": session.id,
        "username": session.username,
        "course_id": session.course_id,
        "title": session.title,
        "language": session.language,
        "code": session.code,
        "challenge_id": getattr(session, "challenge_id", None),
        "session_type": getattr(session, "session_type", None) or "normal",
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def serialize_code_challenge(challenge):
    return {
        "id": challenge.id,
        "username": challenge.username,
        "course_id": challenge.course_id,
        "language": challenge.language,
        "title": challenge.title,
        "difficulty": challenge.difficulty,
        "knowledge_point": challenge.knowledge_point,
        "description": challenge.description,
        "requirements": challenge.requirements,
        "input_format": challenge.input_format,
        "output_format": challenge.output_format,
        "examples": challenge.examples,
        "starter_code": challenge.starter_code,
        "source": getattr(challenge, "source", None) or "normal",
        "target_weak_point": getattr(challenge, "target_weak_point", None),
        "created_at": challenge.created_at,
    }


def serialize_learning_task(task, knowledge_point_title=None):
    return {
        "id": task.id,
        "username": task.username,
        "course_id": task.course_id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "status": task.status,
        "source": task.source,
        "priority": task.priority,
        "due_date": serialize_datetime(task.due_date) if task.due_date else None,
        "related_session_id": task.related_session_id,
        "related_challenge_id": task.related_challenge_id,
        "related_material_id": task.related_material_id,
        "knowledge_point_id": getattr(task, "knowledge_point_id", None),
        "knowledge_point_title": knowledge_point_title,
        "related_question_id": getattr(task, "related_question_id", None),
        "completed_at": serialize_datetime(task.completed_at) if task.completed_at else None,
        "created_at": serialize_datetime(task.created_at) if task.created_at else None,
        "updated_at": serialize_datetime(task.updated_at) if task.updated_at else None,
    }


def serialize_knowledge_point(point, progress_info=None):
    return {
        "id": point.id,
        "username": point.username,
        "course_id": point.course_id,
        "parent_id": point.parent_id,
        "title": point.title,
        "description": point.description,
        "order_index": point.order_index,
        "level": point.level,
        "mastery_score": progress_info.get("mastery_score", 0) if progress_info else 0,
        "status": progress_info.get("status", "not_started") if progress_info else "not_started",
        "created_at": serialize_datetime(point.created_at) if point.created_at else None,
        "updated_at": serialize_datetime(point.updated_at) if point.updated_at else None,
    }


CODE_TEMPLATES = {
    "Python": 'def main():\n    print("Hello, World!")\n\nif __name__ == "__main__":\n    main()',
    "C": '#include <stdio.h>\n\nint main() {\n    printf("Hello, World!\\n");\n    return 0;\n}',
    "Java": 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, World!");\n    }\n}',
}

MAX_CODE_ANALYZE_CHARS = 12000

CODE_ANALYZE_SYSTEM_PROMPT = """你是编程学习助手。根据用户提供的代码和问题，输出以下格式的中文分析：

## 问题定位
指出代码中可能的问题或用户问题的核心。

## 修改建议
给出具体修改方案。

## 参考代码
提供修改后的参考代码片段（用 ```语言 包裹）。

## 知识点解释
解释涉及的核心知识点。

## 下一步学习建议
给出 1-2 条具体的学习方向建议。"""


@app.get("/code/sessions")
def get_code_sessions(username: str, course_id: str = "", db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    query = db.query(models.CodeSession).filter(
        models.CodeSession.username == user.username,
    )
    normalized_course_id = normalize_subject(course_id, default="")
    if normalized_course_id:
        query = query.filter(models.CodeSession.course_id == normalized_course_id)
    sessions = query.order_by(models.CodeSession.updated_at.desc()).all()

    # Bulk-fetch challenge metadata for sessions with challenge_id
    challenge_ids = [
        getattr(s, "challenge_id", None)
        for s in sessions
        if getattr(s, "challenge_id", None)
    ]
    challenge_map: dict[int, dict] = {}
    if challenge_ids:
        challenges = (
            db.query(models.CodeChallenge)
            .filter(models.CodeChallenge.id.in_(challenge_ids))
            .all()
        )
        for ch in challenges:
            challenge_map[ch.id] = {
                "source": getattr(ch, "source", None) or "normal",
                "target_weak_point": getattr(ch, "target_weak_point", None),
            }

    return {
        "sessions": [
            {
                **serialize_code_session(s),
                "challenge_source": (challenge_map.get(getattr(s, "challenge_id", None)) or {}).get("source", None),
                "challenge_weak_point": (challenge_map.get(getattr(s, "challenge_id", None)) or {}).get("target_weak_point", None),
            }
            for s in sessions
        ],
    }


@app.post("/code/sessions")
def create_code_session(req: schemas.CodeSessionCreate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    language = (req.language or "Python").strip()
    if language not in CODE_TEMPLATES:
        language = "Python"
    session = models.CodeSession(
        username=user.username,
        course_id=normalize_subject(req.course_id),
        title=(req.title or "未命名练习").strip()[:255] or "未命名练习",
        language=language,
        code=req.code or CODE_TEMPLATES.get(language, ""),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"success": True, "session": serialize_code_session(session)}


@app.get("/code/sessions/{session_id}")
def get_code_session(session_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    session = (
        db.query(models.CodeSession)
        .filter(
            models.CodeSession.id == session_id,
            models.CodeSession.username == user.username,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="代码练习不存在")
    return {"session": serialize_code_session(session)}


@app.put("/code/sessions/{session_id}")
def update_code_session(session_id: int, req: schemas.CodeSessionUpdate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    session = (
        db.query(models.CodeSession)
        .filter(
            models.CodeSession.id == session_id,
            models.CodeSession.username == user.username,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="代码练习不存在")

    if req.course_id is not None:
        session.course_id = normalize_subject(req.course_id)
    if req.title is not None:
        session.title = (req.title or "未命名练习").strip()[:255]
    if req.language is not None:
        language = req.language.strip()
        if language in CODE_TEMPLATES:
            session.language = language
    if req.code is not None:
        session.code = req.code

    session.updated_at = utc_now()
    db.commit()
    db.refresh(session)
    return {"success": True, "session": serialize_code_session(session)}


@app.delete("/code/sessions/{session_id}")
def delete_code_session(session_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    session = (
        db.query(models.CodeSession)
        .filter(
            models.CodeSession.id == session_id,
            models.CodeSession.username == user.username,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="代码练习不存在")

    # Delete related AI messages
    db.query(models.CodeAIMessage).filter(
        models.CodeAIMessage.session_id == session_id,
    ).delete()

    # Delete related challenge attempts (keep the challenge itself)
    db.query(models.CodeChallengeAttempt).filter(
        models.CodeChallengeAttempt.session_id == session_id,
    ).delete()

    # Update learning tasks that reference this session
    db.query(models.LearningTask).filter(
        models.LearningTask.related_session_id == session_id,
    ).update({models.LearningTask.related_session_id: None}, synchronize_session=False)

    db.delete(session)
    db.commit()
    return {"success": True, "message": "代码练习已删除"}


MAX_CODE_EXECUTE_CHARS = 50000
MAX_STDIN_CHARS = 10000
EXECUTE_TIMEOUT_SECONDS = 3
DOCKER_MEMORY_LIMIT = "128m"
DOCKER_CPU_LIMIT = 1.0
DOCKER_PIDS_LIMIT = 64
DOCKER_IMAGE = "python:3.11-slim"


def _run_code_in_docker(code: str, stdin: str = "") -> dict:
    """Run user Python code inside a locked-down Docker container.

    This function ONLY runs 'docker' CLI. User code is written to a temp file
    and executed INSIDE the container, never on the host.
    """
    tmp_dir = tempfile.mkdtemp(prefix="code_exec_")
    script_path = os.path.join(tmp_dir, "script.py")
    input_path = os.path.join(tmp_dir, "stdin.txt")

    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        if stdin:
            with open(input_path, "w", encoding="utf-8") as f:
                f.write(stdin)

        # Security: --network none, --read-only root, --tmpfs for /tmp, strict limits
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", DOCKER_MEMORY_LIMIT,
            "--cpus", str(DOCKER_CPU_LIMIT),
            "--pids-limit", str(DOCKER_PIDS_LIMIT),
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", f"{tmp_dir}:/code:ro",
            "-w", "/code",
            DOCKER_IMAGE,
            "python", "-u", "script.py",
        ]

        start = time.time()
        proc = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=EXECUTE_TIMEOUT_SECONDS,
            cwd=tmp_dir,
            input=stdin or None,
        )
        elapsed_ms = int((time.time() - start) * 1000)

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        # Trim output
        if len(stdout) > 50000:
            stdout = stdout[:50000] + "\n[输出过长，已截断]"
        if len(stderr) > 50000:
            stderr = stderr[:50000] + "\n[错误输出过长，已截断]"

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode,
            "duration_ms": elapsed_ms,
            "timed_out": False,
            "error_message": None,
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "stdout": "",
            "stderr": f"执行超时（超过 {EXECUTE_TIMEOUT_SECONDS} 秒）",
            "exit_code": -1,
            "duration_ms": elapsed_ms,
            "timed_out": True,
            "error_message": None,
        }
    except FileNotFoundError:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": "Docker 未安装或不可用，请联系管理员。",
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": f"代码执行环境异常：{str(exc)[:200]}",
        }
    finally:
        # Clean up temp files
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
        except OSError:
            pass
        try:
            if os.path.exists(script_path):
                os.remove(script_path)
        except OSError:
            pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass


@app.post("/code/execute")
def execute_code(req: schemas.CodeExecuteRequest, db: Session = Depends(get_db)):
    language = (req.language or "").strip().lower()

    if language != "python":
        return {
            "success": True,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": f"当前真实运行暂只支持 Python，{req.language or '该语言'} 暂不支持。请使用 AI 判定功能分析代码。",
        }

    code = (req.code or "").strip()
    if not code:
        return {
            "success": True,
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": None,
        }

    if len(code) > MAX_CODE_EXECUTE_CHARS:
        return {
            "success": True,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": f"代码过长（{len(code)} 字符），当前限制 {MAX_CODE_EXECUTE_CHARS} 字符。",
        }

    stdin = (req.stdin or "")[:MAX_STDIN_CHARS]

    # Session ownership check (if session_id provided)
    if req.session_id:
        user = get_user_by_username(req.username, db)
        session = (
            db.query(models.CodeSession)
            .filter(
                models.CodeSession.id == req.session_id,
                models.CodeSession.username == user.username,
            )
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="代码练习不存在")

    result = _run_code_in_docker(code, stdin)
    result["success"] = True
    return result


@app.post("/code/analyze")
def analyze_code(req: schemas.CodeAnalyzeRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    code = (req.code or "").strip()
    question = (req.question or "").strip()

    if not code:
        raise HTTPException(status_code=400, detail="请先输入代码再进行分析。")
    if not question:
        raise HTTPException(status_code=400, detail="请输入要分析的问题。")

    session = None
    if req.session_id is not None:
        session = (
            db.query(models.CodeSession)
            .filter(
                models.CodeSession.id == req.session_id,
                models.CodeSession.username == user.username,
            )
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="代码练习不存在")

    truncated_code = code
    code_note = ""
    if len(code) > MAX_CODE_ANALYZE_CHARS:
        truncated_code = code[:MAX_CODE_ANALYZE_CHARS]
        code_note = "（注意：代码较长，已截断至前 {} 字符进行分析）".format(MAX_CODE_ANALYZE_CHARS)

    language = (req.language or "").strip() or "未知"
    course_info = normalize_subject(req.course_id, default="")

    if session:
        db.add(models.CodeAIMessage(
            username=user.username,
            session_id=session.id,
            role="user",
            content=question,
            language=language,
            code_snapshot=code,
        ))

    # Check if session is linked to a challenge
    challenge = None
    challenge_id = getattr(session, "challenge_id", None) if session else None
    if challenge_id:
        challenge = db.query(models.CodeChallenge).filter(
            models.CodeChallenge.id == challenge_id,
        ).first()

    if challenge:
        system_prompt = """你是编程学习出题助手。用户正在完成你出的编程题，请根据题目要求分析用户代码。

输出以下格式的中文分析：
## 是否符合题目要求
判断代码是否满足题目要求，指出哪些要求已满足、哪些未满足。

## 问题定位
指出代码中的具体问题。

## 修改建议
给出具体修改方案。

## 边界情况提醒
提醒可能遗漏的边界情况。

## 涉及知识点
列出题目涉及的核心知识点。

## 下一步练习建议
给出 1-2 条具体的学习方向建议。"""

        challenge_context = ""
        if challenge.description:
            challenge_context += f"\n题目描述：{challenge.description}"
        if challenge.requirements:
            challenge_context += f"\n题目要求：{challenge.requirements}"
        if challenge.input_format:
            challenge_context += f"\n输入格式：{challenge.input_format}"
        if challenge.output_format:
            challenge_context += f"\n输出格式：{challenge.output_format}"
        if challenge.examples:
            challenge_context += f"\n示例：{challenge.examples}"

        user_message = f"""语言：{language}
课程：{course_info or "未指定"}
题目名称：{challenge.title}
难度：{challenge.difficulty}
知识点：{challenge.knowledge_point or "未指定"}
{challenge_context}
{code_note}

用户代码：
```
{truncated_code}
```

用户问题：{question}"""
    else:
        system_prompt = CODE_ANALYZE_SYSTEM_PROMPT
        user_message = f"""语言：{language}
课程：{course_info or "未指定"}
{code_note}

代码：
```
{truncated_code}
```

用户问题：{question}"""

    check_usage_limit(user.username, "code_analyze", db)

    answer = call_deepseek(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
    )

    record_ai_usage(user.username, "code_analyze", db, estimated_tokens=estimate_tokens_from_text(answer), status="success")

    answer = normalize_assistant_markdown(answer)

    if session:
        db.add(models.CodeAIMessage(
            username=user.username,
            session_id=session.id,
            role="assistant",
            content=answer,
            language=language,
        ))
        db.commit()

    return {
        "success": True,
        "answer": answer,
        "language": language,
        "code_truncated": len(code) > MAX_CODE_ANALYZE_CHARS,
    }


def serialize_code_ai_message(msg):
    return {
        "id": msg.id,
        "username": msg.username,
        "session_id": msg.session_id,
        "role": msg.role,
        "content": msg.content,
        "language": msg.language,
        "code_snapshot": msg.code_snapshot,
        "created_at": msg.created_at,
    }


@app.get("/code/sessions/{session_id}/messages")
def get_code_session_messages(session_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    session = (
        db.query(models.CodeSession)
        .filter(
            models.CodeSession.id == session_id,
            models.CodeSession.username == user.username,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="代码练习不存在")

    messages = (
        db.query(models.CodeAIMessage)
        .filter(models.CodeAIMessage.session_id == session_id)
        .order_by(models.CodeAIMessage.created_at.asc())
        .all()
    )
    return {"messages": [serialize_code_ai_message(m) for m in messages]}


@app.delete("/code/sessions/{session_id}/messages")
def delete_code_session_messages(session_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    session = (
        db.query(models.CodeSession)
        .filter(
            models.CodeSession.id == session_id,
            models.CodeSession.username == user.username,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="代码练习不存在")

    db.query(models.CodeAIMessage).filter(
        models.CodeAIMessage.session_id == session_id,
    ).delete()
    db.commit()
    return {"success": True}


CODE_CHALLENGE_GENERATE_PROMPT = """你是编程学习出题助手。根据用户的学习背景和编程进度，生成一道合适的编程练习题。

要求：
1. 题目难度适合用户当前水平
2. 题目可以在单文件中完成，不依赖第三方库
3. 不要求读取文件、网络请求或系统命令
4. 题目描述要清晰，输入输出格式要明确
5. starter_code 提供代码框架，让用户填写核心逻辑
6. reference_solution 是完整参考解法

请严格按照以下 JSON 格式输出（不要输出其他内容）：

```json
{
  "title": "题目标题",
  "difficulty": "基础|中等|提高",
  "knowledge_point": "涉及的核心知识点",
  "description": "题目详细描述",
  "requirements": "具体要求，编号列表",
  "input_format": "输入格式说明",
  "output_format": "输出格式说明",
  "examples": "示例输入输出",
  "starter_code": "用户可编辑的起始代码框架",
  "reference_solution": "完整参考解法"
}
```"""


@app.post("/code/challenges/generate")
def generate_code_challenge(req: schemas.CodeChallengeGenerateRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    language = (req.language or "Python").strip()
    if language not in CODE_TEMPLATES:
        language = "Python"
    difficulty = (req.difficulty or "基础").strip()
    if difficulty not in ("基础", "中等", "提高"):
        difficulty = "基础"
    course_id = normalize_subject(req.course_id, default="")

    challenge_source = (req.source or "normal").strip()
    if challenge_source not in ("normal", "diagnosis"):
        challenge_source = "normal"
    target_weak_point = (req.target_weak_point or req.focus or "").strip()

    recommended_focus = ""
    if not target_weak_point and course_id:
        weak_points = get_weak_knowledge_points(user.username, course_id, db)
        if weak_points:
            recommended_focus = weak_points[0]["title"]
            target_weak_point = recommended_focus

    # Gather user's programming progress summary
    progress_query = db.query(models.CodeSession).filter(
        models.CodeSession.username == user.username,
    )
    if course_id:
        progress_query = progress_query.filter(models.CodeSession.course_id == course_id)
    all_sessions = progress_query.order_by(models.CodeSession.updated_at.desc()).all()
    total_exercises = len(all_sessions)
    lang_counts: dict[str, int] = {}
    for s in all_sessions:
        lang_counts[s.language] = lang_counts.get(s.language, 0) + 1
    recent_titles = [s.title for s in all_sessions[:3] if s.title]

    # Recent AI analysis history (max 3 summaries)
    recent_history_summary = ""
    if all_sessions:
        recent_session_ids = [s.id for s in all_sessions[:3]]
        recent_messages = (
            db.query(models.CodeAIMessage)
            .filter(models.CodeAIMessage.session_id.in_(recent_session_ids))
            .order_by(models.CodeAIMessage.created_at.desc())
            .limit(6)
            .all()
        )
        if recent_messages:
            summaries = []
            for msg in recent_messages:
                content_preview = msg.content[:80].replace("\n", " ")
                summaries.append(f"[{msg.role}] {content_preview}")
            recent_history_summary = "；".join(summaries)

    focus_text = f"用户想练习的知识点：{req.focus.strip()}" if req.focus.strip() else ""
    if target_weak_point:
        hint = "系统检测到用户当前薄弱知识点" if recommended_focus else "本题针对的薄弱点"
        weak_point_text = (
            f"{hint}：{target_weak_point}。"
            f"请优先围绕该知识点设计题目，题目难度不要过高，不要超出当前课程范围。"
        )
    else:
        weak_point_text = ""

    is_diagnosis_driven = (req.source or "").strip() == "diagnosis"
    diagnosis_context = ""
    if is_diagnosis_driven and req.diagnosis_summary:
        diagnosis_summary = req.diagnosis_summary[:2000]
        diagnosis_context = f"""

以下是最新的编程学习诊断报告摘要。请根据诊断报告中的薄弱点生成一道针对性训练题：
{diagnosis_summary}

重要要求：
- 题目必须针对诊断报告中最突出的薄弱点
- 题目应能训练一个核心知识点
- 难度不要过高，从基础概念开始训练
- 不要直接复述诊断报告原文
- 不要生成过大题目
- 不要生成需要复杂数学背景的题"""

    progress_summary = f"""用户编程进度：
- 当前课程：{course_id or "未指定"}
- 编程语言：{language}
- 总练习数：{total_exercises}
- 各语言练习分布：{lang_counts or "暂无"}
- 最近练习：{recent_titles or "暂无"}
- 最近 AI 分析摘要：{recent_history_summary or "暂无"}
{focus_text}
{weak_point_text}
{diagnosis_context}"""

    if is_diagnosis_driven:
        question_text = f"请根据诊断报告中的薄弱点，为上述用户生成一道 {difficulty} 难度的 {language} 针对性训练题。"
    else:
        question_text = f"请为上述用户生成一道 {difficulty} 难度的 {language} 编程题。"

    user_prompt = f"""{progress_summary}

{question_text}"""

    check_usage_limit(user.username, "challenge_generate", db)

    ai_response = call_deepseek(
        [
            {"role": "system", "content": CODE_CHALLENGE_GENERATE_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )

    record_ai_usage(user.username, "challenge_generate", db, estimated_tokens=estimate_tokens_from_text(ai_response), status="success")

    # Parse JSON from AI response
    import json as json_module
    import re as re_module

    json_match = re_module.search(r"```json\s*([\s\S]*?)\s*```", ai_response)
    if json_match:
        json_str = json_match.group(1)
    else:
        raise HTTPException(status_code=500, detail="AI 生成题目格式异常，请重试")

    try:
        challenge_data = json_module.loads(json_str)
    except json_module.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI 生成题目解析失败，请重试")

    required_fields = ["title", "difficulty", "description"]
    for field in required_fields:
        if not challenge_data.get(field):
            raise HTTPException(status_code=500, detail=f"AI 生成题目缺少 {field}，请重试")

    challenge = models.CodeChallenge(
        username=user.username,
        course_id=course_id,
        language=language,
        title=str(challenge_data.get("title", ""))[:255],
        difficulty=str(challenge_data.get("difficulty", difficulty))[:20],
        knowledge_point=str(challenge_data.get("knowledge_point") or recommended_focus or "")[:255],
        description=str(challenge_data.get("description", "")),
        requirements=str(challenge_data.get("requirements", "")),
        input_format=str(challenge_data.get("input_format", "")),
        output_format=str(challenge_data.get("output_format", "")),
        examples=str(challenge_data.get("examples", "")),
        starter_code=str(challenge_data.get("starter_code", CODE_TEMPLATES.get(language, ""))),
        reference_solution=str(challenge_data.get("reference_solution", "")),
        source=challenge_source,
        target_weak_point=target_weak_point or None,
    )
    db.add(challenge)
    db.flush()

    session = models.CodeSession(
        username=user.username,
        course_id=course_id,
        title=challenge.title,
        language=language,
        code=challenge.starter_code or CODE_TEMPLATES.get(language, ""),
        challenge_id=challenge.id,
        session_type="challenge",
    )
    db.add(session)
    db.commit()
    db.refresh(challenge)
    db.refresh(session)

    return {
        "success": True,
        "challenge": serialize_code_challenge(challenge),
        "session": serialize_code_session(session),
    }


@app.get("/code/challenges/{challenge_id}")
def get_code_challenge(challenge_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    challenge = (
        db.query(models.CodeChallenge)
        .filter(
            models.CodeChallenge.id == challenge_id,
            models.CodeChallenge.username == user.username,
        )
        .first()
    )
    if not challenge:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {"challenge": serialize_code_challenge(challenge)}


CODE_CHALLENGE_SUBMIT_PROMPT = """你是编程学习判题助手。请根据题目要求，仔细分析用户提交的代码，给出结构化的判定反馈。

重要：你没有真实运行这段代码。请基于代码静态分析、逻辑正确性、语法正确性和对题目要求的满足程度来判定。

按要求输出以下 Markdown 格式：

## 判定结论
（从以下选一项，不要编造其他结论）
- **大概率通过**：代码逻辑正确，应该能通过大部分测试
- **可能部分通过**：代码有部分正确的逻辑，但存在一些问题
- **大概率不通过**：代码有较严重的逻辑错误或未完成

## 按题目要求逐项检查
逐条列出题目要求，标注用户代码是否满足（✅ / ⚠️ / ❌），给出简要说明。

## 主要问题
列出代码中的具体问题，每个问题一行。如果代码为空或明显未完成请直接指出。

## 边界情况提醒
提醒可能遗漏的边界情况。

## 修改建议
给出具体修改方案，可以包含关键代码片段。

## 可参考的关键思路
简要说明这道题的正确解法思路（不要直接贴完整参考代码，给思路即可）。"""


@app.post("/code/challenges/{challenge_id}/submit")
def submit_code_challenge(challenge_id: int, req: schemas.CodeChallengeSubmitRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)

    challenge = (
        db.query(models.CodeChallenge)
        .filter(
            models.CodeChallenge.id == challenge_id,
            models.CodeChallenge.username == user.username,
        )
        .first()
    )
    if not challenge:
        raise HTTPException(status_code=404, detail="题目不存在")

    session = (
        db.query(models.CodeSession)
        .filter(
            models.CodeSession.id == req.session_id,
            models.CodeSession.username == user.username,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="代码练习不存在")

    code = (req.code or "").strip()
    language = (req.language or challenge.language or "").strip()

    if not code:
        status = "failed"
        ai_feedback = (
            "## 判定结论\n\n"
            "**大概率不通过**\n\n"
            "## 按题目要求逐项检查\n\n"
            "## 主要问题\n\n"
            "用户尚未提交任何代码。请先编写代码再提交判定。\n\n"
            "## 边界情况提醒\n\n"
            "## 修改建议\n\n"
            "请先根据题目要求编写代码。\n\n"
            "## 可参考的关键思路\n"
        )
    elif language and challenge.language and language.lower() != challenge.language.lower():
        status = "failed"
        ai_feedback = (
            f"## 判定结论\n\n"
            f"**大概率不通过**\n\n"
            f"## 按题目要求逐项检查\n\n"
            f"## 主要问题\n\n"
            f"题目要求使用 {challenge.language} 编写，但当前提交的代码语言为 {language}。"
            f"请切换到 {challenge.language} 后再提交。\n\n"
            f"## 边界情况提醒\n\n"
            f"## 修改建议\n\n"
            f"请使用 {challenge.language} 重新编写代码。\n\n"
            f"## 可参考的关键思路\n"
        )
    else:
        # Build challenge context
        challenge_context = ""
        if challenge.description:
            challenge_context += f"\n## 题目描述\n{challenge.description}\n"
        if challenge.requirements:
            challenge_context += f"\n## 题目要求\n{challenge.requirements}\n"
        if challenge.input_format:
            challenge_context += f"\n## 输入格式\n{challenge.input_format}\n"
        if challenge.output_format:
            challenge_context += f"\n## 输出格式\n{challenge.output_format}\n"
        if challenge.examples:
            challenge_context += f"\n## 示例\n{challenge.examples}\n"

        user_prompt = f"""## 题目信息
语言：{challenge.language}
标题：{challenge.title}
难度：{challenge.difficulty}
知识点：{challenge.knowledge_point or "未指定"}
{challenge_context}

## 用户提交的代码
```{challenge.language}
{code[:8000]}
```

请根据题目要求判定以上代码。"""

        check_usage_limit(user.username, "code_analyze", db)

        ai_feedback = call_deepseek(
            [
                {"role": "system", "content": CODE_CHALLENGE_SUBMIT_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )

        record_ai_usage(user.username, "code_analyze", db, estimated_tokens=estimate_tokens_from_text(ai_feedback), status="success")

        ai_feedback = normalize_assistant_markdown(ai_feedback)

        # Determine status from AI response
        if "大概率不通过" in ai_feedback:
            status = "failed"
        elif "可能部分通过" in ai_feedback:
            status = "partial"
        elif "大概率通过" in ai_feedback:
            status = "probable_pass"
        else:
            status = "unknown"

    # Save attempt record
    attempt = models.CodeChallengeAttempt(
        username=user.username,
        session_id=session.id,
        challenge_id=challenge.id,
        language=language,
        code=code,
        status=status,
        ai_feedback=ai_feedback,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    # Also save as AI message so it appears in chat history
    db.add(models.CodeAIMessage(
        username=user.username,
        session_id=session.id,
        role="user",
        content=f"提交答案（题目：{challenge.title}）",
        language=language,
        code_snapshot=code,
    ))
    db.add(models.CodeAIMessage(
        username=user.username,
        session_id=session.id,
        role="assistant",
        content=ai_feedback,
        language=language,
    ))
    db.commit()

    return {
        "success": True,
        "status": status,
        "ai_feedback": ai_feedback,
        "attempt_id": attempt.id,
    }


CODE_LEARNING_DIAGNOSIS_PROMPT = """你是编程学习诊断助手。根据用户的代码练习记录、AI 分析历史和出题记录，生成一份结构化的编程学习诊断报告。

要求：
1. 如果数据明显不足（少于 3 条练习记录），不要编造内容，明确说明「当前练习数据较少，以下建议仅作为初步参考」
2. 从 AI 分析记录中提取反复出现的问题模式，找出薄弱点
3. 每个薄弱点必须基于实际数据，给出证据依据
4. 7 天学习计划要具体可执行，每天一个明确的小目标
5. 推荐出题方向要结合用户当前语言的薄弱环节

请严格按照以下 Markdown 格式输出：

## 编程学习概况
用户总练习数、各语言分布、AI 出题数、最近学习动态的简要概述。

## 主要薄弱点
- **薄弱点名称**：具体表现；可能原因；对应知识点
- （2~4 个薄弱点，如果没有足够数据则标注「数据不足」）

## 证据依据
引用最近练习和 AI 分析中的具体现象。

## 下一步训练建议
3~5 个具体训练方向。

## 推荐 AI 出题方向
3~5 个适合 AI 出题的练习主题。

## 7 天学习计划
| 天数 | 目标 | 方式 |
|------|------|------|
| 第 N 天 | 目标描述 | 自由练习 / AI 出题 / 专项分析 |
"""


@app.post("/code/learning-diagnosis")
def generate_learning_diagnosis(req: schemas.CodeLearningDiagnosisRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    course_id = normalize_subject(req.course_id, default="")
    language_filter = (req.language or "").strip()

    # Query sessions for this user + course
    session_query = db.query(models.CodeSession).filter(
        models.CodeSession.username == user.username,
    )
    if course_id:
        session_query = session_query.filter(models.CodeSession.course_id == course_id)
    if language_filter:
        session_query = session_query.filter(models.CodeSession.language == language_filter)
    all_sessions = session_query.order_by(models.CodeSession.updated_at.desc()).all()

    if len(all_sessions) < 3:
        return {
            "success": True,
            "summary": (
                "当前还没有足够的编程练习记录（至少需要 3 条），请先完成几次 AI 出题或代码分析。\n\n"
                "建议：\n"
                "- 点击「AI 出题」生成一道编程题\n"
                "- 写代码后点击「发送」让 AI 分析\n"
                "- 积累 3 条以上记录后再生成诊断报告"
            ),
            "generated_at": utc_now().isoformat(),
            "used_sessions_count": len(all_sessions),
            "used_messages_count": 0,
            "used_challenges_count": 0,
            "data_insufficient": True,
        }

    # Build progress summary
    lang_counts: dict[str, int] = {}
    challenge_count = 0
    normal_count = 0
    for s in all_sessions:
        lang_counts[s.language] = lang_counts.get(s.language, 0) + 1
        st = getattr(s, "session_type", None) or "normal"
        if st == "challenge":
            challenge_count += 1
        else:
            normal_count += 1

    # Recent sessions (max 10)
    recent_sessions = all_sessions[:10]
    session_summaries = []
    session_ids = [s.id for s in recent_sessions]
    for s in recent_sessions:
        challenge_info = ""
        cid = getattr(s, "challenge_id", None)
        if cid:
            ch = db.query(models.CodeChallenge).filter(models.CodeChallenge.id == cid).first()
            if ch:
                challenge_info = f" [AI出题: {ch.knowledge_point or '无'}]"
        session_summaries.append(
            f"- [{getattr(s, 'session_type', 'normal') or 'normal'}] {s.title} ({s.language}){challenge_info}"
        )

    # Recent AI messages (max 10, each truncated to 800 chars)
    recent_messages = (
        db.query(models.CodeAIMessage)
        .filter(models.CodeAIMessage.session_id.in_(session_ids))
        .order_by(models.CodeAIMessage.created_at.desc())
        .limit(20)
        .all()
    )
    message_summaries = []
    for msg in recent_messages[:10]:
        preview = msg.content[:800]
        if len(msg.content) > 800:
            preview += "..."
        message_summaries.append(
            f"[{msg.role}] ({msg.language or '未知'}) {preview}"
        )

    # Recent challenges (max 5)
    challenges = (
        db.query(models.CodeChallenge)
        .filter(models.CodeChallenge.username == user.username)
        .order_by(models.CodeChallenge.created_at.desc())
        .limit(5)
        .all()
    )
    challenge_summaries = []
    for ch in challenges:
        challenge_summaries.append(
            f"- {ch.title} ({ch.language}, {ch.difficulty}, 知识点: {ch.knowledge_point or '未指定'})"
        )

    progress_summary = f"""## 用户编程数据汇总

总练习数：{len(all_sessions)}（AI 出题：{challenge_count}，自由练习：{normal_count}）
各语言分布：{lang_counts}
{course_id and f"当前课程：{course_id}" or "未指定课程"}

### 最近练习列表（最近 {len(recent_sessions)} 条）
{chr(10).join(session_summaries)}

### 最近 AI 分析记录（最近 {len(message_summaries)} 条）
{chr(10).join(message_summaries) if message_summaries else '暂无 AI 分析记录'}

### 最近 AI 出题记录（最近 {len(challenges)} 条）
{chr(10).join(challenge_summaries) if challenge_summaries else '暂无 AI 出题记录'}"""

    user_prompt = f"""{progress_summary}

请根据以上数据生成编程学习诊断报告。"""

    check_usage_limit(user.username, "learning_diagnosis", db)

    ai_response = call_deepseek(
        [
            {"role": "system", "content": CODE_LEARNING_DIAGNOSIS_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )

    record_ai_usage(user.username, "learning_diagnosis", db, estimated_tokens=estimate_tokens_from_text(ai_response), status="success")

    return {
        "success": True,
        "summary": ai_response,
        "generated_at": utc_now().isoformat(),
        "used_sessions_count": len(all_sessions),
        "used_messages_count": min(len(recent_messages), 10),
        "used_challenges_count": len(challenges),
        "data_insufficient": False,
    }


@app.get("/code/progress")
def get_code_progress(username: str, course_id: str = "", db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    query = db.query(models.CodeSession).filter(
        models.CodeSession.username == user.username,
    )
    normalized_course_id = normalize_subject(course_id, default="")
    if normalized_course_id:
        query = query.filter(models.CodeSession.course_id == normalized_course_id)

    sessions = query.order_by(models.CodeSession.updated_at.desc()).all()
    language_counts: dict[str, int] = {}
    for s in sessions:
        language_counts[s.language] = language_counts.get(s.language, 0) + 1

    latest = sessions[0] if sessions else None
    return {
        "total": len(sessions),
        "language_counts": language_counts,
        "recent_updated_at": latest.updated_at if latest else None,
        "recent_title": latest.title if latest else None,
        "recent_language": latest.language if latest else None,
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


# ── Learning Task Center ──

@app.get("/learning/tasks")
def get_learning_tasks(username: str, course_id: str = "", status: str = "", db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    query = db.query(models.LearningTask).filter(
        models.LearningTask.username == user.username,
    )
    normalized_course = normalize_subject(course_id, default="")
    if normalized_course:
        query = query.filter(models.LearningTask.course_id == normalized_course)
    status_filter = (status or "").strip()
    if status_filter and status_filter in ALLOWED_TASK_STATUSES:
        query = query.filter(models.LearningTask.status == status_filter)
    tasks = query.order_by(
        models.LearningTask.status.asc(),
        models.LearningTask.updated_at.desc(),
    ).all()
    # Bulk-fetch knowledge point titles
    kp_ids = [getattr(t, "knowledge_point_id", None) for t in tasks if getattr(t, "knowledge_point_id", None)]
    kp_map: dict[int, str] = {}
    if kp_ids:
        kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(kp_ids)).all()
        for kp in kps:
            kp_map[kp.id] = kp.title
    return {"tasks": [serialize_learning_task(t, knowledge_point_title=kp_map.get(getattr(t, "knowledge_point_id", None))) for t in tasks]}


@app.post("/learning/tasks")
def create_learning_task(req: schemas.LearningTaskCreate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    task_type = (req.task_type or "").strip()
    if task_type not in ALLOWED_TASK_TYPES:
        task_type = "custom"
    status = (req.status or "todo").strip()
    if status not in ALLOWED_TASK_STATUSES:
        status = "todo"
    source = (req.source or "manual").strip()
    if source not in ALLOWED_TASK_SOURCES:
        source = "manual"
    priority = (req.priority or "medium").strip()
    if priority not in ALLOWED_TASK_PRIORITIES:
        priority = "medium"
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="任务标题不能为空")
    now = utc_now()
    task = models.LearningTask(
        username=user.username,
        course_id=normalize_subject(req.course_id, default="") or None,
        title=title[:255],
        description=(req.description or "").strip() or None,
        task_type=task_type,
        status=status,
        source=source,
        priority=priority,
        due_date=req.due_date,
        related_session_id=req.related_session_id,
        related_challenge_id=req.related_challenge_id,
        related_material_id=req.related_material_id,
        knowledge_point_id=req.knowledge_point_id,
        related_question_id=req.related_question_id,
        completed_at=now if status == "done" else None,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"task": serialize_learning_task(task)}


@app.put("/learning/tasks/{task_id}")
def update_learning_task(task_id: int, req: schemas.LearningTaskUpdate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    task = (
        db.query(models.LearningTask)
        .filter(
            models.LearningTask.id == task_id,
            models.LearningTask.username == user.username,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if req.title is not None:
        title = (req.title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="任务标题不能为空")
        task.title = title[:255]
    if req.description is not None:
        task.description = (req.description or "").strip() or None
    if req.task_type is not None:
        new_type = (req.task_type or "").strip()
        if new_type in ALLOWED_TASK_TYPES:
            task.task_type = new_type
    progress_event = None
    if req.status is not None:
        new_status = (req.status or "").strip()
        if new_status in ALLOWED_TASK_STATUSES:
            old_status = task.status
            task.status = new_status
            now = utc_now()
            if new_status == "done" and old_status != "done":
                task.completed_at = now
                if task.knowledge_point_id and task.course_id:
                    progress_event = {
                        "username": user.username,
                        "course_id": task.course_id,
                        "knowledge_point_id": task.knowledge_point_id,
                        "event_type": "task_done",
                        "delta": 5,
                        "reason": f"完成任务「{task.title}」",
                        "source_type": "learning_task",
                        "source_id": task.id,
                    }
            elif new_status != "done" and old_status == "done":
                task.completed_at = None
                if task.knowledge_point_id and task.course_id:
                    progress_event = {
                        "username": user.username,
                        "course_id": task.course_id,
                        "knowledge_point_id": task.knowledge_point_id,
                        "event_type": "task_reopened",
                        "delta": -5,
                        "reason": f"任务「{task.title}」从完成改为进行中",
                        "source_type": "learning_task",
                        "source_id": task.id,
                    }
    if req.priority is not None:
        new_priority = (req.priority or "medium").strip()
        if new_priority in ALLOWED_TASK_PRIORITIES:
            task.priority = new_priority
    if req.due_date is not None:
        task.due_date = req.due_date if (req.due_date or "").strip() else None
    if req.knowledge_point_id is not None:
        task.knowledge_point_id = req.knowledge_point_id
    if req.related_question_id is not None:
        task.related_question_id = req.related_question_id

    task.updated_at = utc_now()
    db.commit()
    db.refresh(task)

    if progress_event:
        apply_knowledge_progress_event(
            username=progress_event["username"],
            course_id=progress_event["course_id"],
            knowledge_point_id=progress_event["knowledge_point_id"],
            event_type=progress_event["event_type"],
            delta=progress_event["delta"],
            reason=progress_event["reason"],
            source_type=progress_event["source_type"],
            source_id=progress_event["source_id"],
            db=db,
        )
        db.commit()

    return {"task": serialize_learning_task(task)}


@app.delete("/learning/tasks/{task_id}")
def delete_learning_task(task_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    task = (
        db.query(models.LearningTask)
        .filter(
            models.LearningTask.id == task_id,
            models.LearningTask.username == user.username,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.delete(task)
    db.commit()
    return {"message": "任务已删除"}


@app.get("/learning/tasks/summary")
def get_learning_tasks_summary(username: str, course_id: str = "", db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    query = db.query(models.LearningTask).filter(
        models.LearningTask.username == user.username,
    )
    normalized_course = normalize_subject(course_id, default="")
    if normalized_course:
        query = query.filter(models.LearningTask.course_id == normalized_course)

    total = query.count()
    todo_count = query.filter(models.LearningTask.status == "todo").count()
    doing_count = query.filter(models.LearningTask.status == "doing").count()
    done_count = query.filter(models.LearningTask.status == "done").count()

    now = utc_now()
    overdue_count = query.filter(
        models.LearningTask.due_date.isnot(None),
        models.LearningTask.due_date < now,
        models.LearningTask.status != "done",
    ).count()

    high_priority_count = query.filter(
        models.LearningTask.priority == "high",
        models.LearningTask.status != "done",
    ).count()

    recent_tasks = query.order_by(models.LearningTask.updated_at.desc()).limit(5).all()

    kp_ids = [getattr(t, "knowledge_point_id", None) for t in recent_tasks if getattr(t, "knowledge_point_id", None)]
    kp_map: dict[int, str] = {}
    if kp_ids:
        kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(kp_ids)).all()
        for kp in kps:
            kp_map[kp.id] = kp.title

    return {
        "total": total,
        "todo_count": todo_count,
        "doing_count": doing_count,
        "done_count": done_count,
        "overdue_count": overdue_count,
        "high_priority_count": high_priority_count,
        "recent_tasks": [serialize_learning_task(t, knowledge_point_title=kp_map.get(getattr(t, "knowledge_point_id", None))) for t in recent_tasks],
    }


@app.get("/learning/dashboard")
def get_learning_dashboard(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)

    # ── Collect all distinct course_ids across tables ──
    course_ids: set[str] = set()

    materials = (
        db.query(models.StudyMaterial)
        .filter(models.StudyMaterial.username == user.username, models.StudyMaterial.is_deleted.is_(False))
        .all()
    )
    for m in materials:
        if m.subject:
            course_ids.add(m.subject)

    kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.username == user.username).all()
    for kp in kps:
        if kp.course_id:
            course_ids.add(kp.course_id)

    tasks = db.query(models.LearningTask).filter(models.LearningTask.username == user.username).all()
    for t in tasks:
        if t.course_id:
            course_ids.add(t.course_id)

    sessions = db.query(models.CodeSession).filter(models.CodeSession.username == user.username).all()
    for s in sessions:
        if s.course_id:
            course_ids.add(s.course_id)

    questions = db.query(models.Question).filter(models.Question.username == user.username).all()
    for q in questions:
        if q.course_id:
            course_ids.add(q.course_id)

    # ── Overview ──
    kp_progresses = (
        db.query(models.UserKnowledgeProgress)
        .filter(models.UserKnowledgeProgress.username == user.username)
        .all()
    )
    avg_mastery = 0
    if kp_progresses:
        scores = [p.mastery_score or 0 for p in kp_progresses]
        avg_mastery = round(sum(scores) / len(scores))

    all_tasks = db.query(models.LearningTask).filter(models.LearningTask.username == user.username)
    todo_task_count = all_tasks.filter(models.LearningTask.status == "todo").count()
    doing_task_count = all_tasks.filter(models.LearningTask.status == "doing").count()
    done_task_count = all_tasks.filter(models.LearningTask.status == "done").count()

    overview = {
        "course_count": len(course_ids),
        "material_count": len(materials),
        "knowledge_point_count": len(kps),
        "average_mastery": avg_mastery,
        "todo_task_count": todo_task_count,
        "doing_task_count": doing_task_count,
        "done_task_count": done_task_count,
        "code_session_count": len(sessions),
        "challenge_count": db.query(models.CodeChallenge).filter(
            models.CodeChallenge.username == user.username
        ).count(),
        "question_count": len(questions),
        "attempt_count": db.query(models.QuestionAttempt).filter(
            models.QuestionAttempt.username == user.username
        ).count(),
    }

    # ── Weak Points ──
    weak_points = []
    weak_progresses = (
        db.query(models.UserKnowledgeProgress)
        .filter(
            models.UserKnowledgeProgress.username == user.username,
            models.UserKnowledgeProgress.mastery_score < 40,
        )
        .order_by(models.UserKnowledgeProgress.mastery_score.asc())
        .limit(5)
        .all()
    )
    if len(weak_progresses) < 5:
        extra = (
            db.query(models.UserKnowledgeProgress)
            .filter(
                models.UserKnowledgeProgress.username == user.username,
                models.UserKnowledgeProgress.status.in_(["not_started", "learning", "reviewing"]),
                ~models.UserKnowledgeProgress.id.in_([p.id for p in weak_progresses]),
            )
            .order_by(models.UserKnowledgeProgress.mastery_score.asc())
            .limit(5 - len(weak_progresses))
            .all()
        )
        weak_progresses.extend(extra)

    kp_id_to_title: dict[int, str] = {}
    kp_id_to_course: dict[int, str] = {}
    if weak_progresses:
        wp_kp_ids = [p.knowledge_point_id for p in weak_progresses]
        wp_kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(wp_kp_ids)).all()
        for kp in wp_kps:
            kp_id_to_title[kp.id] = kp.title
            kp_id_to_course[kp.id] = kp.course_id

    for p in weak_progresses:
        title = kp_id_to_title.get(p.knowledge_point_id, "")
        course_id = kp_id_to_course.get(p.knowledge_point_id, p.course_id)
        weak_points.append({
            "course_id": course_id,
            "course_name": course_id,
            "knowledge_point_id": p.knowledge_point_id,
            "title": title,
            "mastery_score": p.mastery_score or 0,
            "status": p.status or "not_started",
        })

    # ── Recent Activities ──
    activities = []

    # Recent completed tasks
    recent_done_tasks = (
        db.query(models.LearningTask)
        .filter(models.LearningTask.username == user.username, models.LearningTask.status == "done")
        .order_by(models.LearningTask.updated_at.desc())
        .limit(5)
        .all()
    )
    for t in recent_done_tasks:
        activities.append({
            "type": "task_done",
            "title": t.title,
            "course_id": t.course_id or "",
            "course_name": t.course_id or "",
            "created_at": serialize_datetime(t.updated_at) if t.updated_at else None,
        })

    # Recent progress events
    recent_events = (
        db.query(models.KnowledgeProgressEvent)
        .filter(models.KnowledgeProgressEvent.username == user.username)
        .order_by(models.KnowledgeProgressEvent.created_at.desc())
        .limit(5)
        .all()
    )
    event_kp_ids = [e.knowledge_point_id for e in recent_events]
    event_kp_map: dict[int, str] = {}
    event_kp_course: dict[int, str] = {}
    if event_kp_ids:
        ekps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(event_kp_ids)).all()
        for ekp in ekps:
            event_kp_map[ekp.id] = ekp.title
            event_kp_course[ekp.id] = ekp.course_id

    for e in recent_events:
        activities.append({
            "type": "knowledge_progress",
            "title": event_kp_map.get(e.knowledge_point_id, f"知识点#{e.knowledge_point_id}"),
            "course_id": e.course_id,
            "course_name": e.course_id,
            "created_at": serialize_datetime(e.created_at) if e.created_at else None,
        })

    # Recent materials
    recent_materials = (
        db.query(models.StudyMaterial)
        .filter(models.StudyMaterial.username == user.username, models.StudyMaterial.is_deleted.is_(False))
        .order_by(models.StudyMaterial.created_at.desc())
        .limit(3)
        .all()
    )
    for m in recent_materials:
        activities.append({
            "type": "material_uploaded",
            "title": m.original_filename or "资料",
            "course_id": m.subject or "",
            "course_name": m.subject or "",
            "created_at": serialize_datetime(m.created_at) if m.created_at else None,
        })

    # Sort by created_at desc and limit to 10
    activities.sort(key=lambda x: x["created_at"] or "", reverse=True)
    activities = activities[:10]

    # ── Course Summaries ──
    course_summaries = []
    for cid in sorted(course_ids):
        cid_materials = [m for m in materials if m.subject == cid]
        cid_kps = [kp for kp in kps if kp.course_id == cid]
        cid_tasks = [t for t in tasks if t.course_id == cid]
        cid_sessions = [s for s in sessions if s.course_id == cid]
        cid_questions_list = [q for q in questions if q.course_id == cid]

        cid_progresses = [
            p for p in kp_progresses
            if p.course_id == cid
        ]
        cid_avg = 0
        if cid_progresses:
            cid_scores = [p.mastery_score or 0 for p in cid_progresses]
            cid_avg = round(sum(cid_scores) / len(cid_scores))

        course_summaries.append({
            "course_id": cid,
            "course_name": cid,
            "material_count": len(cid_materials),
            "knowledge_point_count": len(cid_kps),
            "average_mastery": cid_avg,
            "todo_task_count": len([t for t in cid_tasks if t.status == "todo"]),
            "doing_task_count": len([t for t in cid_tasks if t.status == "doing"]),
            "done_task_count": len([t for t in cid_tasks if t.status == "done"]),
            "code_session_count": len(cid_sessions),
            "challenge_count": db.query(models.CodeChallenge).filter(
                models.CodeChallenge.username == user.username,
                models.CodeChallenge.course_id == cid,
            ).count(),
            "question_count": len(cid_questions_list),
        })

    # ── Recommendations ──
    recommendations = []
    if todo_task_count > 0:
        recommendations.append(f"你还有 {todo_task_count} 个待完成任务，建议先完成最近的学习任务。")
    if weak_points:
        top_weak = weak_points[0]["title"] if weak_points[0]["title"] else "薄弱知识点"
        recommendations.append(f"你有 {len(weak_points)} 个薄弱知识点，建议优先复习：{top_weak}。")
    if overview["material_count"] == 0:
        recommendations.append("建议先上传课程资料，让 AI 回答更贴合你的课程内容。")
    if overview["knowledge_point_count"] == 0:
        recommendations.append("建议进入课程工作台，使用 AI 生成知识点路线图。")
    if overview["code_session_count"] < 3:
        recommendations.append("建议进入编程学习助手完成几次代码练习，积累诊断数据。")
    if overview["attempt_count"] < 3:
        recommendations.append("建议进入练习中心完成几道题，系统会自动更新知识点掌握度。")
    if not recommendations:
        recommendations.append("当前学习数据较完整，可以继续按薄弱知识点进行针对性练习。")
    recommendations = recommendations[:5]

    return {
        "overview": overview,
        "weak_points": weak_points,
        "recent_activities": activities,
        "course_summaries": course_summaries,
        "recommendations": recommendations,
    }


@app.get("/review/center")
def get_review_center(username: str, course_id: str = "", db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    normalized_course = normalize_subject(course_id, default="")

    # ── Wrong Questions ──
    wrong_query = (
        db.query(models.QuestionAttempt, models.Question)
        .join(models.Question, models.QuestionAttempt.question_id == models.Question.id)
        .filter(
            models.QuestionAttempt.username == user.username,
            models.QuestionAttempt.self_result == "incorrect",
        )
    )
    if normalized_course:
        wrong_query = wrong_query.filter(models.QuestionAttempt.course_id == normalized_course)
    wrong_rows = wrong_query.order_by(models.QuestionAttempt.created_at.desc()).limit(20).all()

    wrong_questions = []
    for attempt, question in wrong_rows:
        wrong_questions.append({
            "question_id": question.id,
            "attempt_id": attempt.id,
            "course_id": question.course_id or "",
            "course_name": question.course_id or "",
            "knowledge_point_id": question.knowledge_point_id,
            "knowledge_point_title": "",
            "question_type": question.type,
            "title": question.title,
            "user_answer": attempt.user_answer or "",
            "correct_answer": question.answer or "",
            "created_at": serialize_datetime(attempt.created_at) if attempt.created_at else None,
        })

    # Fill knowledge point titles for wrong questions
    wrong_kp_ids = [wq["knowledge_point_id"] for wq in wrong_questions if wq["knowledge_point_id"]]
    if wrong_kp_ids:
        wrong_kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(wrong_kp_ids)).all()
        wrong_kp_map = {kp.id: kp.title for kp in wrong_kps}
        for wq in wrong_questions:
            if wq["knowledge_point_id"]:
                wq["knowledge_point_title"] = wrong_kp_map.get(wq["knowledge_point_id"], "")

    # ── Weak Points ──
    weak_progress = (
        db.query(models.UserKnowledgeProgress)
        .filter(
            models.UserKnowledgeProgress.username == user.username,
            models.UserKnowledgeProgress.mastery_score < 40,
        )
    )
    if normalized_course:
        weak_progress = weak_progress.filter(models.UserKnowledgeProgress.course_id == normalized_course)
    weak_progress = weak_progress.order_by(models.UserKnowledgeProgress.mastery_score.asc()).limit(10).all()

    wp_kp_ids = [p.knowledge_point_id for p in weak_progress]
    wp_kp_map: dict[int, tuple[str, str]] = {}
    if wp_kp_ids:
        wp_kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(wp_kp_ids)).all()
        for kp in wp_kps:
            wp_kp_map[kp.id] = (kp.title, kp.course_id)

    weak_points = []
    for p in weak_progress:
        title, kp_course = wp_kp_map.get(p.knowledge_point_id, ("", p.course_id))
        weak_points.append({
            "knowledge_point_id": p.knowledge_point_id,
            "course_id": kp_course or p.course_id,
            "course_name": kp_course or p.course_id,
            "title": title,
            "mastery_score": p.mastery_score or 0,
            "status": p.status or "not_started",
        })

    # ── Negative Events ──
    neg_query = (
        db.query(models.KnowledgeProgressEvent)
        .filter(
            models.KnowledgeProgressEvent.username == user.username,
            models.KnowledgeProgressEvent.delta < 0,
        )
    )
    if normalized_course:
        neg_query = neg_query.filter(models.KnowledgeProgressEvent.course_id == normalized_course)
    neg_events = neg_query.order_by(models.KnowledgeProgressEvent.created_at.desc()).limit(20).all()

    neg_kp_ids = [e.knowledge_point_id for e in neg_events]
    neg_kp_map: dict[int, str] = {}
    if neg_kp_ids:
        neg_kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(neg_kp_ids)).all()
        for kp in neg_kps:
            neg_kp_map[kp.id] = kp.title

    negative_events = []
    for e in neg_events:
        negative_events.append({
            "event_id": e.id,
            "course_id": e.course_id,
            "knowledge_point_id": e.knowledge_point_id,
            "knowledge_point_title": neg_kp_map.get(e.knowledge_point_id, ""),
            "event_type": e.event_type,
            "delta": e.delta,
            "reason": e.reason or "",
            "created_at": serialize_datetime(e.created_at) if e.created_at else None,
        })

    # ── Review Tasks ──
    task_query = (
        db.query(models.LearningTask)
        .filter(
            models.LearningTask.username == user.username,
            models.LearningTask.status != "done",
            models.LearningTask.knowledge_point_id.isnot(None),
        )
    )
    if normalized_course:
        task_query = task_query.filter(models.LearningTask.course_id == normalized_course)
    review_tasks = task_query.order_by(models.LearningTask.updated_at.desc()).limit(10).all()

    task_kp_ids = [t.knowledge_point_id for t in review_tasks if t.knowledge_point_id]
    task_kp_map: dict[int, str] = {}
    if task_kp_ids:
        task_kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(task_kp_ids)).all()
        for kp in task_kps:
            task_kp_map[kp.id] = kp.title

    return {
        "overview": {
            "wrong_question_count": len(wrong_questions),
            "weak_knowledge_count": len(weak_points),
            "negative_event_count": len(negative_events),
            "review_task_count": len(review_tasks),
        },
        "wrong_questions": wrong_questions,
        "weak_points": weak_points,
        "negative_events": negative_events,
        "review_tasks": [
            {
                "task_id": t.id,
                "course_id": t.course_id or "",
                "title": t.title,
                "status": t.status,
                "knowledge_point_id": t.knowledge_point_id,
                "knowledge_point_title": task_kp_map.get(t.knowledge_point_id or 0, ""),
                "due_date": serialize_datetime(t.due_date) if t.due_date else None,
            }
            for t in review_tasks
        ],
    }


class ReviewTaskCreateRequest(BaseModel):
    username: str
    course_id: str = ""
    knowledge_point_id: int | None = None
    question_id: int | None = None
    title: str = ""
    description: str = ""


@app.post("/review/tasks/create")
def create_review_task(req: ReviewTaskCreateRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    course_id = normalize_subject(req.course_id, default="") or None

    if req.knowledge_point_id:
        kp = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.id == req.knowledge_point_id,
                models.KnowledgePoint.username == user.username,
            )
            .first()
        )
        if not kp:
            raise HTTPException(status_code=404, detail="知识点不存在")

    if req.question_id:
        question = (
            db.query(models.Question)
            .filter(
                models.Question.id == req.question_id,
                models.Question.username == user.username,
            )
            .first()
        )
        if not question:
            raise HTTPException(status_code=404, detail="题目不存在")

    kp_obj = None
    q_obj = None
    if req.knowledge_point_id:
        kp_obj = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id == req.knowledge_point_id).first()
    if req.question_id:
        q_obj = db.query(models.Question).filter(models.Question.id == req.question_id).first()

    title = (req.title or "").strip()
    if not title:
        if kp_obj and q_obj:
            title = f"复盘：{kp_obj.title} — {q_obj.title}"
        elif kp_obj:
            title = f"复习：{kp_obj.title}"
        elif q_obj:
            title = f"复盘错题：{q_obj.title}"
        else:
            title = "复盘任务"

    now = utc_now()
    task_course_id = course_id or (kp_obj.course_id if kp_obj else None)
    task = models.LearningTask(
        username=user.username,
        course_id=task_course_id,
        title=title[:255],
        description=(req.description or "").strip() or None,
        task_type="review",
        status="todo",
        source="review_center",
        priority="high",
        knowledge_point_id=req.knowledge_point_id,
        related_question_id=req.question_id,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return {"success": True, "task": serialize_learning_task(task)}


LEARNING_TASKS_FROM_DIAGNOSIS_PROMPT = """你是学习任务规划助手。根据用户的编程学习诊断报告和薄弱知识点，生成 3 到 5 个具体可执行的学习任务。

要求：
1. 每个任务必须具体可执行，不要空泛（如"好好学习"）
2. 任务类型优先使用：code_practice、challenge、review、ask_ai
3. 根据诊断中的薄弱点设置优先级
4. 每个任务要有清晰的描述，说明要做什么
5. 尽量围绕提供的薄弱知识点设计任务
6. 薄弱知识点只作为推荐依据，不要编造不存在的知识点
7. 输出严格 JSON 数组格式

输出格式示例：
[
  {"title": "任务标题", "description": "详细描述", "task_type": "code_practice", "priority": "high", "knowledge_point_title": "对应知识点标题（可选）"},
  {"title": "另一个任务", "description": "详细描述", "task_type": "review", "priority": "medium"}
]"""


@app.post("/learning/tasks/from-diagnosis")
def generate_tasks_from_diagnosis(req: schemas.GenerateTasksFromDiagnosisRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    course_name = (req.course_name or "").strip()
    language = (req.language or "").strip()
    diagnosis_summary = (req.diagnosis_summary or "").strip()
    if not diagnosis_summary:
        raise HTTPException(status_code=400, detail="诊断报告不能为空")

    # Truncate for cost control
    if len(diagnosis_summary) > 2000:
        diagnosis_summary = diagnosis_summary[:2000]

    course_id = normalize_subject(req.course_id, default="") or None

    # Query weak knowledge points for the course
    weak_points = []
    weak_point_id_map: dict[str, int] = {}
    if course_id:
        weak_points = get_weak_knowledge_points(user.username, course_id, db)
        for wp in weak_points:
            weak_point_id_map[wp["title"]] = wp["id"]

    weak_points_context = ""
    if weak_points:
        wp_lines = ["当前课程薄弱知识点（仅作为个性化推荐依据，请勿编造不存在的知识点）："]
        for wp in weak_points:
            wp_lines.append(
                f"- id={wp['id']} title={wp['title']} status={wp['status']} mastery_score={wp['mastery_score']}"
            )
        weak_points_context = "\n".join(wp_lines)
        weak_points_context += (
            "\n生成任务时请尽量围绕这些薄弱知识点，每个任务绑定一个最相关的知识点。"
            "如果任务涉及的知识点不在列表中，可以不绑定。"
            "请在 JSON 输出中增加可选字段 knowledge_point_title（字符串）。"
        )

    user_prompt = f"""课程：{course_name or '未指定'}
编程语言：{language or '未指定'}

{"薄弱知识点参考：" + chr(10) + weak_points_context + chr(10) if weak_points_context else ""}
诊断报告摘要：
{diagnosis_summary}

请根据以上诊断报告生成 3 到 5 个学习任务。"""

    try:
        ai_response = call_deepseek(
            [
                {"role": "system", "content": LEARNING_TASKS_FROM_DIAGNOSIS_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )
        # Parse JSON array from response
        json_match = re.search(r"\[[\s\S]*?\]", ai_response)
        if json_match:
            tasks_data = json.loads(json_match.group(0))
        else:
            tasks_data = json.loads(ai_response)
    except Exception:
        # Fallback: create 3 default tasks
        fallback_weak_point = "诊断报告中的薄弱点"
        for line in diagnosis_summary.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- **") or stripped.startswith("- **"):
                fallback_weak_point = stripped.lstrip("- *").strip()
                if len(fallback_weak_point) > 50:
                    fallback_weak_point = fallback_weak_point[:50] + "..."
                break
        tasks_data = [
            {"title": f"复习：{fallback_weak_point}", "description": f"根据诊断报告复习 {fallback_weak_point}，重点理解薄弱环节。", "task_type": "review", "priority": "high"},
            {"title": "完成一道针对性 AI 出题练习", "description": "使用 AI 出题功能生成一道针对性编程题并完成练习。", "task_type": "challenge", "priority": "high"},
            {"title": "让 AI 分析一次修改后的代码", "description": "将练习代码提交给 AI 分析，获取改进建议。", "task_type": "code_practice", "priority": "medium"},
        ]

    if not isinstance(tasks_data, list) or len(tasks_data) == 0:
        raise HTTPException(status_code=500, detail="AI 未能生成有效任务，请稍后重试")

    created_tasks = []
    now = utc_now()
    for item in tasks_data[:5]:
        task_type = (str(item.get("task_type", "custom"))).strip()
        if task_type not in ALLOWED_TASK_TYPES:
            task_type = "custom"
        priority = (str(item.get("priority", "medium"))).strip()
        if priority not in ALLOWED_TASK_PRIORITIES:
            priority = "medium"

        # Try to bind knowledge_point_id from AI response or title matching
        bound_kp_id = None
        ai_kp_title = str(item.get("knowledge_point_title", "")).strip()
        task_title = str(item.get("title", ""))
        task_desc = str(item.get("description", ""))

        if ai_kp_title and ai_kp_title in weak_point_id_map:
            bound_kp_id = weak_point_id_map[ai_kp_title]
        else:
            for wp_title, wp_id in weak_point_id_map.items():
                if wp_title in task_title or wp_title in task_desc or wp_title in ai_kp_title:
                    bound_kp_id = wp_id
                    break

        task = models.LearningTask(
            username=user.username,
            course_id=course_id,
            title=task_title[:255],
            description=task_desc[:500] or None,
            task_type=task_type,
            status="todo",
            source="code_diagnosis",
            priority=priority,
            knowledge_point_id=bound_kp_id,
            created_at=now,
            updated_at=now,
        )
        db.add(task)
        created_tasks.append(task)

    db.commit()
    for t in created_tasks:
        db.refresh(t)

    return {
        "success": True,
        "tasks": [serialize_learning_task(t) for t in created_tasks],
        "message": f"已生成 {len(created_tasks)} 个学习任务",
    }


# ── Knowledge Points ──────────────────────────────────────────────


@app.get("/knowledge-points")
def list_knowledge_points(
    username: str,
    course_id: str = "",
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    normalized_course = normalize_subject(course_id, default="")
    if not normalized_course:
        raise HTTPException(status_code=400, detail="course_id 不能为空")

    points = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.username == user.username,
            models.KnowledgePoint.course_id == normalized_course,
        )
        .order_by(models.KnowledgePoint.order_index, models.KnowledgePoint.id)
        .all()
    )

    progresses = (
        db.query(models.UserKnowledgeProgress)
        .filter(
            models.UserKnowledgeProgress.username == user.username,
            models.UserKnowledgeProgress.course_id == normalized_course,
        )
        .all()
    )
    progress_map = {p.knowledge_point_id: p for p in progresses}

    # Count questions per knowledge point
    from sqlalchemy import func
    q_counts = (
        db.query(
            models.Question.knowledge_point_id,
            func.count(models.Question.id).label("cnt"),
        )
        .filter(
            models.Question.username == user.username,
            models.Question.course_id == normalized_course,
            models.Question.knowledge_point_id.isnot(None),
        )
        .group_by(models.Question.knowledge_point_id)
        .all()
    )
    qc_map = {row[0]: row[1] for row in q_counts}

    # Count linked materials per knowledge point
    ml_counts = (
        db.query(
            models.MaterialKnowledgeLink.knowledge_point_id,
            func.count(models.MaterialKnowledgeLink.id).label("cnt"),
        )
        .filter(
            models.MaterialKnowledgeLink.username == user.username,
            models.MaterialKnowledgeLink.course_id == normalized_course,
        )
        .group_by(models.MaterialKnowledgeLink.knowledge_point_id)
        .all()
    )
    ml_map = {row[0]: row[1] for row in ml_counts}

    serialized = [
        serialize_knowledge_point(
            p,
            progress_info={
                "mastery_score": progress_map[p.id].mastery_score if p.id in progress_map else 0,
                "status": progress_map[p.id].status if p.id in progress_map else "not_started",
            } if p.id in progress_map else None,
        )
        for p in points
    ]

    for s in serialized:
        s["question_count"] = qc_map.get(s["id"], 0)
        s["material_count"] = ml_map.get(s["id"], 0)

    # Build tree
    point_map = {s["id"]: s for s in serialized}
    for s in serialized:
        s["children"] = []
    roots = []
    for s in serialized:
        parent_id = s.get("parent_id")
        if parent_id and parent_id in point_map:
            point_map[parent_id]["children"].append(s)
        else:
            roots.append(s)

    return {"success": True, "knowledge_points": serialized, "roots": [r["id"] for r in roots]}


@app.post("/knowledge-points")
def create_knowledge_point(req: schemas.KnowledgePointCreate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    normalized_course = normalize_subject(req.course_id, default="")
    if not normalized_course:
        raise HTTPException(status_code=400, detail="course_id 不能为空")

    if req.parent_id:
        parent = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.id == req.parent_id,
                models.KnowledgePoint.username == user.username,
            )
            .first()
        )
        if not parent:
            raise HTTPException(status_code=404, detail="父知识点不存在")

    max_order = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.username == user.username,
            models.KnowledgePoint.course_id == normalized_course,
        )
        .count()
    )

    level = req.level
    if level is None:
        if req.parent_id:
            parent = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id == req.parent_id).first()
            level = (parent.level or 0) + 1 if parent else 0
        else:
            level = 0

    point = models.KnowledgePoint(
        username=user.username,
        course_id=normalized_course,
        parent_id=req.parent_id,
        title=req.title,
        description=req.description or "",
        order_index=req.order_index if req.order_index is not None else max_order,
        level=level,
    )
    db.add(point)
    db.flush()

    progress = models.UserKnowledgeProgress(
        username=user.username,
        course_id=normalized_course,
        knowledge_point_id=point.id,
        mastery_score=0,
        status="not_started",
        practice_count=0,
        task_count=0,
    )
    db.add(progress)
    db.commit()
    db.refresh(point)

    return {
        "success": True,
        "knowledge_point": serialize_knowledge_point(
            point,
            progress_info={"mastery_score": 0, "status": "not_started"},
        ),
    }


@app.put("/knowledge-points/{point_id}")
def update_knowledge_point(
    point_id: int,
    req: schemas.KnowledgePointUpdate,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(req.username, db)
    point = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.id == point_id,
            models.KnowledgePoint.username == user.username,
        )
        .first()
    )
    if not point:
        raise HTTPException(status_code=404, detail="知识点不存在")

    if req.title is not None:
        point.title = req.title
    if req.description is not None:
        point.description = req.description
    if req.order_index is not None:
        point.order_index = req.order_index
    if req.level is not None:
        point.level = req.level
    if req.parent_id is not None:
        if req.parent_id == point_id:
            raise HTTPException(status_code=400, detail="父知识点不能是自己")
        point.parent_id = req.parent_id

    point.updated_at = utc_now()
    db.commit()
    db.refresh(point)

    progress = (
        db.query(models.UserKnowledgeProgress)
        .filter(
            models.UserKnowledgeProgress.username == user.username,
            models.UserKnowledgeProgress.knowledge_point_id == point.id,
        )
        .first()
    )

    return {
        "success": True,
        "knowledge_point": serialize_knowledge_point(
            point,
            progress_info={
                "mastery_score": progress.mastery_score if progress else 0,
                "status": progress.status if progress else "not_started",
            } if progress else None,
        ),
    }


@app.delete("/knowledge-points/{point_id}")
def delete_knowledge_point(
    point_id: int,
    username: str,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    point = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.id == point_id,
            models.KnowledgePoint.username == user.username,
        )
        .first()
    )
    if not point:
        raise HTTPException(status_code=404, detail="知识点不存在")

    children = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.parent_id == point_id,
            models.KnowledgePoint.username == user.username,
        )
        .count()
    )
    if children > 0:
        raise HTTPException(status_code=400, detail="该知识点下存在子知识点，请先删除子知识点")

    db.query(models.UserKnowledgeProgress).filter(
        models.UserKnowledgeProgress.knowledge_point_id == point_id,
        models.UserKnowledgeProgress.username == user.username,
    ).delete()
    db.delete(point)
    db.commit()

    return {"success": True, "message": "知识点已删除"}


@app.put("/knowledge-points/{point_id}/progress")
def update_knowledge_point_progress(
    point_id: int,
    req: schemas.KnowledgeProgressUpdate,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(req.username, db)
    point = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.id == point_id,
            models.KnowledgePoint.username == user.username,
        )
        .first()
    )
    if not point:
        raise HTTPException(status_code=404, detail="知识点不存在")

    progress = (
        db.query(models.UserKnowledgeProgress)
        .filter(
            models.UserKnowledgeProgress.username == user.username,
            models.UserKnowledgeProgress.knowledge_point_id == point_id,
        )
        .first()
    )
    if not progress:
        progress = models.UserKnowledgeProgress(
            username=user.username,
            course_id=point.course_id,
            knowledge_point_id=point_id,
            mastery_score=0,
            status="not_started",
            practice_count=0,
            task_count=0,
        )
        db.add(progress)
        db.flush()

    old_score = progress.mastery_score or 0

    if req.mastery_score is not None:
        progress.mastery_score = max(0, min(100, req.mastery_score))
    if req.status is not None:
        progress.status = req.status
    progress.updated_at = utc_now()
    progress.last_studied_at = utc_now()

    db.commit()
    db.refresh(progress)

    # Record manual_update event if score changed
    new_score = progress.mastery_score or 0
    if new_score != old_score:
        apply_knowledge_progress_event(
            username=user.username,
            course_id=point.course_id,
            knowledge_point_id=point_id,
            event_type="manual_update",
            delta=new_score - old_score,
            reason="用户手动调整掌握度",
            source_type="manual",
            db=db,
        )
        db.commit()

    return {
        "success": True,
        "progress": {
            "id": progress.id,
            "username": progress.username,
            "course_id": progress.course_id,
            "knowledge_point_id": progress.knowledge_point_id,
            "mastery_score": progress.mastery_score,
            "status": progress.status,
            "practice_count": progress.practice_count,
            "task_count": progress.task_count,
            "last_studied_at": serialize_datetime(progress.last_studied_at) if progress.last_studied_at else None,
            "created_at": serialize_datetime(progress.created_at) if progress.created_at else None,
            "updated_at": serialize_datetime(progress.updated_at) if progress.updated_at else None,
        },
    }


@app.get("/knowledge-points/{point_id}/progress-events")
def get_knowledge_point_progress_events(
    point_id: int,
    username: str,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    point = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.id == point_id,
            models.KnowledgePoint.username == user.username,
        )
        .first()
    )
    if not point:
        raise HTTPException(status_code=404, detail="知识点不存在")

    events = (
        db.query(models.KnowledgeProgressEvent)
        .filter(
            models.KnowledgeProgressEvent.knowledge_point_id == point_id,
            models.KnowledgeProgressEvent.username == user.username,
        )
        .order_by(models.KnowledgeProgressEvent.created_at.desc())
        .limit(30)
        .all()
    )

    return {
        "success": True,
        "events": [
            {
                "event_type": e.event_type,
                "delta": e.delta,
                "reason": e.reason,
                "source_type": e.source_type,
                "source_id": e.source_id,
                "created_at": serialize_datetime(e.created_at) if e.created_at else None,
            }
            for e in events
        ],
    }


# ── AI Knowledge Point Generation ─────────────────────────────────


KP_GENERATION_PROMPT = """你是课程大纲设计助手。根据给定的课程名称或课程资料摘要，为该课程生成一份结构化的知识点路线图。

要求：
1. 顶层知识点 4-8 个，覆盖课程核心主题
2. 每个顶层知识点下 2-5 个子知识点
3. 最多两层结构（顶层 + 子层），不要生成过深层级
4. 标题简洁（不超过 15 字），描述具体（不超过 80 字）
5. 知识点按学习逻辑顺序排列
6. 如果根据资料生成，要贴合资料内容
7. 如果根据课程名称生成，要符合该课程常见教学结构
8. 不要生成重复或高度重叠的知识点
9. 不要编造过于细碎或无关的知识点
10. 输出严格 JSON，不要 Markdown

输出格式：
{
  "items": [
    {
      "title": "知识点标题",
      "description": "知识点描述说明",
      "children": [
        {"title": "子知识点标题", "description": "子知识点描述"}
      ]
    }
  ]
}"""


@app.post("/knowledge-points/generate-preview")
def generate_knowledge_points_preview(req: schemas.KnowledgePointGeneratePreviewRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    course_id = normalize_subject(req.course_id, default="")
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id 不能为空")

    mode = (req.mode or "course_name").strip()
    if mode not in ("course_name", "materials"):
        raise HTTPException(status_code=400, detail="mode 必须是 course_name 或 materials")

    max_top = max(3, min(req.max_top_points or 8, 12))
    max_children = max(2, min(req.max_children_per_point or 6, 8))

    course_name = (req.course_name or "").strip() or course_id

    if mode == "materials":
        materials = (
            db.query(models.StudyMaterial)
            .filter(
                models.StudyMaterial.username == user.username,
                models.StudyMaterial.subject == course_id,
                models.StudyMaterial.is_deleted.is_(False),
            )
            .order_by(models.StudyMaterial.created_at.desc())
            .limit(8)
            .all()
        )
        if not materials:
            raise HTTPException(
                status_code=400,
                detail="当前课程还没有可用于生成路线图的资料，请先上传资料或改用课程名称生成。",
            )

        material_snippets = []
        for mat in materials:
            snippet = f"【{mat.original_filename}】"
            text = (mat.extracted_text or "").strip()
            if text:
                snippet += "\n" + text[:1000]
            if mat.summary and (mat.summary or "").strip():
                snippet += "\n摘要：" + (mat.summary or "").strip()[:300]
            material_snippets.append(snippet)

        context_text = "\n\n---\n\n".join(material_snippets)
        prompt_hint = f"课程：{course_name}\n\n以下是该课程已有资料的内容摘要：\n\n{context_text}\n\n请根据以上资料内容生成该课程的知识点路线图。知识点必须贴合资料实际内容，不要凭空编造。顶层最多 {max_top} 个知识点，每个顶层知识点最多 {max_children} 个子知识点。"
    else:
        prompt_hint = f"课程名称：{course_name}\n\n请根据该课程名称生成一份合理的知识点路线图。顶层最多 {max_top} 个知识点，每个顶层知识点最多 {max_children} 个子知识点。"

    check_usage_limit(user.username, "knowledge_generate", db)

    try:
        ai_response = call_deepseek(
            [
                {"role": "system", "content": KP_GENERATION_PROMPT},
                {"role": "user", "content": prompt_hint},
            ]
        )

        record_ai_usage(user.username, "knowledge_generate", db, estimated_tokens=estimate_tokens_from_text(ai_response), status="success")

        # Parse JSON
        json_match = re.search(r"\{[\s\S]*\}", ai_response)
        if json_match:
            result = json.loads(json_match.group(0))
        else:
            result = json.loads(ai_response)

        items = result.get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            raise ValueError("AI 返回的知识点列表为空")

        # Filter and deduplicate
        seen_titles = set()
        clean_items = []
        for item in items:
            title = str(item.get("title", "")).strip()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            desc = str(item.get("description", "")).strip()[:200]
            children = []
            child_seen = set()
            for child in item.get("children", [])[:max_children]:
                c_title = str(child.get("title", "")).strip()
                if not c_title or c_title in child_seen or c_title == title:
                    continue
                child_seen.add(c_title)
                c_desc = str(child.get("description", "")).strip()[:200]
                children.append({"title": c_title, "description": c_desc})
            clean_items.append({"title": title, "description": desc, "children": children})

        if not clean_items:
            raise ValueError("过滤后没有有效知识点")

        return {"success": True, "items": clean_items, "source": mode}

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        raise HTTPException(status_code=500, detail=f"AI 生成结果解析失败，请重试：{str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 生成请求失败：{str(e)}")


@app.post("/knowledge-points/import-generated")
def import_generated_knowledge_points(req: schemas.KnowledgePointImportRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    course_id = normalize_subject(req.course_id, default="")
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id 不能为空")

    items = req.items
    if not isinstance(items, list) or len(items) == 0:
        raise HTTPException(status_code=400, detail="items 不能为空")

    import_mode = (req.import_mode or "append").strip()
    if import_mode not in ("append", "replace"):
        import_mode = "append"

    if import_mode == "replace":
        # Delete existing points and progress for this user + course
        existing_points = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.username == user.username,
                models.KnowledgePoint.course_id == course_id,
            )
            .all()
        )
        existing_ids = [p.id for p in existing_points]
        if existing_ids:
            db.query(models.UserKnowledgeProgress).filter(
                models.UserKnowledgeProgress.knowledge_point_id.in_(existing_ids),
                models.UserKnowledgeProgress.username == user.username,
            ).delete(synchronize_session=False)
            db.query(models.KnowledgePoint).filter(
                models.KnowledgePoint.id.in_(existing_ids),
                models.KnowledgePoint.username == user.username,
            ).delete(synchronize_session=False)
        db.flush()

    # Get the current max order_index for appending
    max_order = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.username == user.username,
            models.KnowledgePoint.course_id == course_id,
        )
        .count()
    )

    created_count = 0
    for idx, item in enumerate(items):
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        description = str(item.get("description", "")).strip()[:255]

        parent = models.KnowledgePoint(
            username=user.username,
            course_id=course_id,
            parent_id=None,
            title=title[:255],
            description=description,
            order_index=max_order + idx,
            level=1,
        )
        db.add(parent)
        db.flush()

        progress = models.UserKnowledgeProgress(
            username=user.username,
            course_id=course_id,
            knowledge_point_id=parent.id,
            mastery_score=0,
            status="not_started",
            practice_count=0,
            task_count=0,
        )
        db.add(progress)
        created_count += 1

        children = item.get("children", [])
        if isinstance(children, list):
            for c_idx, child in enumerate(children):
                c_title = str(child.get("title", "")).strip()
                if not c_title:
                    continue
                c_description = str(child.get("description", "")).strip()[:255]

                child_point = models.KnowledgePoint(
                    username=user.username,
                    course_id=course_id,
                    parent_id=parent.id,
                    title=c_title[:255],
                    description=c_description,
                    order_index=c_idx,
                    level=2,
                )
                db.add(child_point)
                db.flush()

                child_progress = models.UserKnowledgeProgress(
                    username=user.username,
                    course_id=course_id,
                    knowledge_point_id=child_point.id,
                    mastery_score=0,
                    status="not_started",
                    practice_count=0,
                    task_count=0,
                )
                db.add(child_progress)
                created_count += 1

    db.commit()

    return {
        "success": True,
        "message": f"已导入 {created_count} 个知识点",
        "count": created_count,
    }


# ── Practice / Question Bank ──────────────────────────────────────


def serialize_question(q, knowledge_point_title=None):
    return {
        "id": q.id,
        "username": q.username,
        "course_id": q.course_id,
        "knowledge_point_id": q.knowledge_point_id,
        "knowledge_point_title": knowledge_point_title,
        "type": q.type,
        "title": q.title,
        "content": q.content,
        "options": q.options,
        "answer": q.answer,
        "explanation": q.explanation,
        "difficulty": q.difficulty,
        "source": q.source,
        "created_at": serialize_datetime(q.created_at) if q.created_at else None,
        "updated_at": serialize_datetime(q.updated_at) if q.updated_at else None,
    }


def serialize_question_list_item(q, knowledge_point_title=None):
    return {
        "id": q.id,
        "username": q.username,
        "course_id": q.course_id,
        "knowledge_point_id": q.knowledge_point_id,
        "knowledge_point_title": knowledge_point_title,
        "type": q.type,
        "title": q.title,
        "content": q.content,
        "difficulty": q.difficulty,
        "source": q.source,
        "created_at": serialize_datetime(q.created_at) if q.created_at else None,
        "updated_at": serialize_datetime(q.updated_at) if q.updated_at else None,
    }


def serialize_attempt(a, question_title=None):
    return {
        "id": a.id,
        "username": a.username,
        "question_id": a.question_id,
        "question_title": question_title,
        "course_id": a.course_id,
        "knowledge_point_id": a.knowledge_point_id,
        "user_answer": a.user_answer,
        "ai_feedback": a.ai_feedback,
        "self_result": a.self_result,
        "created_at": serialize_datetime(a.created_at) if a.created_at else None,
    }


@app.get("/practice/questions")
def list_questions(
    username: str,
    course_id: str = "",
    knowledge_point_id: int | None = None,
    type: str = "",
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    query = db.query(models.Question).filter(models.Question.username == user.username)
    normalized_course = normalize_subject(course_id, default="")
    if normalized_course:
        query = query.filter(models.Question.course_id == normalized_course)
    if knowledge_point_id is not None:
        query = query.filter(models.Question.knowledge_point_id == knowledge_point_id)
    qtype = (type or "").strip()
    if qtype and qtype in ("choice", "short_answer", "programming"):
        query = query.filter(models.Question.type == qtype)

    questions = query.order_by(models.Question.updated_at.desc()).all()

    kp_ids = [q.knowledge_point_id for q in questions if q.knowledge_point_id]
    kp_map: dict[int, str] = {}
    if kp_ids:
        kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(kp_ids)).all()
        for kp in kps:
            kp_map[kp.id] = kp.title

    return {
        "success": True,
        "questions": [serialize_question_list_item(q, knowledge_point_title=kp_map.get(q.knowledge_point_id)) for q in questions],
    }


@app.post("/practice/questions")
def create_question(req: schemas.QuestionCreate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    qtype = (req.type or "").strip()
    if qtype not in ("choice", "short_answer", "programming"):
        raise HTTPException(status_code=400, detail="无效的题型")
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="题目标题不能为空")
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="题目内容不能为空")

    question = models.Question(
        username=user.username,
        course_id=normalize_subject(req.course_id, default="") or None,
        knowledge_point_id=req.knowledge_point_id,
        type=qtype,
        title=title[:255],
        content=content,
        options=(req.options or "").strip() or None,
        answer=(req.answer or "").strip() or None,
        explanation=(req.explanation or "").strip() or None,
        difficulty=req.difficulty or "基础",
        source=req.source or "manual",
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return {"success": True, "question": serialize_question(question)}


@app.get("/practice/questions/{question_id}")
def get_question(question_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    question = (
        db.query(models.Question)
        .filter(models.Question.id == question_id, models.Question.username == user.username)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    kp_title = None
    if question.knowledge_point_id:
        kp = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id == question.knowledge_point_id).first()
        if kp:
            kp_title = kp.title

    return {"success": True, "question": serialize_question(question, knowledge_point_title=kp_title)}


@app.put("/practice/questions/{question_id}")
def update_question(question_id: int, req: schemas.QuestionUpdate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    question = (
        db.query(models.Question)
        .filter(models.Question.id == question_id, models.Question.username == user.username)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    if req.type is not None:
        new_type = (req.type or "").strip()
        if new_type not in ("choice", "short_answer", "programming"):
            raise HTTPException(status_code=400, detail="无效的题型")
        question.type = new_type
    if req.title is not None:
        question.title = (req.title or "").strip()[:255]
    if req.content is not None:
        question.content = (req.content or "").strip()
    if req.options is not None:
        question.options = (req.options or "").strip() or None
    if req.answer is not None:
        question.answer = (req.answer or "").strip() or None
    if req.explanation is not None:
        question.explanation = (req.explanation or "").strip() or None
    if req.difficulty is not None:
        question.difficulty = req.difficulty
    if req.course_id is not None:
        question.course_id = normalize_subject(req.course_id, default="") or None
    if req.knowledge_point_id is not None:
        question.knowledge_point_id = req.knowledge_point_id

    question.updated_at = utc_now()
    db.commit()
    db.refresh(question)
    return {"success": True, "question": serialize_question(question)}


@app.delete("/practice/questions/{question_id}")
def delete_question(question_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    question = (
        db.query(models.Question)
        .filter(models.Question.id == question_id, models.Question.username == user.username)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    db.query(models.QuestionAttempt).filter(models.QuestionAttempt.question_id == question_id).delete()
    db.delete(question)
    db.commit()
    return {"success": True, "message": "题目已删除"}


@app.post("/practice/questions/{question_id}/attempts")
def submit_attempt(question_id: int, req: schemas.QuestionAttemptCreate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    question = (
        db.query(models.Question)
        .filter(models.Question.id == question_id, models.Question.username == user.username)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    self_result = "unknown"
    if question.type == "choice" and question.answer:
        ua = (req.user_answer or "").strip()
        ca = (question.answer or "").strip()
        if ua and ca and ua == ca:
            self_result = "correct"
        elif ua:
            self_result = "incorrect"

    attempt = models.QuestionAttempt(
        username=user.username,
        question_id=question_id,
        course_id=question.course_id,
        knowledge_point_id=question.knowledge_point_id,
        user_answer=req.user_answer,
        self_result=self_result,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    # Auto-update knowledge point mastery
    if question.knowledge_point_id and question.course_id:
        if self_result == "correct":
            apply_knowledge_progress_event(
                username=user.username,
                course_id=question.course_id,
                knowledge_point_id=question.knowledge_point_id,
                event_type="question_correct",
                delta=8,
                reason=f"选择题「{question.title}」作答正确",
                source_type="question_attempt",
                source_id=attempt.id,
                db=db,
            )
        elif self_result == "incorrect":
            apply_knowledge_progress_event(
                username=user.username,
                course_id=question.course_id,
                knowledge_point_id=question.knowledge_point_id,
                event_type="question_incorrect",
                delta=-5,
                reason=f"选择题「{question.title}」作答错误",
                source_type="question_attempt",
                source_id=attempt.id,
                db=db,
            )
        elif self_result == "unknown" and question.type == "short_answer":
            apply_knowledge_progress_event(
                username=user.username,
                course_id=question.course_id,
                knowledge_point_id=question.knowledge_point_id,
                event_type="question_attempt",
                delta=2,
                reason=f"简答题「{question.title}」已提交作答",
                source_type="question_attempt",
                source_id=attempt.id,
                db=db,
            )
        db.commit()

    return {"success": True, "attempt": serialize_attempt(attempt)}


@app.get("/practice/questions/{question_id}/attempts")
def list_attempts(question_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    question = (
        db.query(models.Question)
        .filter(models.Question.id == question_id, models.Question.username == user.username)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    attempts = (
        db.query(models.QuestionAttempt)
        .filter(
            models.QuestionAttempt.question_id == question_id,
            models.QuestionAttempt.username == user.username,
        )
        .order_by(models.QuestionAttempt.created_at.desc())
        .all()
    )
    return {
        "success": True,
        "attempts": [serialize_attempt(a, question_title=question.title) for a in attempts],
    }


PRACTICE_FEEDBACK_PROMPT = """你是学习辅导助手。根据题目、参考答案、解析和用户的作答，给出结构化反馈。

要求：
1. 答案判断：用户答案是否正确/部分正确/错误
2. 问题分析：分析为什么对/错
3. 正确思路：分析正确解法
4. 知识点提醒：涉及什么知识点
5. 下一步建议：下一步学什么

输出格式：Markdown，结构化清晰。"""


@app.post("/practice/questions/{question_id}/feedback")
def request_feedback(question_id: int, req: schemas.QuestionFeedbackRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    question = (
        db.query(models.Question)
        .filter(models.Question.id == question_id, models.Question.username == user.username)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    user_prompt = f"""题目：{question.title}

题面：
{question.content}

题目类型：{question.type}
参考答案：{question.answer or '未提供'}
解析：{question.explanation or '未提供'}

用户的答案：
{req.user_answer}

请根据以上信息给出反馈。"""

    check_usage_limit(user.username, "question_feedback", db)

    try:
        ai_response = call_deepseek(
            [
                {"role": "system", "content": PRACTICE_FEEDBACK_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )

        record_ai_usage(user.username, "question_feedback", db, estimated_tokens=estimate_tokens_from_text(ai_response), status="success")
    except Exception as e:
        record_ai_usage(user.username, "question_feedback", db, status="failed", error_message=str(e))
        raise HTTPException(status_code=500, detail=f"AI 反馈请求失败：{str(e)}")

    # Keyword-based sentiment analysis on AI feedback
    feedback_lower = ai_response.lower()
    positive_hits = sum(
        1 for kw in ["基本正确", "正确", "思路正确", "掌握较好", "回答正确", "很好", "不错", "答对了"]
        if kw in feedback_lower or kw in ai_response
    )
    negative_hits = sum(
        1 for kw in ["错误", "不符合", "遗漏", "概念混淆", "不正确", "理解有误", "需要纠正", "答错了"]
        if kw in feedback_lower or kw in ai_response
    )

    if positive_hits > negative_hits:
        feedback_event = "ai_feedback_positive"
        feedback_delta = 5
    elif negative_hits > positive_hits:
        feedback_event = "ai_feedback_negative"
        feedback_delta = -3
    else:
        feedback_event = "ai_feedback_neutral"
        feedback_delta = 2

    attempt = models.QuestionAttempt(
        username=user.username,
        question_id=question_id,
        course_id=question.course_id,
        knowledge_point_id=question.knowledge_point_id,
        user_answer=req.user_answer,
        ai_feedback=ai_response,
        self_result="unknown",
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    if question.knowledge_point_id and question.course_id:
        apply_knowledge_progress_event(
            username=user.username,
            course_id=question.course_id,
            knowledge_point_id=question.knowledge_point_id,
            event_type=feedback_event,
            delta=feedback_delta,
            reason=f"AI 反馈「{question.title}」",
            source_type="question_feedback",
            source_id=attempt.id,
            db=db,
        )
        db.commit()

    return {"success": True, "feedback": ai_response, "attempt": serialize_attempt(attempt)}


@app.get("/practice/summary")
def get_practice_summary(
    username: str,
    course_id: str = "",
    knowledge_point_id: int | None = None,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    q_query = db.query(models.Question).filter(models.Question.username == user.username)
    normalized_course = normalize_subject(course_id, default="")
    if normalized_course:
        q_query = q_query.filter(models.Question.course_id == normalized_course)
    if knowledge_point_id is not None:
        q_query = q_query.filter(models.Question.knowledge_point_id == knowledge_point_id)

    a_query = db.query(models.QuestionAttempt).filter(models.QuestionAttempt.username == user.username)
    if normalized_course:
        a_query = a_query.filter(models.QuestionAttempt.course_id == normalized_course)
    if knowledge_point_id is not None:
        a_query = a_query.filter(models.QuestionAttempt.knowledge_point_id == knowledge_point_id)

    total_questions = q_query.count()
    total_attempts = a_query.count()
    choice_count = q_query.filter(models.Question.type == "choice").count()
    short_answer_count = q_query.filter(models.Question.type == "short_answer").count()
    programming_count = q_query.filter(models.Question.type == "programming").count()
    correct_count = a_query.filter(models.QuestionAttempt.self_result == "correct").count()

    recent = a_query.order_by(models.QuestionAttempt.created_at.desc()).limit(5).all()
    recent_attempts = []
    if recent:
        a_q_ids = [a.question_id for a in recent]
        a_q_map = {}
        qs = db.query(models.Question).filter(models.Question.id.in_(a_q_ids)).all()
        for q in qs:
            a_q_map[q.id] = q.title
        recent_attempts = [
            {
                "id": a.id,
                "question_id": a.question_id,
                "question_title": a_q_map.get(a.question_id, ""),
                "self_result": a.self_result,
                "created_at": serialize_datetime(a.created_at) if a.created_at else None,
            }
            for a in recent
        ]

    return {
        "success": True,
        "total_questions": total_questions,
        "total_attempts": total_attempts,
        "choice_count": choice_count,
        "short_answer_count": short_answer_count,
        "programming_count": programming_count,
        "correct_count": correct_count,
        "recent_attempts": recent_attempts,
    }


GENERATE_QUESTION_PROMPT = """你是教育题库生成助手。根据课程和知识点信息，生成练习题。

要求：
1. 题目必须围绕指定的课程和知识点
2. 题面清晰，不超纲
3. 难度适中
4. 选择题必须有 4 个选项（A/B/C/D），并标注标准答案
5. 简答题必须有参考答案和解析
6. 不生成需要运行代码的题
7. 不生成需要外部文件或网络的题
8. 输出严格 JSON 格式

输出格式：
如果是选择题：
{"type": "choice", "title": "题目标题", "content": "题面内容", "options": "A. 选项1\\nB. 选项2\\nC. 选项3\\nD. 选项4", "answer": "A", "explanation": "解析说明"}

如果是简答题：
{"type": "short_answer", "title": "题目标题", "content": "题面内容", "answer": "参考答案", "explanation": "解析说明"}"""


@app.post("/practice/questions/generate")
def generate_questions(req: schemas.GenerateQuestionRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    count = min(max(req.count, 1), 5)
    qtype = (req.type or "choice").strip()
    if qtype not in ("choice", "short_answer"):
        raise HTTPException(status_code=400, detail="AI 生成仅支持 choice 和 short_answer")

    course_name = (req.course_name or req.course_id or "").strip()
    kp_title = (req.knowledge_point_title or "").strip()
    kp_id = req.knowledge_point_id
    difficulty = (req.difficulty or "基础").strip()

    course_id = normalize_subject(req.course_id, default="") or None
    recommended_kp_id = None
    recommended_kp_title = ""

    if not kp_id and not kp_title and course_id:
        weak_points = get_weak_knowledge_points(user.username, course_id, db)
        if weak_points:
            recommended_kp_id = weak_points[0]["id"]
            recommended_kp_title = weak_points[0]["title"]
            kp_title = recommended_kp_title
            kp_id = recommended_kp_id

    kp_label = kp_title or "通用"
    weak_hint = ""
    if recommended_kp_title:
        weak_hint = (
            f"（系统检测到用户薄弱知识点：{recommended_kp_title}，mastery_score={weak_points[0]['mastery_score']}，"
            f"请围绕该知识点出题，难度适中，不超纲。）"
        )

    user_prompt = f"""课程：{course_name or '未指定'}
知识点：{kp_label}{weak_hint}
题型：{qtype}
难度：{difficulty}
数量：{count} 道

请生成 {count} 道{qtype}类型的题目。{"如果选择题，请返回一个 JSON 对象数组。" if qtype == "choice" else "请返回一个 JSON 对象数组。"}

请直接输出 JSON 数组："""

    check_usage_limit(user.username, "question_generate", db)

    try:
        ai_response = call_deepseek(
            [
                {"role": "system", "content": GENERATE_QUESTION_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )

        record_ai_usage(user.username, "question_generate", db, estimated_tokens=estimate_tokens_from_text(ai_response), status="success")

        json_match = re.search(r"\[[\s\S]*?\]", ai_response)
        if json_match:
            questions_data = json.loads(json_match.group(0))
        else:
            obj_match = re.search(r"\{[\s\S]*?\}", ai_response)
            if obj_match:
                questions_data = [json.loads(obj_match.group(0))]
            else:
                questions_data = []
    except Exception as e:
        record_ai_usage(user.username, "question_generate", db, status="failed", error_message=str(e))
        raise HTTPException(status_code=500, detail=f"AI 生成题目失败，JSON 解析错误：{str(e)}")

    if not isinstance(questions_data, list) or len(questions_data) == 0:
        raise HTTPException(status_code=500, detail="AI 未能生成有效题目，请稍后重试")

    created = []
    for item in questions_data[:count]:
        gen_type = (str(item.get("type", qtype))).strip()
        if gen_type not in ("choice", "short_answer"):
            gen_type = qtype
        question = models.Question(
            username=user.username,
            course_id=course_id,
            knowledge_point_id=kp_id,
            type=gen_type,
            title=str(item.get("title", "AI 生成题目"))[:255],
            content=str(item.get("content", "")),
            options=str(item.get("options", "")) or None,
            answer=str(item.get("answer", "")) or None,
            explanation=str(item.get("explanation", "")) or None,
            difficulty=difficulty,
            source="ai",
        )
        db.add(question)
        created.append(question)

    db.commit()
    for q in created:
        db.refresh(q)

    return {
        "success": True,
        "questions": [serialize_question(q) for q in created],
        "message": f"已生成 {len(created)} 道题目",
    }


# ── AI Learning Plan ─────────────────────────────────────

ALLOWED_PLAN_TYPES = {"today", "three_day", "seven_day", "exam", "coding"}
ALLOWED_TASK_TYPES = {"review", "practice", "coding", "material", "summary", "custom"}
ALLOWED_PRIORITIES = {"high", "medium", "low"}


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


def _gather_plan_data(username: str, course_id: str, db: Session):
    """Gather lightweight user data for plan generation."""
    normalized_course = normalize_subject(course_id, default="")

    # Weak knowledge points (max 10)
    weak_kp_query = (
        db.query(models.UserKnowledgeProgress, models.KnowledgePoint.title, models.KnowledgePoint.id, models.KnowledgePoint.course_id)
        .join(models.KnowledgePoint, models.UserKnowledgeProgress.knowledge_point_id == models.KnowledgePoint.id)
        .filter(
            models.UserKnowledgeProgress.username == username,
            models.UserKnowledgeProgress.mastery_score < 40,
        )
    )
    if normalized_course:
        weak_kp_query = weak_kp_query.filter(models.UserKnowledgeProgress.course_id == normalized_course)
    weak_kp_rows = weak_kp_query.order_by(models.UserKnowledgeProgress.mastery_score.asc()).limit(10).all()
    weak_points = [
        {"id": kp_id, "title": title, "course_id": kp_course, "mastery_score": p.mastery_score or 0, "status": p.status or "not_started"}
        for p, title, kp_id, kp_course in weak_kp_rows
    ]

    # Wrong questions (max 10)
    wrong_query = (
        db.query(models.QuestionAttempt, models.Question)
        .join(models.Question, models.QuestionAttempt.question_id == models.Question.id)
        .filter(
            models.QuestionAttempt.username == username,
            models.QuestionAttempt.self_result == "incorrect",
        )
    )
    if normalized_course:
        wrong_query = wrong_query.filter(models.QuestionAttempt.course_id == normalized_course)
    wrong_rows = wrong_query.order_by(models.QuestionAttempt.created_at.desc()).limit(10).all()
    wrong_questions = [
        {
            "title": q.title,
            "course_id": q.course_id or "",
            "knowledge_point_id": q.knowledge_point_id,
            "user_answer": a.user_answer or "",
            "correct_answer": q.answer or "",
        }
        for a, q in wrong_rows
    ]

    # Unfinished tasks (max 10)
    task_query = (
        db.query(models.LearningTask)
        .filter(
            models.LearningTask.username == username,
            models.LearningTask.status != "done",
        )
    )
    if normalized_course:
        task_query = task_query.filter(models.LearningTask.course_id == normalized_course)
    unfinished_tasks = task_query.order_by(models.LearningTask.created_at.desc()).limit(10).all()
    tasks_data = [
        {
            "title": t.title,
            "course_id": t.course_id or "",
            "task_type": t.task_type,
            "status": t.status,
            "priority": t.priority or "medium",
            "knowledge_point_id": t.knowledge_point_id,
        }
        for t in unfinished_tasks
    ]

    # Negative events (max 10)
    neg_query = (
        db.query(models.KnowledgeProgressEvent)
        .filter(
            models.KnowledgeProgressEvent.username == username,
            models.KnowledgeProgressEvent.delta < 0,
        )
    )
    if normalized_course:
        neg_query = neg_query.filter(models.KnowledgeProgressEvent.course_id == normalized_course)
    neg_events = neg_query.order_by(models.KnowledgeProgressEvent.created_at.desc()).limit(10).all()
    neg_kp_ids = [e.knowledge_point_id for e in neg_events]
    neg_kp_map = {}
    if neg_kp_ids:
        neg_kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(neg_kp_ids)).all()
        neg_kp_map = {kp.id: kp.title for kp in neg_kps}
    negative_events = [
        {
            "event_type": e.event_type,
            "delta": e.delta,
            "reason": e.reason or "",
            "course_id": e.course_id,
            "knowledge_point_id": e.knowledge_point_id,
            "knowledge_point_title": neg_kp_map.get(e.knowledge_point_id, ""),
        }
        for e in neg_events
    ]

    # Code sessions summary (max 5)
    code_query = (
        db.query(models.CodeSession)
        .filter(models.CodeSession.username == username)
    )
    if normalized_course:
        code_query = code_query.filter(models.CodeSession.course_id == normalized_course)
    code_sessions = code_query.order_by(models.CodeSession.updated_at.desc()).limit(5).all()
    code_data = [
        {"title": cs.title, "language": cs.language, "course_id": cs.course_id}
        for cs in code_sessions
    ]

    # Material and knowledge point counts
    mat_count = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.username == username,
        models.StudyMaterial.is_deleted == False,
    ).count()

    kp_query = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.username == username)
    if normalized_course:
        kp_query = kp_query.filter(models.KnowledgePoint.course_id == normalized_course)
    kp_count = kp_query.count()

    return {
        "weak_points": weak_points,
        "wrong_questions": wrong_questions,
        "unfinished_tasks": tasks_data,
        "negative_events": negative_events,
        "code_sessions": code_data,
        "material_count": mat_count,
        "knowledge_point_count": kp_count,
    }


PLAN_SYSTEM_PROMPT = """You are a learning plan assistant. Generate a structured learning plan based on the user's data.

Rules:
1. Output ONLY valid JSON — no markdown, no code fences, no extra text.
2. The JSON must have: plan_title (string), summary (string), items (array).
3. Each item must have: day_index (int), title (string, short), description (string, specific), course_id (string), knowledge_point_id (int or null), task_type (string), estimated_minutes (int), priority (string).
4. task_type must be one of: review, practice, coding, material, summary, custom.
5. priority must be one of: high, medium, low.
6. knowledge_point_id must be an existing ID from the user's data, or null.
7. Prioritize low-mastery knowledge points.
8. Don't overload — each day should have at most 3-4 tasks.
9. For "coding" plan type, prioritize coding exercises and code review.
10. For "exam" plan type, prioritize review, practice, and summary.
11. If user data is sparse, still generate a basic plan but mention it in the summary.
12. estimated_minutes should be between 15 and 120."""


def _parse_plan_json(raw_text: str, valid_kp_ids: set[int], username: str) -> dict:
    """Parse and validate AI-generated plan JSON."""
    text = raw_text.strip()
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        end_idx = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end_idx = i
                break
        text = "\n".join(lines[1:end_idx]).strip()

    # Try to find JSON object
    json_start = text.find("{")
    json_end = text.rfind("}")
    if json_start == -1 or json_end == -1:
        raise HTTPException(status_code=500, detail="AI 返回格式异常，未找到 JSON 对象")

    try:
        data = json.loads(text[json_start:json_end + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"AI 返回 JSON 解析失败：{str(exc)}")

    plan_title = str(data.get("plan_title") or "").strip()
    summary = str(data.get("summary") or "").strip()
    raw_items = data.get("items", [])

    if not isinstance(raw_items, list) or len(raw_items) == 0:
        raise HTTPException(status_code=500, detail="AI 返回的计划任务为空，请重试")

    items = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        description = str(item.get("description") or "").strip()
        course_id = str(item.get("course_id") or "").strip()
        kp_id = item.get("knowledge_point_id")
        if kp_id is not None and isinstance(kp_id, (int, float)):
            kp_id = int(kp_id)
            if kp_id not in valid_kp_ids:
                kp_id = None
        else:
            kp_id = None
        task_type = str(item.get("task_type") or "review").strip().lower()
        if task_type not in ALLOWED_TASK_TYPES:
            task_type = "review"
        estimated = int(item.get("estimated_minutes", 30))
        estimated = max(10, min(120, estimated))
        priority = str(item.get("priority") or "medium").strip().lower()
        if priority not in ALLOWED_PRIORITIES:
            priority = "medium"
        day_index = int(item.get("day_index", 1))

        items.append({
            "day_index": day_index,
            "title": title,
            "description": description,
            "course_id": course_id,
            "knowledge_point_id": kp_id,
            "task_type": task_type,
            "estimated_minutes": estimated,
            "priority": priority,
        })

    if not items:
        raise HTTPException(status_code=500, detail="AI 返回的计划中没有有效任务")

    return {
        "plan_title": plan_title,
        "summary": summary,
        "items": items,
    }


@app.post("/learning/plans/generate-preview")
def generate_plan_preview(req: PlanGeneratePreviewRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)

    if req.plan_type not in ALLOWED_PLAN_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的计划类型：{req.plan_type}")

    plan_data = _gather_plan_data(req.username, req.course_id, db)

    # Build valid knowledge point ID set
    valid_kp_ids = {wp["id"] for wp in plan_data["weak_points"]}
    for t in plan_data["unfinished_tasks"]:
        if t["knowledge_point_id"]:
            valid_kp_ids.add(t["knowledge_point_id"])

    # Count total knowledge points
    all_kp_count = db.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == req.username
    ).count()

    user_prompt_parts = [
        f"Plan type: {req.plan_type}",
        f"Days: {req.days}",
        f"Daily study time: {req.daily_minutes} minutes",
        f"User goal: {req.goal or '无特定目标'}" if req.goal else "",
    ]
    if req.course_id:
        user_prompt_parts.append(f"Focus course: {req.course_id}")

    user_prompt_parts.append("")
    user_prompt_parts.append("--- User Data ---")

    user_prompt_parts.append(f"Total knowledge points: {all_kp_count}")
    user_prompt_parts.append(f"Total materials: {plan_data['material_count']}")

    # Weak points
    user_prompt_parts.append(f"\nWeak knowledge points (mastery < 40, max 10, {len(plan_data['weak_points'])} found):")
    for wp in plan_data["weak_points"]:
        user_prompt_parts.append(
            f"  - id={wp['id']}, title={wp['title']}, course={wp['course_id']}, "
            f"mastery={wp['mastery_score']}%, status={wp['status']}"
        )

    # Wrong questions
    user_prompt_parts.append(f"\nRecent wrong answers ({len(plan_data['wrong_questions'])} found):")
    for wq in plan_data["wrong_questions"]:
        user_prompt_parts.append(
            f"  - {wq['title']} (course: {wq['course_id']}, "
            f"user answered: {wq['user_answer'][:80]}, correct: {wq['correct_answer'][:80]})"
        )

    # Unfinished tasks
    user_prompt_parts.append(f"\nUnfinished tasks ({len(plan_data['unfinished_tasks'])} found):")
    for t in plan_data["unfinished_tasks"]:
        user_prompt_parts.append(
            f"  - {t['title']} ({t['task_type']}, status={t['status']}, "
            f"course={t['course_id']}, kp_id={t['knowledge_point_id']})"
        )

    # Negative events
    user_prompt_parts.append(f"\nNegative mastery events ({len(plan_data['negative_events'])} found):")
    for e in plan_data["negative_events"]:
        user_prompt_parts.append(
            f"  - kp={e['knowledge_point_title'] or e['knowledge_point_id']}, "
            f"delta={e['delta']}, type={e['event_type']}"
        )

    # Code sessions
    user_prompt_parts.append(f"\nRecent code sessions ({len(plan_data['code_sessions'])} found):")
    for cs in plan_data["code_sessions"]:
        user_prompt_parts.append(f"  - {cs['title']} ({cs['language']}, course={cs['course_id']})")

    # Instruction
    user_prompt_parts.append(f"\n--- Instructions ---")
    user_prompt_parts.append(f"Generate a {req.plan_type} learning plan for {req.days} day(s).")
    user_prompt_parts.append("Prioritize low-mastery knowledge points and wrong answer topics.")
    if req.plan_type == "coding":
        user_prompt_parts.append("This is a CODING plan — prioritize programming practice and code review tasks.")
    elif req.plan_type == "exam":
        user_prompt_parts.append("This is an EXAM plan — prioritize review, practice, and summary tasks.")
    user_prompt_parts.append("Use ONLY the knowledge_point_ids listed above, or null.")
    user_prompt_parts.append("Each day should have 2-4 tasks totaling around the daily study time.")
    user_prompt_parts.append("If user data is sparse, note that in the summary and suggest general study activities.")

    user_prompt = "\n".join(user_prompt_parts)

    messages = [
        {"role": "system", "content": PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    check_usage_limit(user.username, "learning_plan_generate", db)

    try:
        raw = call_deepseek(messages)

        record_ai_usage(user.username, "learning_plan_generate", db, estimated_tokens=estimate_tokens_from_text(raw), status="success")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="AI 计划生成失败，请稍后重试") from exc

    result = _parse_plan_json(raw, valid_kp_ids, req.username)

    # Add course_name for frontend display
    course_name = req.course_id if req.course_id else "全部课程"

    return {
        "plan_title": result["plan_title"],
        "plan_type": req.plan_type,
        "summary": result["summary"],
        "course_name": course_name,
        "items": result["items"],
    }


@app.post("/learning/plans/import-tasks")
def import_plan_tasks(req: PlanImportTasksRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)

    if not req.items:
        raise HTTPException(status_code=400, detail="没有可导入的计划项")

    # Collect all knowledge_point_ids for validation
    kp_ids_in_plan = set()
    for item in req.items:
        if isinstance(item, dict) and item.get("knowledge_point_id"):
            kp_ids_in_plan.add(int(item["knowledge_point_id"]))

    # Validate knowledge points belong to user
    valid_kp_ids = set()
    if kp_ids_in_plan:
        valid_kps = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.username == req.username,
                models.KnowledgePoint.id.in_(list(kp_ids_in_plan)),
            )
            .all()
        )
        valid_kp_ids = {kp.id for kp in valid_kps}

    created_tasks = []
    today = date.today()

    for item in req.items:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        if not title:
            continue

        description = str(item.get("description") or "").strip()
        course_id = normalize_subject(str(item.get("course_id") or ""), default="") or None

        kp_id = item.get("knowledge_point_id")
        if kp_id is not None:
            kp_id = int(kp_id)
            if kp_id not in valid_kp_ids:
                kp_id = None
        else:
            kp_id = None

        task_type = str(item.get("task_type") or "review").strip().lower()
        if task_type not in ALLOWED_TASK_TYPES:
            task_type = "review"

        priority = str(item.get("priority") or "medium").strip().lower()
        if priority not in ALLOWED_PRIORITIES:
            priority = "medium"

        day_index = max(1, int(item.get("day_index", 1)))
        due_date = today.replace(day=today.day + day_index - 1) if day_index <= 30 else today
        try:
            due_date = datetime.combine(due_date, datetime.min.time())
        except ValueError:
            due_date = datetime.combine(today, datetime.min.time())

        task = models.LearningTask(
            username=req.username,
            course_id=course_id,
            title=title,
            description=description,
            task_type=task_type,
            status="todo",
            source="learning_plan",
            priority=priority,
            due_date=due_date,
            knowledge_point_id=kp_id,
        )
        db.add(task)
        created_tasks.append(task)

    if not created_tasks:
        raise HTTPException(status_code=400, detail="没有有效的任务可导入")

    db.commit()
    for t in created_tasks:
        db.refresh(t)

    return {
        "success": True,
        "created_count": len(created_tasks),
        "message": f"已创建 {len(created_tasks)} 个学习任务，可前往任务中心查看。",
        "tasks": [serialize_learning_task(t) for t in created_tasks],
    }


# ── Knowledge Base Center ────────────────────────────────


def _get_knowledge_base_dashboard_data(username: str, course_id: str, db: Session):
    """Shared helper for knowledge-base dashboard queries."""
    normalized_course = normalize_subject(course_id, default="")

    mat_query = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.username == username,
        models.StudyMaterial.is_deleted == False,
    )
    if normalized_course:
        mat_query = mat_query.filter(models.StudyMaterial.subject == normalized_course)
    materials = mat_query.all()
    material_count = len(materials)
    material_ids = [m.id for m in materials]

    # Linked material IDs
    link_query = db.query(models.MaterialKnowledgeLink.material_id).filter(
        models.MaterialKnowledgeLink.username == username,
    )
    if normalized_course:
        link_query = link_query.filter(models.MaterialKnowledgeLink.course_id == normalized_course)
    linked_material_ids = set(row[0] for row in link_query.distinct().all())

    linked_material_count = len(linked_material_ids)
    unlinked_material_count = material_count - linked_material_count

    kp_query = db.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == username,
    )
    if normalized_course:
        kp_query = kp_query.filter(models.KnowledgePoint.course_id == normalized_course)
    kp_count = kp_query.count()

    # Covered knowledge point IDs
    covered_query = db.query(models.MaterialKnowledgeLink.knowledge_point_id).filter(
        models.MaterialKnowledgeLink.username == username,
    )
    if normalized_course:
        covered_query = covered_query.filter(models.MaterialKnowledgeLink.course_id == normalized_course)
    covered_kp_ids = set(row[0] for row in covered_query.distinct().all())
    covered_kp_count = len(covered_kp_ids)

    uncovered_kp_count = max(0, kp_count - covered_kp_count)
    coverage_rate = round(covered_kp_count * 100 / kp_count, 1) if kp_count > 0 else 0

    return {
        "material_count": material_count,
        "linked_material_count": linked_material_count,
        "unlinked_material_count": unlinked_material_count,
        "knowledge_point_count": kp_count,
        "covered_knowledge_point_count": covered_kp_count,
        "uncovered_knowledge_point_count": uncovered_kp_count,
        "coverage_rate": coverage_rate,
        "materials": materials,
        "material_ids": material_ids,
        "linked_material_ids": linked_material_ids,
        "covered_kp_ids": covered_kp_ids,
        "normalized_course": normalized_course,
    }


@app.get("/knowledge-base/dashboard")
def get_knowledge_base_dashboard(username: str, course_id: str = "", db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    dd = _get_knowledge_base_dashboard_data(username, course_id, db)

    # ── Course summaries ──
    all_kps = (
        db.query(models.KnowledgePoint)
        .filter(models.KnowledgePoint.username == username)
        .all()
    )
    course_kp_map: dict[str, int] = {}
    for kp in all_kps:
        cid = kp.course_id or ""
        course_kp_map[cid] = course_kp_map.get(cid, 0) + 1

    all_links = (
        db.query(models.MaterialKnowledgeLink)
        .filter(models.MaterialKnowledgeLink.username == username)
        .all()
    )
    course_links_by_material: dict[str, set[int]] = {}
    course_links_by_kp: dict[str, set[int]] = {}
    for link in all_links:
        cid = link.course_id or ""
        if cid not in course_links_by_material:
            course_links_by_material[cid] = set()
        if cid not in course_links_by_kp:
            course_links_by_kp[cid] = set()
        course_links_by_material[cid].add(link.material_id)
        course_links_by_kp[cid].add(link.knowledge_point_id)

    course_materials: dict[str, int] = {}
    for m in dd["materials"]:
        cid = m.subject or ""
        course_materials[cid] = course_materials.get(cid, 0) + 1

    all_courses = set(list(course_kp_map.keys()) + list(course_materials.keys()))
    course_summaries = []
    for cid in sorted(all_courses):
        mat_c = course_materials.get(cid, 0)
        linked_mat = len(course_links_by_material.get(cid, set()))
        kp_c = course_kp_map.get(cid, 0)
        covered = len(course_links_by_kp.get(cid, set()))
        rate = round(covered * 100 / kp_c, 1) if kp_c > 0 else 0
        course_summaries.append({
            "course_id": cid,
            "course_name": cid,
            "material_count": mat_c,
            "linked_material_count": linked_mat,
            "knowledge_point_count": kp_c,
            "covered_knowledge_point_count": covered,
            "coverage_rate": rate,
        })

    # ── Unlinked materials ──
    unlinked = [m for m in dd["materials"] if m.id not in dd["linked_material_ids"]]
    unlinked_materials = []
    for m in unlinked[:20]:
        unlinked_materials.append({
            "id": m.id,
            "title": m.original_filename or "",
            "filename": m.original_filename or "",
            "course_id": m.subject or "",
            "course_name": m.subject or "",
            "created_at": serialize_datetime(m.created_at) if m.created_at else None,
        })

    # ── Uncovered points ──
    kps_for_uncovered = db.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == username,
    )
    if dd["normalized_course"]:
        kps_for_uncovered = kps_for_uncovered.filter(models.KnowledgePoint.course_id == dd["normalized_course"])
    kps_for_uncovered = kps_for_uncovered.all()

    progress_query = db.query(models.UserKnowledgeProgress).filter(
        models.UserKnowledgeProgress.username == username,
    )
    if dd["normalized_course"]:
        progress_query = progress_query.filter(models.UserKnowledgeProgress.course_id == dd["normalized_course"])
    progress_map = {p.knowledge_point_id: p for p in progress_query.all()}

    uncovered_points = []
    for kp in kps_for_uncovered:
        if kp.id not in dd["covered_kp_ids"]:
            prog = progress_map.get(kp.id)
            uncovered_points.append({
                "id": kp.id,
                "title": kp.title,
                "course_id": kp.course_id,
                "course_name": kp.course_id,
                "mastery_score": prog.mastery_score or 0 if prog else 0,
                "status": prog.status or "not_started" if prog else "not_started",
            })
    uncovered_points = uncovered_points[:20]

    # ── Recent links ──
    recent = (
        db.query(models.MaterialKnowledgeLink)
        .filter(models.MaterialKnowledgeLink.username == username)
        .order_by(models.MaterialKnowledgeLink.created_at.desc())
        .limit(20)
        .all()
    )
    recent_mat_ids = list(set(r.material_id for r in recent))
    recent_kp_ids = list(set(r.knowledge_point_id for r in recent))
    mat_map = {}
    if recent_mat_ids:
        mats = db.query(models.StudyMaterial).filter(
            models.StudyMaterial.id.in_(recent_mat_ids),
            models.StudyMaterial.is_deleted == False,
        ).all()
        mat_map = {m.id: m.original_filename or "" for m in mats}
    kp_map = {}
    if recent_kp_ids:
        kps = db.query(models.KnowledgePoint).filter(
            models.KnowledgePoint.id.in_(recent_kp_ids),
        ).all()
        kp_map = {kp.id: kp.title for kp in kps}

    recent_links = []
    for r in recent:
        recent_links.append({
            "material_id": r.material_id,
            "material_title": mat_map.get(r.material_id, ""),
            "knowledge_point_id": r.knowledge_point_id,
            "knowledge_point_title": kp_map.get(r.knowledge_point_id, ""),
            "source": r.source or "manual",
            "confidence": r.confidence or 100,
            "created_at": serialize_datetime(r.created_at) if r.created_at else None,
        })

    return {
        "overview": {
            "material_count": dd["material_count"],
            "linked_material_count": dd["linked_material_count"],
            "unlinked_material_count": dd["unlinked_material_count"],
            "knowledge_point_count": dd["knowledge_point_count"],
            "covered_knowledge_point_count": dd["covered_knowledge_point_count"],
            "uncovered_knowledge_point_count": dd["uncovered_knowledge_point_count"],
            "coverage_rate": dd["coverage_rate"],
        },
        "course_summaries": course_summaries,
        "unlinked_materials": unlinked_materials,
        "uncovered_points": uncovered_points,
        "recent_links": recent_links,
    }


@app.get("/materials/{material_id}/knowledge-links")
def get_material_knowledge_links(material_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)

    material = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.id == material_id,
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.is_deleted == False,
        )
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    links = (
        db.query(models.MaterialKnowledgeLink)
        .filter(
            models.MaterialKnowledgeLink.material_id == material_id,
            models.MaterialKnowledgeLink.username == user.username,
        )
        .all()
    )

    kp_ids = [l.knowledge_point_id for l in links]
    kp_map = {}
    if kp_ids:
        kps = db.query(models.KnowledgePoint).filter(
            models.KnowledgePoint.id.in_(kp_ids),
        ).all()
        kp_map = {kp.id: kp for kp in kps}

    return {
        "links": [
            {
                "link_id": l.id,
                "knowledge_point_id": l.knowledge_point_id,
                "knowledge_point_title": kp_map[l.knowledge_point_id].title if l.knowledge_point_id in kp_map else "",
                "course_id": l.course_id,
                "source": l.source or "manual",
                "confidence": l.confidence or 100,
                "reason": l.reason or "",
                "created_at": serialize_datetime(l.created_at) if l.created_at else None,
            }
            for l in links
        ],
    }


@app.post("/materials/{material_id}/knowledge-links")
def add_material_knowledge_link(material_id: int, req: schemas.MaterialKnowledgeLinkCreate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    normalized_course = normalize_subject(req.course_id, default="")

    material = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.id == material_id,
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.is_deleted == False,
        )
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    kp = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.id == req.knowledge_point_id,
            models.KnowledgePoint.username == user.username,
        )
        .first()
    )
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    material_course = normalize_subject(material.subject or "", default="")
    kp_course = normalize_subject(kp.course_id or "", default="")
    if material_course and kp_course and material_course != kp_course:
        raise HTTPException(status_code=400, detail="资料和知识点不属于同一课程")

    # Check duplicate
    existing = (
        db.query(models.MaterialKnowledgeLink)
        .filter(
            models.MaterialKnowledgeLink.username == user.username,
            models.MaterialKnowledgeLink.material_id == material_id,
            models.MaterialKnowledgeLink.knowledge_point_id == req.knowledge_point_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该资料已绑定此知识点")

    link = models.MaterialKnowledgeLink(
        username=user.username,
        course_id=normalized_course or material_course or kp_course,
        material_id=material_id,
        knowledge_point_id=req.knowledge_point_id,
        source=req.source or "manual",
        confidence=req.confidence or 100,
        reason=req.reason or "",
    )
    db.add(link)
    db.commit()
    db.refresh(link)

    return {
        "success": True,
        "link_id": link.id,
        "message": "知识点绑定成功",
    }


@app.delete("/materials/{material_id}/knowledge-links/{link_id}")
def delete_material_knowledge_link(material_id: int, link_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)

    link = (
        db.query(models.MaterialKnowledgeLink)
        .filter(
            models.MaterialKnowledgeLink.id == link_id,
            models.MaterialKnowledgeLink.username == user.username,
            models.MaterialKnowledgeLink.material_id == material_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="绑定关系不存在")

    db.delete(link)
    db.commit()

    return {"success": True, "message": "绑定关系已删除"}


RECOMMEND_SYSTEM_PROMPT = """You are a knowledge point recommendation assistant. Given a study material and a list of knowledge points, recommend which knowledge points the material is most relevant to.

Rules:
1. Output ONLY valid JSON — no markdown, no code fences, no extra text.
2. The JSON must have: recommendations (array).
3. Each recommendation must use an EXISTING knowledge_point_id from the provided list.
4. Never invent new IDs.
5. Max 5 recommendations.
6. If nothing matches well, return an empty array.
7. confidence must be 0-100.
8. reason should be short and specific (1 sentence)."""


@app.post("/materials/{material_id}/knowledge-links/recommend")
def recommend_material_knowledge_links(material_id: int, req: schemas.MaterialKnowledgeRecommendRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    normalized_course = normalize_subject(req.course_id, default="")

    material = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.id == material_id,
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.is_deleted == False,
        )
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    material_course = normalize_subject(material.subject or "", default="")
    target_course = normalized_course or material_course

    kps = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.username == user.username,
            models.KnowledgePoint.course_id == target_course,
        )
        .all()
    )
    if not kps:
        raise HTTPException(status_code=400, detail="当前课程还没有知识点，请先生成知识点路线图。")

    # Build material text (max 2000 chars)
    mat_text = material.summary or ""
    if len(mat_text) < 200 and material.extracted_text:
        mat_text = material.extracted_text[:2000]

    kp_list = [
        f"id={kp.id}, title={kp.title}, desc={kp.description or ''}"
        for kp in kps
    ]

    user_prompt = (
        f"Material: {material.original_filename}\n"
        f"Material content (excerpt): {mat_text[:2000]}\n\n"
        f"Knowledge points in course \"{target_course}\":\n"
        + "\n".join(kp_list)
        + "\n\nRecommend which knowledge points this material relates to."
    )

    messages = [
        {"role": "system", "content": RECOMMEND_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    check_usage_limit(user.username, "material_link_recommend", db)

    try:
        raw = call_deepseek(messages)

        record_ai_usage(user.username, "material_link_recommend", db, estimated_tokens=estimate_tokens_from_text(raw), status="success")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="AI 推荐失败，请稍后重试") from exc

    # Parse JSON
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end_idx = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end_idx = i
                break
        text = "\n".join(lines[1:end_idx]).strip()
    json_start = text.find("{")
    json_end = text.rfind("}")
    if json_start == -1 or json_end == -1:
        raise HTTPException(status_code=500, detail="AI 返回格式异常，未找到 JSON 对象")

    try:
        data = json.loads(text[json_start:json_end + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"AI 返回 JSON 解析失败：{str(exc)}")

    raw_recs = data.get("recommendations", [])
    if not isinstance(raw_recs, list):
        raw_recs = []

    kp_id_set = {kp.id for kp in kps}
    recommendations = []
    for rec in raw_recs:
        if not isinstance(rec, dict):
            continue
        kp_id = rec.get("knowledge_point_id")
        if kp_id is None or not isinstance(kp_id, (int, float)):
            continue
        kp_id = int(kp_id)
        if kp_id not in kp_id_set:
            continue
        confidence = int(rec.get("confidence", 50))
        confidence = max(0, min(100, confidence))
        reason = str(rec.get("reason") or "").strip()
        if not reason:
            reason = "该资料与该知识点相关。"
        kp_title = next((kp.title for kp in kps if kp.id == kp_id), "")
        recommendations.append({
            "knowledge_point_id": kp_id,
            "knowledge_point_title": kp_title,
            "confidence": confidence,
            "reason": reason,
        })

    return {"recommendations": recommendations}


@app.post("/materials/{material_id}/knowledge-links/apply")
def apply_material_knowledge_recommendations(material_id: int, req: schemas.MaterialKnowledgeApplyRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)

    material = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.id == material_id,
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.is_deleted == False,
        )
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")

    if not req.links:
        raise HTTPException(status_code=400, detail="没有可应用的推荐结果")

    # Validate all kp_ids
    kp_ids = []
    for item in req.links:
        if isinstance(item, dict) and item.get("knowledge_point_id"):
            kp_ids.append(int(item["knowledge_point_id"]))
    if not kp_ids:
        raise HTTPException(status_code=400, detail="没有有效的知识点 ID")

    valid_kps = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.id.in_(kp_ids),
            models.KnowledgePoint.username == user.username,
        )
        .all()
    )
    valid_kp_ids = {kp.id for kp in valid_kps}

    # Check existing links
    existing = (
        db.query(models.MaterialKnowledgeLink)
        .filter(
            models.MaterialKnowledgeLink.username == user.username,
            models.MaterialKnowledgeLink.material_id == material_id,
        )
        .all()
    )
    existing_kp_ids = {l.knowledge_point_id for l in existing}

    material_course = normalize_subject(material.subject or "", default="")
    created = 0
    for item in req.links:
        if not isinstance(item, dict):
            continue
        kp_id = int(item.get("knowledge_point_id", 0))
        if kp_id not in valid_kp_ids:
            continue
        if kp_id in existing_kp_ids:
            continue
        confidence = max(0, min(100, int(item.get("confidence", 50))))
        reason = str(item.get("reason") or "").strip() or "AI 推荐"

        kp = next((kp for kp in valid_kps if kp.id == kp_id), None)
        kp_course = normalize_subject(kp.course_id if kp else "", default="")

        link = models.MaterialKnowledgeLink(
            username=user.username,
            course_id=material_course or kp_course,
            material_id=material_id,
            knowledge_point_id=kp_id,
            source="ai",
            confidence=confidence,
            reason=reason,
        )
        db.add(link)
        created += 1

    db.commit()

    return {
        "success": True,
        "created_count": created,
        "message": f"已应用 {created} 个知识点关联",
    }


# ── Admin / Usage ──────────────────────────────────────────


def require_admin(username: str, db: Session):
    admin = get_user_by_username(username, db)
    if not admin.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    return admin


def _write_audit_log(admin_username: str, action: str, db: Session,
                     target_type: str = None, target_username: str = None,
                     detail: str = None):
    try:
        log = models.AdminAuditLog(
            admin_username=admin_username,
            action=action,
            target_type=target_type or "",
            target_username=target_username or "",
            detail=detail or "",
        )
        db.add(log)
        db.commit()
    except Exception:
        logger.warning(f"Failed to write audit log for {admin_username}/{action}")


@app.get("/admin/dashboard")
def admin_dashboard(admin_username: str, db: Session = Depends(get_db)):
    require_admin(admin_username, db)

    today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = db.query(models.User).count()
    plan_counts = {}
    for p in ("free", "pro", "admin"):
        plan_counts[p] = db.query(models.User).filter(models.User.plan == p).count()

    total_materials = (
        db.query(models.StudyMaterial)
        .filter(models.StudyMaterial.is_deleted.is_(False))
        .count()
    )

    # Distinct courses from materials and knowledge_points
    material_courses = {
        row[0] for row in
        db.query(models.StudyMaterial.subject)
        .filter(models.StudyMaterial.is_deleted.is_(False), models.StudyMaterial.subject != "")
        .distinct().all()
        if row[0]
    }
    kp_courses = {
        row[0] for row in
        db.query(models.KnowledgePoint.course_id)
        .filter(models.KnowledgePoint.course_id != "")
        .distinct().all()
        if row[0]
    }
    total_courses = len(material_courses | kp_courses)

    total_knowledge_points = db.query(models.KnowledgePoint).count()
    total_tasks = db.query(models.LearningTask).count()
    total_questions = db.query(models.Question).count()

    today_ai_calls = (
        db.query(models.AiUsageLog)
        .filter(models.AiUsageLog.created_at >= today_start, models.AiUsageLog.status == "success")
        .count()
    )
    total_ai_calls = (
        db.query(models.AiUsageLog)
        .filter(models.AiUsageLog.status == "success")
        .count()
    )

    # Today usage by feature
    today_usage_by_feature = []
    for feature in ALL_FEATURES:
        count = (
            db.query(models.AiUsageLog)
            .filter(
                models.AiUsageLog.feature == feature,
                models.AiUsageLog.status == "success",
                models.AiUsageLog.created_at >= today_start,
            )
            .count()
        )
        if count > 0:
            today_usage_by_feature.append({"feature": feature, "count": count})

    # Recent users
    recent_users = (
        db.query(models.User)
        .order_by(models.User.created_at.desc())
        .limit(10)
        .all()
    )

    # Recent AI logs
    recent_ai_logs = (
        db.query(models.AiUsageLog)
        .order_by(models.AiUsageLog.created_at.desc())
        .limit(20)
        .all()
    )

    system_notes = ["AI 使用记录正常"]
    ai_error_today = (
        db.query(models.AiUsageLog)
        .filter(
            models.AiUsageLog.status != "success",
            models.AiUsageLog.created_at >= today_start,
        )
        .count()
    )
    if ai_error_today > 0:
        system_notes.append(f"今日有 {ai_error_today} 条 AI 调用失败记录")
    else:
        system_notes.append("今日暂无 AI 调用异常")

    return {
        "overview": {
            "total_users": total_users,
            "free_users": plan_counts.get("free", 0),
            "pro_users": plan_counts.get("pro", 0),
            "admin_users": plan_counts.get("admin", 0),
            "total_materials": total_materials,
            "total_courses": total_courses,
            "total_knowledge_points": total_knowledge_points,
            "total_tasks": total_tasks,
            "total_questions": total_questions,
            "today_ai_calls": today_ai_calls,
            "total_ai_calls": total_ai_calls,
        },
        "today_usage_by_feature": today_usage_by_feature,
        "recent_users": [
            {
                "username": u.username,
                "plan": u.plan or "free",
                "is_admin": bool(u.is_admin),
                "created_at": serialize_datetime(u.created_at),
            }
            for u in recent_users
        ],
        "recent_ai_logs": [
            {
                "username": log.username,
                "feature": log.feature,
                "status": log.status,
                "estimated_tokens": log.estimated_tokens,
                "created_at": serialize_datetime(log.created_at),
            }
            for log in recent_ai_logs
        ],
        "system_notes": system_notes,
    }


@app.get("/admin/users")
def admin_users_list(
    admin_username: str,
    keyword: str = "",
    plan: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    require_admin(admin_username, db)

    page = max(1, page)
    page_size = min(100, max(1, page_size))

    today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)

    query = db.query(models.User)
    if keyword := keyword.strip():
        query = query.filter(models.User.username.contains(keyword))
    if plan_filter := plan.strip():
        query = query.filter(models.User.plan == plan_filter)

    total = query.count()
    users = query.order_by(models.User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for u in users:
        material_count = (
            db.query(models.StudyMaterial)
            .filter(models.StudyMaterial.username == u.username, models.StudyMaterial.is_deleted.is_(False))
            .count()
        )
        ai_call_count = (
            db.query(models.AiUsageLog)
            .filter(models.AiUsageLog.username == u.username, models.AiUsageLog.status == "success")
            .count()
        )
        today_ai_call_count = (
            db.query(models.AiUsageLog)
            .filter(
                models.AiUsageLog.username == u.username,
                models.AiUsageLog.status == "success",
                models.AiUsageLog.created_at >= today_start,
            )
            .count()
        )
        kp_count = (
            db.query(models.KnowledgePoint).filter(models.KnowledgePoint.username == u.username).count()
        )
        task_count = (
            db.query(models.LearningTask).filter(models.LearningTask.username == u.username).count()
        )
        items.append({
            "username": u.username,
            "nickname": u.nickname or "",
            "plan": u.plan or "free",
            "is_admin": bool(u.is_admin),
            "plan_expire_at": serialize_datetime(u.plan_expire_at),
            "material_count": material_count,
            "ai_call_count": ai_call_count,
            "today_ai_call_count": today_ai_call_count,
            "knowledge_point_count": kp_count,
            "task_count": task_count,
            "created_at": serialize_datetime(u.created_at),
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/admin/users/{target_username}/detail")
def admin_user_detail(target_username: str, admin_username: str, db: Session = Depends(get_db)):
    require_admin(admin_username, db)
    u = get_user_by_username(target_username, db)

    material_count = (
        db.query(models.StudyMaterial)
        .filter(models.StudyMaterial.username == u.username, models.StudyMaterial.is_deleted.is_(False))
        .count()
    )
    course_set = {
        row[0] for row in
        db.query(models.StudyMaterial.subject)
        .filter(models.StudyMaterial.username == u.username, models.StudyMaterial.is_deleted.is_(False))
        .distinct().all()
        if row[0]
    }
    kp_count = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.username == u.username).count()
    task_count = db.query(models.LearningTask).filter(models.LearningTask.username == u.username).count()
    question_count = db.query(models.Question).filter(models.Question.username == u.username).count()
    attempt_count = db.query(models.QuestionAttempt).filter(models.QuestionAttempt.username == u.username).count()
    code_session_count = db.query(models.CodeSession).filter(models.CodeSession.username == u.username).count()

    # AI usage by feature
    ai_usage_by_feature = {}
    for feature in ALL_FEATURES:
        count = (
            db.query(models.AiUsageLog)
            .filter(models.AiUsageLog.username == u.username, models.AiUsageLog.feature == feature, models.AiUsageLog.status == "success")
            .count()
        )
        if count > 0:
            ai_usage_by_feature[feature] = count

    recent_ai_logs = (
        db.query(models.AiUsageLog)
        .filter(models.AiUsageLog.username == u.username)
        .order_by(models.AiUsageLog.created_at.desc())
        .limit(20)
        .all()
    )
    recent_materials = (
        db.query(models.StudyMaterial)
        .filter(models.StudyMaterial.username == u.username, models.StudyMaterial.is_deleted.is_(False))
        .order_by(models.StudyMaterial.created_at.desc())
        .limit(10)
        .all()
    )
    recent_tasks = (
        db.query(models.LearningTask)
        .filter(models.LearningTask.username == u.username)
        .order_by(models.LearningTask.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "username": u.username,
        "nickname": u.nickname or "",
        "plan": u.plan or "free",
        "is_admin": bool(u.is_admin),
        "plan_expire_at": serialize_datetime(u.plan_expire_at),
        "material_count": material_count,
        "course_count": len(course_set),
        "knowledge_point_count": kp_count,
        "task_count": task_count,
        "question_count": question_count,
        "attempt_count": attempt_count,
        "code_session_count": code_session_count,
        "ai_usage_by_feature": ai_usage_by_feature,
        "recent_ai_logs": [
            {"feature": log.feature, "status": log.status, "estimated_tokens": log.estimated_tokens, "created_at": serialize_datetime(log.created_at)}
            for log in recent_ai_logs
        ],
        "recent_materials": [
            {"id": m.id, "original_filename": m.original_filename, "subject": m.subject, "file_type": m.file_type, "created_at": serialize_datetime(m.created_at)}
            for m in recent_materials
        ],
        "recent_tasks": [
            {"id": t.id, "title": t.title, "task_type": t.task_type, "status": t.status, "created_at": serialize_datetime(t.created_at)}
            for t in recent_tasks
        ],
    }


@app.get("/admin/ai-logs")
def admin_ai_logs(
    admin_username: str,
    feature: str = "",
    target_username: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 30,
    db: Session = Depends(get_db),
):
    require_admin(admin_username, db)

    page = max(1, page)
    page_size = min(100, max(1, page_size))

    query = db.query(models.AiUsageLog)
    if feature_filter := feature.strip():
        query = query.filter(models.AiUsageLog.feature == feature_filter)
    if username_filter := target_username.strip():
        query = query.filter(models.AiUsageLog.username.contains(username_filter))
    if status_filter := status.strip():
        query = query.filter(models.AiUsageLog.status == status_filter)

    total = query.count()
    logs = query.order_by(models.AiUsageLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [
            {
                "username": log.username,
                "feature": log.feature,
                "model": log.model,
                "estimated_tokens": log.estimated_tokens,
                "status": log.status,
                "error_message": log.error_message,
                "created_at": serialize_datetime(log.created_at),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/admin/materials")
def admin_materials(
    admin_username: str,
    keyword: str = "",
    course_id: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    require_admin(admin_username, db)

    page = max(1, page)
    page_size = min(100, max(1, page_size))

    query = db.query(models.StudyMaterial).filter(models.StudyMaterial.is_deleted.is_(False))
    if keyword_filter := keyword.strip():
        query = query.filter(
            models.StudyMaterial.original_filename.contains(keyword_filter)
        )
    if course_filter := normalize_subject(course_id, default=""):
        query = query.filter(models.StudyMaterial.subject == course_filter)

    total = query.count()
    materials = query.order_by(models.StudyMaterial.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    material_ids = [m.id for m in materials]
    link_counts = {}
    if material_ids:
        from sqlalchemy import func as sql_func
        rows = (
            db.query(models.MaterialKnowledgeLink.material_id, sql_func.count(models.MaterialKnowledgeLink.id))
            .filter(models.MaterialKnowledgeLink.material_id.in_(material_ids))
            .group_by(models.MaterialKnowledgeLink.material_id)
            .all()
        )
        link_counts = {row[0]: row[1] for row in rows}

    return {
        "items": [
            {
                "material_id": m.id,
                "username": m.username,
                "original_filename": m.original_filename,
                "subject": m.subject,
                "file_type": m.file_type,
                "file_size": m.file_size,
                "parse_status": m.parse_status,
                "knowledge_link_count": link_counts.get(m.id, 0),
                "created_at": serialize_datetime(m.created_at),
            }
            for m in materials
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/admin/courses-summary")
def admin_courses_summary(admin_username: str, db: Session = Depends(get_db)):
    require_admin(admin_username, db)

    # Collect unique course_id values
    course_ids = set()
    course_ids |= {row[0] for row in db.query(models.StudyMaterial.subject).filter(models.StudyMaterial.is_deleted.is_(False), models.StudyMaterial.subject != "").distinct().all() if row[0]}
    course_ids |= {row[0] for row in db.query(models.KnowledgePoint.course_id).filter(models.KnowledgePoint.course_id != "").distinct().all() if row[0]}
    course_ids |= {row[0] for row in db.query(models.LearningTask.course_id).filter(models.LearningTask.course_id != "").distinct().all() if row[0]}
    course_ids |= {row[0] for row in db.query(models.Question.course_id).filter(models.Question.course_id != "").distinct().all() if row[0]}

    results = []
    for cid in sorted(course_ids):
        user_count = (
            db.query(models.UserKnowledgeProgress)
            .filter(models.UserKnowledgeProgress.course_id == cid)
            .distinct(models.UserKnowledgeProgress.username)
            .count()
        )
        if user_count == 0:
            user_count = (
                db.query(models.StudyMaterial)
                .filter(models.StudyMaterial.subject == cid, models.StudyMaterial.is_deleted.is_(False))
                .distinct(models.StudyMaterial.username)
                .count()
            )
        material_count = (
            db.query(models.StudyMaterial)
            .filter(models.StudyMaterial.subject == cid, models.StudyMaterial.is_deleted.is_(False))
            .count()
        )
        kp_count = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.course_id == cid).count()
        task_count = db.query(models.LearningTask).filter(models.LearningTask.course_id == cid).count()
        question_count = db.query(models.Question).filter(models.Question.course_id == cid).count()

        # Average mastery
        avg_row = (
            db.query(models.UserKnowledgeProgress)
            .filter(models.UserKnowledgeProgress.course_id == cid, models.UserKnowledgeProgress.mastery_score.isnot(None))
            .all()
        )
        if avg_row:
            average_mastery = round(sum(r.mastery_score or 0 for r in avg_row) / len(avg_row), 1)
        else:
            average_mastery = 0

        results.append({
            "course_id": cid,
            "user_count": user_count,
            "material_count": material_count,
            "knowledge_point_count": kp_count,
            "task_count": task_count,
            "question_count": question_count,
            "average_mastery": average_mastery,
        })

    return results


@app.post("/admin/users/{target_username}/plan")
def admin_update_user_plan(
    target_username: str,
    req: schemas.AdminUpdatePlanRequest,
    db: Session = Depends(get_db),
):
    admin = require_admin(req.admin_username, db)

    target_user = get_user_by_username(target_username, db)
    old_plan = target_user.plan or "free"
    plan = (req.plan or "free").strip().lower()
    if plan not in ("free", "pro", "admin"):
        raise HTTPException(status_code=400, detail="无效的套餐类型")

    target_user.plan = plan
    if req.plan_expire_at:
        target_user.plan_expire_at = req.plan_expire_at
    db.commit()
    db.refresh(target_user)

    _write_audit_log(
        admin_username=admin.username,
        action="update_plan",
        db=db,
        target_type="user",
        target_username=target_user.username,
        detail=f"套餐 {old_plan} → {plan}",
    )

    return {
        "success": True,
        "username": target_user.username,
        "plan": target_user.plan,
        "plan_expire_at": serialize_datetime(target_user.plan_expire_at),
    }


@app.get("/admin/usage-summary")
def admin_usage_summary(admin_username: str, db: Session = Depends(get_db)):
    require_admin(admin_username, db)

    today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)

    feature_stats = {}
    for feature in ALL_FEATURES:
        count = (
            db.query(models.AiUsageLog)
            .filter(
                models.AiUsageLog.feature == feature,
                models.AiUsageLog.status == "success",
                models.AiUsageLog.created_at >= today_start,
            )
            .count()
        )
        feature_stats[feature] = count

    total_usage = (
        db.query(models.AiUsageLog)
        .filter(
            models.AiUsageLog.status == "success",
            models.AiUsageLog.created_at >= today_start,
        )
        .count()
    )

    plan_counts = {}
    for plan_name in ["free", "pro", "admin"]:
        plan_counts[plan_name] = (
            db.query(models.User).filter(models.User.plan == plan_name).count()
        )

    recent_logs = (
        db.query(models.AiUsageLog)
        .order_by(models.AiUsageLog.created_at.desc())
        .limit(100)
        .all()
    )

    return {
        "today_total": total_usage,
        "feature_stats": feature_stats,
        "plan_counts": plan_counts,
        "recent_logs": [
            {
                "username": log.username,
                "feature": log.feature,
                "model": log.model,
                "estimated_tokens": log.estimated_tokens,
                "status": log.status,
                "error_message": log.error_message,
                "created_at": serialize_datetime(log.created_at),
            }
            for log in recent_logs
        ],
    }


@app.get("/admin/audit-logs")
def admin_audit_logs(
    admin_username: str,
    page: int = 1,
    page_size: int = 30,
    db: Session = Depends(get_db),
):
    require_admin(admin_username, db)

    page = max(1, page)
    page_size = min(100, max(1, page_size))

    total = db.query(models.AdminAuditLog).count()
    logs = (
        db.query(models.AdminAuditLog)
        .order_by(models.AdminAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [
            {
                "admin_username": log.admin_username,
                "action": log.action,
                "target_type": log.target_type,
                "target_username": log.target_username,
                "detail": log.detail,
                "created_at": serialize_datetime(log.created_at),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── Learning Reports ──────────────────────────────────────

REPORT_TYPE_LABELS = {
    "today": "今日学习总结",
    "weekly": "本周学习报告",
    "monthly": "本月学习报告",
    "course": "课程学习报告",
    "exam": "考前复盘报告",
    "growth": "成长档案概览",
}

REPORT_PROMPT = """你是一个专业的学习教练。请根据用户的学习数据摘要，生成一份客观、鼓励、可执行的学习报告。

要求：
1. 使用中文
2. 结构清晰，包含：学习概况、已完成内容、掌握较好的部分、主要薄弱点、错题复盘、资料使用、AI使用、下一步建议
3. 语气鼓励但客观，不要虚假表扬
4. 如果数据较少，明确说明"当前学习数据较少，建议多练习后再次生成报告"
5. 不要编造不存在的数据
6. 建议要具体可执行
7. content 总长度控制在 2000 字以内

请只输出一个 JSON 对象，不要加 ```json 代码块：
{"title": "报告标题", "summary": "一句话摘要", "content": "完整报告正文", "suggestions": ["建议1", "建议2"]}"""


def _resolve_date_range(report_type: str, start_date: str | None, end_date: str | None):
    now = utc_now()
    if start_date:
        start = datetime.fromisoformat(str(start_date).replace("Z", "+00:00"))
    elif report_type == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif report_type == "weekly":
        start = now - timedelta(days=7)
    elif report_type == "monthly":
        start = now - timedelta(days=30)
    elif report_type == "growth":
        start = now - timedelta(days=90)
    else:
        start = now - timedelta(days=30)

    if end_date:
        end = datetime.fromisoformat(str(end_date).replace("Z", "+00:00"))
    else:
        end = now

    return start, end


def build_learning_report_data(username: str, report_type: str, course_id: str,
                                start: datetime, end: datetime, db: Session):
    data = {
        "report_type": report_type,
        "report_type_label": REPORT_TYPE_LABELS.get(report_type, report_type),
        "username": username,
        "course_id": course_id or "全部课程",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }

    # ── Tasks ──
    task_query = db.query(models.LearningTask).filter(
        models.LearningTask.username == username,
        models.LearningTask.created_at >= start,
        models.LearningTask.created_at <= end,
    )
    if course_id:
        task_query = task_query.filter(models.LearningTask.course_id == course_id)
    tasks = task_query.all()
    completed_tasks = [t for t in tasks if t.status == "done"]
    task_type_dist = {}
    for t in tasks:
        tt = t.task_type or "other"
        task_type_dist[tt] = task_type_dist.get(tt, 0) + 1
    data["tasks"] = {
        "total": len(tasks),
        "completed": len(completed_tasks),
        "todo": sum(1 for t in tasks if t.status == "todo"),
        "in_progress": sum(1 for t in tasks if t.status == "in_progress"),
        "type_distribution": task_type_dist,
        "recent_titles": [t.title for t in tasks[-10:]],
    }

    # ── Knowledge Points ──
    kp_query = db.query(models.UserKnowledgeProgress).filter(
        models.UserKnowledgeProgress.username == username,
    )
    if course_id:
        kp_query = kp_query.filter(models.UserKnowledgeProgress.course_id == course_id)
    kp_progresses = kp_query.all()
    mastered = [p for p in kp_progresses if p.status == "mastered"]
    weak_points = sorted(
        [p for p in kp_progresses if p.mastery_score is not None and p.mastery_score < 50],
        key=lambda p: p.mastery_score or 0,
    )[:5]
    avg_mastery = round(sum(p.mastery_score or 0 for p in kp_progresses) / max(1, len(kp_progresses)), 1)

    # Progress events for improvements
    improvements = (
        db.query(models.KnowledgeProgressEvent)
        .filter(
            models.KnowledgeProgressEvent.username == username,
            models.KnowledgeProgressEvent.delta > 0,
            models.KnowledgeProgressEvent.created_at >= start,
            models.KnowledgeProgressEvent.created_at <= end,
        )
        .order_by(models.KnowledgeProgressEvent.delta.desc())
        .limit(5)
        .all()
    )

    data["knowledge"] = {
        "total_points": len(kp_progresses),
        "mastered": len(mastered),
        "reviewing": sum(1 for p in kp_progresses if p.status == "reviewing"),
        "learning": sum(1 for p in kp_progresses if p.status == "learning"),
        "not_started": sum(1 for p in kp_progresses if p.status == "not_started"),
        "average_mastery": avg_mastery,
        "weak_points": [{"title": _kp_title(wp, db), "score": wp.mastery_score} for wp in weak_points],
        "improvements": [{"reason": imp.reason or "", "delta": imp.delta} for imp in improvements],
    }

    # ── Questions & Attempts ──
    attempt_query = db.query(models.QuestionAttempt).filter(
        models.QuestionAttempt.username == username,
        models.QuestionAttempt.created_at >= start,
        models.QuestionAttempt.created_at <= end,
    )
    if course_id:
        attempt_query = attempt_query.filter(models.QuestionAttempt.course_id == course_id)
    attempts = attempt_query.all()
    correct_attempts = [a for a in attempts if a.self_result == "correct"]
    wrong_attempts = [a for a in attempts if a.self_result == "wrong"]
    data["practice"] = {
        "attempt_count": len(attempts),
        "correct_count": len(correct_attempts),
        "wrong_count": len(wrong_attempts),
        "correct_rate": round(len(correct_attempts) / max(1, len(attempts)), 2),
        "recent_wrong": [
            {"question_id": a.question_id, "user_answer": str(a.user_answer or "")[:100]}
            for a in wrong_attempts[-5:]
        ],
    }

    # ── Materials ──
    mat_query = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.username == username,
        models.StudyMaterial.is_deleted.is_(False),
        models.StudyMaterial.created_at >= start,
        models.StudyMaterial.created_at <= end,
    )
    if course_id:
        mat_query = mat_query.filter(models.StudyMaterial.subject == course_id)
    materials = mat_query.all()
    linked_count = 0
    if materials:
        mat_ids = [m.id for m in materials]
        linked_count = (
            db.query(models.MaterialKnowledgeLink)
            .filter(models.MaterialKnowledgeLink.material_id.in_(mat_ids))
            .distinct(models.MaterialKnowledgeLink.material_id)
            .count()
        )
    data["materials"] = {
        "uploaded": len(materials),
        "linked_to_kp": linked_count,
    }

    # ── Code Sessions ──
    code_query = db.query(models.CodeSession).filter(
        models.CodeSession.username == username,
        models.CodeSession.created_at >= start,
        models.CodeSession.created_at <= end,
    )
    if course_id:
        code_query = code_query.filter(models.CodeSession.course_id == course_id)
    code_sessions = code_query.all()
    data["code"] = {
        "session_count": len(code_sessions),
        "languages": list(set(s.language for s in code_sessions if s.language)),
    }

    # ── AI Usage ──
    ai_query = db.query(models.AiUsageLog).filter(
        models.AiUsageLog.username == username,
        models.AiUsageLog.status == "success",
        models.AiUsageLog.created_at >= start,
        models.AiUsageLog.created_at <= end,
    )
    ai_logs = ai_query.all()
    ai_by_feature = {}
    for log in ai_logs:
        f = log.feature or "other"
        ai_by_feature[f] = ai_by_feature.get(f, 0) + 1
    data["ai_usage"] = {
        "total_calls": len(ai_logs),
        "by_feature": ai_by_feature,
    }

    return data


def _kp_title(kp_progress, db):
    kp = db.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.id == kp_progress.knowledge_point_id
    ).first()
    return kp.title if kp else f"KP-{kp_progress.knowledge_point_id}"


@app.post("/learning/reports/generate-preview")
def generate_report_preview(req: schemas.LearningReportGenerateRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)

    check_usage_limit(user.username, "learning_report_generate", db)

    report_type = (req.report_type or "weekly").strip()
    if report_type not in REPORT_TYPE_LABELS:
        raise HTTPException(status_code=400, detail=f"无效的报告类型：{report_type}")

    course_id = normalize_subject(req.course_id, default="")
    start, end = _resolve_date_range(report_type, req.start_date, req.end_date)

    # Build data summary
    report_data = build_learning_report_data(
        user.username, report_type, course_id, start, end, db
    )

    # Build AI prompt
    user_prompt = f"""报告类型：{report_data['report_type_label']}
时间范围：{report_data['start_date']} 至 {report_data['end_date']}
课程：{report_data['course_id']}
{("学习目标：" + req.goal) if req.goal.strip() else ""}

【学习任务】
总数：{report_data['tasks']['total']}，完成：{report_data['tasks']['completed']}，待办：{report_data['tasks']['todo']}，进行中：{report_data['tasks']['in_progress']}
任务类型分布：{json.dumps(report_data['tasks']['type_distribution'], ensure_ascii=False)}
最近任务：{', '.join(report_data['tasks']['recent_titles'][-5:]) if report_data['tasks']['recent_titles'] else '无'}

【知识点掌握】
总知识点：{report_data['knowledge']['total_points']}，已掌握：{report_data['knowledge']['mastered']}，复习中：{report_data['knowledge']['reviewing']}，学习中：{report_data['knowledge']['learning']}，未开始：{report_data['knowledge']['not_started']}
平均掌握度：{report_data['knowledge']['average_mastery']}%
薄弱知识点：{json.dumps(report_data['knowledge']['weak_points'], ensure_ascii=False) if report_data['knowledge']['weak_points'] else '暂无'}
近期进步：{json.dumps(report_data['knowledge']['improvements'][:5], ensure_ascii=False) if report_data['knowledge']['improvements'] else '暂无'}

【练习与错题】
作答次数：{report_data['practice']['attempt_count']}，正确率：{round(report_data['practice']['correct_rate'] * 100)}%

【资料使用】
上传资料：{report_data['materials']['uploaded']} 份，已关联知识点：{report_data['materials']['linked_to_kp']} 份

【编程学习】
代码练习次数：{report_data['code']['session_count']}

【AI 使用】
总调用：{report_data['ai_usage']['total_calls']} 次
按功能分布：{json.dumps(report_data['ai_usage']['by_feature'], ensure_ascii=False)}

请根据以上数据生成学习报告。"""

    try:
        raw = call_deepseek([
            {"role": "system", "content": REPORT_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="AI 报告生成失败，请稍后重试") from exc

    record_ai_usage(user.username, "learning_report_generate", db,
                    estimated_tokens=estimate_tokens_from_text(user_prompt) + estimate_tokens_from_text(raw),
                    status="success")

    # Parse JSON
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end_idx = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end_idx = i
                break
        text = "\n".join(lines[1:end_idx]).strip()
    json_start = text.find("{")
    json_end = text.rfind("}")
    if json_start == -1 or json_end == -1:
        raise HTTPException(status_code=500, detail="AI 返回格式异常，未找到 JSON 对象")

    try:
        result = json.loads(text[json_start:json_end + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"AI 返回 JSON 解析失败：{str(exc)}")

    title = str(result.get("title") or "").strip() or f"{REPORT_TYPE_LABELS.get(report_type, report_type)}"
    summary = str(result.get("summary") or "").strip()
    content = str(result.get("content") or "").strip()
    suggestions = result.get("suggestions", [])
    if not isinstance(suggestions, list):
        suggestions = []

    if not content:
        raise HTTPException(status_code=500, detail="AI 未能生成报告内容，请稍后重试")

    if len(content) > 8000:
        content = content[:8000] + "..."

    metrics = {
        "task_completed_count": report_data["tasks"]["completed"],
        "question_attempt_count": report_data["practice"]["attempt_count"],
        "correct_rate": report_data["practice"]["correct_rate"],
        "material_count": report_data["materials"]["uploaded"],
        "knowledge_point_count": report_data["knowledge"]["total_points"],
        "mastered_point_count": report_data["knowledge"]["mastered"],
        "weak_point_count": len(report_data["knowledge"]["weak_points"]),
        "ai_chat_count": report_data["ai_usage"]["total_calls"],
    }

    return {
        "title": title,
        "summary": summary,
        "content": content,
        "metrics": metrics,
        "suggestions": suggestions,
        "start_date": serialize_datetime(start),
        "end_date": serialize_datetime(end),
    }


@app.post("/learning/reports/save")
def save_report(req: schemas.LearningReportSaveRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)

    title = (req.title or "未命名报告").strip()[:200]
    content = (req.content or "").strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="报告标题和内容不能为空")

    metrics_json = None
    if req.metrics:
        try:
            metrics_json = json.dumps(req.metrics, ensure_ascii=False)
        except (TypeError, ValueError):
            metrics_json = None
    suggestions_json = None
    if req.suggestions:
        try:
            suggestions_json = json.dumps(req.suggestions, ensure_ascii=False)
        except (TypeError, ValueError):
            suggestions_json = None

    report = models.LearningReport(
        username=user.username,
        course_id=normalize_subject(req.course_id, default="") or None,
        course_name=(req.course_name or "").strip()[:100] or None,
        report_type=(req.report_type or "weekly").strip(),
        title=title,
        summary=(req.summary or "").strip()[:500],
        content=content,
        metrics_json=metrics_json,
        suggestions_json=suggestions_json,
        start_date=parse_optional_datetime(req.start_date),
        end_date=parse_optional_datetime(req.end_date),
    )
    try:
        db.add(report)
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="保存报告失败，请稍后重试。")

    return {"success": True, "report_id": report.id}


@app.get("/learning/reports")
def list_reports(
    username: str,
    course_id: str = "",
    report_type: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)

    page = max(1, page)
    page_size = min(100, max(1, page_size))

    query = db.query(models.LearningReport).filter(models.LearningReport.username == user.username)
    if course_filter := normalize_subject(course_id, default=""):
        query = query.filter(models.LearningReport.course_id == course_filter)
    if type_filter := report_type.strip():
        query = query.filter(models.LearningReport.report_type == type_filter)

    total = query.count()
    reports = query.order_by(models.LearningReport.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "summary": r.summary,
                "report_type": r.report_type,
                "course_id": r.course_id,
                "course_name": r.course_name,
                "start_date": serialize_datetime(r.start_date),
                "end_date": serialize_datetime(r.end_date),
                "created_at": serialize_datetime(r.created_at),
            }
            for r in reports
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/learning/reports/{report_id}")
def get_report_detail(report_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    report = (
        db.query(models.LearningReport)
        .filter(models.LearningReport.id == report_id, models.LearningReport.username == user.username)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    metrics = None
    if report.metrics_json:
        try:
            metrics = json.loads(report.metrics_json)
        except (json.JSONDecodeError, TypeError):
            metrics = None
    suggestions = None
    if report.suggestions_json:
        try:
            suggestions = json.loads(report.suggestions_json)
        except (json.JSONDecodeError, TypeError):
            suggestions = None

    return {
        "id": report.id,
        "title": report.title,
        "summary": report.summary,
        "content": report.content,
        "report_type": report.report_type,
        "course_id": report.course_id,
        "course_name": report.course_name,
        "metrics": metrics,
        "suggestions": suggestions,
        "start_date": serialize_datetime(report.start_date),
        "end_date": serialize_datetime(report.end_date),
        "created_at": serialize_datetime(report.created_at),
    }


@app.delete("/learning/reports/{report_id}")
def delete_report(report_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    report = (
        db.query(models.LearningReport)
        .filter(models.LearningReport.id == report_id, models.LearningReport.username == user.username)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    # Deactivate any active shares for this report
    active_shares = (
        db.query(models.LearningReportShare)
        .filter(
            models.LearningReportShare.report_id == report_id,
            models.LearningReportShare.username == user.username,
            models.LearningReportShare.is_active == 1,
        )
        .all()
    )
    now = utc_now()
    for share in active_shares:
        share.is_active = 0
        share.revoked_at = now

    db.delete(report)
    db.commit()

    return {"success": True, "message": "报告已删除"}


# ── Report Export / Share ──────────────────────────────────


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9一-鿿._-]", "_", name)[:80]


def _format_report_as_markdown(report, metrics, suggestions) -> str:
    lines = []
    lines.append(f"# {report.title}")
    lines.append("")
    type_label = REPORT_TYPE_LABELS.get(report.report_type, report.report_type)
    lines.append(f"报告类型：{type_label}")
    if report.course_name:
        lines.append(f"课程：{report.course_name}")
    elif report.course_id:
        lines.append(f"课程：{report.course_id}")
    if report.start_date:
        lines.append(f"时间范围：{serialize_datetime(report.start_date)} 至 {serialize_datetime(report.end_date)}")
    lines.append(f"生成时间：{serialize_datetime(report.created_at)}")
    lines.append("")

    if report.summary:
        lines.append("## 摘要")
        lines.append("")
        lines.append(report.summary)
        lines.append("")

    if metrics:
        lines.append("## 核心指标")
        lines.append("")
        for k, v in metrics.items():
            label_k = k.replace("_", " ").title()
            if isinstance(v, float) and v < 1:
                lines.append(f"- {label_k}：{round(v * 100)}%")
            else:
                lines.append(f"- {label_k}：{v}")
        lines.append("")

    lines.append("## 报告正文")
    lines.append("")
    lines.append(report.content)
    lines.append("")

    if suggestions:
        lines.append("## 下一步建议")
        lines.append("")
        for i, s in enumerate(suggestions, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    lines.append("---")
    lines.append("由 AI Study Platform 生成")
    return "\n".join(lines)


def _parse_report_meta(report):
    metrics = None
    if report.metrics_json:
        try:
            metrics = json.loads(report.metrics_json)
        except (json.JSONDecodeError, TypeError):
            metrics = None
    suggestions = None
    if report.suggestions_json:
        try:
            suggestions = json.loads(report.suggestions_json)
        except (json.JSONDecodeError, TypeError):
            suggestions = None
    return metrics, suggestions


@app.get("/learning/reports/{report_id}/export/markdown")
def export_report_markdown(report_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    report = (
        db.query(models.LearningReport)
        .filter(models.LearningReport.id == report_id, models.LearningReport.username == user.username)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    try:
        metrics, suggestions = _parse_report_meta(report)
        content = _format_report_as_markdown(report, metrics, suggestions)
        filename = _sanitize_filename(f"学习报告-{report.title}") + ".md"
        return {"filename": filename, "content": content}
    except Exception:
        raise HTTPException(status_code=500, detail="导出 Markdown 失败，请稍后重试。")


@app.get("/learning/reports/{report_id}/export/text")
def export_report_text(report_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    report = (
        db.query(models.LearningReport)
        .filter(models.LearningReport.id == report_id, models.LearningReport.username == user.username)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    try:
        lines = []
        lines.append(report.title)
        lines.append("")
        if report.summary:
            lines.append(report.summary)
            lines.append("")
        lines.append(report.content)
        lines.append("")

        metrics, suggestions = _parse_report_meta(report)
        if suggestions:
            lines.append("建议：")
            for i, s in enumerate(suggestions, 1):
                lines.append(f"{i}. {s}")

        content = "\n".join(lines)
        filename = _sanitize_filename(f"学习报告-{report.title}") + ".txt"
        return {"filename": filename, "content": content}
    except Exception:
        raise HTTPException(status_code=500, detail="导出 TXT 失败，请稍后重试。")


@app.post("/learning/reports/{report_id}/share")
def create_report_share(report_id: int, req: schemas.LearningReportShareCreateRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    report = (
        db.query(models.LearningReport)
        .filter(models.LearningReport.id == report_id, models.LearningReport.username == user.username)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    try:
        existing = (
            db.query(models.LearningReportShare)
            .filter(
                models.LearningReportShare.report_id == report_id,
                models.LearningReportShare.username == user.username,
                models.LearningReportShare.is_active == 1,
            )
            .first()
        )
        if existing:
            return {
                "share_token": existing.share_token,
                "share_url": f"/shared/reports/{existing.share_token}",
                "created_at": serialize_datetime(existing.created_at),
                "view_count": existing.view_count or 0,
            }

        token = __import__("secrets").token_urlsafe(32)
        share = models.LearningReportShare(
            username=user.username,
            report_id=report.id,
            share_token=token,
            title=report.title,
            is_active=1,
            view_count=0,
        )
        db.add(share)
        db.commit()
        db.refresh(share)

        return {
            "share_token": share.share_token,
            "share_url": f"/shared/reports/{share.share_token}",
            "created_at": serialize_datetime(share.created_at),
            "view_count": 0,
        }
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="创建分享失败，请稍后重试。")


@app.delete("/learning/reports/{report_id}/share")
def revoke_report_share(report_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    share = (
        db.query(models.LearningReportShare)
        .filter(
            models.LearningReportShare.report_id == report_id,
            models.LearningReportShare.username == user.username,
            models.LearningReportShare.is_active == 1,
        )
        .first()
    )
    if not share:
        raise HTTPException(status_code=404, detail="该报告没有活跃的分享链接")

    try:
        share.is_active = 0
        share.revoked_at = utc_now()
        db.commit()
        return {"success": True, "message": "分享已撤销"}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="撤销分享失败，请稍后重试。")


@app.get("/learning/reports/{report_id}/share")
def get_report_share_status(report_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    share = (
        db.query(models.LearningReportShare)
        .filter(
            models.LearningReportShare.report_id == report_id,
            models.LearningReportShare.username == user.username,
        )
        .order_by(models.LearningReportShare.created_at.desc())
        .first()
    )
    if not share:
        return {"is_shared": False}

    return {
        "is_shared": bool(share.is_active),
        "share_token": share.share_token if share.is_active else None,
        "share_url": f"/shared/reports/{share.share_token}" if share.is_active else None,
        "view_count": share.view_count or 0,
        "created_at": serialize_datetime(share.created_at),
        "revoked_at": serialize_datetime(share.revoked_at) if share.revoked_at else None,
        "last_viewed_at": serialize_datetime(share.last_viewed_at) if share.last_viewed_at else None,
    }


@app.get("/shared/reports/{share_token}")
def public_shared_report(share_token: str, db: Session = Depends(get_db)):
    share = (
        db.query(models.LearningReportShare)
        .filter(
            models.LearningReportShare.share_token == share_token,
            models.LearningReportShare.is_active == 1,
        )
        .first()
    )
    if not share:
        raise HTTPException(status_code=404, detail="该报告分享链接不存在或已被撤销。")

    report = db.query(models.LearningReport).filter(models.LearningReport.id == share.report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="该报告分享链接不存在或已被撤销。")

    try:
        share.view_count = (share.view_count or 0) + 1
        share.last_viewed_at = utc_now()
        db.commit()
    except Exception:
        db.rollback()

    metrics, suggestions = _parse_report_meta(report)
    safe_metrics = {}
    if metrics:
        for k, v in metrics.items():
            if not isinstance(v, (int, float, str, bool)):
                continue
            safe_metrics[k] = v

    return {
        "title": report.title,
        "summary": report.summary,
        "content": report.content,
        "report_type": report.report_type,
        "course_name": report.course_name,
        "start_date": serialize_datetime(report.start_date),
        "end_date": serialize_datetime(report.end_date),
        "created_at": serialize_datetime(report.created_at),
        "suggestions": suggestions,
        "metrics": safe_metrics,
    }


@app.get("/admin/report-shares")
def admin_report_shares(
    admin_username: str,
    page: int = 1,
    page_size: int = 30,
    db: Session = Depends(get_db),
):
    require_admin(admin_username, db)

    page = max(1, page)
    page_size = min(100, max(1, page_size))

    total = db.query(models.LearningReportShare).count()
    shares = (
        db.query(models.LearningReportShare)
        .order_by(models.LearningReportShare.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [
            {
                "id": s.id,
                "report_id": s.report_id,
                "title": s.title,
                "username": s.username,
                "is_active": bool(s.is_active),
                "view_count": s.view_count or 0,
                "created_at": serialize_datetime(s.created_at),
                "revoked_at": serialize_datetime(s.revoked_at),
                "last_viewed_at": serialize_datetime(s.last_viewed_at),
            }
            for s in shares
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
