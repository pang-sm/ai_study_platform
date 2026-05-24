import json
import logging
import os
import re
import secrets
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

    system_prompt = build_system_prompt(
        subject,
        req.message,
        {
            "grade": req.grade or user.grade,
            "major": req.major or user.major,
        },
        has_attachment=bool(material_ids),
        rag_chunks=rag_chunks,
    )

    user_content = req.message
    if material_ids and selected_materials:
        file_names = "、".join(m.original_filename for m in selected_materials)
        user_content = f"【用户本轮上传文件：{file_names}】\n{req.message}"

    answer = call_deepseek(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
    )

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
