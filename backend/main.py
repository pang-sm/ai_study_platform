import json
import csv
import logging
import os
import re
import time
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import hashlib
import asyncio
import threading
import time
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import quote

import fitz
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from openai import OpenAI
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from pypdf import PdfReader
import pytesseract
from sqlalchemy import func, or_
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
from membership import (
    PLAN_DEFINITIONS,
    VALID_PLANS,
    get_effective_plan,
    get_plan_limits_v2,
    check_user_entitlement,
    normalize_major,
    recommend_plan_by_major,
    redeem_code,
    preload_redemption_codes,
    is_developer_account,
)
from prompts import build_system_prompt
from qwen_parser import (
    SCANNED_PDF_PAGE_PROMPT,
    get_qwen_pdf_ocr_model,
    get_qwen_parse_max_pages,
    get_qwen_status_payload,
    is_qwen_enabled,
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

# Preload redemption codes from env var on startup
with SessionLocal() as _db:
    try:
        preload_redemption_codes(_db)
    except Exception:
        pass  # Table may not exist on first run

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


# ── Global Exception Handlers ── ensure ALL responses are JSON ──
@app.exception_handler(HTTPException)
async def http_exception_json_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_json_handler(request: Request, exc: RequestValidationError):
    logger.warning("[validation-error] %s %s → %s", request.method, request.url.path, str(exc.errors())[:500])
    return JSONResponse(
        status_code=422,
        content={"detail": f"请求参数校验失败：{str(exc.errors())[:500]}"},
    )


@app.exception_handler(Exception)
async def global_exception_json_handler(request: Request, exc: Exception):
    logger.exception("[global-exception] %s %s → %s", request.method, request.url.path, str(exc)[:500])
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误，请稍后重试。详情：{str(exc)[:300]}"},
    )

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = BASE_DIR / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
MATERIAL_UPLOAD_ROOT = UPLOAD_ROOT / "materials"
MATERIAL_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
PRACTICE_IMPORT_ROOT = UPLOAD_ROOT / "practice_imports"
PRACTICE_IMPORT_ROOT.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
MAX_PDF_CHARS = 12000
MAX_OCR_CHARS = 12000
PRACTICE_PAPER_MAX_CHARS = 50000  # 试卷识别用更高上限，避免截断多页试卷
PRACTICE_IMPORT_JOB_TIMEOUT_SECONDS = 600
PRACTICE_IMPORT_QWEN_PAGE_TIMEOUT_SECONDS = 60
PRACTICE_IMPORT_DEEPSEEK_TIMEOUT_SECONDS = 180
PRACTICE_IMPORT_PDF_MIN_TEXT_CHARS = 1000
PRACTICE_IMPORT_PDF_MIN_AVG_PAGE_CHARS = 100
MAX_HISTORY_EXTRACT_CHARS = 4000
TOP_K_CHUNKS = 4
MIN_QWEN_CHINESE_CHARS = 30
MIN_QWEN_ALNUM_CHARS = 80
MIN_PDF_AVG_PAGE_CHARS = 30
MIN_PDF_MIN_TEXT_CHARS = 100
DEFAULT_LOCAL_PDF_SYNC_MAX_PAGES = 200
DEFAULT_PDF_OCR_RENDER_DPI = 150
DEFAULT_PDF_OCR_IMAGE_FORMAT = "jpeg"
DEFAULT_PDF_OCR_JPEG_QUALITY = 80
DEFAULT_PDF_OCR_MAX_IMAGE_SIDE = 1600
DEFAULT_PDF_OCR_CONCURRENCY = 2
DEFAULT_PDF_OCR_PAGE_TIMEOUT_SECONDS = 45
DEFAULT_SCANNED_PDF_OCR_MAX_PAGES = 20

# ── Per‑plan OCR page limits (only scanned pages count, not text pages) ──
DEFAULT_OCR_LIMIT = 20
FULL_EXAM_OCR_LIMIT = int(os.getenv("PDF_OCR_MAX_PAGES_FULL_PACKAGE", "500"))
ADMIN_OCR_LIMIT = int(os.getenv("PDF_OCR_MAX_PAGES_ADMIN", "1000"))

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
    school: str | None = None
    learning_direction: str | None = None
    default_course_id: str | None = None
    learning_stage: str | None = None
    daily_study_minutes: int | None = None
    ai_answer_style: str | None = None
    answer_detail_level: str | None = None
    material_reference_preference: str | None = None
    focus_courses: str | None = None


class OnboardingUpdateRequest(BaseModel):
    nickname: str | None = None
    grade: str | None = None
    major: str | None = None
    learning_direction: str | None = None
    learning_goal: str | None = None
    preferred_subjects: list[str] | None = None
    daily_study_time: str | None = None
    daily_study_minutes: int | None = None
    target: str | None = None
    learning_goal_type: str | None = None
    onboarding_detail: dict | None = None
    exam_package_type: str | None = None


class CourseLearningOnboardingRequest(BaseModel):
    major: str
    grade: str
    selected_courses: list[str]
    material_types: list[str] = []


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


# ── Learning Track Helpers ──

TRACK_PERMISSIONS = {
    "exam_408": {
        "access_exam_home": True,
        "access_exam_subjects": True,
        "access_exam_plan": True,
        "access_exam_review": True,
        "access_exam_report": True,
    },
    "university_course": {
        "access_course_home": True,
        "access_course_dashboard": True,
        "access_course_qa": True,
        "access_material_library": True,
        "access_practice_center": True,
        "access_learning_report": True,
    },
    "programming": {
        "access_code_studio": True,
        "access_code_execute": True,
        "access_ai_code_review": True,
        "access_code_practice": True,
        "access_code_diagnosis": True,
    },
}

EXAM_PACKAGE_TIERS = ["free", "monthly_sprint", "quarterly_boost", "full_exam"]
EXAM_PACKAGE_NAMES = {
    "free": "免费模式",
    "monthly_sprint": "月度冲刺包",
    "quarterly_boost": "季度强化包",
    "full_exam": "全程考包",
}
EXAM_PACKAGE_PLANS = {
    "free": "free",
    "monthly_sprint": "exam_monthly",
    "quarterly_boost": "exam_quarterly",
    "full_exam": "exam_yearly",
}
EXAM_PACKAGE_QUOTA = {
    "free": {
        "ai_chat_daily_limit": 50,
        "ai_question_daily_limit": 5,
        "material_upload_limit_mb": 100,
        "learning_plan": False,
        "mistake_review": False,
        "learning_report": False,
    },
    "monthly_sprint": {
        "ai_chat_daily_limit": 300,
        "ai_question_daily_limit": 30,
        "material_upload_limit_mb": 500,
        "learning_plan": True,
        "mistake_review": True,
        "learning_report": True,
    },
    "quarterly_boost": {
        "ai_chat_daily_limit": 500,
        "ai_question_daily_limit": 50,
        "material_upload_limit_mb": 1024,
        "learning_plan": True,
        "mistake_review": True,
        "learning_report": True,
    },
    "full_exam": {
        "ai_chat_daily_limit": 1000,
        "ai_question_daily_limit": 100,
        "material_upload_limit_mb": 2048,
        "learning_plan": True,
        "mistake_review": True,
        "learning_report": True,
    },
}

# Normalize legacy/Chinese package values to English enum.
PACKAGE_NORMALIZE_MAP = {
    "免费模式": "free", "free": "free",
    "月度冲刺": "monthly_sprint", "月度冲刺包": "monthly_sprint", "exam_monthly": "monthly_sprint", "monthly_sprint": "monthly_sprint",
    "季度强化包": "quarterly_boost", "quarterly": "quarterly_boost", "exam_quarterly": "quarterly_boost", "quarterly_boost": "quarterly_boost",
    "全程考包": "full_exam", "全程备考包": "full_exam", "exam_yearly": "full_exam", "full_exam": "full_exam",
}


def normalize_exam_package(raw):
    if not raw:
        return "free"
    val = str(raw).strip()
    return PACKAGE_NORMALIZE_MAP.get(val, "free")


def normalize_package_type(raw):
    return normalize_exam_package(raw)


def get_exam_package_permissions(package_type: str | None):
    package = normalize_exam_package(package_type)
    permissions = dict(TRACK_PERMISSIONS.get("exam_408", {}))
    permissions.update(EXAM_PACKAGE_QUOTA.get(package, EXAM_PACKAGE_QUOTA["free"]))
    # Legacy aliases for older frontend code. New code should use the canonical keys above.
    permissions["review"] = permissions["mistake_review"]
    permissions["report"] = permissions["learning_report"]
    permissions["ai_generate_question_daily_limit"] = permissions["ai_question_daily_limit"]
    return permissions


def get_exam_package_quota(package_type: str | None):
    package = normalize_exam_package(package_type)
    return {
        "package_type": package,
        "package_display_name": EXAM_PACKAGE_NAMES[package],
        "plan": EXAM_PACKAGE_PLANS[package],
        **EXAM_PACKAGE_QUOTA[package],
    }

def get_user_tracks(db: Session, user_id: int):
    return db.query(models.UserLearningTrack).filter(
        models.UserLearningTrack.user_id == user_id,
        models.UserLearningTrack.status == "active",
    ).all()

def get_user_track(db: Session, user_id: int, track_type: str):
    return db.query(models.UserLearningTrack).filter(
        models.UserLearningTrack.user_id == user_id,
        models.UserLearningTrack.track_type == track_type,
    ).first()

def user_has_track(db: Session, user_id: int, track_type: str) -> bool:
    return get_user_track(db, user_id, track_type) is not None

def require_track(db: Session, user_id: int, track_type: str):
    track = get_user_track(db, user_id, track_type)
    if not track:
        raise HTTPException(status_code=403, detail=f"请先开通该学习方向")
    return track

def upsert_user_track(db: Session, user_id: int, track_type: str, plan: str = "free",
                      package_type: str | None = None, onboarding_detail: dict | None = None):
    normalized_package = normalize_exam_package(package_type) if track_type == "exam_408" else package_type
    track = get_user_track(db, user_id, track_type)
    if not track:
        track = models.UserLearningTrack(
            user_id=user_id,
            track_type=track_type,
            plan=plan,
            package_type=normalized_package,
        )
        db.add(track)
    else:
        track.plan = plan
        track.package_type = normalize_package_type(normalized_package or track.package_type)
    perms = dict(TRACK_PERMISSIONS.get(track_type, {}))
    if track_type == "exam_408":
        package = normalize_exam_package(normalized_package or track.package_type)
        track.package_type = package
        track.plan = EXAM_PACKAGE_PLANS[package]
        perms = get_exam_package_permissions(package)
        track.quota_json = json.dumps(get_exam_package_quota(package), ensure_ascii=False)
    track.permissions_json = json.dumps(perms, ensure_ascii=False)
    if onboarding_detail:
        track.onboarding_detail_json = json.dumps(onboarding_detail, ensure_ascii=False)
    track.updated_at = utc_now()
    db.flush()
    return track

def serialize_track(track):
    perms = {}
    quota = {}
    try:
        if track.permissions_json:
            perms = json.loads(track.permissions_json)
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        if track.quota_json:
            quota = json.loads(track.quota_json)
    except (json.JSONDecodeError, TypeError):
        pass
    onboarding = None
    try:
        if track.onboarding_detail_json:
            onboarding = json.loads(track.onboarding_detail_json)
    except (json.JSONDecodeError, TypeError):
        pass
    package = normalize_package_type(track.package_type)
    if track.track_type == "exam_408":
        default_perms = get_exam_package_permissions(package)
        default_quota = get_exam_package_quota(package)
        default_perms.update(perms or {})
        perms = default_perms
        default_quota.update(quota or {})
        quota = default_quota
    return {
        "id": track.id,
        "track_type": track.track_type,
        "plan": quota.get("plan") or track.plan or "free",
        "package_type": package,
        "package_display_name": EXAM_PACKAGE_NAMES.get(package, package) if track.track_type == "exam_408" else "",
        "permissions": perms,
        "quota": quota,
        "onboarding_detail": onboarding,
        "is_active": bool(track.is_active),
        "status": track.status or "active",
        "created_at": serialize_datetime(track.created_at),
        "updated_at": serialize_datetime(track.updated_at),
    }


def _parse_track_onboarding_detail(track) -> dict:
    if not track or not track.onboarding_detail_json:
        return {}
    try:
        detail = json.loads(track.onboarding_detail_json)
        return detail if isinstance(detail, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


# ── 11408 School Whitelist ──

EXAM_408_SCHOOLS = [
    "北京大学",
    "南京大学",
    "浙江大学",
    "上海交通大学",
    "复旦大学",
    "中国科学技术大学",
    "武汉大学",
    "华中科技大学",
    "同济大学",
    "中国人民大学",
    "北京邮电大学",
    "北京工业大学",
    "北京交通大学",
    "南京理工大学",
    "华东理工大学",
    "上海大学",
    "郑州大学",
    "云南大学",
    "河北工业大学",
    "武汉理工大学",
]

@app.get("/exam-408/schools")
def search_exam_408_schools(q: str = ""):
    query = (q or "").strip()
    if not query:
        return {"schools": EXAM_408_SCHOOLS}
    lower_q = query.lower()
    results = [s for s in EXAM_408_SCHOOLS if lower_q in s.lower()]
    return {"schools": results}


@app.put("/exam-408/target-school")
def update_target_school(req: dict, db: Session = Depends(get_db)):
    username = str(req.get("username", "")).strip()
    school = str(req.get("school", "")).strip()
    user = get_user_by_username(username, db)
    if school and school not in EXAM_408_SCHOOLS:
        raise HTTPException(status_code=400, detail="请选择 11408 院校库中的学校")
    track = ensure_exam_408_track(db, user)
    if not track:
        raise HTTPException(status_code=404, detail="尚未开通 11408 备考方向")
    detail = {}
    try:
        if track.onboarding_detail_json:
            detail = json.loads(track.onboarding_detail_json)
    except (json.JSONDecodeError, TypeError):
        pass
    detail["target_school"] = school
    track.onboarding_detail_json = json.dumps(detail, ensure_ascii=False)
    db.commit()
    db.refresh(track)
    return {"target_school": school, "message": "目标院校已更新", "track": serialize_track(track)}


@app.put("/exam-408/motto")
def update_exam_motto(req: dict, db: Session = Depends(get_db)):
    username = str(req.get("username", "")).strip()
    motto = str(req.get("motto", "")).strip()
    user = get_user_by_username(username, db)
    track = ensure_exam_408_track(db, user)
    if not track:
        raise HTTPException(status_code=404, detail="尚未开通 11408 备考方向")
    detail = {}
    try:
        if track.onboarding_detail_json:
            detail = json.loads(track.onboarding_detail_json)
    except (json.JSONDecodeError, TypeError):
        pass
    detail["welcome_motto"] = motto
    track.onboarding_detail_json = json.dumps(detail, ensure_ascii=False)
    db.commit()
    db.refresh(track)
    return {"welcome_motto": motto, "message": "已更新"}


@app.put("/me/tracks/exam_408/package")
def upgrade_exam_package(req: dict, db: Session = Depends(get_db)):
    username = str(req.get("username", "")).strip()
    raw_pkg = str(req.get("package_type", "")).strip()
    new_pkg = normalize_package_type(raw_pkg)
    if new_pkg not in EXAM_PACKAGE_TIERS:
        raise HTTPException(status_code=400, detail="无效的套餐类型")
    user = get_user_by_username(username, db)
    track = ensure_exam_408_track(db, user)
    if not track:
        raise HTTPException(status_code=404, detail="尚未开通 11408 备考方向")
    # Normalize current package too (handles legacy Chinese values in DB)
    old_raw = track.package_type
    old_pkg = normalize_package_type(old_raw)
    # If legacy value differs from normalized, clean up the DB
    if old_raw != old_pkg:
        track.package_type = old_pkg
    old_idx = EXAM_PACKAGE_TIERS.index(old_pkg)
    new_idx = EXAM_PACKAGE_TIERS.index(new_pkg)
    if new_idx < old_idx:
        raise HTTPException(status_code=400, detail="当前已是该套餐或更高等级，无需降级")
    if new_idx == old_idx:
        raise HTTPException(status_code=400, detail="当前已是该套餐或更高等级，无需升级")
    track.package_type = new_pkg
    track.plan = EXAM_PACKAGE_PLANS[new_pkg]
    track.permissions_json = json.dumps(get_exam_package_permissions(new_pkg), ensure_ascii=False)
    track.quota_json = json.dumps(get_exam_package_quota(new_pkg), ensure_ascii=False)
    track.updated_at = utc_now()
    db.commit()
    db.refresh(track)
    return {
        "message": f"已升级至{EXAM_PACKAGE_NAMES.get(new_pkg, new_pkg)}",
        "track": serialize_track(track),
    }


def get_user_service_membership(db: Session, user_id: int, service_key: str):
    """Unified membership reader.

    Returns the UserServiceMembership record for (user_id, service_key),
    or None if no record exists.

    Usage:
        m = get_user_service_membership(db, user.id, "exam_11408")
        plan = m.plan if m and m.is_enabled else "free"

    IMPORTANT:
        - users.plan is a LEGACY compatibility field only — do NOT use it
          as the primary plan source for 11408/course/programming.
        - Always read plan from user_service_memberships for accurate
          service-direction membership.
        - course and programming should use get_user_service_membership
          with their respective service_key when they are implemented.
    """
    return db.query(models.UserServiceMembership).filter(
        models.UserServiceMembership.user_id == user_id,
        models.UserServiceMembership.service_key == service_key,
    ).first()


def get_effective_service_plan(db: Session, user_id: int, service_key: str) -> str:
    """Return the effective plan for a service direction.

    Returns the membership's plan if enabled, otherwise 'free'.
    Falls back to 'free' if no membership record exists.

    This is the SINGLE source of truth for service-direction plan lookups.
    """
    m = get_user_service_membership(db, user_id, service_key)
    if m and m.is_enabled:
        return m.plan or "free"
    return "free"


def _sync_membership_to_track(db: Session, user: models.User):
    """Sync exam_11408 membership plan to UserLearningTrack for 11408 backward compat."""
    membership = get_user_service_membership(db, user.id, "exam_11408")
    if not membership or not membership.is_enabled:
        return
    track = get_user_track(db, user.id, "exam_408")
    mplan = get_effective_service_plan(db, user.id, "exam_11408")
    # Map membership plan → existing package_type
    plan_to_pkg = {"free": "free", "monthly": "monthly_sprint", "quarterly": "quarterly_boost", "full": "full_exam"}
    pkg = plan_to_pkg.get(mplan, "free")
    pkg = normalize_package_type(pkg)
    if track:
        if track.package_type != pkg:
            track.package_type = pkg
            track.plan = EXAM_PACKAGE_PLANS[pkg]
            track.permissions_json = json.dumps(get_exam_package_permissions(pkg), ensure_ascii=False)
            track.quota_json = json.dumps(get_exam_package_quota(pkg), ensure_ascii=False)
            track.updated_at = utc_now()
            db.commit()
    # Sync users.plan for legacy compat using standard plan names
    user.plan = mplan  # free / monthly / quarterly / full
    db.commit()


def ensure_exam_408_track(db: Session, user: models.User):
    """Auto-create exam_408 track for old users who have 11408 data but no track record."""
    # Sync from membership first
    _sync_membership_to_track(db, user)
    existing = get_user_track(db, user.id, "exam_408")
    if existing:
        package = normalize_package_type(existing.package_type)
        repaired = False
        if existing.package_type != package:
            existing.package_type = package
            repaired = True
        expected_plan = EXAM_PACKAGE_PLANS[package]
        if existing.plan != expected_plan:
            existing.plan = expected_plan
            repaired = True
        expected_permissions = get_exam_package_permissions(package)
        expected_quota = get_exam_package_quota(package)
        try:
            current_permissions = json.loads(existing.permissions_json) if existing.permissions_json else {}
        except (json.JSONDecodeError, TypeError):
            current_permissions = {}
        try:
            current_quota = json.loads(existing.quota_json) if existing.quota_json else {}
        except (json.JSONDecodeError, TypeError):
            current_quota = {}
        if any(current_permissions.get(k) != v for k, v in expected_permissions.items()):
            existing.permissions_json = json.dumps(expected_permissions, ensure_ascii=False)
            repaired = True
        if any(current_quota.get(k) != v for k, v in expected_quota.items()):
            existing.quota_json = json.dumps(expected_quota, ensure_ascii=False)
            repaired = True
        if repaired:
            existing.updated_at = utc_now()
            db.commit()
            db.refresh(existing)
        return existing
    # Check if user is a 11408 user via legacy fields
    goal_type = _parse_onboarding_detail_type(user) or ""
    ld = (getattr(user, "learning_direction", "") or "").strip()
    is_408 = (
        goal_type == "exam_408"
        or "408" in ld
        or "11408" in ld
        or "考研" in ld
        or "408" in (getattr(user, "default_course_id", "") or "")
    )
    if not is_408:
        return None
    # Build detail from legacy fields
    old_detail = _parse_onboarding_detail(user) or {}
    # Determine package from legacy plan — normalize
    raw_pkg = old_detail.get("exam_package_type", "free") if old_detail else "free"
    pkg = normalize_package_type(raw_pkg)
    plan = EXAM_PACKAGE_PLANS[pkg]
    # Create track
    track = models.UserLearningTrack(
        user_id=user.id,
        track_type="exam_408",
        plan=plan,
        package_type=pkg,
    )
    track.permissions_json = json.dumps(get_exam_package_permissions(pkg), ensure_ascii=False)
    track.quota_json = json.dumps(get_exam_package_quota(pkg), ensure_ascii=False)
    track.onboarding_detail_json = json.dumps(old_detail, ensure_ascii=False) if old_detail else None
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def user_needs_onboarding(user: models.User) -> bool:
    if is_admin_user(user):
        return False
    return not bool(user.onboarding_completed)


def _parse_onboarding_detail(user):
    raw = getattr(user, "onboarding_detail", None)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _parse_onboarding_detail_type(user):
    detail = _parse_onboarding_detail(user)
    if detail and isinstance(detail, dict):
        return detail.get("learning_goal_type", None)
    return None


def user_profile(user: models.User):
    avatar_id = (user.avatar or "").strip()
    avatar_url = None
    if avatar_id:
        if avatar_id in ALLOWED_AVATARS:
            avatar_url = avatar_id
        else:
            avatar_url = f"/api/me/avatar/{avatar_id}"

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
        "needs_onboarding": user_needs_onboarding(user),
        "learning_goals": learning_goals,
        "learning_goal_type": _parse_onboarding_detail_type(user),
        "onboarding_detail": _parse_onboarding_detail(user),
        "is_admin": bool(user.is_admin),
        "plan": user.plan or "free",
        "plan_source": user.plan_source or "",
        "plan_expires_at": serialize_datetime(user.plan_expire_at) if user.plan_expire_at else None,
        "admin_role": (getattr(user, "admin_role", None) or "none").strip(),
        "school": getattr(user, "school", "") or "",
        "learning_direction": getattr(user, "learning_direction", "") or "",
        "default_course_id": getattr(user, "default_course_id", "") or "",
        "learning_stage": getattr(user, "learning_stage", "") or "",
        "daily_study_minutes": getattr(user, "daily_study_minutes", 0) or 0,
        "ai_answer_style": getattr(user, "ai_answer_style", "") or "",
        "answer_detail_level": getattr(user, "answer_detail_level", "") or "",
        "material_reference_preference": getattr(user, "material_reference_preference", "") or "",
        "focus_courses": getattr(user, "focus_courses", "") or "",
        "email": getattr(user, "email", None) or "",
        "email_verified": bool(getattr(user, "email_verified", False)),
        "phone": getattr(user, "phone", None) or "",
        "phone_verified": bool(getattr(user, "phone_verified", False)),
        "is_banned": bool(getattr(user, "is_banned", 0)),
        "banned_reason": getattr(user, "banned_reason", None) or "",
        "banned_at": getattr(user, "banned_at", None) or "",
        "is_deleted": bool(getattr(user, "is_deleted", 0)),
        "deleted_at": getattr(user, "deleted_at", None) or "",
        "created_at": serialize_datetime(user.created_at) if user.created_at else None,
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


def ensure_user_can_access(user: models.User):
    if bool(getattr(user, "is_deleted", 0)):
        raise HTTPException(status_code=403, detail="账号已被删除")
    if bool(getattr(user, "is_banned", 0)):
        raise HTTPException(status_code=403, detail="账号已被封禁，请联系管理员")
    if getattr(user, "is_active", 1) == 0:
        raise HTTPException(status_code=403, detail="账号已被停用，请联系管理员")


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


def validate_upload(file: UploadFile, file_bytes: bytes, max_size_mb: int | None = None):
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
    if max_size_mb:
        size_limit = max(size_limit, int(max_size_mb) * 1024 * 1024)

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
    """Returns True only when NO usable text could be extracted locally.

    This matches is_pdf_text_usable(): text PDFs (even sparse slides)
    are handled locally; only truly unextractable PDFs need Qwen OCR.
    """
    return not is_pdf_text_usable(extracted_text, total_pages)


def should_use_qwen_for_practice_pdf(extracted_text: str, total_pages: int) -> bool:
    cleaned = (extracted_text or "").strip()
    if not cleaned:
        return True
    checked_pages = max(1, total_pages or 1)
    avg_chars = len(cleaned) / checked_pages
    if len(cleaned) >= PRACTICE_IMPORT_PDF_MIN_TEXT_CHARS:
        return False
    if avg_chars >= PRACTICE_IMPORT_PDF_MIN_AVG_PAGE_CHARS:
        return False
    return True


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


def run_qwen_pdf_page_with_timeout(image_path: str, timeout_seconds: int | float) -> dict:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        parse_image_with_qwen,
        image_path,
        SCANNED_PDF_PAGE_PROMPT,
        None,
        timeout_seconds,
    )
    try:
        return future.result(timeout=timeout_seconds + 5)
    except FuturesTimeoutError:
        future.cancel()
        return {
            "success": False,
            "extracted_text": "",
            "error": f"Qwen 单页识别超过 {int(timeout_seconds)} 秒",
        }
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def parse_scanned_pdf_with_qwen(
    file_bytes: bytes,
    progress_callback=None,
    page_timeout_seconds: int | float = PRACTICE_IMPORT_QWEN_PAGE_TIMEOUT_SECONDS,
    max_pages_override: int | None = None,
) -> dict:
    max_pages = max_pages_override or get_qwen_parse_max_pages()
    image_paths = render_pdf_pages_to_images(file_bytes, max_pages)
    page_texts: list[str] = []
    errors: list[str] = []
    success_pages = 0
    failed_pages = 0

    try:
        for page_index, image_path in enumerate(image_paths, start=1):
            if progress_callback:
                progress_callback(page_index, len(image_paths))
            result = run_qwen_pdf_page_with_timeout(image_path, page_timeout_seconds)
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
        "qwen_pages": success_pages,
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


PRIVATE_VISIBILITY = "private"
SYSTEM_METADATA_VISIBILITY = "system_public_metadata"
SYSTEM_FULLTEXT_VISIBILITY = "system_public_fulltext"
USER_UPLOAD_SOURCE = "user_upload"
REFERENCE_METADATA_SOURCE = "reference_metadata"


def material_source_type(material: models.StudyMaterial) -> str:
    return (getattr(material, "source_type", None) or USER_UPLOAD_SOURCE).strip() or USER_UPLOAD_SOURCE


def material_visibility(material: models.StudyMaterial) -> str:
    return (getattr(material, "visibility", None) or PRIVATE_VISIBILITY).strip() or PRIVATE_VISIBILITY


def is_reference_metadata_material(material: models.StudyMaterial) -> bool:
    return material_source_type(material) == REFERENCE_METADATA_SOURCE or material_visibility(material) == SYSTEM_METADATA_VISIBILITY


def is_public_fulltext_material(material: models.StudyMaterial) -> bool:
    return material_visibility(material) == SYSTEM_FULLTEXT_VISIBILITY and bool(getattr(material, "allow_public_rag", False))


def is_user_private_material(material: models.StudyMaterial, username: str) -> bool:
    return material.username == username and material_visibility(material) == PRIVATE_VISIBILITY


def can_user_modify_material(material: models.StudyMaterial, username: str) -> bool:
    return is_user_private_material(material, username) and material_source_type(material) == USER_UPLOAD_SOURCE


def accessible_material_filter(username: str):
    return or_(
        (
            (models.StudyMaterial.username == username)
            & (models.StudyMaterial.visibility == PRIVATE_VISIBILITY)
        ),
        models.StudyMaterial.visibility == SYSTEM_METADATA_VISIBILITY,
        (
            (models.StudyMaterial.visibility == SYSTEM_FULLTEXT_VISIBILITY)
            & (models.StudyMaterial.allow_public_rag.is_(True))
        ),
    )


def query_accessible_materials(db: Session, username: str):
    return db.query(models.StudyMaterial).filter(
        models.StudyMaterial.is_deleted.is_(False),
        accessible_material_filter(username),
    )


def get_accessible_material_or_404(db: Session, username: str, material_id: int):
    material = query_accessible_materials(db, username).filter(models.StudyMaterial.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在或无权访问")
    return material


def build_reference_metadata_context(materials: list[models.StudyMaterial]) -> str:
    reference_materials = [material for material in materials if is_reference_metadata_material(material)]
    if not reference_materials:
        return ""

    lines = [
        "系统参考资料说明：以下资料仅为目录级参考索引，不包含第三方资料正文，不可下载，也不代表已读取原书全文。",
        "回答时只能基于这些目录/章节/知识点索引做学习路径和章节定位提示，不要声称依据原书正文。",
    ]
    for material in reference_materials:
        title = material.original_filename or "系统参考资料"
        summary = ((material.summary or material.extracted_text or "").strip())[:1000]
        lines.append(f"- {title}：{summary}")
    return "\n".join(lines)


def get_material_download_metadata(material: models.StudyMaterial):
    if not bool(getattr(material, "allow_download", True)) or is_reference_metadata_material(material):
        return {
            "can_download": False,
            "download_url": None,
        }
    file_path = get_material_file_path(material)
    return {
        "can_download": file_path is not None,
        "download_url": f"/materials/{material.id}/download" if file_path else None,
    }


PREVIEWABLE_FILE_TYPES = frozenset({"pdf", "image", "txt", "text", "markdown", "code"})


def get_material_preview_metadata(material: models.StudyMaterial):
    if is_reference_metadata_material(material):
        return {
            "can_preview": False,
            "preview_url": None,
        }
    file_path = get_material_file_path(material)
    file_type = (material.file_type or "").lower().strip()
    can_preview = file_path is not None and file_type in PREVIEWABLE_FILE_TYPES
    return {
        "can_preview": can_preview,
        "preview_url": f"/materials/{material.id}/preview" if can_preview else None,
    }


MODEL_CONFIG_DEFAULTS = {
    "ai_text_model_provider": "deepseek",
    "ai_text_model_name": "deepseek-chat",
    "ai_text_temperature": "0.3",
    "ai_text_max_tokens": "2000",
    "ai_vision_model_provider": "qwen",
    "ai_vision_enabled": "true",
    "ai_pdf_scan_parse_enabled": "true",
    "ai_pdf_scan_max_pages": "1000",
    "ai_chat_enabled_model_config": "true",
    "ai_report_enabled_model_config": "true",
    "ai_question_generation_enabled_model_config": "true",
}

MODEL_CONFIG_DESCRIPTIONS = {
    "ai_text_model_provider": "文本模型提供商",
    "ai_text_model_name": "文本模型名称",
    "ai_text_temperature": "文本模型 temperature",
    "ai_text_max_tokens": "文本模型 max_tokens",
    "ai_vision_model_provider": "视觉模型提供商",
    "ai_vision_enabled": "是否启用 Qwen 视觉解析",
    "ai_pdf_scan_parse_enabled": "是否启用扫描 PDF 视觉解析",
    "ai_pdf_scan_max_pages": "扫描 PDF 最大视觉解析页数",
    "ai_chat_enabled_model_config": "AI 问答使用模型配置",
    "ai_report_enabled_model_config": "学习报告使用模型配置",
    "ai_question_generation_enabled_model_config": "题目生成使用模型配置",
}

ALLOWED_MODEL_CONFIG_KEYS = set(MODEL_CONFIG_DEFAULTS.keys())
SENSITIVE_MODEL_CONFIG_KEY_PARTS = ("api_key", "apikey", "secret", "token", "password")


def _open_temp_db_if_needed(db: Session | None):
    if db is not None:
        return db, False
    return SessionLocal(), True


def get_system_setting(db: Session | None, key: str, default=None):
    local_db, should_close = _open_temp_db_if_needed(db)
    try:
        setting = local_db.query(models.SystemSetting).filter(models.SystemSetting.key == key).first()
        if setting and setting.value is not None and str(setting.value).strip() != "":
            return setting.value
        return default
    except Exception:
        return default
    finally:
        if should_close:
            local_db.close()


def get_float_setting(db: Session | None, key: str, default: float, min_value=None, max_value=None) -> float:
    raw_value = get_system_setting(db, key, str(default))
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and value < min_value:
        return default
    if max_value is not None and value > max_value:
        return default
    return value


def get_int_setting(db: Session | None, key: str, default: int, min_value=None, max_value=None) -> int:
    raw_value = get_system_setting(db, key, str(default))
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    if min_value is not None and value < min_value:
        return default
    if max_value is not None and value > max_value:
        return default
    return value


def get_bool_setting(db: Session | None, key: str, default: bool) -> bool:
    raw_value = str(get_system_setting(db, key, "true" if default else "false")).strip().lower()
    if raw_value in ("true", "1", "yes", "on"):
        return True
    if raw_value in ("false", "0", "no", "off"):
        return False
    return default


def get_model_runtime_config(db: Session | None = None) -> dict:
    provider = str(get_system_setting(db, "ai_text_model_provider", MODEL_CONFIG_DEFAULTS["ai_text_model_provider"])).strip().lower()
    if provider != "deepseek":
        provider = "deepseek"
    model = str(get_system_setting(db, "ai_text_model_name", MODEL_CONFIG_DEFAULTS["ai_text_model_name"])).strip() or MODEL_CONFIG_DEFAULTS["ai_text_model_name"]
    return {
        "provider": provider,
        "model": model,
        "temperature": get_float_setting(db, "ai_text_temperature", 0.3, 0, 1.5),
        "max_tokens": get_int_setting(db, "ai_text_max_tokens", 2000, 256, 8000),
    }


def get_vision_runtime_config(db: Session | None = None) -> dict:
    provider = str(get_system_setting(db, "ai_vision_model_provider", MODEL_CONFIG_DEFAULTS["ai_vision_model_provider"])).strip().lower()
    if provider != "qwen":
        provider = "qwen"
    return {
        "provider": provider,
        "vision_enabled": get_bool_setting(db, "ai_vision_enabled", True),
        "pdf_scan_parse_enabled": get_bool_setting(db, "ai_pdf_scan_parse_enabled", True),
        # Default to ADMIN_OCR_LIMIT so the system ceiling never
        # accidentally reduces a user's plan-based OCR limit below
        # what their package promises.
        "pdf_scan_max_pages": get_int_setting(db, "ai_pdf_scan_max_pages", ADMIN_OCR_LIMIT, 1, ADMIN_OCR_LIMIT),
    }


def call_deepseek(messages: list[dict], timeout_seconds: int | float | None = None,
                  model: str | None = None, temperature: float | None = None,
                  max_tokens: int | None = None):
    runtime_config = get_model_runtime_config(None)
    final_model = (model or runtime_config["model"] or "deepseek-chat").strip()
    final_temperature = runtime_config["temperature"] if temperature is None else temperature
    final_max_tokens = runtime_config["max_tokens"] if max_tokens is None else max_tokens
    try:
        response = client.chat.completions.create(
            model=final_model,
            messages=messages,
            temperature=final_temperature,
            max_tokens=final_max_tokens,
            timeout=timeout_seconds,
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
        "challenge_explain": 10,
        "challenge_test_gen": 10,
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
        "challenge_explain": 100,
        "challenge_test_gen": 100,
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
        "challenge_explain": 999999,
        "challenge_test_gen": 999999,
        "material_upload_count": 999999,
        "single_file_size_mb": 500,
    },
}

ALL_FEATURES = [
    "chat", "code_analyze", "challenge_generate", "learning_diagnosis",
    "knowledge_generate", "learning_plan_generate", "material_link_recommend",
    "question_generate", "question_feedback", "learning_report_generate",
    "challenge_explain", "challenge_test_gen",
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
        "plan_expires_at": serialize_datetime(user.plan_expire_at) if user.plan_expire_at else None,
    }


def get_plan_limits(plan: str, db: Session = None):
    """Get plan limits, prioritizing DB system_settings over hardcoded PLAN_LIMITS."""
    base = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]).copy()
    if db:
        try:
            total_limit_key = f"limit_{plan}_daily_ai_calls"
            val = db.query(models.SystemSetting).filter(models.SystemSetting.key == total_limit_key).first()
            if val and val.value:
                v = int(val.value)
                if v == -1:  # unlimited
                    for k in base:
                        base[k] = 999999
                elif v > 0:
                    # Distribute total daily limit proportionally across features
                    feature_count = len([k for k in base if k not in ("material_upload_count", "single_file_size_mb")])
                    per_feature = max(1, v // max(1, feature_count))
                    for k in base:
                        if k not in ("material_upload_count", "single_file_size_mb"):
                            base[k] = per_feature
        except Exception:
            pass
    return base


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
    limits = get_plan_limits(plan, db)
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


EXAM_408_SUBJECT_KEYWORDS = ("11408", "数据结构", "计算机组成原理", "操作系统", "计算机网络")

EXAM_408_SUBJECT_KEYS = {
    "data_structure",
    "computer_organization",
    "operating_system",
    "computer_network",
}


def normalize_exam_subject_key(*values: str | None) -> str:
    for value in values:
        key = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if key in EXAM_408_SUBJECT_KEYS:
            return key
    return ""


def is_exam_408_context(subject: str | None = "", course: str | None = "") -> bool:
    text = f"{subject or ''} {course or ''}".strip()
    if not text:
        return False
    return any(keyword in text for keyword in EXAM_408_SUBJECT_KEYWORDS)


def get_exam_408_permissions_for_user(db: Session, user: models.User):
    track = ensure_exam_408_track(db, user)
    if not track:
        return None
    return serialize_track(track).get("permissions") or {}


def get_exam_408_feature_limit(permissions: dict, feature: str):
    if feature == "chat":
        return int(permissions.get("ai_chat_daily_limit") or 0)
    if feature == "question_generate":
        return int(permissions.get("ai_question_daily_limit") or 0)
    if feature == "learning_plan_generate":
        return 999999 if permissions.get("learning_plan") else 0
    if feature == "learning_report_generate":
        return 999999 if permissions.get("learning_report") else 0
    return None


def check_exam_408_usage_limit(user: models.User, feature: str, db: Session):
    permissions = get_exam_408_permissions_for_user(db, user)
    if not permissions:
        return check_usage_limit(user.username, feature, db)
    limit = get_exam_408_feature_limit(permissions, feature)
    if limit is None:
        return check_usage_limit(user.username, feature, db)
    used = get_today_usage(user.username, feature, db)
    remaining = max(0, limit - used)
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"今日 11408 套餐 {feature} 使用次数已达上限（{used}/{limit}），当前套餐限制为 {limit} 次/天。",
        )
    return {
        "allowed": True,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "plan": "exam_408",
    }


def record_ai_usage(username: str, feature: str, db: Session, model: str = None,
                    estimated_tokens: int = 0, status: str = "success",
                    error_message: str = None):
    try:
        runtime_model = model or get_model_runtime_config(db).get("model") or "deepseek-chat"
        log = models.AiUsageLog(
            username=username,
            feature=feature,
            model=runtime_model,
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
如果资料里没有足够信息，请明确说明"资料内容中没有找到相关信息"。
""".strip()


def serialize_session(chat_session: models.ChatSession):
    session_subject = normalize_subject(chat_session.subject, chat_session.course)
    return {
        "id": chat_session.id,
        "title": chat_session.title,
        "course": chat_session.course or session_subject,
        "subject": session_subject,
        "exam_subject": chat_session.exam_subject or "",
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
        "parent_message_id": message.parent_message_id,
        "root_message_id": message.root_message_id,
        "branch_id": message.branch_id or "",
        "version_index": message.version_index or 0,
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
        "ocr_page_limit": getattr(material, "ocr_page_limit", 0) or 0,
        "is_partial_index": (material.parse_status == "partial"),
        "ocr_required": getattr(material, "ocr_required", 0) or 0,
        "chunk_count": material.chunk_count or 0,
        "parsed_at": serialize_datetime(material.parsed_at),
        "parse_started_at": serialize_datetime(material.parse_started_at),
        "parse_completed_at": serialize_datetime(material.parse_completed_at),
        "created_at": serialize_datetime(material.created_at),
        "updated_at": serialize_datetime(material.updated_at),
        "source_message_id": material.source_message_id,
        "source_type": material_source_type(material),
        "visibility": material_visibility(material),
        "copyright_status": getattr(material, "copyright_status", None) or "user_responsibility",
        "allow_download": bool(getattr(material, "allow_download", True)),
        "allow_public_rag": bool(getattr(material, "allow_public_rag", False)),
        "allow_private_rag": bool(getattr(material, "allow_private_rag", True)),
        "allow_generate_knowledge": bool(getattr(material, "allow_generate_knowledge", True)),
        "is_default_reference": bool(getattr(material, "is_default_reference", False)),
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
        "ocr_page_limit": getattr(material, "ocr_page_limit", 0) or 0,
        "is_partial_index": (material.parse_status == "partial"),
        "ocr_required": getattr(material, "ocr_required", 0) or 0,
        "chunk_count": material.chunk_count or 0,
        "parsed_at": serialize_datetime(material.parsed_at),
        "parse_started_at": serialize_datetime(material.parse_started_at),
        "parse_completed_at": serialize_datetime(material.parse_completed_at),
        "source_message_id": material.source_message_id,
        "source_type": material_source_type(material),
        "visibility": material_visibility(material),
        "copyright_status": getattr(material, "copyright_status", None) or "user_responsibility",
        "allow_download": bool(getattr(material, "allow_download", True)),
        "allow_public_rag": bool(getattr(material, "allow_public_rag", False)),
        "allow_private_rag": bool(getattr(material, "allow_private_rag", True)),
        "allow_generate_knowledge": bool(getattr(material, "allow_generate_knowledge", True)),
        "is_default_reference": bool(getattr(material, "is_default_reference", False)),
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
        "ocr_page_limit": getattr(material, "ocr_page_limit", 0) or 0,
        "is_partial_index": (material.parse_status == "partial"),
        "partial_index_reason": (material.parse_error or "") if material.parse_status == "partial" else "",
        "ocr_required": getattr(material, "ocr_required", 0) or 0,
        "source_type": material_source_type(material),
        "visibility": material_visibility(material),
        "allow_download": bool(getattr(material, "allow_download", True)),
        "allow_private_rag": bool(getattr(material, "allow_private_rag", True)),
        "allow_generate_knowledge": bool(getattr(material, "allow_generate_knowledge", True)),
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


def serialize_course_preference(record: models.CourseLearningPreference | None, course_id: str):
    if not record:
        return {
            "course_id": course_id,
            "subject": course_id,
            "mastery_level": "",
            "learning_goal": "",
            "is_started": False,
            "started_at": None,
            "created_at": None,
            "updated_at": None,
        }
    return {
        "id": record.id,
        "course_id": record.course_id,
        "subject": record.course_id,
        "mastery_level": record.mastery_level or "",
        "learning_goal": record.learning_goal or "",
        "is_started": bool(record.is_started),
        "started_at": serialize_datetime(record.started_at) if record.started_at else None,
        "created_at": serialize_datetime(record.created_at) if record.created_at else None,
        "updated_at": serialize_datetime(record.updated_at) if record.updated_at else None,
    }


def get_course_preference_record(db: Session, username: str, course_id: str):
    normalized_course = normalize_subject(course_id, default="")
    if not username or not normalized_course:
        return None
    return (
        db.query(models.CourseLearningPreference)
        .filter(
            models.CourseLearningPreference.username == username,
            models.CourseLearningPreference.course_id == normalized_course,
        )
        .first()
    )


def get_course_preference_payload(db: Session, username: str, course_id: str):
    normalized_course = normalize_subject(course_id, default="")
    return serialize_course_preference(
        get_course_preference_record(db, username, normalized_course),
        normalized_course,
    )


def build_course_preference_prompt(preference: dict | None, course_id: str = "") -> str:
    if not preference:
        return ""
    mastery_level = (preference.get("mastery_level") or "").strip()
    learning_goal = (preference.get("learning_goal") or "").strip()
    is_started = bool(preference.get("is_started"))
    if not (is_started and mastery_level and learning_goal):
        return ""

    course_label = (course_id or preference.get("course_id") or preference.get("subject") or "").strip()
    lines = [
        "当前课程学习背景：",
        f"- 课程：{course_label}",
        f"- 用户希望掌握程度：{mastery_level}",
        f"- 用户学习目标：{learning_goal}",
        "回答要求：",
        "- 按该掌握程度调整讲解深度。",
        "- 按该学习目标组织重点。",
    ]
    if learning_goal == "期末复习":
        lines.append("- 优先总结考点、易错点、常考题型，并给出复习优先级。")
    if learning_goal == "查漏补缺":
        lines.append("- 优先诊断薄弱点，覆盖容易混淆的概念，并说明错误原因。")
    if learning_goal == "项目实践":
        lines.append("- 优先结合应用场景、案例分析和动手实现。")
    if mastery_level == "课堂跟上":
        lines.append("- 难度偏基础，解释更通俗，必要时补充前置知识。")
    if mastery_level == "系统掌握":
        lines.append("- 回答要体现知识结构、相互联系和原理链路。")
    if mastery_level == "深入理解":
        lines.append("- 可以加入原理分析、边界条件和扩展问题。")
    return "\n".join(lines)


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
    course_preference = get_course_preference_payload(db, user.username, normalized_course)

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

    # Unlinked materials (no knowledge point linkage)
    unlinked_material_count = 0
    try:
        linked_ids = db.query(models.MaterialKnowledgeLink.material_id).filter(
            models.MaterialKnowledgeLink.username == user.username,
            models.MaterialKnowledgeLink.course_id == normalized_course,
        ).distinct().subquery()
        unlinked_material_count = material_query.filter(
            ~models.StudyMaterial.id.in_(linked_ids)
        ).count()
    except Exception:
        unlinked_material_count = 0

    # Pending materials: not yet successfully indexed
    # (null/empty = pending, parsing = in progress, pending = queued)
    pending_materials_count = material_query.filter(
        or_(
            models.StudyMaterial.parse_status.is_(None),
            models.StudyMaterial.parse_status == "",
            models.StudyMaterial.parse_status.in_(["parsing", "pending"]),
        )
    ).count()

    # Weekly study minutes
    # NOTE: LearningRecord / CodeSession / QuestionAttempt tables do not have
    # explicit duration columns, so this is a best-effort estimate:
    #   - each learning record ≈ 5 min
    #   - each code session ≈ 10 min
    #   - each question attempt ≈ 3 min
    weekly_study_minutes = 0
    try:
        week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_records = db.query(models.LearningRecord).filter(
            models.LearningRecord.user_id == user.id,
            models.LearningRecord.subject == normalized_course,
            models.LearningRecord.is_deleted.is_(False),
            models.LearningRecord.created_at >= week_start,
        ).count()
        week_code = db.query(models.CodeSession).filter(
            models.CodeSession.username == user.username,
            models.CodeSession.course_id == normalized_course,
            models.CodeSession.updated_at >= week_start,
        ).count()
        week_attempts = db.query(models.QuestionAttempt).filter(
            models.QuestionAttempt.username == user.username,
            models.QuestionAttempt.course_id == normalized_course,
            models.QuestionAttempt.created_at >= week_start,
        ).count()
        weekly_study_minutes = week_records * 5 + week_code * 10 + week_attempts * 3
    except Exception:
        weekly_study_minutes = 0

    # Streak days (consecutive days with activity)
    streak_days = 0
    try:
        all_dates = set()
        records_dates = db.query(models.LearningRecord.created_at).filter(
            models.LearningRecord.user_id == user.id,
            models.LearningRecord.subject == normalized_course,
            models.LearningRecord.is_deleted.is_(False),
        ).all()
        for (dt,) in records_dates:
            if dt: all_dates.add(dt.date())
        chat_dates = db.query(models.ChatSession.created_at).filter(
            models.ChatSession.user_id == user.id,
            or_(models.ChatSession.subject == normalized_course, models.ChatSession.course == normalized_course),
        ).all()
        for (dt,) in chat_dates:
            if dt: all_dates.add(dt.date())
        code_dates = db.query(models.CodeSession.updated_at).filter(
            models.CodeSession.username == user.username,
            models.CodeSession.course_id == normalized_course,
        ).all()
        for (dt,) in code_dates:
            if dt: all_dates.add(dt.date())
        today = date.today()
        check_date = today
        while check_date in all_dates:
            streak_days += 1
            check_date -= timedelta(days=1)
    except Exception:
        streak_days = 0

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
            "knowledge_points_count": kp_total,
            "unlinked_material_count": unlinked_material_count,
            "pending_materials_count": pending_materials_count,
            "weekly_study_minutes": weekly_study_minutes,
            "streak_days": streak_days,
            "last_study_date": serialize_datetime(recent_learning_at) if recent_learning_at else None,
        },
        "recent_learning_at": recent_learning_at,
        "recent_materials": [serialize_material_list_item(item) for item in recent_materials],
        "recent_chats": [serialize_session(item) for item in recent_chats],
        "progress": progress,
        "roadmap": get_course_roadmap(normalized_course),
        "suggestion": suggestion,
        "preference": course_preference,
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
        source_type=USER_UPLOAD_SOURCE,
        visibility=PRIVATE_VISIBILITY,
        copyright_status="user_responsibility",
        allow_download=True,
        allow_public_rag=False,
        allow_private_rag=True,
        allow_generate_knowledge=True,
        is_default_reference=False,
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
        "ocr_page_limit",
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
    """Determine whether extracted PDF text is usable for indexing.

    Returns True if ANY text was extracted — even low-density slide PDFs
    have valuable text content.  Only completely unextractable PDFs
    (truly scanned/image-only) need OCR fallback.
    """
    cleaned = (extracted_text or "").strip()
    if not cleaned:
        return False

    # If there is at least a minimal amount of text, treat it as a text-based
    # PDF and keep the locally extracted content.  Slide-style courseware
    # typically has 50–100 chars per page which is perfectly usable for RAG.
    if len(cleaned) >= MIN_PDF_MIN_TEXT_CHARS:
        return True

    # For extremely sparse PDFs (< 100 chars total) fall back to the
    # average-per-page check with a generous threshold.
    checked_pages = max(1, min(total_pages or 1, 15))
    return len(cleaned) / checked_pages >= MIN_PDF_AVG_PAGE_CHARS


def get_pdf_ocr_max_pages() -> int:
    raw_value = (os.getenv("PDF_OCR_MAX_PAGES") or str(DEFAULT_SCANNED_PDF_OCR_MAX_PAGES)).strip()
    try:
        value = int(raw_value)
        return max(1, min(value, DEFAULT_SCANNED_PDF_OCR_MAX_PAGES))
    except (TypeError, ValueError):
        return DEFAULT_SCANNED_PDF_OCR_MAX_PAGES


def get_pdf_ocr_page_limit_for_user(username: str, db: Session) -> int:
    """Return the scanned-page OCR limit for a specific user.

    Text-type PDF pages are NOT counted toward this limit; only pages
    that actually need vision-model OCR are constrained.

    * developer / admin accounts  → ADMIN_OCR_LIMIT
    * full_exam exam package      → FULL_EXAM_OCR_LIMIT
    * all other plans / packages  → DEFAULT_OCR_LIMIT (20)
    """
    from membership import is_admin_account, is_developer_account

    if is_developer_account(username) or is_admin_account(username):
        return ADMIN_OCR_LIMIT

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return DEFAULT_OCR_LIMIT

    # Full-exam-package users detected via user-track (exam_408 track)
    try:
        track = get_user_track(db, user.id, "exam_408")
        if track:
            norm_pkg = normalize_exam_package(track.package_type)
            if norm_pkg == "full_exam":
                return FULL_EXAM_OCR_LIMIT
    except Exception:
        pass

    # Fallback: check onboarding_detail for legacy exam_package_type
    if user.onboarding_detail:
        try:
            detail = json.loads(user.onboarding_detail) if isinstance(user.onboarding_detail, str) else user.onboarding_detail
            if isinstance(detail, dict) and normalize_exam_package(detail.get("exam_package_type", "")) == "full_exam":
                return FULL_EXAM_OCR_LIMIT
        except (json.JSONDecodeError, TypeError):
            pass

    return DEFAULT_OCR_LIMIT


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
    vision_config = get_vision_runtime_config(db)

    # Per-user OCR limit — determined solely by the user's plan / exam package.
    # The system setting 'ai_pdf_scan_max_pages' is an admin-controlled global
    # ceiling for server protection and must NOT reduce a user's plan-level OCR
    # limit below what their package promises.
    username = (material.username or "").strip()
    user_ocr_limit = get_pdf_ocr_page_limit_for_user(username, db) if username else DEFAULT_OCR_LIMIT
    if user_ocr_limit <= 0:
        user_ocr_limit = DEFAULT_OCR_LIMIT

    # Global ceiling: only applied when the admin has explicitly set a value
    # LOWER than the plan limit (e.g. to protect server resources).  By
    # default the ceiling is high enough to never interfere.
    system_ceiling = vision_config.get("pdf_scan_max_pages", 0)
    if system_ceiling > 0:
        max_pages = min(user_ocr_limit, system_ceiling)
    else:
        max_pages = user_ocr_limit

    # Fail fast if Qwen OCR is not available — save the local text if any exists
    if not vision_config["vision_enabled"] or not vision_config["pdf_scan_parse_enabled"] or not is_qwen_enabled():
        local_text = (local_pdf_text or "").strip()
        if local_text:
            update_material_parse_state(
                db, material.id,
                extracted_text=local_text,
                summary=local_text[:300] or "PDF 文本提取完成（OCR 未启用，仅使用直接提取的文本）。",
                parse_status="parsing", parse_progress=80,
                total_pages=0, parsed_pages=0,
                ocr_required=0, qwen_used=False,
                extract_method="local",
            )
            chunk_count = replace_material_chunks(db, material)
            update_material_parse_state(
                db, material.id,
                parse_status="success", parse_progress=100,
                chunk_count=chunk_count,
                parse_error=None,
                ocr_required=0, qwen_used=False,
                extract_method="local",
                parsed_at=utc_now(),
                parse_completed_at=serialize_datetime(utc_now()),
            )
            return
        update_material_parse_state(
            db, material.id,
            parse_status="failed",
            parse_error="PDF 无法直接提取文本且 Qwen OCR 未启用，请上传可选择文本的 PDF 或联系管理员配置 OCR。",
            parse_progress=0,
            ocr_required=1, qwen_used=False,
            extract_method="failed",
            parse_completed_at=serialize_datetime(utc_now()),
        )
        return

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
            ocr_page_limit=max_pages,
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

        # Build human-readable partial-index reason for frontend display
        partial_index_reason = ""
        if reached_page_limit:
            partial_index_reason = (
                f"该 PDF 包含扫描页。当前套餐最多 OCR {max_pages} 页，"
                f"系统已完成前 {ocr_page_count} 页扫描内容解析，"
                f"其余 {total_pages - ocr_page_count} 个扫描页暂未识别。"
                f"升级至全程考包可支持更大规模 OCR。"
            )
        elif failed_pages:
            partial_index_reason = (
                f"部分页面（第 {', '.join(str(p) for p in failed_pages[:5])} 页等）OCR 识别失败，"
                f"已完成 {ocr_page_count - len(failed_pages)}/{ocr_page_count} 页解析。"
            )

        update_material_parse_state(
            db,
            material.id,
            parse_status=parse_status,
            parse_progress=100,
            total_pages=total_pages,
            parsed_pages=ocr_page_count if reached_page_limit else total_pages,
            ocr_page_limit=max_pages,
            chunk_count=chunk_count,
            parse_error=parse_error or partial_index_reason or None,
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
        source_type=USER_UPLOAD_SOURCE,
        visibility=PRIVATE_VISIBILITY,
        copyright_status="user_responsibility",
        allow_download=True,
        allow_public_rag=False,
        allow_private_rag=True,
        allow_generate_knowledge=True,
        is_default_reference=False,
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

        vision_config = get_vision_runtime_config(db)
        if vision_config["vision_enabled"] and should_use_qwen_for_image(local_ocr_text):
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
        vision_config = get_vision_runtime_config(db)
        if should_fallback and vision_config["vision_enabled"] and vision_config["pdf_scan_parse_enabled"]:
            pdf_qwen_result = parse_scanned_pdf_with_qwen(file_bytes, max_pages_override=vision_config["pdf_scan_max_pages"])
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


@app.get("/home/summary")
def get_home_summary(username: str, db: Session = Depends(get_db)):
    """Minimal dashboard summary for the homepage. Aggregates real data only."""
    user = get_user_by_username(username, db)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # ── 学习进度 (average mastery across all knowledge points) ──
    kp_progresses = (
        db.query(models.UserKnowledgeProgress)
        .filter(models.UserKnowledgeProgress.username == user.username)
        .all()
    )
    average_mastery = None
    if kp_progresses:
        scores = [p.mastery_score or 0 for p in kp_progresses]
        average_mastery = round(sum(scores) / len(scores))

    # ── 任务进度 ──
    all_tasks_q = db.query(models.LearningTask).filter(models.LearningTask.username == user.username)
    total_tasks = all_tasks_q.count()
    completed_tasks = all_tasks_q.filter(models.LearningTask.status == "done").count()
    today_completed_tasks = (
        all_tasks_q.filter(
            models.LearningTask.status == "done",
            models.LearningTask.completed_at >= today_start,
        ).count()
    )
    todo_tasks = all_tasks_q.filter(models.LearningTask.status == "todo").count()

    # ── AI 提问次数 (user messages in chat) ──
    total_questions = (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.user_id == user.id,
            models.ChatMessage.role == "user",
        )
        .count()
    )
    today_questions = (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.user_id == user.id,
            models.ChatMessage.role == "user",
            models.ChatMessage.created_at >= today_start,
        )
        .count()
    )

    # ── 练习题目 ──
    total_practice_questions = (
        db.query(models.Question)
        .filter(models.Question.username == user.username)
        .count()
    )

    # ── 连续学习天数 (from KnowledgeProgressEvent, naive consecutive-day count) ──
    streak = None
    if kp_progresses:
        study_dates = set()
        for p in kp_progresses:
            if p.last_studied_at:
                study_dates.add(p.last_studied_at.date())
        if study_dates:
            sorted_dates = sorted(study_dates, reverse=True)
            streak = 1
            for i in range(1, len(sorted_dates)):
                if (sorted_dates[i - 1] - sorted_dates[i]).days == 1:
                    streak += 1
                else:
                    break
            if (date.today() - sorted_dates[0]).days > 1:
                streak = 0

    return {
        "average_mastery": average_mastery,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "today_completed_tasks": today_completed_tasks,
        "todo_tasks": todo_tasks,
        "total_questions": total_questions,
        "today_questions": today_questions,
        "total_practice_questions": total_practice_questions,
        "study_streak": streak,
    }


# ── Global Search ────────────────────────────────────────

SEARCH_MAX_RESULTS = 50


def _safe_like_pattern(keyword: str) -> str:
    """Escape % and _ for LIKE, and wrap with %wildcard%."""
    safe = keyword.replace("%", "\\%").replace("_", "\\_")
    return f"%{safe}%"


def _score_exact(text: str, keyword: str, max_score: int) -> int:
    """Score: exact match = max, normalized exact = max-2, contains keyword = max-10."""
    if not text or not keyword:
        return 0
    t = text.strip()
    k = keyword.strip()
    if t == k:
        return max_score
    if t.lower() == k.lower():
        return max_score - 2
    if k.lower() in t.lower():
        return max_score - 10
    return 0


def _score_contains(text: str, keyword: str, max_score: int) -> int:
    """Score: text contains keyword, with frequency bonus (capped)."""
    if not text or not keyword:
        return 0
    t = text.lower()
    k = keyword.lower()
    if k not in t:
        return 0
    count = t.count(k)
    bonus = min(count - 1, 5) * 2
    return min(max_score - 10 + bonus, max_score)


def _matched_fields(checks: list[tuple[str, bool]]) -> list[str]:
    """Return list of field names that matched."""
    return [name for name, matched in checks if matched]


def _match_reason(score: int, fields: list[str]) -> str:
    """Generate a human-readable match reason from score and matched fields."""
    if score >= 98:
        return "完全匹配"
    if score >= 85:
        return f"{'、'.join(fields[:2])}命中"
    if score >= 65:
        return f"{fields[0] if fields else '内容'}命中"
    return "关键词命中"


def _build_snippet(text: str, keyword: str, max_len: int = 120) -> str:
    """Smart snippet: show text around keyword, or leading text if no match."""
    if not text:
        return ""
    t = text.strip()
    if not t:
        return ""
    k = keyword.strip().lower()
    idx = t.lower().find(k)
    if idx == -1:
        return t[:max_len] + ("..." if len(t) > max_len else "")
    # Take ~50 chars before and ~(max_len-50) after the keyword
    before = max(0, idx - 50)
    after = min(len(t), idx + len(k) + max_len - 50)
    snippet = t[before:after]
    if before > 0:
        snippet = "..." + snippet
    if after < len(t):
        snippet = snippet + "..."
    return snippet


@app.get("/search/global")
def global_search(
    q: str,
    username: str,
    limit: int = 5,
    include_chunks: bool = True,
    db: Session = Depends(get_db),
):
    """Unified global search across courses, materials, knowledge points, tasks, questions, and chats."""
    t_start = time.perf_counter()
    keyword = (q or "").strip()
    if not keyword:
        return {"query": "", "total": 0, "groups": [], "search_time_ms": 0}

    user = get_user_by_username(username, db)
    limit = max(1, min(limit, SEARCH_MAX_RESULTS))
    pattern = _safe_like_pattern(keyword)
    results = []
    total = 0

    # ── 1. Courses ──
    # Aggregate unique course names from all available sources.
    # knowledge_points course_id: course names are shared, not user-private
    kp_courses = set()
    for r in db.query(models.KnowledgePoint.course_id).distinct().all():
        if r.course_id:
            kp_courses.add(normalize_subject(r.course_id))

    # study_materials.subject: user-visible courses from uploaded materials
    mat_courses = set()
    for r in db.query(models.StudyMaterial.subject).filter(
        models.StudyMaterial.username == user.username,
        models.StudyMaterial.is_deleted.is_(False),
    ).distinct().all():
        if r.subject:
            mat_courses.add(normalize_subject(r.subject))

    # learning_tasks.course_id
    task_courses = set()
    for r in db.query(models.LearningTask.course_id).filter(
        models.LearningTask.username == user.username
    ).distinct().all():
        if r.course_id:
            task_courses.add(normalize_subject(r.course_id))

    all_user_courses = sorted(kp_courses | mat_courses | task_courses)
    course_items = []
    seen_courses = set()
    for cid in all_user_courses:
        if not cid or cid in seen_courses:
            continue
        if keyword.lower() in cid.lower():
            seen_courses.add(cid)
            score = _score_exact(cid, keyword, 100)
            fields = _matched_fields([("课程名", True)])
            course_items.append({
                "type": "course", "id": cid, "title": cid, "subtitle": "课程",
                "snippet": f"进入 {cid} 课程工作台",
                "course_id": cid,
                "score": score, "matched_fields": fields,
                "match_reason": _match_reason(score, fields),
                "target": {"page": "dashboard", "courseId": cid},
            })
        if len(course_items) >= limit:
            break
    course_items.sort(key=lambda x: x["score"], reverse=True)
    total += len(course_items)
    results.append({"type": "course", "title": "课程", "items": course_items})

    # ── 2. Materials ──
    mat_query = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.username == user.username,
        models.StudyMaterial.is_deleted.is_(False),
    )
    mat_items = []
    mat_query = mat_query.filter(
        (models.StudyMaterial.original_filename.ilike(pattern))
        | (models.StudyMaterial.subject.ilike(pattern))
        | (models.StudyMaterial.summary.ilike(pattern))
    ).order_by(models.StudyMaterial.created_at.desc()).limit(limit)
    for m in mat_query.all():
        score = max(_score_contains(m.original_filename, keyword, 95), _score_contains(m.subject or "", keyword, 70))
        fields = _matched_fields([("文件名", keyword.lower() in (m.original_filename or "").lower()), ("课程", keyword.lower() in (m.subject or "").lower())])
        mat_items.append({
            "type": "material", "id": m.id, "title": m.original_filename,
            "subtitle": f"资料 · {m.subject or ''}",
            "snippet": _build_snippet(m.original_filename + " " + (m.summary or ""), keyword),
            "course_id": m.subject or "", "material_id": m.id,
            "score": score, "matched_fields": fields,
            "match_reason": _match_reason(score, fields),
            "target": {"page": "workspaceMaterials", "courseId": m.subject or "", "tab": "materials", "materialId": m.id},
        })
    mat_items.sort(key=lambda x: x["score"], reverse=True)
    total += len(mat_items)
    results.append({"type": "material", "title": "资料", "items": mat_items})

    # ── 3. Material Chunks (content fragments) ──
    chunk_items = []
    if include_chunks:
        chunk_query = db.query(models.MaterialChunk).filter(
            models.MaterialChunk.username == user.username,
            models.MaterialChunk.is_deleted.is_(False),
            models.MaterialChunk.chunk_text.ilike(pattern),
        ).order_by(models.MaterialChunk.material_id, models.MaterialChunk.chunk_index).limit(limit)
        for c in chunk_query.all():
            score = _score_contains(c.chunk_text or "", keyword, 75)
            fields = _matched_fields([("资料内容", True)])
            chunk_items.append({
                "type": "chunk", "id": c.id,
                "title": c.source_filename or f"资料 #{c.material_id}",
                "subtitle": f"内容片段 · 第{c.chunk_index}段",
                "snippet": _build_snippet(c.chunk_text or "", keyword, 150),
                "course_id": c.subject or "", "material_id": c.material_id,
                "score": score, "matched_fields": fields,
                "match_reason": _match_reason(score, fields),
                "target": {"page": "workspaceMaterials", "courseId": c.subject or "", "tab": "materials", "materialId": c.material_id},
            })
        chunk_items.sort(key=lambda x: x["score"], reverse=True)
    total += len(chunk_items)
    results.append({"type": "chunk", "title": "资料内容", "items": chunk_items})

    # ── 4. Knowledge Points ──
    kp_items = []
    kp_query = db.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == user.username,
        models.KnowledgePoint.title.ilike(pattern),
    ).order_by(models.KnowledgePoint.course_id, models.KnowledgePoint.order_index).limit(limit)
    for k in kp_query.all():
        score = max(_score_exact(k.title, keyword, 95), _score_contains(k.description or "", keyword, 65))
        fields = _matched_fields([("标题", keyword.lower() in (k.title or "").lower()), ("描述", keyword.lower() in (k.description or "").lower())])
        kp_items.append({
            "type": "knowledge_point", "id": k.id, "title": k.title,
            "subtitle": f"知识点 · {k.course_id or ''}",
            "snippet": _build_snippet(k.description or k.title, keyword),
            "course_id": k.course_id or "", "knowledge_point_id": k.id,
            "score": score, "matched_fields": fields,
            "match_reason": _match_reason(score, fields),
            "target": {"page": "knowledgeLearning", "courseId": k.course_id or "", "knowledgePointId": k.id},
        })
    kp_items.sort(key=lambda x: x["score"], reverse=True)
    total += len(kp_items)
    results.append({"type": "knowledge_point", "title": "知识点", "items": kp_items})

    # ── 5. Tasks ──
    task_items = []
    task_query = db.query(models.LearningTask).filter(
        models.LearningTask.username == user.username,
        (models.LearningTask.title.ilike(pattern))
        | (models.LearningTask.description.ilike(pattern))
        | (models.LearningTask.knowledge_point_text.ilike(pattern)),
    ).order_by(models.LearningTask.created_at.desc()).limit(limit)
    for t in task_query.all():
        score = max(_score_exact(t.title, keyword, 90), _score_contains(t.description or "", keyword, 65))
        fields = _matched_fields([("标题", keyword.lower() in (t.title or "").lower()), ("描述", keyword.lower() in (t.description or "").lower())])
        task_items.append({
            "type": "task", "id": t.id, "title": t.title,
            "subtitle": f"任务 · {t.course_id or ''} · {t.status or 'todo'}",
            "snippet": _build_snippet((t.description or t.title), keyword),
            "course_id": t.course_id or "", "task_id": t.id,
            "score": score, "matched_fields": fields,
            "match_reason": _match_reason(score, fields),
            "target": {"page": "taskCenter", "courseId": t.course_id or "", "taskId": t.id},
        })
    task_items.sort(key=lambda x: x["score"], reverse=True)
    total += len(task_items)
    results.append({"type": "task", "title": "学习任务", "items": task_items})

    # ── 6. Practice Questions ──
    q_items = []
    q_query = db.query(models.Question).filter(
        models.Question.username == user.username,
        (models.Question.title.ilike(pattern))
        | (models.Question.content.ilike(pattern)),
    ).order_by(models.Question.created_at.desc()).limit(limit)
    for q in q_query.all():
        is_programming = q.type == "programming"
        target_page = "codeStudio" if is_programming else "practiceCenter"
        score = max(_score_contains(q.title, keyword, 80), _score_contains(q.content or "", keyword, 75))
        fields = _matched_fields([("标题", keyword.lower() in (q.title or "").lower()), ("题干", keyword.lower() in (q.content or "").lower())])
        q_items.append({
            "type": "question", "id": q.id, "title": q.title,
            "subtitle": f"{'编程题' if is_programming else '练习题'} · {q.type or ''} · {q.course_id or ''}",
            "snippet": _build_snippet(q.content or q.title, keyword),
            "course_id": q.course_id or "", "question_id": q.id, "knowledge_point_id": q.knowledge_point_id,
            "score": score, "matched_fields": fields,
            "match_reason": _match_reason(score, fields),
            "target": {"page": target_page, "courseId": q.course_id or "", "questionId": q.id, "knowledgePointId": q.knowledge_point_id},
        })
    q_items.sort(key=lambda x: x["score"], reverse=True)
    total += len(q_items)
    results.append({"type": "question", "title": "练习题", "items": q_items})

    # ── 7. Chat History ──
    chat_items = []
    user_obj = db.query(models.User).filter(models.User.username == user.username).first()
    if user_obj:
        chat_query = db.query(models.ChatMessage).filter(
            models.ChatMessage.user_id == user_obj.id,
            models.ChatMessage.role.in_(["user", "assistant"]),
            (models.ChatMessage.content.ilike(pattern)),
        ).order_by(models.ChatMessage.created_at.desc()).limit(limit)
        for msg in chat_query.all():
            session = db.query(models.ChatSession).filter(models.ChatSession.id == msg.session_id).first()
            course_from_session = session.subject or session.course or ""
            session_title = (session.title if session else "对话") or "对话"
            score = _score_contains(msg.content or "", keyword, 75 if msg.role == "user" else 60)
            fields = _matched_fields([("对话内容", True)])
            chat_items.append({
                "type": "chat", "id": msg.id,
                "title": session_title,
                "subtitle": f"{'你' if msg.role == 'user' else 'AI'} · {course_from_session}",
                "snippet": _build_snippet(msg.content or "", keyword),
                "course_id": course_from_session, "conversation_id": msg.session_id,
                "score": score, "matched_fields": fields,
                "match_reason": _match_reason(score, fields),
                "target": {"page": "chat", "courseId": course_from_session, "conversationId": msg.session_id},
            })
        chat_items.sort(key=lambda x: x["score"], reverse=True)
    total += len(chat_items)
    results.append({"type": "chat", "title": "历史对话", "items": chat_items})

    # Remove empty groups with zero items
    results = [g for g in results if len(g["items"]) > 0]
    # Update total to sum of visible groups
    actual_total = sum(len(g["items"]) for g in results)
    search_time_ms = round((time.perf_counter() - t_start) * 1000, 2)
    return {"query": keyword, "total": actual_total, "search_time_ms": search_time_ms, "groups": results}


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

    ensure_user_can_access(db_user)
    return {"message": "登录成功", "user": user_profile(db_user), "profile": user_profile(db_user)}


# ═══════════════════════════════════════════════════════════
# Admin Auth
# ═══════════════════════════════════════════════════════════

def is_admin_user(user) -> bool:
    """Check if a user has admin privileges.
    Compatible with: role='admin', is_admin=True, plan='admin', or admin_role in ('super_admin','operator','auditor').
    """
    if not user:
        return False
    if getattr(user, "role", None) == "admin":
        return True
    if bool(getattr(user, "is_admin", 0)):
        return True
    if getattr(user, "plan", None) == "admin":
        return True
    admin_role = (getattr(user, "admin_role", None) or "none").strip()
    if admin_role in ("super_admin", "operator", "auditor"):
        return True
    return False


def require_admin_user(current_user):
    """FastAPI dependency: reject non-admin users with 403."""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return current_user


# /admin/login has been deprecated — all users now authenticate via /login.
# The endpoint is kept as a 410 Gone stub for API compatibility.
@app.post("/admin/login")
def admin_login_deprecated():
    raise HTTPException(status_code=410, detail="管理员专用登录已取消，请使用统一登录入口 /login。")


@app.post("/me")
def me(req: MeRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    ensure_user_can_access(user)
    # Auto-migrate old 408 users
    ensure_exam_408_track(db, user)
    profile = user_profile(user)
    tracks = [serialize_track(t) for t in get_user_tracks(db, user.id)]
    active_track = next((t["track_type"] for t in tracks if t["is_active"]), tracks[0]["track_type"] if tracks else None)
    profile["tracks"] = tracks
    profile["active_track_type"] = active_track
    return {"user": profile}


@app.get("/me/tracks")
def get_my_tracks(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    # Auto-migrate old 408 users
    ensure_exam_408_track(db, user)
    tracks = [serialize_track(t) for t in get_user_tracks(db, user.id)]
    active = next((t["track_type"] for t in tracks if t["is_active"]), tracks[0]["track_type"] if tracks else None)
    return {"tracks": tracks, "active_track_type": active}

@app.get("/me/profile")
def get_profile(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    return {"profile": user_profile(user)}


@app.put("/me/profile")
def update_profile(req: ProfileUpdateRequest, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)

    ALLOWED_GRADES = {"大一", "大二", "大三", "大四", "研究生", ""}
    nickname = (req.nickname or "").strip()[:30]
    grade = (req.grade or "").strip()[:20]
    major = (req.major or "").strip()[:50]
    avatar = (req.avatar or "").strip()

    if grade and grade not in ALLOWED_GRADES:
        raise HTTPException(status_code=400, detail="年级仅支持：大一、大二、大三、大四、研究生")

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

    # Learning settings fields
    if req.school is not None:
        user.school = (req.school or "").strip()[:100]
    if req.learning_direction is not None:
        user.learning_direction = (req.learning_direction or "").strip()[:100]
    if req.default_course_id is not None:
        user.default_course_id = (req.default_course_id or "").strip()[:100]
    if req.learning_stage is not None:
        user.learning_stage = (req.learning_stage or "").strip()[:50]
    if req.daily_study_minutes is not None:
        user.daily_study_minutes = max(0, min(480, req.daily_study_minutes))
    if req.ai_answer_style is not None:
        user.ai_answer_style = (req.ai_answer_style or "").strip()[:50]
    if req.answer_detail_level is not None:
        user.answer_detail_level = (req.answer_detail_level or "").strip()[:50]
    if req.material_reference_preference is not None:
        user.material_reference_preference = (req.material_reference_preference or "").strip()[:50]
    if req.focus_courses is not None:
        user.focus_courses = (req.focus_courses or "").strip()[:200]

    db.commit()
    db.refresh(user)

    return {"profile": user_profile(user)}


@app.post("/me/onboarding")
def complete_onboarding(req: OnboardingUpdateRequest, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)

    if req.nickname is not None:
        user.nickname = (req.nickname or "").strip()[:30]
    if req.grade is not None:
        user.grade = (req.grade or "").strip()[:20]
    if req.major is not None:
        user.major = (req.major or "").strip()[:50]
    if req.learning_direction is not None:
        user.learning_direction = (req.learning_direction or "").strip()[:100]
    if req.daily_study_minutes is not None:
        user.daily_study_minutes = max(0, min(480, req.daily_study_minutes))
    if req.daily_study_time is not None and req.daily_study_minutes is None:
        text_value = (req.daily_study_time or "").strip()
        minute_match = re.search(r"\d+", text_value)
        if minute_match:
            user.daily_study_minutes = max(0, min(480, int(minute_match.group(0))))

    goal_type = (req.learning_goal_type or "").strip()
    goal_text = (req.learning_goal or req.target or "").strip()
    subjects = [item.strip() for item in (req.preferred_subjects or []) if item and item.strip()]
    if goal_text or subjects:
        user.learning_goals = json.dumps(
            [
                {
                    "subject": subject or user.default_course_id or "general",
                    "target_level": goal_text or "course_follow",
                    "note": goal_text,
                }
                for subject in (subjects or [user.default_course_id or "general"])
            ],
            ensure_ascii=False,
        )

    # Save onboarding detail as JSON
    if goal_type:
        detail = dict(req.onboarding_detail or {})
        detail["learning_goal_type"] = goal_type

        # Save exam package type if provided
        exam_pkg = (req.exam_package_type or "").strip()
        if exam_pkg and goal_type == "exam_408":
            detail["exam_package_type"] = exam_pkg
            package_plan_map = {
                "free": "free",
                "monthly_sprint": "pro",
                "quarterly_boost": "pro",
                "full_exam": "pro",
            }
            mapped_plan = package_plan_map.get(exam_pkg, "free")
            user.plan = mapped_plan

        user.onboarding_detail = json.dumps(detail, ensure_ascii=False)
        if goal_type == "exam_408":
            user.learning_direction = user.learning_direction or "考研 408 备考"
        elif goal_type == "university_course":
            user.learning_direction = user.learning_direction or "大学课程学习"
        elif goal_type == "programming":
            user.learning_direction = user.learning_direction or "编程能力提升"

    user.onboarding_completed = True

    # Create or update learning track based on goal_type
    if goal_type:
        track_plan = "free"
        track_package = None
        if goal_type == "exam_408":
            track_package = exam_pkg if exam_pkg else "free"
            track_plan = "free" if track_package == "free" else "pro"
        elif goal_type == "university_course":
            track_plan = "free"
        elif goal_type == "programming":
            track_plan = "free"
        upsert_user_track(
            db, user.id, goal_type,
            plan=track_plan, package_type=track_package,
            onboarding_detail=detail,
        )
        # Deactivate other tracks
        for t in get_user_tracks(db, user.id):
            if t.track_type != goal_type:
                t.is_active = False

    db.commit()
    db.refresh(user)

    profile = user_profile(user)
    tracks = [serialize_track(t) for t in get_user_tracks(db, user.id)]
    profile["tracks"] = tracks
    profile["active_track_type"] = goal_type if goal_type else None
    return {"message": "onboarding saved", "user": profile, "profile": profile}


def _course_learning_onboarding_payload(user: models.User, track: models.UserLearningTrack | None):
    detail = _parse_track_onboarding_detail(track)
    completed = bool(detail.get("course_learning_onboarding_completed"))
    return {
        "service_key": "course_learning",
        "onboarding_completed": completed,
        "major": detail.get("major") or user.major or "",
        "grade": detail.get("grade") or user.grade or "",
        "selected_courses": detail.get("selected_courses") if isinstance(detail.get("selected_courses"), list) else [],
        "material_types": detail.get("material_types") if isinstance(detail.get("material_types"), list) else [],
        "created_at": detail.get("course_learning_created_at") or (serialize_datetime(track.created_at) if track else None),
        "updated_at": detail.get("course_learning_updated_at") or (serialize_datetime(track.updated_at) if track else None),
    }


@app.get("/course-learning/onboarding")
def get_course_learning_onboarding(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    ensure_user_can_access(user)
    track = get_user_track(db, user.id, "university_course")
    return _course_learning_onboarding_payload(user, track)


@app.post("/course-learning/onboarding")
def save_course_learning_onboarding(
    req: CourseLearningOnboardingRequest,
    username: str,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    ensure_user_can_access(user)

    major = (req.major or "").strip()[:80]
    grade = (req.grade or "").strip()[:30]
    selected_courses = []
    for item in req.selected_courses or []:
        value = (item or "").strip()
        if value and value not in selected_courses:
            selected_courses.append(value[:60])
    material_types = []
    for item in req.material_types or []:
        value = (item or "").strip()
        if value and value not in material_types:
            material_types.append(value[:30])

    if not major:
        raise HTTPException(status_code=400, detail="请选择专业")
    if not grade:
        raise HTTPException(status_code=400, detail="请选择年级")
    if not selected_courses:
        raise HTTPException(status_code=400, detail="请选择至少一门想学习的课程")

    user.major = major
    user.grade = grade
    if selected_courses:
        user.focus_courses = "、".join(selected_courses)[:200]
        user.default_course_id = selected_courses[0][:100]
    user.learning_direction = user.learning_direction or "大学课程学习"

    track = get_user_track(db, user.id, "university_course")
    detail = _parse_track_onboarding_detail(track)
    now_text = serialize_datetime(utc_now())
    detail.update({
        "service_key": "course_learning",
        "major": major,
        "grade": grade,
        "selected_courses": selected_courses,
        "material_types": material_types,
        "course_learning_onboarding_completed": True,
        "course_learning_updated_at": now_text,
    })
    if not detail.get("course_learning_created_at"):
        detail["course_learning_created_at"] = now_text

    track = upsert_user_track(
        db,
        user.id,
        "university_course",
        plan="free",
        package_type=None,
        onboarding_detail=detail,
    )
    db.commit()
    db.refresh(user)
    db.refresh(track)

    profile = user_profile(user)
    tracks = [serialize_track(t) for t in get_user_tracks(db, user.id)]
    profile["tracks"] = tracks
    profile["active_track_type"] = next((t["track_type"] for t in tracks if t["is_active"]), "university_course")
    return {
        "message": "course learning onboarding saved",
        "onboarding": _course_learning_onboarding_payload(user, track),
        "user": profile,
        "profile": profile,
    }


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


@app.put("/me/password")
def change_password(req: ChangePasswordRequest, username: str, db: Session = Depends(get_db)):
    old_pw = req.old_password.strip()
    new_pw = req.new_password.strip()
    confirm_pw = req.confirm_password.strip()

    if not old_pw or not new_pw or not confirm_pw:
        raise HTTPException(status_code=400, detail="所有密码字段不能为空")
    if len(new_pw) < 8:
        raise HTTPException(status_code=400, detail="新密码长度至少 8 位")
    if new_pw != confirm_pw:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致")
    if new_pw == old_pw:
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")

    user = get_user_by_username(username, db)
    if not verify_password(old_pw, user.hashed_password):
        raise HTTPException(status_code=401, detail="旧密码不正确")

    user.hashed_password = hash_password(new_pw)
    db.commit()

    return {"message": "密码修改成功"}


# ═══════════════════════════════════════════════════════════
# Email Verification
# ═══════════════════════════════════════════════════════════

import hashlib as _hashlib
import smtplib as _smtplib
from email.mime.text import MIMEText as _MIMEText
import string as _string

def _hash_code(code: str) -> str:
    return _hashlib.sha256(code.encode()).hexdigest()


def _send_email_code(to_email: str, code: str) -> bool:
    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    smtp_port = (os.getenv("SMTP_PORT") or "").strip()
    smtp_user = (os.getenv("SMTP_USER") or "").strip()
    smtp_pass = (os.getenv("SMTP_PASSWORD") or "").strip()
    smtp_from = (os.getenv("SMTP_FROM") or smtp_user or "noreply@ai-study.local").strip()

    if not smtp_host or not smtp_user or not smtp_pass:
        return False

    try:
        msg = _MIMEText(
            f"您的邮箱验证码是：{code}\n\n该验证码 10 分钟内有效，请勿泄露给他人。\n\nAI 学习平台",
            "plain", "utf-8"
        )
        msg["Subject"] = "AI 学习平台 - 邮箱验证码"
        msg["From"] = smtp_from
        msg["To"] = to_email

        port = int(smtp_port) if smtp_port else 587
        if port == 465:
            server = _smtplib.SMTP_SSL(smtp_host, port, timeout=15)
        else:
            server = _smtplib.SMTP(smtp_host, port, timeout=15)
            server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_from, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception:
        return False


class SendEmailCodeRequest(BaseModel):
    email: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


@app.post("/me/email/send-code")
def send_email_code(req: SendEmailCodeRequest, username: str, db: Session = Depends(get_db)):
    email = req.email.strip()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="请输入有效的邮箱地址")

    user = get_user_by_username(username, db)

    # Rate limit: 60s per email
    one_min_ago = datetime.utcnow() - timedelta(seconds=60)
    recent = db.query(models.VerificationCode).filter(
        models.VerificationCode.username == user.username,
        models.VerificationCode.target == email,
        models.VerificationCode.purpose == "bind_email",
        models.VerificationCode.created_at >= one_min_ago,
    ).first()
    if recent:
        raise HTTPException(status_code=429, detail="请 60 秒后再试")

    code = "".join(__import__("secrets").choice("0123456789") for _ in range(6))
    code_hash = _hash_code(code)
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    record = models.VerificationCode(
        username=user.username, target=email, purpose="bind_email",
        code_hash=code_hash, expires_at=expires_at,
    )
    db.add(record)
    db.commit()

    sent = _send_email_code(email, code)
    if not sent:
        raise HTTPException(status_code=503, detail="邮件服务暂未配置，请联系管理员")

    return {"message": "验证码已发送"}


@app.put("/me/email/verify")
def verify_email_code(req: VerifyEmailRequest, username: str, db: Session = Depends(get_db)):
    email = req.email.strip()
    code = req.code.strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="邮箱和验证码不能为空")

    user = get_user_by_username(username, db)

    code_hash = _hash_code(code)
    now = datetime.utcnow()

    record = db.query(models.VerificationCode).filter(
        models.VerificationCode.username == user.username,
        models.VerificationCode.target == email,
        models.VerificationCode.purpose == "bind_email",
        models.VerificationCode.used == False,
    ).order_by(models.VerificationCode.created_at.desc()).first()

    if not record:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    if record.expires_at < now:
        raise HTTPException(status_code=400, detail="验证码已过期，请重新发送")
    if record.attempts >= 5:
        raise HTTPException(status_code=400, detail="验证码尝试次数过多，请重新发送")
    if record.code_hash != code_hash:
        record.attempts = (record.attempts or 0) + 1
        db.commit()
        raise HTTPException(status_code=400, detail="验证码错误")

    record.used = True
    user.email = email
    user.email_verified = True
    db.commit()

    return {"message": "邮箱绑定成功", "profile": user_profile(user)}


# ═══════════════════════════════════════════════════════════
# Email-based Login
# ═══════════════════════════════════════════════════════════

class EmailLoginSendCodeRequest(BaseModel):
    email: str


class EmailLoginRequest(BaseModel):
    email: str
    code: str


@app.post("/auth/email-login/send-code")
def email_login_send_code(req: EmailLoginSendCodeRequest, db: Session = Depends(get_db)):
    email = req.email.strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="请输入有效的邮箱地址")

    # Find user by verified email
    user = db.query(models.User).filter(
        models.User.email == email,
        models.User.email_verified == True,
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="该邮箱尚未绑定账号，请先用账号密码登录后在个人资料中绑定邮箱")

    # Rate limit: 60s
    one_min_ago = datetime.utcnow() - timedelta(seconds=60)
    recent = db.query(models.VerificationCode).filter(
        models.VerificationCode.username == user.username,
        models.VerificationCode.target == email,
        models.VerificationCode.purpose == "login_email",
        models.VerificationCode.created_at >= one_min_ago,
    ).first()
    if recent:
        raise HTTPException(status_code=429, detail="请 60 秒后再试")

    code = "".join(__import__("secrets").choice("0123456789") for _ in range(6))
    code_hash = _hash_code(code)
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    record = models.VerificationCode(
        username=user.username, target=email, purpose="login_email",
        code_hash=code_hash, expires_at=expires_at,
    )
    db.add(record)
    db.commit()

    sent = _send_email_code(email, code)
    if not sent:
        raise HTTPException(status_code=503, detail="邮件服务暂未配置，请联系管理员")

    return {"message": "验证码已发送"}


@app.post("/auth/email-login")
def email_login(req: EmailLoginRequest, db: Session = Depends(get_db)):
    email = req.email.strip()
    code = req.code.strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="邮箱和验证码不能为空")

    # Find user by verified email
    user = db.query(models.User).filter(
        models.User.email == email,
        models.User.email_verified == True,
    ).first()
    if not user:
        raise HTTPException(status_code=400, detail="该邮箱尚未绑定账号")

    code_hash = _hash_code(code)
    now = datetime.utcnow()

    record = db.query(models.VerificationCode).filter(
        models.VerificationCode.username == user.username,
        models.VerificationCode.target == email,
        models.VerificationCode.purpose == "login_email",
        models.VerificationCode.used == False,
    ).order_by(models.VerificationCode.created_at.desc()).first()

    if not record:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    if record.expires_at < now:
        raise HTTPException(status_code=400, detail="验证码已过期，请重新发送")
    if record.attempts >= 5:
        raise HTTPException(status_code=400, detail="验证码尝试次数过多，请重新发送")
    if record.code_hash != code_hash:
        record.attempts = (record.attempts or 0) + 1
        db.commit()
        raise HTTPException(status_code=400, detail="验证码错误")

    record.used = True
    db.commit()

    profile = user_profile(user)
    return {"message": "登录成功", "user": profile, "profile": profile}


@app.get("/me/quota")
def get_my_quota(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    exam_track = ensure_exam_408_track(db, user)
    plan_info = get_user_plan(user.username, db)
    limits = get_plan_limits(plan_info["plan"])
    exam_serialized = serialize_track(exam_track) if exam_track else None
    exam_permissions = exam_serialized.get("permissions", {}) if exam_serialized else {}
    if exam_permissions:
        limits["chat"] = int(exam_permissions.get("ai_chat_daily_limit") or limits.get("chat", 0))
        limits["question_generate"] = int(exam_permissions.get("ai_question_daily_limit") or limits.get("question_generate", 0))
        limits["single_file_size_mb"] = int(exam_permissions.get("material_upload_limit_mb") or limits.get("single_file_size_mb", 20))
        limits["learning_plan_generate"] = 999999 if exam_permissions.get("learning_plan") else 0
        limits["learning_report_generate"] = 999999 if exam_permissions.get("learning_report") else 0

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
        "active_track_type": "exam_408" if exam_track else None,
        "exam_408_track": exam_serialized,
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

    # Delete old avatar file if exists
    old_avatar = (user.avatar or "").strip()
    if old_avatar and old_avatar not in ALLOWED_AVATARS:
        try:
            old_path = AVATAR_UPLOAD_ROOT / old_avatar
            if old_path.exists() and old_path.is_file():
                os.remove(old_path)
        except Exception:
            pass

    avatar_filename = f"{secrets.token_hex(16)}{suffix}"
    AVATAR_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    avatar_path = AVATAR_UPLOAD_ROOT / avatar_filename

    with open(avatar_path, "wb") as output:
        output.write(file_bytes)

    user.avatar = avatar_filename
    db.commit()
    db.refresh(user)

    return {"avatar_url": f"/api/me/avatar/{avatar_filename}", "message": "头像已更新", "profile": user_profile(user)}


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


@app.delete("/me/avatar")
def delete_avatar(username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    old_avatar = (user.avatar or "").strip()
    if old_avatar and old_avatar not in ALLOWED_AVATARS:
        try:
            old_path = AVATAR_UPLOAD_ROOT / old_avatar
            if old_path.exists() and old_path.is_file():
                os.remove(old_path)
        except Exception:
            pass
    user.avatar = ""
    db.commit()
    db.refresh(user)
    return {"message": "头像已删除", "profile": user_profile(user)}


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

    ensure_feature_enabled(db, "feature_ai_chat_enabled", "AI 问答功能暂时维护中，请稍后再试")

    user = get_user_by_username(req.username, db)
    subject = normalize_subject(req.subject, req.course)
    exam_subject = normalize_exam_subject_key(req.exam_subject, req.subject_key)
    material_ids = sorted({int(item) for item in (req.material_ids or []) if int(item) > 0})
    selected_materials: list[models.StudyMaterial] = []
    branch_id = (req.branch_id or "").strip()[:64]
    edit_source_message: models.ChatMessage | None = None
    root_message_id: int | None = None
    parent_message_id: int | None = None
    version_index = 0

    if material_ids:
        selected_query = query_accessible_materials(db, user.username).filter(
            models.StudyMaterial.id.in_(material_ids),
        )
        if subject:
            selected_query = selected_query.filter(models.StudyMaterial.subject == subject)
        selected_materials = selected_query.all()
        material_map = {material.id: material for material in selected_materials}
        if len(material_map) != len(material_ids):
            raise HTTPException(status_code=404, detail="指定资料不存在或不属于当前用户")

        blocked_materials = [
            material
            for material in selected_materials
            if not is_reference_metadata_material(material)
            and ((material.parse_status or "success") != "success" or (material.chunk_count or 0) <= 0)
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
        session_exam_subject = normalize_exam_subject_key(chat_session.exam_subject)
        if exam_subject and session_exam_subject != exam_subject:
            raise HTTPException(status_code=400, detail="当前对话不属于该 11408 科目，请先新建本科目对话")
        session_subject = normalize_subject(chat_session.subject, chat_session.course)
        if not exam_subject and subject and session_subject and session_subject != subject:
            raise HTTPException(status_code=400, detail="当前对话不属于该科目，请先新建本科目对话")
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
            exam_subject=exam_subject or None,
        )
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)

    if req.edit_source_message_id is not None:
        edit_source_message = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.id == req.edit_source_message_id,
                models.ChatMessage.user_id == user.id,
                models.ChatMessage.session_id == chat_session.id,
                models.ChatMessage.role == "user",
            )
            .first()
        )
        if not edit_source_message:
            raise HTTPException(status_code=404, detail="原问题不存在，无法创建分支")
        root_message_id = edit_source_message.root_message_id or edit_source_message.id
        parent_message_id = edit_source_message.id
        max_version = (
            db.query(func.max(models.ChatMessage.version_index))
            .filter(
                models.ChatMessage.user_id == user.id,
                models.ChatMessage.session_id == chat_session.id,
                models.ChatMessage.role == "user",
                (
                    (models.ChatMessage.id == root_message_id)
                    | (models.ChatMessage.root_message_id == root_message_id)
                ),
            )
            .scalar()
        )
        version_index = int(max_version or 0) + 1
        branch_id = branch_id or f"msg-{root_message_id}-v{version_index}"

    primary_material = selected_materials[0] if selected_materials else None
    user_message = models.ChatMessage(
        user_id=user.id,
        session_id=chat_session.id,
        role="user",
        content=req.message,
        attachment_type=primary_material.file_type if primary_material else None,
        attachment_filename=primary_material.original_filename if primary_material else None,
        material_id=primary_material.id if primary_material else None,
        parent_message_id=parent_message_id,
        root_message_id=root_message_id,
        branch_id=branch_id or None,
        version_index=version_index,
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
    reference_metadata_context = build_reference_metadata_context(selected_materials)
    if reference_metadata_context:
        knowledge_context = "\n\n".join([item for item in [knowledge_context, reference_metadata_context] if item])
    course_preference = get_course_preference_payload(db, user.username, subject)
    if not build_course_preference_prompt(course_preference, subject) and req.mastery_level and req.learning_goal:
        course_preference = {
            "course_id": subject,
            "mastery_level": req.mastery_level,
            "learning_goal": req.learning_goal,
            "is_started": True,
        }
    course_preference_context = build_course_preference_prompt(course_preference, subject)
    if course_preference_context:
        knowledge_context = "\n\n".join([item for item in [knowledge_context, course_preference_context] if item])

    system_prompt = build_system_prompt(
        subject,
        req.message,
        {
            "grade": user.grade or "",
            "major": user.major or "",
        },
        has_attachment=bool(material_ids),
        rag_chunks=rag_chunks,
        knowledge_context=knowledge_context,
    )

    user_content = req.message
    if req.hidden_instruction:
        user_content = f"{req.hidden_instruction}\n\n---\n学生问题：{req.message}"
    if material_ids and selected_materials:
        file_names = "、".join(m.original_filename for m in selected_materials)
        user_content = f"【本轮引用资料：{file_names}】\n{user_content}"

    if is_exam_408_context(subject, req.course):
        check_exam_408_usage_limit(user, "chat", db)
    else:
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
        parent_message_id=user_message.id,
        root_message_id=root_message_id,
        branch_id=branch_id or None,
        version_index=version_index,
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
        "branch_id": branch_id,
        "root_message_id": root_message_id,
        "version_index": version_index,
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

    ensure_feature_enabled(db, "feature_material_upload_enabled", "资料上传功能暂时维护中，请稍后再试")

    user = get_user_by_username(upload_username, db)
    normalized_subject = normalize_subject(subject)

    # Upload quota checks
    plan_info = get_user_plan(user.username, db)
    plan_limits = get_plan_limits(plan_info["plan"])
    max_file_size_mb = plan_limits.get("single_file_size_mb", 20)
    max_material_count = plan_limits.get("material_upload_count", 30)
    if is_exam_408_context(normalized_subject, subject):
        exam_permissions = get_exam_408_permissions_for_user(db, user)
        if exam_permissions:
            max_file_size_mb = int(exam_permissions.get("material_upload_limit_mb") or max_file_size_mb)
            max_material_count = 999999

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

    file_bytes = await file.read()
    validate_upload(file, file_bytes, max_size_mb=max_file_size_mb)

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
            "message": "文件已上传，系统正在后台分批解析。大文件可能需要较长时间，解析完成后可用于 AI 问答。",
            "material": serialize_material_detail(material),
        }

    background_tasks.add_task(parse_material_in_background, material.id)
    user_ocr_limit = get_pdf_ocr_page_limit_for_user(user.username, db) if file_type == "pdf" else 0
    if file_type == "pdf":
        if user_ocr_limit > DEFAULT_OCR_LIMIT:
            pending_message = (
                f"文件已上传，系统正在后台解析。"
                f"当前套餐支持扫描型 PDF 最多 OCR {user_ocr_limit} 页，"
                f"文本页面不受此限制。大文件可能需要较长时间。"
            )
        else:
            pending_message = (
                "文件已上传，系统正在后台解析。"
                "文本型 PDF 会尽量全文解析；扫描型 PDF 按套餐控制，"
                "普通套餐默认最多 OCR 20 页，全程考包支持更大规模 OCR。"
                "完成后会更新索引状态。"
            )
    else:
        pending_message = "文件已上传，系统正在后台解析，完成后会更新索引状态。"

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


@app.post("/materials/{material_id}/reparse")
def reparse_single_material(material_id: int, username: str, db: Session = Depends(get_db)):
    """Re-parse a single material from its source file: re-extract text, re-OCR if needed, re-chunk."""
    user = get_user_by_username(username, db)
    material = get_accessible_material_or_404(db, user.username, material_id)
    if not can_user_modify_material(material, user.username):
        raise HTTPException(status_code=403, detail="只有本人上传的私有资料可以重新解析")

    file_path = resolve_stored_file_path(material.file_path)
    if not file_path.exists() or not file_path.is_file():
        material.parse_status = "failed"
        material.parse_error = "上传文件不存在，无法重新解析。"
        db.commit()
        return {
            "material_id": material.id,
            "parse_status": "failed",
            "parse_error": material.parse_error,
            "message": "原文件不存在，无法重新解析。",
            "material": serialize_material_detail(material),
        }

    try:
        file_bytes = file_path.read_bytes()
    except Exception:
        material.parse_status = "failed"
        material.parse_error = "读取原文件失败，请重新上传。"
        db.commit()
        return {
            "material_id": material.id,
            "parse_status": "failed",
            "parse_error": material.parse_error,
            "message": "读取原文件失败。",
            "material": serialize_material_detail(material),
        }

    material.parse_status = "parsing"
    material.parse_error = None
    material.parse_progress = 1
    material.parse_started_at = serialize_datetime(utc_now())
    db.commit()
    db.refresh(material)

    extracted_text = ""
    chunk_count = 0
    file_type = (material.file_type or "").lower()
    original_filename = material.original_filename or ""

    try:
        if file_type == "pdf":
            total_pages, page_texts = extract_pdf_pages(file_bytes)
            extracted_text = build_pdf_text_from_pages(page_texts)
            is_text = is_pdf_text_usable(extracted_text, total_pages)

            update_material_parse_state(
                db, material_id,
                total_pages=total_pages,
                parse_progress=20,
                parsed_pages=0,
                ocr_required=0 if is_text else 1,
            )

            if is_text:
                material, chunk_count = complete_material_with_local_pdf_text(
                    db, material, extracted_text, total_pages,
                )
            else:
                # Try OCR fallback via Qwen
                parse_scanned_pdf_in_background(db, material, file_bytes, extracted_text)
                db.refresh(material)
                chunk_count = material.chunk_count or 0

        elif file_type == "image":
            extracted_text = extract_image_text(file_bytes)
            if (extracted_text or "").strip():
                update_material_parse_state(
                    db, material_id,
                    extracted_text=extracted_text,
                    extract_method="local",
                    parse_progress=40,
                )
                chunk_count = replace_material_chunks(db, material)
                update_material_parse_state(
                    db, material_id,
                    parse_status="success",
                    parse_progress=100,
                    parse_completed_at=serialize_datetime(utc_now()),
                    chunk_count=chunk_count,
                )
            else:
                # Image: try Qwen OCR
                update_material_parse_state(db, material_id, parse_status="parsing", parse_progress=10)
                material = get_material_for_parsing(db, material_id)
                vision_config = get_vision_runtime_config(db)
                qwen_result = (
                    parse_image_with_qwen(str(file_path), prompt=SCANNED_PDF_PAGE_PROMPT)
                    if vision_config["vision_enabled"] else {"success": False, "error": "Qwen 视觉解析已在模型配置中停用"}
                )
                qwen_text = (qwen_result.get("extracted_text") or "").strip()
                if qwen_result.get("success") and qwen_text:
                    update_material_parse_state(
                        db, material_id,
                        extracted_text=qwen_text,
                        extract_method="qwen",
                        qwen_used=True,
                        parse_progress=50,
                    )
                    chunk_count = replace_material_chunks(db, material)
                    update_material_parse_state(
                        db, material_id,
                        parse_status="success",
                        parse_progress=100,
                        parse_completed_at=serialize_datetime(utc_now()),
                        chunk_count=chunk_count,
                    )
                else:
                    update_material_parse_state(
                        db, material_id,
                        parse_status="failed",
                        parse_error=qwen_result.get("error") or "图片 OCR 解析失败，未能提取文字。",
                        parse_progress=0,
                        parse_completed_at=serialize_datetime(utc_now()),
                    )

        elif file_type in ("docx", "pptx", "text", "code"):
            from document_parser import extract_supported_file_text
            result = extract_supported_file_text(file_bytes, original_filename)
            extracted_text = result["text"]
            if (extracted_text or "").strip():
                update_material_parse_state(
                    db, material_id,
                    extracted_text=extracted_text,
                    extract_method="local",
                    parse_progress=40,
                )
                chunk_count = replace_material_chunks(db, material)
                update_material_parse_state(
                    db, material_id,
                    parse_status="success",
                    parse_progress=100,
                    parse_completed_at=serialize_datetime(utc_now()),
                    chunk_count=chunk_count,
                )
            else:
                update_material_parse_state(
                    db, material_id,
                    parse_status="failed",
                    parse_error="文件内容为空，无法解析。",
                    parse_progress=0,
                    parse_completed_at=serialize_datetime(utc_now()),
                )
        else:
            update_material_parse_state(
                db, material_id,
                parse_status="failed",
                parse_error=f"暂不支持 {file_type} 类型的重新解析。",
                parse_progress=0,
                parse_completed_at=serialize_datetime(utc_now()),
            )
    except Exception as exc:
        update_material_parse_state(
            db, material_id,
            parse_status="failed",
            parse_error=f"重新解析失败：{str(exc)[:200]}",
            parse_progress=0,
            parse_completed_at=serialize_datetime(utc_now()),
        )

    db.refresh(material)
    return {
        "material_id": material.id,
        "parse_status": material.parse_status,
        "parse_error": material.parse_error,
        "chunk_count": material.chunk_count or 0,
        "message": "重新解析完成" if material.parse_status == "success" else "重新解析失败",
        "material": serialize_material_detail(material),
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
    query = query_accessible_materials(db, user.username)

    normalized_subject = normalize_subject(subject, default="")
    if normalized_subject:
        query = query.filter(models.StudyMaterial.subject == normalized_subject)

    materials = query.order_by(models.StudyMaterial.is_default_reference.desc(), models.StudyMaterial.created_at.desc()).all()
    return {"materials": [serialize_material_list_item(material) for material in materials]}


@app.get("/materials/{material_id}/download")
def download_material_file(material_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    material = get_accessible_material_or_404(db, user.username, material_id)
    if not can_user_modify_material(material, user.username) or not bool(getattr(material, "allow_download", True)):
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
    material = get_accessible_material_or_404(db, user.username, material_id)
    if not can_user_modify_material(material, user.username):
        raise HTTPException(status_code=403, detail="没有权限查看该资料原文")

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
    material = get_accessible_material_or_404(db, user.username, material_id)

    return serialize_material_status(material)


@app.get("/materials/{material_id}")
def get_material_detail(material_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    material = get_accessible_material_or_404(db, user.username, material_id)

    return {"material": serialize_material_detail(material)}


@app.delete("/materials/{material_id}")
def delete_material(material_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    material = get_accessible_material_or_404(db, user.username, material_id)
    if not can_user_modify_material(material, user.username):
        raise HTTPException(status_code=403, detail="只有本人上传的私有资料可以删除")

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


@app.get("/course-preferences")
def get_course_preference(username: str, subject: str = "", course_id: str = "", db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    normalized_course = normalize_subject(course_id or subject, default="")
    if not normalized_course:
        raise HTTPException(status_code=400, detail="请提供课程")
    return {"success": True, "preference": get_course_preference_payload(db, user.username, normalized_course)}


@app.post("/course-preferences")
def save_course_preference(req: schemas.CourseLearningPreferenceUpsert, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    normalized_course = normalize_subject(req.course_id or req.subject, default="")
    mastery_level = (req.mastery_level or "").strip()
    learning_goal = (req.learning_goal or "").strip()
    if not normalized_course:
        raise HTTPException(status_code=400, detail="请提供课程")
    if not mastery_level or not learning_goal:
        raise HTTPException(status_code=400, detail="请选择掌握程度和学习目标")

    now = utc_now()
    preference = get_course_preference_record(db, user.username, normalized_course)
    if preference:
        preference.mastery_level = mastery_level
        preference.learning_goal = learning_goal
        preference.is_started = True
        preference.started_at = preference.started_at or now
        preference.updated_at = now
    else:
        preference = models.CourseLearningPreference(
            username=user.username,
            course_id=normalized_course,
            mastery_level=mastery_level,
            learning_goal=learning_goal,
            is_started=True,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(preference)

    db.commit()
    db.refresh(preference)
    return {"success": True, "preference": serialize_course_preference(preference, normalized_course)}


@app.get("/chat/history")
def get_chat_history(
    username: str,
    subject: str = "",
    course: str = "",
    subject_key: str = "",
    exam_subject: str = "",
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    normalized_subject = normalize_subject(subject, course, default="") if (subject or course) else ""
    normalized_exam_subject = normalize_exam_subject_key(exam_subject, subject_key)

    query = db.query(models.ChatSession).filter(models.ChatSession.user_id == user.id)
    if normalized_exam_subject:
        query = query.filter(models.ChatSession.exam_subject == normalized_exam_subject)
    elif normalized_subject:
        query = query.filter(
            or_(
                models.ChatSession.subject == normalized_subject,
                models.ChatSession.course == normalized_subject,
            )
        )

    sessions = query.order_by(models.ChatSession.created_at.desc()).all()

    return {"sessions": [serialize_session(session) for session in sessions]}


@app.get("/chat/sessions/{session_id}")
def get_chat_session_messages(
    session_id: int,
    username: str,
    subject: str = "",
    course: str = "",
    subject_key: str = "",
    exam_subject: str = "",
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    normalized_subject = normalize_subject(subject, course, default="") if (subject or course) else ""
    normalized_exam_subject = normalize_exam_subject_key(exam_subject, subject_key)

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

    session_exam_subject = normalize_exam_subject_key(chat_session.exam_subject)
    if normalized_exam_subject and session_exam_subject != normalized_exam_subject:
        raise HTTPException(status_code=404, detail="Chat session not found for this subject")
    session_subject = normalize_subject(chat_session.subject, chat_session.course, default="")
    if not normalized_exam_subject and normalized_subject and session_subject and session_subject != normalized_subject:
        raise HTTPException(status_code=404, detail="Chat session not found for this subject")

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
def delete_chat_session(
    session_id: int,
    username: str,
    subject_key: str = "",
    exam_subject: str = "",
    db: Session = Depends(get_db),
):
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

    normalized_exam_subject = normalize_exam_subject_key(exam_subject, subject_key)
    if normalized_exam_subject and normalize_exam_subject_key(chat_session.exam_subject) != normalized_exam_subject:
        raise HTTPException(status_code=404, detail="Chat session not found for this subject")

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
        "reference_solution": challenge.reference_solution,
        "source": getattr(challenge, "source", None) or "ai",
        "target_weak_point": getattr(challenge, "target_weak_point", None),
        "test_cases": getattr(challenge, "test_cases", None) or "[]",
        "created_at": challenge.created_at,
    }


def serialize_learning_task(task, knowledge_point_title=None, related_material=None, related_material_titles=None):
    task_metadata = None
    raw_metadata = getattr(task, "task_metadata", None)
    if raw_metadata:
        try:
            task_metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata
        except Exception:
            task_metadata = None
    return {
        "id": task.id,
        "username": task.username,
        "course_id": task.course_id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "status": task.status,
        "source": task.source,
        "priority": getattr(task, "priority", None),
        "order_index": getattr(task, "order_index", 0),
        "due_date": serialize_datetime(task.due_date) if task.due_date else None,
        "related_session_id": task.related_session_id,
        "related_challenge_id": task.related_challenge_id,
        "related_material_id": task.related_material_id,
        "related_material_title": related_material.original_filename if related_material else None,
        "related_material_file_type": related_material.file_type if related_material else None,
        "knowledge_point_id": getattr(task, "knowledge_point_id", None),
        "knowledge_point_title": knowledge_point_title,
        "knowledge_point_text": getattr(task, "knowledge_point_text", None),
        "related_question_id": getattr(task, "related_question_id", None),
        "metadata": task_metadata,
        "related_material_titles": related_material_titles or [],
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
        "node_key": getattr(point, "node_key", None) or None,
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
            src = getattr(ch, "source", None) or "ai"
            # Backward compat: old AI challenges stored as "normal"
            if src == "normal":
                src = "ai"
            challenge_map[ch.id] = {
                "source": src,
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

    challenge_id = getattr(req, "challenge_id", None)
    if challenge_id:
        challenge = (
            db.query(models.CodeChallenge)
            .filter(
                models.CodeChallenge.id == challenge_id,
                models.CodeChallenge.username == user.username,
            )
            .first()
        )
        if not challenge:
            raise HTTPException(status_code=400, detail="题目不存在或不属于当前用户")

    session = models.CodeSession(
        username=user.username,
        course_id=normalize_subject(req.course_id),
        title=(req.title or "未命名练习").strip()[:255] or "未命名练习",
        language=language,
        code=req.code or CODE_TEMPLATES.get(language, ""),
        challenge_id=challenge_id,
        session_type="challenge" if challenge_id else "normal",
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


MAX_CODE_EXECUTE_CHARS = 20000
MAX_STDIN_CHARS = 5000
MAX_OUTPUT_CHARS = 8000
MAX_TEST_CASES = 10
MAX_TEST_CASE_INPUT_CHARS = 5000
MAX_TEST_CASE_OUTPUT_CHARS = 5000
EXECUTE_TIMEOUT_SECONDS = 3
EXECUTE_TIMEOUT_SECONDS_C = 6  # C compile+run needs more time
DOCKER_MEMORY_LIMIT = "128m"
DOCKER_MEMORY_LIMIT_C = "256m"  # gcc compilation needs more memory
DOCKER_CPU_LIMIT = 1.0
DOCKER_PIDS_LIMIT = 64
DOCKER_IMAGE = "python:3.11-slim"
DOCKER_IMAGE_C = "gcc:13"

# ── Rate limiting (in-memory, cleared on restart) ──
CODE_RUN_RATE_LIMITS: dict[str, list[float]] = defaultdict(list)
CODE_RUN_RATE_WINDOW = 60  # seconds
CODE_RUN_RATE_EXECUTE = 10  # per window
CODE_RUN_RATE_TESTS = 5     # per window

# ── Docker concurrency semaphore ──
DOCKER_SEMAPHORE = threading.Semaphore(2)
DOCKER_SEMAPHORE_TIMEOUT = 8  # seconds


def _check_code_run_rate(username: str, limit: int, window: int = CODE_RUN_RATE_WINDOW) -> bool:
    """Return True if rate limit is NOT exceeded."""
    now = time.time()
    bucket = CODE_RUN_RATE_LIMITS[username]
    # Remove entries outside the window
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def _classify_docker_error(stderr: str) -> tuple[str | None, str | None]:
    """Classify Docker stderr into user-friendly Chinese messages.

    Returns (error_message, error_type).
    error_type is one of: docker_permission, docker_not_found, image_not_found,
    container_permission, container_noexec, or None.
    """
    if not stderr or not stderr.strip():
        return None, None
    lower = stderr.lower()

    # Docker daemon socket permission denied — must mention docker socket / daemon
    # e.g. "Got permission denied while trying to connect to the Docker daemon socket
    #       at unix:///var/run/docker.sock"
    if "permission denied" in lower and "docker" in lower and ("socket" in lower or "daemon" in lower or "connect" in lower):
        return (
            "后端服务暂无 Docker 权限，无法运行代码。请联系管理员配置 Docker 权限。",
            "docker_permission",
        )

    # Docker command not found on host
    if ("no such file" in lower or "not found" in lower) and "docker" in lower:
        return (
            "服务器 Docker 环境未就绪，Docker 命令不存在。请联系管理员安装 Docker。",
            "docker_not_found",
        )

    # Docker image not found / pull required
    if "image" in lower and ("not found" in lower or "pull" in lower or "unable" in lower):
        return (
            "运行镜像尚未准备完成，请先执行 docker pull python:3.11-slim 和 docker pull gcc:13。",
            "image_not_found",
        )

    # Container-internal permission error — binary cannot execute (likely noexec tmpfs)
    # e.g. "sh: 1: /tmp/main: Permission denied"
    if "permission denied" in lower and "/tmp/" in lower:
        return (
            "C 程序编译成功，但运行二进制失败，可能是容器临时目录缺少执行权限。",
            "container_noexec",
        )

    # Generic container permission error
    if "cannot execute" in lower or "exec format error" in lower:
        return (
            "C 程序编译成功，但运行二进制失败，可能是容器临时目录缺少执行权限。",
            "container_noexec",
        )

    return None, None


def _compute_diff_summary(expected: str, actual: str) -> str:
    """Compute a simple line-by-line diff summary."""
    if expected == actual:
        return ""
    expected_lines = expected.splitlines()
    actual_lines = actual.splitlines()

    if len(expected_lines) != len(actual_lines):
        parts = [f"输出行数不同：期望 {len(expected_lines)} 行，实际 {len(actual_lines)} 行"]
        max_lines = max(len(expected_lines), len(actual_lines))
        for i in range(min(max_lines, 3)):
            exp_line = expected_lines[i] if i < len(expected_lines) else "(无)"
            act_line = actual_lines[i] if i < len(actual_lines) else "(无)"
            if exp_line != act_line:
                parts.append(f"第 {i + 1} 行不同：期望「{exp_line[:80]}」，实际「{act_line[:80]}」")
                break
        else:
            parts.append("行数不同但前几行内容一致")
        return "；".join(parts)
    else:
        for i, (e, a) in enumerate(zip(expected_lines, actual_lines)):
            if e != a:
                return f"第 {i + 1} 行不同：期望「{e[:120]}」，实际「{a[:120]}」"
        return "输出内容存在差异（可能是空白字符不同）"


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

        stdout_truncated = False
        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS]
            stdout_truncated = True

        stderr_truncated = False
        if len(stderr) > MAX_OUTPUT_CHARS:
            stderr = stderr[:MAX_OUTPUT_CHARS]
            stderr_truncated = True

        docker_error, docker_error_type = _classify_docker_error(proc.stderr or "")

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode,
            "duration_ms": elapsed_ms,
            "timed_out": False,
            "error_message": docker_error,
            "docker_error_type": docker_error_type,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "stdout": "",
            "stderr": f"执行超时（超过 {EXECUTE_TIMEOUT_SECONDS} 秒），您的代码可能包含死循环或复杂度过高的算法。",
            "exit_code": -1,
            "duration_ms": elapsed_ms,
            "timed_out": True,
            "error_message": None,
            "docker_error_type": None,
            "stdout_truncated": False,
            "stderr_truncated": False,
        }
    except FileNotFoundError:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": "服务器 Docker 环境未就绪，Docker 命令不存在。请联系管理员安装 Docker。",
            "docker_error_type": "docker_not_found",
            "stdout_truncated": False,
            "stderr_truncated": False,
        }
    except PermissionError:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": "后端服务暂无 Docker 权限，无法运行代码。请联系管理员配置 Docker 权限。",
            "docker_error_type": "docker_permission",
            "stdout_truncated": False,
            "stderr_truncated": False,
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": f"代码执行环境异常：{str(exc)[:200]}",
            "docker_error_type": None,
            "stdout_truncated": False,
            "stderr_truncated": False,
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


def _run_c_code_in_docker(code: str, stdin: str = "") -> dict:
    """Compile and run user C code inside a locked-down Docker container.

    Uses gcc:13 image. Compiles main.c then executes the binary.
    User code is mounted read-only; binary is compiled to /tmp inside the container.
    --tmpfs for C uses :rw,nosuid (without noexec) so the compiled binary can run.
    """
    tmp_dir = tempfile.mkdtemp(prefix="code_exec_c_")
    source_path = os.path.join(tmp_dir, "main.c")
    input_path = os.path.join(tmp_dir, "stdin.txt")

    try:
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(code)

        with open(input_path, "w", encoding="utf-8") as f:
            f.write(stdin or "")

        # Shell script inside container:
        # 1. gcc compile, redirect errors to a temp file
        # 2. If compile fails (non-zero), cat errors to stderr, exit 101
        # 3. If compile succeeds, run the binary with stdin
        compile_and_run = (
            "gcc /code/main.c -O2 -std=c11 -Wall -Wextra -o /tmp/main 2>/tmp/compile_err.txt; "
            "if [ $? -ne 0 ]; then cat /tmp/compile_err.txt >&2; exit 101; fi; "
            "/tmp/main < /code/stdin.txt"
        )

        # Security: --network none, --read-only root,
        # --tmpfs /tmp:rw,exec,nosuid (exec MUST be explicit to override Docker's default noexec)
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", DOCKER_MEMORY_LIMIT_C,
            "--cpus", str(DOCKER_CPU_LIMIT),
            "--pids-limit", str(DOCKER_PIDS_LIMIT),
            "--read-only",
            "--tmpfs", "/tmp:rw,exec,nosuid,size=128m",
            "-v", f"{tmp_dir}:/code:ro",
            "-w", "/code",
            DOCKER_IMAGE_C,
            "sh", "-c", compile_and_run,
        ]

        start = time.time()
        proc = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=EXECUTE_TIMEOUT_SECONDS_C,
            cwd=tmp_dir,
        )
        elapsed_ms = int((time.time() - start) * 1000)

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        compile_error = None
        compiled = True

        # Exit code 101 = compile error
        if proc.returncode == 101:
            compile_error = (proc.stderr or "").strip()
            compiled = False
            stdout = ""
            stderr = ""

        stdout_truncated = False
        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS]
            stdout_truncated = True

        stderr_truncated = False
        if len(stderr) > MAX_OUTPUT_CHARS:
            stderr = stderr[:MAX_OUTPUT_CHARS]
            stderr_truncated = True

        docker_error, docker_error_type = _classify_docker_error(proc.stderr or "")

        # Diagnostic log for C execution
        stderr_preview = (proc.stderr or "")[:200].replace("\n", "\\n")
        print(
            f"[C-DOCKER] exit_code={proc.returncode} compiled={compiled} "
            f"has_compile_error={'yes' if compile_error else 'no'} "
            f"docker_error_type={docker_error_type} "
            f"stderr_preview={stderr_preview}"
        )

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc.returncode if proc.returncode != 101 else 1,
            "duration_ms": elapsed_ms,
            "timed_out": False,
            "error_message": docker_error,
            "docker_error_type": docker_error_type,
            "compile_error": compile_error,
            "compiled": compiled,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "stdout": "",
            "stderr": f"执行超时（超过 {EXECUTE_TIMEOUT_SECONDS_C} 秒），您的代码可能包含死循环或复杂度过高的算法。",
            "exit_code": -1,
            "duration_ms": elapsed_ms,
            "timed_out": True,
            "error_message": None,
            "docker_error_type": None,
            "compile_error": None,
            "compiled": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
        }
    except FileNotFoundError:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": "服务器 Docker 环境未就绪，Docker 命令不存在。请联系管理员安装 Docker。",
            "docker_error_type": "docker_not_found",
            "compile_error": None,
            "compiled": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
        }
    except PermissionError:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": "后端服务暂无 Docker 权限，无法运行代码。请联系管理员配置 Docker 权限。",
            "docker_error_type": "docker_permission",
            "compile_error": None,
            "compiled": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": f"代码执行环境异常：{str(exc)[:200]}",
            "docker_error_type": None,
            "compile_error": None,
            "compiled": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
        }
    finally:
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
        except OSError:
            pass
        try:
            if os.path.exists(source_path):
                os.remove(source_path)
        except OSError:
            pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass


# ── Code Diagnostics ──────────────────────────────────

import re as _diagnose_re


def _parse_gcc_diagnostics(output: str) -> list[dict]:
    """Parse gcc/clang output into structured diagnostics."""
    items = []
    # Pattern: file:line:column: severity: message
    # e.g. main.c:10:17: warning: format '%d' expects argument of type 'int *'...
    # e.g. main.c:5:1: error: expected ';' before '}' token
    pattern = r"^[^:]+:(\d+):(\d+):\s*(warning|error|fatal error|note):\s*(.+)$"
    for match in _diagnose_re.finditer(pattern, output, _diagnose_re.MULTILINE):
        line = int(match.group(1))
        col = int(match.group(2))
        sev_raw = match.group(3).lower()
        msg = match.group(4).strip()
        severity = "error" if sev_raw in ("error", "fatal error") else "warning"
        items.append({"line": line, "column": col, "message": msg, "severity": severity, "source": "gcc"})
    return items


def _fallback_c_diagnostics(code: str) -> list[dict]:
    """Small local fallback for common C syntax mistakes when gcc is unavailable."""
    items = []
    control_prefixes = ("if", "for", "while", "switch")
    lines = code.splitlines()
    for idx, raw_line in enumerate(code.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        if stripped.endswith((";", "{", "}", ":", ",")):
            continue
        if any(stripped.startswith(f"{prefix} ") or stripped.startswith(f"{prefix}(") for prefix in control_prefixes):
            continue
        if stripped.startswith(("else", "do")):
            continue
        if "(" in stripped and ")" in stripped:
            items.append({
                "line": idx,
                "column": len(raw_line.rstrip()) + 1,
                "message": "expected ';' at end of statement (local fallback: gcc/docker unavailable)",
                "severity": "error",
                "source": "c-fallback",
            })
            break
    if items:
        return items

    declaration_pattern = _diagnose_re.compile(r"^\s*int\s+([A-Za-z_]\w*)\s*;\s*$")
    for idx, raw_line in enumerate(lines, start=1):
        match = declaration_pattern.match(raw_line)
        if not match:
            continue
        name = match.group(1)
        rest = "\n".join(lines[idx:])
        if not _diagnose_re.search(rf"\b{_diagnose_re.escape(name)}\b", rest):
            items.append({
                "line": idx,
                "column": raw_line.find(name) + 1,
                "message": f"unused variable '{name}' (local fallback: gcc/docker unavailable)",
                "severity": "warning",
                "source": "c-fallback",
            })
            break
    return items


def _parse_python_diagnostics(output: str) -> list[dict]:
    """Parse python -m py_compile stderr into structured diagnostics."""
    items = []
    line_number = 1
    for line in output.splitlines():
        match = _diagnose_re.search(r'File\s+"[^"]+",\s+line\s+(\d+)', line)
        if match:
            line_number = int(match.group(1))

    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if _diagnose_re.match(r"^(SyntaxError|IndentationError|TabError):", stripped):
            items.append({
                "line": line_number,
                "column": 1,
                "message": stripped[:300],
                "severity": "error",
                "source": "python",
            })
            break

    if not items and output.strip():
        items.append({
            "line": line_number,
            "column": 1,
            "message": output.strip().splitlines()[-1][:300],
            "severity": "error",
            "source": "python",
        })
    return items


@app.post("/code/diagnose")
def diagnose_code(req: schemas.CodeDiagnoseRequest):
    """Perform syntax/compile diagnostics without executing code."""
    language = (req.language or "").strip().lower()
    code = (req.code or "")

    if not code.strip():
        return {"language": language, "status": "ok", "errors": [], "warnings": [], "raw_output": ""}

    if language == "c":
        import subprocess as _sp
        tmp_dir = tempfile.mkdtemp(prefix="code_diag_")
        c_path = os.path.join(tmp_dir, "main.c")
        try:
            with open(c_path, "w", encoding="utf-8") as f:
                f.write(code)
            proc = _sp.run(
                ["docker", "run", "--rm", "--network", "none", "--memory", "128m",
                 "-v", f"{tmp_dir}:/code:ro", "-w", "/code", DOCKER_IMAGE_C,
                 "gcc", "-fsyntax-only", "-Wall", "-Wextra", "-o", "/dev/null", "main.c"],
                capture_output=True, text=True, timeout=15, cwd=tmp_dir,
            )
            raw = (proc.stderr or "") or (proc.stdout or "")
            items = _parse_gcc_diagnostics(raw)
            errors = [i for i in items if i["severity"] == "error"]
            warnings = [i for i in items if i["severity"] == "warning"]
            if proc.returncode == 0 and not warnings:
                return {"language": "c", "status": "ok", "errors": [], "warnings": [], "raw_output": raw}
            if proc.returncode != 0 and not errors and not warnings:
                errors = [{
                    "line": 1,
                    "column": 1,
                    "message": (raw.strip() or "C syntax check failed")[:300],
                    "severity": "error",
                    "source": "gcc",
                }]
            status = "error" if errors else ("warning" if warnings else "ok")
            return {"language": "c", "status": status, "errors": errors, "warnings": warnings, "raw_output": raw}
        except FileNotFoundError as e:
            fallback_items = _fallback_c_diagnostics(code)
            fallback_errors = [i for i in fallback_items if i["severity"] == "error"]
            fallback_warnings = [i for i in fallback_items if i["severity"] == "warning"]
            if fallback_items:
                return {
                    "language": "c",
                    "status": "error" if fallback_errors else "warning",
                    "errors": fallback_errors,
                    "warnings": fallback_warnings,
                    "raw_output": str(e),
                }
            return {"language": "c", "status": "ok", "errors": [], "warnings": [], "raw_output": str(e)}
        except (_sp.TimeoutExpired, Exception) as e:
            return {"language": "c", "status": "error", "errors": [
                {"line": 1, "column": 1, "message": f"诊断服务异常：{str(e)[:200]}", "severity": "error", "source": "system"}
            ], "warnings": [], "raw_output": str(e)}
        finally:
            try: os.remove(c_path)
            except OSError: pass
            try: os.rmdir(tmp_dir)
            except OSError: pass

    elif language == "python":
        tmp_dir = tempfile.mkdtemp(prefix="code_diag_")
        py_path = os.path.join(tmp_dir, "main.py")
        try:
            with open(py_path, "w", encoding="utf-8") as f:
                f.write(code)
            proc = subprocess.run(
                [sys.executable, "-m", "py_compile", py_path],
                capture_output=True, text=True, timeout=10, cwd=tmp_dir,
            )
            raw = proc.stderr or ""
            if proc.returncode == 0:
                return {"language": "python", "status": "ok", "errors": [], "warnings": [], "raw_output": ""}
            items = _parse_python_diagnostics(raw)
            errors = [i for i in items if i["severity"] == "error"]
            warnings = [i for i in items if i["severity"] == "warning"]
            status = "error" if errors else "warning"
            return {"language": "python", "status": status, "errors": errors, "warnings": warnings, "raw_output": raw}
        except (subprocess.TimeoutExpired, Exception) as e:
            return {"language": "python", "status": "error", "errors": [
                {"line": 1, "column": 1, "message": f"诊断服务异常：{str(e)[:200]}", "severity": "error", "source": "system"}
            ], "warnings": [], "raw_output": str(e)}
        finally:
            try: os.remove(py_path)
            except OSError: pass
            try: os.rmdir(tmp_dir)
            except OSError: pass

    else:
        return {"language": language, "status": "unsupported", "errors": [], "warnings": [], "raw_output": "该语言暂不支持语法诊断"}


@app.post("/code/execute")
def execute_code(req: schemas.CodeExecuteRequest, db: Session = Depends(get_db)):
    language = (req.language or "").strip().lower()

    if language not in ("python", "c"):
        return {
            "success": True,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "timed_out": False,
            "error_message": f"当前真实运行暂支持 Python 和 C，{req.language or '该语言'} 暂不支持。请使用 AI 判定功能分析代码。",
            "compile_error": None,
            "compiled": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
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
            "compile_error": None,
            "compiled": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
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
            "compile_error": None,
            "compiled": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
        }

    stdin = (req.stdin or "")[:MAX_STDIN_CHARS]

    # Session ownership check (if session_id provided)
    user = None
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

    # Rate limit check (use same limit for both languages)
    username = user.username if user else req.username
    if not _check_code_run_rate(username, CODE_RUN_RATE_EXECUTE):
        raise HTTPException(status_code=429, detail="运行过于频繁，每分钟最多运行 10 次，请稍后再试。")

    # Acquire semaphore with timeout
    acquired = DOCKER_SEMAPHORE.acquire(timeout=DOCKER_SEMAPHORE_TIMEOUT)
    if not acquired:
        raise HTTPException(status_code=503, detail="当前代码运行任务较多，请稍后重试。")

    try:
        if language == "c":
            result = _run_c_code_in_docker(code, stdin)
        else:
            result = _run_code_in_docker(code, stdin)
        result["success"] = True
        return result
    finally:
        DOCKER_SEMAPHORE.release()


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

    # Check if session is linked to a challenge (also check req.challenge_id)
    challenge = None
    challenge_id = getattr(session, "challenge_id", None) if session else None
    if not challenge_id and req.challenge_id:
        challenge_id = req.challenge_id
    if challenge_id:
        challenge = db.query(models.CodeChallenge).filter(
            models.CodeChallenge.id == challenge_id,
        ).first()

    # Build run/test context
    run_context = ""
    last_run = req.last_run_result
    if last_run and isinstance(last_run, dict):
        run_context = "\n## 最近一次运行结果\n"
        if last_run.get("stdout"):
            run_context += f"stdout: {last_run['stdout'][:2000]}"
        if last_run.get("stderr"):
            run_context += f"\nstderr: {last_run['stderr'][:1000]}"
        if last_run.get("compile_error"):
            run_context += f"\n编译错误: {last_run['compile_error'][:1000]}"
        if last_run.get("error_message"):
            run_context += f"\n运行错误: {last_run['error_message'][:500]}"
        run_context += f"\nexit_code: {last_run.get('exit_code', 'N/A')}"
        if last_run.get("timed_out"):
            run_context += "\n(执行超时)"

    test_context = ""
    last_tests = req.last_test_results
    if last_tests and isinstance(last_tests, dict):
        total = last_tests.get("total", 0)
        passed = last_tests.get("passed", 0)
        failed = total - passed
        test_context = f"\n## 最近一次测试结果\n总计 {total} 个测试，通过 {passed} 个，未通过 {failed} 个。"
        results = last_tests.get("results", [])
        if isinstance(results, list) and len(results) > 0:
            test_context += "\n"
            for tc in results:
                if not isinstance(tc, dict):
                    continue
                passed_mark = "✅" if tc.get("passed") else "❌"
                test_context += f"\n{passed_mark} 用例 #{tc.get('index', '?')}: {tc.get('description', '')[:80]}"
                if not tc.get("passed"):
                    if tc.get("expected_output"):
                        test_context += f"\n   期望输出: {str(tc['expected_output'])[:200]}"
                    if tc.get("actual_output"):
                        test_context += f"\n   实际输出: {str(tc['actual_output'])[:200]}"
                    if tc.get("stderr"):
                        test_context += f"\n   stderr: {str(tc['stderr'])[:200]}"
                    if tc.get("compile_error"):
                        test_context += f"\n   编译错误: {str(tc['compile_error'])[:200]}"
                    if tc.get("diff_summary"):
                        test_context += f"\n   差异: {str(tc['diff_summary'])[:200]}"

    diagnostics_context = ""
    diagnostics_payload = req.diagnostics
    if diagnostics_payload and isinstance(diagnostics_payload, dict):
        errors = diagnostics_payload.get("errors") or []
        warnings = diagnostics_payload.get("warnings") or []
        diagnostics_context = "\n## Current editor diagnostics\n"
        diagnostics_context += f"status: {diagnostics_payload.get('status', 'unknown')}\n"
        if isinstance(errors, list) and errors:
            diagnostics_context += "errors:\n"
            for item in errors[:8]:
                if isinstance(item, dict):
                    diagnostics_context += (
                        f"- line {item.get('line', '?')}, column {item.get('column', '?')}: "
                        f"{str(item.get('message', ''))[:300]}\n"
                    )
        if isinstance(warnings, list) and warnings:
            diagnostics_context += "warnings:\n"
            for item in warnings[:8]:
                if isinstance(item, dict):
                    diagnostics_context += (
                        f"- line {item.get('line', '?')}, column {item.get('column', '?')}: "
                        f"{str(item.get('message', ''))[:300]}\n"
                    )
        if not (isinstance(errors, list) and errors) and not (isinstance(warnings, list) and warnings):
            diagnostics_context += "no active diagnostics\n"

    # System prompt additions for run/test context
    context_guidance = ""
    if run_context or test_context or diagnostics_context:
        context_guidance = (
            "\n\n用户提供了运行/测试结果。"
            "如果用户问测试为什么没过，优先结合测试结果中的具体失败用例和差异来分析。"
            "如果用户问运行错误，优先结合运行结果中的 stderr/stdout/编译错误来分析。"
            "如果用户问代码问题，结合代码和运行/测试结果一起分析。"
            "如果用户没有明确问运行/测试相关的问题，也要在分析时参考这些结果来发现代码问题。"
        )

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
给出 1-2 条具体的学习方向建议。""" + context_guidance

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
{run_context}{test_context}{diagnostics_context}

用户问题：{question}"""
    else:
        system_prompt = CODE_ANALYZE_SYSTEM_PROMPT + context_guidance
        user_message = f"""语言：{language}
课程：{course_info or "未指定"}
{code_note}

代码：
```
{truncated_code}
```
{run_context}{test_context}{diagnostics_context}

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


# ── AI Coach Saved Chats ──────────────────────────────

def serialize_saved_chat(sc):
    return {
        "id": sc.id,
        "username": sc.username,
        "challenge_id": sc.challenge_id,
        "session_id": sc.session_id,
        "language": sc.language,
        "user_message": sc.user_message,
        "assistant_message": sc.assistant_message,
        "code_snapshot": sc.code_snapshot,
        "created_at": sc.created_at,
    }


@app.post("/code/ai-coach/saved-chats")
def save_ai_coach_chat(req: schemas.CodeAISavedChatCreate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    if not req.challenge_id:
        raise HTTPException(status_code=400, detail="当前题目未加载完成，暂不能保存记录")

    saved = models.CodeAISavedChat(
        username=user.username,
        challenge_id=req.challenge_id,
        session_id=req.session_id,
        language=req.language,
        user_message=req.user_message,
        assistant_message=req.assistant_message,
        code_snapshot=req.code_snapshot,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return {"success": True, "saved_chat": serialize_saved_chat(saved)}


@app.get("/code/ai-coach/saved-chats")
def get_saved_ai_coach_chats(
    username: str,
    challenge_id: int,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    items = (
        db.query(models.CodeAISavedChat)
        .filter(
            models.CodeAISavedChat.username == user.username,
            models.CodeAISavedChat.challenge_id == challenge_id,
        )
        .order_by(models.CodeAISavedChat.created_at.asc())
        .all()
    )
    return {"items": [serialize_saved_chat(item) for item in items]}


@app.delete("/code/ai-coach/saved-chats/{saved_id}")
def delete_saved_ai_coach_chat(
    saved_id: int,
    username: str,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    saved = (
        db.query(models.CodeAISavedChat)
        .filter(
            models.CodeAISavedChat.id == saved_id,
            models.CodeAISavedChat.username == user.username,
        )
        .first()
    )
    if not saved:
        raise HTTPException(status_code=404, detail="保存记录不存在")
    db.delete(saved)
    db.commit()
    return {"success": True}


_CHALLENGE_REQUIRED_FIELDS = (
    "title",
    "description",
    "requirements",
    "input_format",
    "output_format",
    "examples",
    "hints",
    "starter_code",
    "test_cases",
)

_OUTPUT_EXPLANATION_MARKERS = (
    "解释",
    "说明",
    "原因",
    "因为",
    "所以",
    "输出为",
    "答案是",
    "explanation",
    "because",
    "therefore",
    "expected output",
    "output:",
)


def _normalize_code_language_for_validation(language: str) -> str:
    value = (language or "").strip().lower()
    if value in ("c", "c语言", "c language", "c programming"):
        return "C"
    if value in ("python", "py"):
        return "Python"
    return "Python"


def _extract_json_value(text: str):
    text = (text or "").strip()
    if not text:
        return None
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


def _clean_expected_output(value: object) -> str:
    text = str(value if value is not None else "").strip()
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _challenge_has_no_input(input_format: str) -> bool:
    lowered = (input_format or "").strip().lower()
    return any(marker in lowered for marker in ("无输入", "不需要输入", "没有输入", "no input", "without input"))


def _looks_like_integer_output(output: str) -> bool:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return bool(lines) and all(re.fullmatch(r"[-+]?\d+", line) for line in lines)


def _output_format_requires_yes_no(output_format: str) -> bool:
    lowered = (output_format or "").lower()
    compact = lowered.replace(" ", "")
    return (
        "yes/no" in compact
        or "yes或no" in compact
        or ("yes" in lowered and "no" in lowered)
        or "是/否" in lowered
    )


def _output_format_requires_integer(output_format: str) -> bool:
    lowered = (output_format or "").lower()
    return any(marker in lowered for marker in ("整数", "整型", "integer", "int"))


def _normalize_generated_test_cases(raw_test_cases: object) -> list[dict]:
    if isinstance(raw_test_cases, str):
        parsed = _extract_json_value(raw_test_cases)
        raw_test_cases = parsed if isinstance(parsed, list) else []
    if not isinstance(raw_test_cases, list):
        return []

    cases: list[dict] = []
    for tc in raw_test_cases:
        if not isinstance(tc, dict):
            continue
        cases.append({
            "input": str(tc.get("input", "")),
            "expected_output": _clean_expected_output(tc.get("expected_output", "")),
            "description": str(tc.get("description", ""))[:100],
            "explanation": str(tc.get("explanation", ""))[:300],
        })
    return cases


def _starter_language_errors(starter_code: str, language: str) -> list[str]:
    code = starter_code or ""
    lowered = code.lower()
    normalized_language = _normalize_code_language_for_validation(language)
    errors: list[str] = []
    if normalized_language == "C":
        if "#include" not in code and "int main" not in lowered:
            errors.append("starter_code 不像完整 C 程序，缺少 #include 或 int main")
        if re.search(r"^\s*def\s+\w+\s*\(", code, re.MULTILINE) or "import sys" in lowered or "input(" in lowered:
            errors.append("language=C 但 starter_code 中出现 Python 代码特征")
    else:
        if "#include" in code or "int main" in lowered or "scanf(" in lowered:
            errors.append("language=Python 但 starter_code 中出现 C 代码特征")
        if "input(" not in lowered and "sys.stdin" not in lowered and "def " not in lowered:
            errors.append("starter_code 不像 Python 代码框架，缺少 input/sys.stdin/def 等特征")
    return errors


def validate_generated_challenge(challenge_data: dict, language: str) -> dict:
    """Validate an AI-generated programming challenge before persisting it."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(challenge_data, dict):
        return {"ok": False, "errors": ["AI 返回的题目不是 JSON 对象"], "warnings": []}

    for field in _CHALLENGE_REQUIRED_FIELDS:
        value = challenge_data.get(field)
        if field == "test_cases":
            if not _normalize_generated_test_cases(value):
                errors.append("test_cases 缺失或不是有效数组")
        elif not str(value or "").strip():
            errors.append(f"{field} 不能为空")

    input_format = str(challenge_data.get("input_format") or "")
    output_format = str(challenge_data.get("output_format") or "")
    starter_code = str(challenge_data.get("starter_code") or "")
    examples = str(challenge_data.get("examples") or "")
    test_cases = _normalize_generated_test_cases(challenge_data.get("test_cases"))
    no_input = _challenge_has_no_input(input_format)

    if len(test_cases) < 3:
        errors.append("test_cases 至少需要 3 个有效测试用例")

    for idx, tc in enumerate(test_cases, start=1):
        case_input = str(tc.get("input", ""))
        expected_output = _clean_expected_output(tc.get("expected_output", ""))
        if not no_input and not case_input.strip():
            errors.append(f"第 {idx} 个测试用例 input 为空，但题目未声明无输入")
        if not expected_output:
            errors.append(f"第 {idx} 个测试用例 expected_output 为空")
            continue
        lowered_output = expected_output.lower()
        if any(marker in lowered_output for marker in _OUTPUT_EXPLANATION_MARKERS):
            errors.append(f"第 {idx} 个测试用例 expected_output 包含解释性文字")
        if _output_format_requires_yes_no(output_format):
            values = [line.strip().lower() for line in expected_output.splitlines() if line.strip()]
            if not values or any(value not in ("yes", "no") for value in values):
                errors.append(f"第 {idx} 个测试用例 expected_output 不符合 Yes/No 输出格式")
        if _output_format_requires_integer(output_format) and not _looks_like_integer_output(expected_output):
            warnings.append(f"第 {idx} 个测试用例 expected_output 可能不符合整数输出格式")

    errors.extend(_starter_language_errors(starter_code, language))

    if "输入" in examples and "输出" in examples:
        sample_outputs = re.findall(r"输出[:：]\s*([^\n\r]+)", examples)
        expected_values = {_clean_expected_output(tc.get("expected_output", "")) for tc in test_cases}
        if sample_outputs and not any(_clean_expected_output(sample) in expected_values for sample in sample_outputs):
            warnings.append("examples 中的样例输出未能在 test_cases.expected_output 中找到一致项")
    elif examples.strip():
        warnings.append("examples 未清晰包含输入/输出字段")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


def _repair_generated_challenge_with_ai(challenge_data: dict, language: str, validation: dict) -> dict | None:
    issues = list(validation.get("errors") or []) + list(validation.get("warnings") or [])
    if not issues:
        return None

    repair_prompt = f"""你是编程题一致性校验员。请只修复下面 JSON 题目中的题面、输入输出格式、样例、starter_code 和 test_cases 的一致性问题。

硬性要求：
1. 只返回合法 JSON 对象，不要 Markdown，不要解释。
2. 不要加入 reference_solution，不要泄露完整答案。
3. 不要改变课程、语言和题目核心知识点。
4. language={_normalize_code_language_for_validation(language)} 时，starter_code 必须匹配该语言。
5. test_cases 至少 3 个；每个用例必须有 input、expected_output、description。
6. expected_output 只能是程序真实标准输出，不能包含解释性文字。
7. examples 的输入输出必须和 test_cases 中至少一个用例一致。

发现的问题：
{json.dumps(issues, ensure_ascii=False)}

待修复题目 JSON：
{json.dumps(challenge_data, ensure_ascii=False)}
"""
    try:
        raw = call_deepseek([
            {"role": "system", "content": "你只输出修复后的编程题 JSON 对象。"},
            {"role": "user", "content": repair_prompt},
        ], timeout_seconds=45)
    except Exception as exc:
        logger.warning("challenge repair call failed: %s", exc)
        return None

    fixed = _extract_json_value(raw)
    return fixed if isinstance(fixed, dict) else None


CODE_CHALLENGE_GENERATE_PROMPT = """你是编程学习出题助手。根据用户的学习背景和编程进度，生成完整的编程练习题。你只负责生成题目数据，不生成参考答案代码。

## 通用要求
1. 题目难度适合用户当前水平，可在单文件中完成，不依赖第三方库
2. 题目描述至少 80 个中文字符，要说清背景、任务目标和输入输出逻辑
3. examples 必须包含至少 1 组完整的样例输入+输出，用文本描述清晰
4. requirements 至少列出 3 条具体要求，用编号说明
5. starter_code 提供代码框架，包含必要的 import 和函数签名（不能为空）
6. test_cases 至少提供 5 个测试用例，每个用例包含 input、expected_output、description
7. 测试用例必须覆盖：普通情况、边界情况（空输入/极小/极大）、特殊情况
8. expected_output 必须由题目规则严格推导，确保逻辑自洽
9. 多道题时一次性输出所有题目
10. **不要生成参考答案代码**，用户将通过 AI 教练按需获取
11. test_cases.expected_output 必须是程序真实标准输出，不能包含解释、推理、单位说明或"因为/所以"等自然语言说明
12. examples 中的样例输入/输出必须和 test_cases 中至少一个用例完全一致
13. input_format 必须和每个 test_cases.input 的行数、数据类型和字段数量匹配
14. output_format 必须和每个 test_cases.expected_output 的格式匹配；若要求 Yes/No，只能输出 Yes 或 No
15. starter_code 必须严格匹配请求语言：C 题使用 #include/int main/scanf/fgets 等 C 框架；Python 题使用 input/sys.stdin/def 等 Python 框架
16. starter_code 只能是起始框架或 TODO，占位不要包含完整解法
17. JSON 中不要出现 reference_solution 字段

## 输出格式（严格 JSON 数组，不要 Markdown，不要额外解释）
[
  {
    "title": "题目标题（简洁明确）",
    "difficulty": "基础|中等|提高",
    "knowledge_point": "涉及的核心知识点",
    "description": "详细题目描述，至少80字，包括背景、任务、输入输出说明",
    "requirements": "1. 具体要求一\\n2. 具体要求二\\n3. 具体要求三",
    "input_format": "输入格式详细说明",
    "output_format": "输出格式详细说明",
    "examples": "样例1：\\n输入：xxx\\n输出：xxx\\n解释：xxx",
    "hints": "提示1; 提示2",
    "starter_code": "# 起始代码框架（必填，只含函数签名、输入读取框架、pass/TODO占位）",
    "test_cases": [
      {"input": "stdin输入", "expected_output": "期望输出", "description": "普通样例"},
      {"input": "边界输入", "expected_output": "边界期望输出", "description": "边界测试"},
      {"input": "极小输入", "expected_output": "期望输出", "description": "极小输入"},
      {"input": "较大输入", "expected_output": "期望输出", "description": "较大输入"},
      {"input": "特殊输入", "expected_output": "期望输出", "description": "特殊情况"}
    ]
  }
]"""


@app.post("/code/challenges/generate")
def generate_code_challenge(req: schemas.CodeChallengeGenerateRequest, db: Session = Depends(get_db)):
    import json as json_module
    import re as re_module

    user = get_user_by_username(req.username, db)
    language = (req.language or "Python").strip()
    if language not in CODE_TEMPLATES:
        language = "Python"
    difficulty = (req.difficulty or "基础").strip()
    if difficulty not in ("基础", "中等", "提高"):
        difficulty = "基础"
    course_id = normalize_subject(req.course_id, default="")

    challenge_source = (req.source or "ai").strip()
    if challenge_source not in ("ai", "ai_generated", "diagnosis", "manual"):
        challenge_source = "ai"
    target_weak_point = (req.target_weak_point or req.focus or "").strip()

    # Batch count: 1-10
    count = min(max(int(req.count or 1), 1), 10)

    # Knowledge points from selected IDs
    kp_texts: list[str] = []
    knowledge_point_ids = list(req.knowledge_point_ids or [])
    if knowledge_point_ids and course_id:
        kps = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.username == user.username,
                models.KnowledgePoint.course_id == course_id,
                models.KnowledgePoint.id.in_(knowledge_point_ids),
            )
            .all()
        )
        kp_texts = [kp.title for kp in kps if kp.title]
    if req.knowledge_text and req.knowledge_text.strip():
        kp_texts.append(req.knowledge_text.strip())

    # Material context
    material_context = ""
    if req.material_ids and course_id:
        materials = (
            db.query(models.StudyMaterial)
            .filter(
                models.StudyMaterial.username == user.username,
                models.StudyMaterial.subject == course_id,
                models.StudyMaterial.id.in_(list(req.material_ids)),
                models.StudyMaterial.is_deleted.is_(False),
            )
            .all()
        )
        if materials:
            material_names = [m.original_filename for m in materials[:5]]
            material_previews = []
            for m in materials[:3]:
                preview = (m.summary or m.extracted_text or "")[:300]
                if preview:
                    material_previews.append(f"[{m.original_filename}]: {preview}")
            material_context = (
                f"参考以下资料内容生成题目：\n"
                f"资料列表：{', '.join(material_names)}\n"
                + "\n".join(material_previews)
            )

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
    kp_text = f"绑定知识点：{', '.join(kp_texts)}" if kp_texts else ""
    if target_weak_point:
        hint = "系统检测到用户当前薄弱知识点" if recommended_focus else "本题针对的薄弱点"
        weak_point_text = (
            f"{hint}：{target_weak_point}。"
            f"请优先围绕该知识点设计题目，题目难度不要过高，不要超出当前课程范围。"
        )
    else:
        weak_point_text = ""

    extra_req_text = ""
    if req.extra_requirement and req.extra_requirement.strip():
        extra_req_text = f"额外要求：{req.extra_requirement.strip()}\n请严格遵守这些额外要求。"

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
- 不要直接复述诊断报告原文"""

    progress_summary = f"""用户编程进度：
- 当前课程：{course_id or "未指定"}
- 编程语言：{language}
- 总练习数：{total_exercises}
- 各语言练习分布：{lang_counts or "暂无"}
- 最近练习：{recent_titles or "暂无"}
- 最近 AI 分析摘要：{recent_history_summary or "暂无"}
{focus_text}
{kp_text}
{weak_point_text}
{diagnosis_context}
{material_context}
{extra_req_text}"""

    if is_diagnosis_driven:
        question_text = f"请根据诊断报告中的薄弱点，为上述用户生成 {count} 道 {difficulty} 难度的 {language} 针对性训练题。"
    else:
        question_text = f"请为上述用户生成 {count} 道 {difficulty} 难度的 {language} 编程题。"

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

    # Parse JSON from AI response — support wrapped array and bare array
    json_str = ai_response
    # Try code-fence extraction
    fence_match = re_module.search(r"```(?:json)?\s*([\s\S]*?)\s*```", ai_response)
    if fence_match:
        json_str = fence_match.group(1)
    # Try to find JSON array
    arr_match = re_module.search(r"\[[\s\S]*\]", json_str)
    challenges_list: list[dict] = []
    if arr_match:
        try:
            parsed = json_module.loads(arr_match.group(0))
            if isinstance(parsed, list):
                challenges_list = [item for item in parsed if isinstance(item, dict)]
        except json_module.JSONDecodeError:
            pass
    # Try wrapped object with "questions" / "challenges" key
    if not challenges_list:
        try:
            parsed = json_module.loads(json_str)
            if isinstance(parsed, list):
                challenges_list = [item for item in parsed if isinstance(item, dict)]
            elif isinstance(parsed, dict):
                for key in ("challenges", "questions", "data", "items"):
                    inner = parsed.get(key)
                    if isinstance(inner, list):
                        challenges_list = [item for item in inner if isinstance(item, dict)]
                        break
                if not challenges_list and parsed.get("title"):
                    challenges_list = [parsed]
        except json_module.JSONDecodeError:
            pass

    if not challenges_list:
        raise HTTPException(status_code=500, detail="AI 返回内容格式不符合题目结构，无法解析，请重试")

    created_challenges = []
    created_sessions = []
    validation_failures: list[str] = []

    for item in challenges_list[:count]:
        validation = validate_generated_challenge(item, language)
        if not validation.get("ok"):
            fixed_item = _repair_generated_challenge_with_ai(item, language, validation)
            if fixed_item:
                fixed_validation = validate_generated_challenge(fixed_item, language)
                if fixed_validation.get("ok"):
                    item = fixed_item
                    validation = fixed_validation
                else:
                    validation = fixed_validation
        if not validation.get("ok"):
            title = str(item.get("title") or "未命名题目")[:80]
            reason = "；".join((validation.get("errors") or [])[:3])
            validation_failures.append(f"{title}: {reason}")
            continue

        # Basic required fields
        if not item.get("title") or not item.get("description"):
            validation_failures.append("AI 生成题目缺少 title 或 description")
            continue

        # Parse test_cases
        test_cases_json = "[]"
        valid_cases = []
        for tc in _normalize_generated_test_cases(item.get("test_cases")):
            valid_cases.append({
                "input": str(tc.get("input", "")),
                "expected_output": _clean_expected_output(tc.get("expected_output", "")),
                "description": str(tc.get("description", ""))[:100],
            })
        if valid_cases:
            test_cases_json = json_module.dumps(valid_cases, ensure_ascii=False)

        # Build knowledge_point string
        kp_from_ai = str(item.get("knowledge_point") or item.get("knowledge_points") or "")

        challenge = models.CodeChallenge(
            username=user.username,
            course_id=course_id,
            language=language,
            title=str(item.get("title", ""))[:255],
            difficulty=str(item.get("difficulty", difficulty))[:20],
            knowledge_point=kp_from_ai or ", ".join(kp_texts) or recommended_focus or "",
            description=str(item.get("description", "")),
            requirements=str(item.get("requirements", "")),
            input_format=str(item.get("input_format", "")),
            output_format=str(item.get("output_format", "")),
            examples=str(item.get("examples", "")),
            starter_code=str(item.get("starter_code", CODE_TEMPLATES.get(language, ""))),
            reference_solution="",  # AI no longer generates reference_solution at creation time
            test_cases=test_cases_json,
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
        created_challenges.append(serialize_code_challenge(challenge))
        created_sessions.append(serialize_code_session(session))

    db.commit()

    if not created_sessions:
        detail = "AI 生成的题目未通过一致性校验，请重试。"
        if validation_failures:
            detail += " 原因：" + "；".join(validation_failures[:3])
        raise HTTPException(status_code=500, detail=detail)

    return {
        "success": True,
        "challenges": created_challenges,
        "sessions": created_sessions,
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


@app.post("/code/challenges/{challenge_id}/run-tests")
def run_challenge_tests(challenge_id: int, req: schemas.CodeChallengeRunTestsRequest, db: Session = Depends(get_db)):
    language = (req.language or "").strip().lower()

    if language not in ("python", "c"):
        return {
            "success": True,
            "total": 0,
            "passed": 0,
            "results": [],
            "error_message": f"当前测试运行暂支持 Python 和 C，{req.language or '该语言'} 暂不支持。",
        }

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

    # If session has a challenge_id, verify it matches the requested challenge
    session_challenge_id = getattr(session, "challenge_id", None)
    if session_challenge_id and session_challenge_id != challenge_id:
        return {
            "success": True,
            "total": 0,
            "passed": 0,
            "results": [],
            "error_message": "当前练习关联的题目与请求不一致，请重新选择练习。",
        }

    code = (req.code or "").strip()
    if not code:
        return {
            "success": True,
            "total": 0,
            "passed": 0,
            "results": [],
            "error_message": "请先编写代码再运行测试。",
        }

    if len(code) > MAX_CODE_EXECUTE_CHARS:
        return {
            "success": True,
            "total": 0,
            "passed": 0,
            "results": [],
            "error_message": f"代码过长（{len(code)} 字符），当前限制 {MAX_CODE_EXECUTE_CHARS} 字符。",
        }

    # Rate limit check
    if not _check_code_run_rate(user.username, CODE_RUN_RATE_TESTS):
        raise HTTPException(status_code=429, detail="运行测试过于频繁，每分钟最多运行 5 次，请稍后再试。")

    # Parse test_cases
    test_cases_json = getattr(challenge, "test_cases", None) or "[]"
    try:
        test_cases = json.loads(test_cases_json) if isinstance(test_cases_json, str) else test_cases_json
    except (json.JSONDecodeError, TypeError):
        test_cases = []

    if not isinstance(test_cases, list) or len(test_cases) == 0:
        return {
            "success": True,
            "total": 0,
            "passed": 0,
            "results": [],
            "error_message": "当前题目暂无测试用例，可使用 AI 判定功能分析答案。",
        }

    if len(test_cases) > MAX_TEST_CASES:
        test_cases = test_cases[:MAX_TEST_CASES]

    # Acquire semaphore with timeout
    acquired = DOCKER_SEMAPHORE.acquire(timeout=DOCKER_SEMAPHORE_TIMEOUT)
    if not acquired:
        raise HTTPException(status_code=503, detail="当前代码运行任务较多，请稍后重试。")

    is_c = language == "c"

    try:
        results = []
        passed_count = 0

        for idx, tc in enumerate(test_cases):
            if not isinstance(tc, dict):
                continue
            test_input = str(tc.get("input", ""))[:MAX_TEST_CASE_INPUT_CHARS]
            expected = str(tc.get("expected_output", ""))[:MAX_TEST_CASE_OUTPUT_CHARS].strip()
            description = str(tc.get("description", ""))[:100]

            if is_c:
                exec_result = _run_c_code_in_docker(code, test_input)
            else:
                exec_result = _run_code_in_docker(code, test_input)

            actual_output = (exec_result.get("stdout") or "").strip()
            stderr = (exec_result.get("stderr") or "")
            exit_code = exec_result.get("exit_code", -1)
            duration_ms = exec_result.get("duration_ms", 0)
            timed_out = exec_result.get("timed_out", False)
            error_message = exec_result.get("error_message")
            compile_error = exec_result.get("compile_error")
            compiled = exec_result.get("compiled", True)

            # Determine pass/fail
            if error_message:
                passed = False
            elif compile_error:
                passed = False
            elif timed_out:
                passed = False
            elif not compiled:
                passed = False
            elif exit_code != 0:
                passed = False
            elif actual_output == expected:
                passed = True
            else:
                passed = False

            if passed:
                passed_count += 1

            # Compute diff summary for failed test cases
            diff_summary = ""
            if not passed and not error_message and not timed_out and not compile_error and compiled and exit_code == 0:
                diff_summary = _compute_diff_summary(expected, actual_output)

            results.append({
                "index": idx + 1,
                "description": description,
                "input": test_input,
                "expected_output": expected,
                "actual_output": actual_output,
                "stderr": stderr,
                "exit_code": exit_code,
                "passed": passed,
                "duration_ms": duration_ms,
                "timed_out": timed_out,
                "error_message": error_message,
                "stdout_truncated": exec_result.get("stdout_truncated", False),
                "stderr_truncated": exec_result.get("stderr_truncated", False),
                "diff_summary": diff_summary,
                "compile_error": compile_error,
                "compiled": compiled,
            })

        return {
            "success": True,
            "total": len(results),
            "passed": passed_count,
            "results": results,
        }
    finally:
        DOCKER_SEMAPHORE.release()


CODE_CHALLENGE_EXPLAIN_FAILURE_PROMPT = """你是编程学习辅导助手。用户在练习一道编程题时，某个测试用例没有通过。请根据用户代码、题目信息、测试用例的输入输出和实际运行结果，分析失败原因并给出学习指导。

严格使用以下 Markdown 格式输出（不要输出其他内容）：

## 失败原因总结
用一两句话总结问题。{timed_out_hint}{stderr_hint}{empty_output_hint}

## 本测试点在考察什么
这个测试用例针对什么知识点或边界条件。

## 期望输出 vs 实际输出
对比期望和实际，说明差异的关键所在。

## 最可能出错的位置
指出代码中问题最可能出现在哪里（不要直接给完整答案）。

## 修改建议
给出具体的修改思路和局部建议（不要直接写出完整正确代码）。

## 相关知识点
列出与此问题相关的知识点（2~4 个）。

## 下一步提示
给用户一个具体的、可操作的下一步行动建议。

注意：
- 不要直接把完整答案泄露给用户
- 优先引导用户自己思考和修改
- 可以给关键思路和局部修改建议"""


@app.post("/code/challenges/{challenge_id}/explain-failure")
def explain_challenge_failure(challenge_id: int, req: schemas.CodeChallengeExplainFailureRequest, db: Session = Depends(get_db)):
    language = (req.language or "").strip().lower()

    if language not in ("python", "c"):
        return {
            "success": True,
            "explanation": f"当前 AI 解释暂支持 Python 和 C，{req.language or '该语言'} 暂不支持。",
        }

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
    if not code:
        return {
            "success": True,
            "explanation": "请先编写代码再请求 AI 解释。",
        }

    # Check usage limit
    check_usage_limit(req.username, "challenge_explain", db)

    # Build hints based on failure characteristics
    timed_out_hint = ""
    stderr_hint = ""
    empty_output_hint = ""

    if req.timed_out:
        timed_out_hint = "\n\n（注意：此测试用例执行超时，可能是死循环或算法复杂度过高导致。）"
    if req.stderr and req.stderr.strip():
        stderr_hint = f"\n\n（注意：此测试用例有 stderr 报错，请优先分析报错原因。stderr 内容：{req.stderr.strip()[:500]}）"
    if not req.actual_output.strip():
        empty_output_hint = "\n\n（注意：此测试用例的实际输出为空，可能代码未执行输入处理或未输出结果。）"

    tc = req.test_case or {}
    test_input = tc.get("input", "") or ""
    expected_output = tc.get("expected_output", "") or ""
    description = tc.get("description", "") or ""

    prompt = CODE_CHALLENGE_EXPLAIN_FAILURE_PROMPT.format(
        timed_out_hint=timed_out_hint,
        stderr_hint=stderr_hint,
        empty_output_hint=empty_output_hint,
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"""题目信息：
- 标题：{challenge.title}
- 难度：{challenge.difficulty}
- 知识点：{challenge.knowledge_point or '无'}
- 题目描述：{challenge.description[:500]}
- 输入格式：{challenge.input_format or '无'}
- 输出格式：{challenge.output_format or '无'}

测试用例信息：
- 描述：{description}
- 输入（stdin）：{test_input}
- 期望输出：{expected_output}

实际运行结果：
- 实际输出：{req.actual_output or '(空)'}
- stderr：{req.stderr or '(无)'}
- exit_code：{req.exit_code}
- 超时：{'是' if req.timed_out else '否'}

用户代码：
```python
{code[:3000]}
```"""},
    ]

    try:
        explanation = call_deepseek(messages)
        record_ai_usage(req.username, "challenge_explain", db, estimated_tokens=len(code) // 2 + 500)
        return {"success": True, "explanation": explanation}
    except HTTPException:
        raise
    except Exception as exc:
        record_ai_usage(req.username, "challenge_explain", db, status="error", error_message=str(exc)[:200])
        return {
            "success": True,
            "explanation": "## AI 解释失败\n\n很抱歉，AI 服务暂时不可用，请稍后重试。\n\n错误信息：" + str(exc)[:200],
        }


CODE_CHALLENGE_GENERATE_TESTS_PROMPT = """你是编程教学助手。你需要为一道已有的编程题目补全测试用例。

请根据题目的描述、输入输出格式、要求和示例，生成 3-5 个测试用例。

要求：
1. 每个测试用例包含 input、expected_output、description 三个字段
2. 必须严格符合题目的输入输出格式
3. 覆盖以下类型：
   - 基础用例：题目示例中的简单场景
   - 边界用例：空输入、极值、边界条件
   - 常见错误用例：容易出错的情况
4. input 是可选的stdin输入字符串，如果题目不需要输入可以为空字符串
5. expected_output 是期望的标准输出内容
6. description 用简短中文描述该用例测试什么（不超过50字）

返回严格 JSON 格式：
```json
[
  {
    "input": "...",
    "expected_output": "...",
    "description": "..."
  }
]
```"""


@app.post("/code/challenges/{challenge_id}/generate-tests")
def generate_challenge_tests(challenge_id: int, req: schemas.CodeChallengeGenerateTestsRequest, db: Session = Depends(get_db)):
    language = (req.language or "").strip().lower()

    if language not in ("python", "c"):
        return {
            "success": True,
            "test_cases": "[]",
            "message": f"当前测试用例生成暂支持 Python 和 C，{req.language or '该语言'} 暂不支持。",
        }

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

    # Check if already has test cases
    existing = getattr(challenge, "test_cases", None) or "[]"
    try:
        existing_cases = json.loads(existing) if isinstance(existing, str) else existing
    except (json.JSONDecodeError, TypeError):
        existing_cases = []
    if isinstance(existing_cases, list) and len(existing_cases) > 0:
        return {
            "success": True,
            "test_cases": existing,
            "message": "当前题目已有测试用例，无需重复生成。",
        }

    check_usage_limit(user.username, "challenge_test_gen", db)

    prompt = CODE_CHALLENGE_GENERATE_TESTS_PROMPT

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"""题目信息：
- 标题：{challenge.title}
- 难度：{challenge.difficulty}
- 知识点：{challenge.knowledge_point or '无'}
- 语言：{language}

题目描述：
{challenge.description[:1000]}

输入格式：
{challenge.input_format or '无特殊要求'}

输出格式：
{challenge.output_format or '无特殊要求'}

要求：
{challenge.requirements or '无特殊要求'}

示例：
{challenge.examples or '无示例'}

请根据以上信息生成 3-5 个测试用例。"""},
    ]

    try:
        ai_response = call_deepseek(messages)
        record_ai_usage(user.username, "challenge_test_gen", db, estimated_tokens=estimate_tokens_from_text(ai_response))
    except HTTPException:
        raise
    except Exception as exc:
        record_ai_usage(user.username, "challenge_test_gen", db, status="error", error_message=str(exc)[:200])
        return {
            "success": True,
            "test_cases": "[]",
            "message": "AI 生成测试用例失败，请稍后重试：" + str(exc)[:200],
        }

    # Parse JSON from AI response
    import re as re_module

    json_match = re_module.search(r"```json\s*([\s\S]*?)\s*```", ai_response)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_match = re_module.search(r"\[[\s\S]*\]", ai_response)
        if json_match:
            json_str = json_match.group(0)
        else:
            return {
                "success": True,
                "test_cases": "[]",
                "message": "AI 返回格式异常，请重试。",
            }

    try:
        test_cases = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return {
            "success": True,
            "test_cases": "[]",
            "message": "AI 返回解析失败，请重试。",
        }

    if not isinstance(test_cases, list) or len(test_cases) == 0:
        return {
            "success": True,
            "test_cases": "[]",
            "message": "AI 未生成有效测试用例，请重试。",
        }

    # Validate and sanitize
    valid_cases = []
    for tc in test_cases:
        if isinstance(tc, dict) and tc.get("input") is not None and tc.get("expected_output") is not None:
            valid_cases.append({
                "input": str(tc.get("input", "")),
                "expected_output": str(tc.get("expected_output", "")),
                "description": str(tc.get("description", ""))[:50],
            })
        if len(valid_cases) >= 5:
            break

    if not valid_cases:
        return {
            "success": True,
            "test_cases": "[]",
            "message": "AI 生成的测试用例格式不完整，请重试。",
        }

    test_cases_json = json.dumps(valid_cases, ensure_ascii=False)
    challenge.test_cases = test_cases_json
    db.commit()

    return {
        "success": True,
        "test_cases": test_cases_json,
        "message": f"已生成 {len(valid_cases)} 个测试用例",
    }


# ── Code Attempt History ──────────────────────────────


@app.get("/code/attempts")
def list_code_attempts(
    username: str,
    status: str | None = None,
    course_id: str = "",
    language: str | None = None,
    limit: int = 30,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)

    query = (
        db.query(models.CodeChallengeAttempt)
        .filter(models.CodeChallengeAttempt.username == user.username)
    )

    if status:
        query = query.filter(models.CodeChallengeAttempt.status == status)
    if language:
        query = query.filter(models.CodeChallengeAttempt.language == language)

    query = query.order_by(models.CodeChallengeAttempt.created_at.desc()).limit(max(1, min(limit, 100)))

    attempts = query.all()

    result = []
    for a in attempts:
        challenge = None
        if a.challenge_id:
            challenge = (
                db.query(models.CodeChallenge)
                .filter(models.CodeChallenge.id == a.challenge_id)
                .first()
            )

        ai_summary = ""
        if a.ai_feedback:
            lines = [l.strip() for l in a.ai_feedback.split("\n") if l.strip() and not l.startswith("#")]
            ai_summary = (lines[0][:120] + "..." if len(lines[0]) > 120 else lines[0]) if lines else ""

        if course_id and challenge and (not challenge.course_id or challenge.course_id != course_id):
            continue

        result.append({
            "id": a.id,
            "username": a.username,
            "session_id": a.session_id,
            "challenge_id": a.challenge_id,
            "challenge_title": challenge.title if challenge else None,
            "language": a.language,
            "difficulty": challenge.difficulty if challenge else None,
            "knowledge_point": challenge.knowledge_point if challenge else None,
            "status": a.status,
            "ai_feedback_summary": ai_summary,
            "mastered": a.mastered or 0,
            "created_at": serialize_datetime(a.created_at),
        })

    return {"success": True, "attempts": result}


@app.get("/code/attempts/{attempt_id}")
def get_code_attempt(attempt_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)

    attempt = (
        db.query(models.CodeChallengeAttempt)
        .filter(
            models.CodeChallengeAttempt.id == attempt_id,
            models.CodeChallengeAttempt.username == user.username,
        )
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="提交记录不存在")

    challenge = None
    if attempt.challenge_id:
        challenge = (
            db.query(models.CodeChallenge)
            .filter(models.CodeChallenge.id == attempt.challenge_id)
            .first()
        )

    return {
        "success": True,
        "attempt": {
            "id": attempt.id,
            "username": attempt.username,
            "session_id": attempt.session_id,
            "challenge_id": attempt.challenge_id,
            "language": attempt.language,
            "code": attempt.code,
            "status": attempt.status,
            "ai_feedback": attempt.ai_feedback,
            "mastered": attempt.mastered or 0,
            "mastered_at": attempt.mastered_at,
            "note": attempt.note,
            "created_at": serialize_datetime(attempt.created_at),
            "challenge_title": challenge.title if challenge else None,
            "challenge_difficulty": challenge.difficulty if challenge else None,
            "challenge_knowledge_point": challenge.knowledge_point if challenge else None,
            "challenge_description": challenge.description[:800] if challenge and challenge.description else None,
            "challenge_reference_solution": challenge.reference_solution if challenge else None,
            "challenge_test_cases": getattr(challenge, "test_cases", None) if challenge else None,
        },
    }


@app.put("/code/attempts/{attempt_id}/mastered")
def update_attempt_mastered(attempt_id: int, req: schemas.CodeAttemptMasteredUpdate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)

    attempt = (
        db.query(models.CodeChallengeAttempt)
        .filter(
            models.CodeChallengeAttempt.id == attempt_id,
            models.CodeChallengeAttempt.username == user.username,
        )
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="提交记录不存在")

    attempt.mastered = req.mastered
    if req.mastered:
        from datetime import datetime, timezone as tz
        attempt.mastered_at = datetime.now(tz.utc).isoformat()
    else:
        attempt.mastered_at = None

    db.commit()
    db.refresh(attempt)

    return {
        "success": True,
        "attempt_id": attempt.id,
        "mastered": attempt.mastered,
        "mastered_at": attempt.mastered_at,
    }


CODE_LEARNING_DIAGNOSIS_PROMPT = """你是编程学习诊断助手。根据用户的代码练习记录、AI 分析历史、出题记录和错题本数据，生成一份结构化的编程学习诊断报告。

要求：
1. 如果数据明显不足（少于 3 条练习记录），不要编造内容，明确说明「当前练习数据较少，以下建议仅作为初步参考」
2. 从 AI 分析记录中提取反复出现的问题模式，找出薄弱点
3. 每个薄弱点必须基于实际数据，给出证据依据（包含：失败次数、未掌握次数、最近相关题目标题、最近 AI 判定摘要）
4. 7 天学习计划要具体可执行，每天一个明确的小目标
5. 推荐出题方向要结合用户当前语言的薄弱环节
6. 错题本分析要重点关注未掌握（unmastered）的失败/部分通过记录
7. 已掌握的错题视为用户已有进步，不应再列为主要薄弱点
8. 如果错题本数据充足，优先从错题本中提取薄弱点证据

请严格按照以下 Markdown 格式输出：

## 编程学习概况
用户总练习数、各语言分布、AI 出题数、提交记录概览（含已掌握/未掌握比例）、最近学习动态的简要概述。

## 主要薄弱点
- **薄弱点名称**：具体表现；可能原因；对应知识点
- （2~4 个薄弱点，如果没有足够数据则标注「数据不足」）

## 错题本分析
### 高频错误知识点
列出用户最容易出错的知识点及错误频次。

### 未掌握题目类型
总结用户反复失败的题目类型和模式。

### 已掌握进展
列出用户已掌握的题目/知识点，肯定用户进步。

### 下一步复习建议
基于错题本数据的具体复习建议。

## 证据依据
引用最近练习、AI 分析和错题本记录中的具体现象。

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

    # ── Attempt / Error Notebook Data ──
    all_attempts = (
        db.query(models.CodeChallengeAttempt)
        .filter(models.CodeChallengeAttempt.username == user.username)
        .order_by(models.CodeChallengeAttempt.created_at.desc())
        .all()
    )
    total_attempts = len(all_attempts)
    failed_count = sum(1 for a in all_attempts if a.status == "failed")
    partial_count = sum(1 for a in all_attempts if a.status == "partial")
    pass_count = sum(1 for a in all_attempts if a.status == "probable_pass")
    unknown_count = total_attempts - failed_count - partial_count - pass_count
    mastered_count = sum(1 for a in all_attempts if (a.mastered or 0) == 1)
    unmastered_count = total_attempts - mastered_count
    unmastered_failed = sum(
        1 for a in all_attempts
        if (a.mastered or 0) == 0 and a.status in ("failed", "partial")
    )

    # Weak points from attempts (unmastered, failed/partial only)
    weak_points_map: dict[str, dict] = {}
    for a in all_attempts:
        if (a.mastered or 0) == 1:
            continue
        if a.status not in ("failed", "partial"):
            continue
        challenge = (
            db.query(models.CodeChallenge)
            .filter(models.CodeChallenge.id == a.challenge_id)
            .first()
        )
        kp = (challenge.knowledge_point or "").strip() if challenge else ""
        if not kp:
            kp = "(未指定知识点)"
        if kp not in weak_points_map:
            weak_points_map[kp] = {"knowledge_point": kp, "failed_count": 0, "partial_count": 0, "challenge_titles": [], "ai_feedback_summaries": []}
        if a.status == "failed":
            weak_points_map[kp]["failed_count"] += 1
        else:
            weak_points_map[kp]["partial_count"] += 1
        if challenge and challenge.title and challenge.title not in weak_points_map[kp]["challenge_titles"]:
            weak_points_map[kp]["challenge_titles"].append(challenge.title)
        if a.ai_feedback:
            lines = [l.strip() for l in a.ai_feedback.split("\n") if l.strip() and not l.startswith("#")]
            if lines:
                summary = lines[0][:80]
                if summary not in weak_points_map[kp]["ai_feedback_summaries"]:
                    weak_points_map[kp]["ai_feedback_summaries"].append(summary[:80])

    sorted_weak = sorted(
        weak_points_map.items(),
        key=lambda x: x[1]["failed_count"] + x[1]["partial_count"],
        reverse=True,
    )

    # Recent attempts summary (max 8)
    attempt_summaries = []
    for a in all_attempts[:8]:
        challenge_title = ""
        if a.challenge_id:
            ch = db.query(models.CodeChallenge).filter(models.CodeChallenge.id == a.challenge_id).first()
            if ch:
                challenge_title = ch.title
        feedback_preview = ""
        if a.ai_feedback:
            lines = [l.strip() for l in a.ai_feedback.split("\n") if l.strip() and not l.startswith("#")]
            if lines:
                feedback_preview = lines[0][:100] + ("..." if len(lines[0]) > 100 else "")
        mastered_tag = " [已掌握]" if (a.mastered or 0) == 1 else ""
        attempt_summaries.append(
            f"- [{a.status or '未知'}] {challenge_title or f'提交#{a.id}'} ({a.language or '未知'}){mastered_tag} | {feedback_preview}"
        )

    # High-frequency weak knowledge points
    kp_lines = []
    for kp, counts in sorted_weak[:6]:
        titles = counts.get("challenge_titles", [])[:3]
        feedbacks = counts.get("ai_feedback_summaries", [])[:2]
        parts = [f"- {kp}：失败 {counts['failed_count']} 次、部分通过 {counts['partial_count']} 次"]
        if titles:
            parts.append(f"  相关题目：{'、'.join(titles)}")
        if feedbacks:
            parts.append(f"  判定摘要：{'；'.join(feedbacks)}")
        kp_lines.append("\n".join(parts))

    error_book_summary = f"""## 错题本数据

总提交记录：{total_attempts}
提交结果分布：大概率不通过 {failed_count} 次、可能部分通过 {partial_count} 次、大概率通过 {pass_count} 次{f'、无法判定 {unknown_count} 次' if unknown_count > 0 else ''}
未掌握错题：{unmastered_failed} 条（需重点复习）
已掌握：{mastered_count} 条

### 高频薄弱知识点（未掌握 + 失败/部分通过）
{chr(10).join(kp_lines) if kp_lines else '暂无数据'}

### 最近提交记录（最近 {len(attempt_summaries)} 条）
{chr(10).join(attempt_summaries) if attempt_summaries else '暂无记录'}"""

    progress_summary = f"""## 用户编程数据汇总

总练习数：{len(all_sessions)}（AI 出题：{challenge_count}，自由练习：{normal_count}）
各语言分布：{lang_counts}
{course_id and f"当前课程：{course_id}" or "未指定课程"}

### 最近练习列表（最近 {len(recent_sessions)} 条）
{chr(10).join(session_summaries)}

### 最近 AI 分析记录（最近 {len(message_summaries)} 条）
{chr(10).join(message_summaries) if message_summaries else '暂无 AI 分析记录'}

### 最近 AI 出题记录（最近 {len(challenges)} 条）
{chr(10).join(challenge_summaries) if challenge_summaries else '暂无 AI 出题记录'}

{error_book_summary}"""

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

    # Attempt statistics
    attempt_query = db.query(models.CodeChallengeAttempt).filter(
        models.CodeChallengeAttempt.username == user.username,
    )
    if normalized_course_id:
        challenge_ids = [
            s.challenge_id for s in sessions
            if getattr(s, "challenge_id", None)
        ]
        if challenge_ids:
            attempt_query = attempt_query.filter(
                models.CodeChallengeAttempt.challenge_id.in_(challenge_ids)
            )

    all_attempts = attempt_query.order_by(models.CodeChallengeAttempt.created_at.desc()).all()

    total_attempts = len(all_attempts)
    failed_attempts = sum(1 for a in all_attempts if a.status == "failed")
    partial_attempts = sum(1 for a in all_attempts if a.status == "partial")
    probable_pass_attempts = sum(1 for a in all_attempts if a.status == "probable_pass")
    mastered_attempts = sum(1 for a in all_attempts if (a.mastered or 0) == 1)
    unmastered_attempts = total_attempts - mastered_attempts

    # Weak points from attempts: aggregate by knowledge_point for mastered=0 failed/partial
    weak_points_map: dict[str, dict] = {}
    for a in all_attempts:
        if (a.mastered or 0) == 1:
            continue  # mastered entries are not weak points
        if a.status not in ("failed", "partial"):
            continue
        challenge = (
            db.query(models.CodeChallenge)
            .filter(models.CodeChallenge.id == a.challenge_id)
            .first()
        )
        kp = (challenge.knowledge_point or "").strip() if challenge else ""
        if not kp:
            kp = "(未指定知识点)"
        if kp not in weak_points_map:
            weak_points_map[kp] = {"knowledge_point": kp, "failed_count": 0, "partial_count": 0, "unmastered_count": 0}
        entry = weak_points_map[kp]
        if a.status == "failed":
            entry["failed_count"] += 1
        elif a.status == "partial":
            entry["partial_count"] += 1
        entry["unmastered_count"] += 1

    weak_points_from_attempts = sorted(
        weak_points_map.values(),
        key=lambda x: x["unmastered_count"],
        reverse=True,
    )[:8]

    return {
        "total": len(sessions),
        "language_counts": language_counts,
        "recent_updated_at": latest.updated_at if latest else None,
        "recent_title": latest.title if latest else None,
        "recent_language": latest.language if latest else None,
        "total_attempts": total_attempts,
        "failed_attempts": failed_attempts,
        "partial_attempts": partial_attempts,
        "probable_pass_attempts": probable_pass_attempts,
        "mastered_attempts": mastered_attempts,
        "unmastered_attempts": unmastered_attempts,
        "weak_points_from_attempts": weak_points_from_attempts,
    }


@app.put("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    req: RenameConversationRequest,
    username: str,
    subject_key: str = "",
    exam_subject: str = "",
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)

    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    if len(title) > 50:
        title = title[:50]

    normalized_exam_subject = normalize_exam_subject_key(exam_subject, subject_key)
    if normalized_exam_subject:
        existing_conversation = (
            db.query(models.ChatSession)
            .filter(
                models.ChatSession.id == conversation_id,
                models.ChatSession.user_id == user.id,
            )
            .first()
        )
        if not existing_conversation or normalize_exam_subject_key(existing_conversation.exam_subject) != normalized_exam_subject:
            raise HTTPException(status_code=404, detail="Chat session not found for this subject")

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
        models.LearningTask.order_index.asc(),
        models.LearningTask.created_at.desc(),
    ).all()
    # Bulk-fetch knowledge point titles
    kp_ids = [getattr(t, "knowledge_point_id", None) for t in tasks if getattr(t, "knowledge_point_id", None)]
    kp_map: dict[int, str] = {}
    if kp_ids:
        kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(kp_ids)).all()
        for kp in kps:
            kp_map[kp.id] = kp.title
    material_ids = [getattr(t, "related_material_id", None) for t in tasks if getattr(t, "related_material_id", None)]
    # Also collect material IDs from metadata
    metadata_material_ids = set()
    for t in tasks:
        raw_meta = getattr(t, "task_metadata", None)
        if raw_meta:
            try:
                meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
                mids = meta.get("related_material_ids", []) if isinstance(meta, dict) else []
                for mid in mids:
                    try:
                        metadata_material_ids.add(int(mid))
                    except Exception:
                        pass
            except Exception:
                pass
    all_material_ids = set(mid for mid in material_ids if mid)
    all_material_ids.update(metadata_material_ids)
    material_map: dict[int, models.StudyMaterial] = {}
    material_title_map: dict[int, str] = {}
    if all_material_ids:
        materials = db.query(models.StudyMaterial).filter(
            models.StudyMaterial.id.in_(list(all_material_ids)),
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.is_deleted == False,
        ).all()
        material_map = {m.id: m for m in materials}
        material_title_map = {m.id: m.original_filename for m in materials}
    # Build per-task material titles from metadata
    task_material_titles = {}
    for t in tasks:
        titles = []
        raw_meta = getattr(t, "task_metadata", None)
        if raw_meta:
            try:
                meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
                mids = meta.get("related_material_ids", []) if isinstance(meta, dict) else []
                for mid in mids:
                    try:
                        title = material_title_map.get(int(mid))
                        if title:
                            titles.append(title)
                    except Exception:
                        pass
            except Exception:
                pass
        task_material_titles[t.id] = titles
    return {
        "tasks": [
            serialize_learning_task(
                t,
                knowledge_point_title=kp_map.get(getattr(t, "knowledge_point_id", None)),
                related_material=material_map.get(getattr(t, "related_material_id", None)),
                related_material_titles=task_material_titles.get(t.id, []),
            )
            for t in tasks
        ]
    }


@app.post("/learning/tasks")
def create_learning_task(req: schemas.LearningTaskCreate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    task_type = (req.task_type or "").strip()
    if not task_type:
        task_type = "custom"
    task_type = task_type[:50]
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
    normalized_course = normalize_subject(req.course_id, default="") or None
    order_query = db.query(func.coalesce(func.max(models.LearningTask.order_index), -1)).filter(
        models.LearningTask.username == user.username,
    )
    if normalized_course:
        order_query = order_query.filter(models.LearningTask.course_id == normalized_course)
    else:
        order_query = order_query.filter(models.LearningTask.course_id.is_(None))
    max_order = order_query.scalar() or -1
    task = models.LearningTask(
        username=user.username,
        course_id=normalized_course,
        title=title[:255],
        description=(req.description or "").strip() or None,
        task_type=task_type,
        status=status,
        source=source,
        priority=priority,
        order_index=max_order + 1,
        due_date=parse_optional_datetime(req.due_date),
        related_session_id=req.related_session_id,
        related_challenge_id=req.related_challenge_id,
        related_material_id=req.related_material_id if req.related_material_id and req.related_material_id > 0 else None,
        knowledge_point_id=req.knowledge_point_id if req.knowledge_point_id and req.knowledge_point_id > 0 else None,
        knowledge_point_text=(req.knowledge_point_text or "").strip() or None,
        related_question_id=req.related_question_id,
        completed_at=now if status == "done" else None,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"task": serialize_learning_task(task)}


@app.put("/learning/tasks/reorder")
def reorder_learning_tasks_v2(req: dict, db: Session = Depends(get_db)):
    username = str(req.get("username", "")).strip()
    course_id = normalize_subject(str(req.get("course_id", "") or ""), default="")
    task_ids = req.get("task_ids", [])
    if not username or not isinstance(task_ids, list) or len(task_ids) == 0:
        raise HTTPException(status_code=400, detail="请求参数无效")
    user = get_user_by_username(username, db)
    normalized_ids = [int(task_id) for task_id in task_ids if task_id]
    if len(normalized_ids) != len(task_ids):
        raise HTTPException(status_code=400, detail="任务 ID 无效")
    query = db.query(models.LearningTask).filter(
        models.LearningTask.id.in_(normalized_ids),
        models.LearningTask.username == user.username,
    )
    if course_id:
        query = query.filter(models.LearningTask.course_id == course_id)
    existing = query.all()
    existing_ids = {task.id for task in existing}
    if existing_ids != set(normalized_ids):
        raise HTTPException(status_code=403, detail="无权排序这些任务")
    for index, task_id in enumerate(normalized_ids):
        db.query(models.LearningTask).filter(models.LearningTask.id == task_id).update(
            {"order_index": index, "updated_at": utc_now()}, synchronize_session=False
        )
    db.commit()
    return {"success": True}


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
        task.task_type = (new_type or "custom")[:50]
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
        task.due_date = parse_optional_datetime(req.due_date) if (req.due_date or "").strip() else None
    if req.knowledge_point_id is not None:
        task.knowledge_point_id = req.knowledge_point_id if req.knowledge_point_id > 0 else None
    if req.knowledge_point_text is not None:
        task.knowledge_point_text = (req.knowledge_point_text or "").strip() or None
    if req.related_material_id is not None:
        task.related_material_id = req.related_material_id if req.related_material_id > 0 else None
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

    knowledge_point_title = None
    if task.knowledge_point_id:
        kp = db.query(models.KnowledgePoint).filter(
            models.KnowledgePoint.id == task.knowledge_point_id,
            models.KnowledgePoint.username == user.username,
        ).first()
        knowledge_point_title = kp.title if kp else None
    related_material = None
    if task.related_material_id:
        related_material = db.query(models.StudyMaterial).filter(
            models.StudyMaterial.id == task.related_material_id,
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.is_deleted == False,
        ).first()

    return {"task": serialize_learning_task(task, knowledge_point_title=knowledge_point_title, related_material=related_material)}


@app.post("/learning/tasks/reorder")
def reorder_learning_tasks(req: dict, db: Session = Depends(get_db)):
    """Reorder tasks by updating order_index for each task."""
    username = str(req.get("username", "")).strip()
    items = req.get("items", [])
    if not username or not isinstance(items, list) or len(items) == 0:
        raise HTTPException(status_code=400, detail="请求参数无效")
    user = get_user_by_username(username, db)
    task_ids = [int(item.get("id", 0)) for item in items if isinstance(item, dict) and item.get("id")]
    if not task_ids:
        raise HTTPException(status_code=400, detail="未提供有效的任务ID")
    existing = (
        db.query(models.LearningTask)
        .filter(
            models.LearningTask.id.in_(task_ids),
            models.LearningTask.username == user.username,
        )
        .all()
    )
    existing_ids = {t.id for t in existing}
    for item in items:
        tid = int(item.get("id", 0))
        if tid not in existing_ids:
            continue
        order = int(item.get("order_index", 0))
        db.query(models.LearningTask).filter(models.LearningTask.id == tid).update(
            {"order_index": order, "updated_at": utc_now()}, synchronize_session=False
        )
    db.commit()
    return {"success": True}


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

    now = utc_now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timedelta(days=6)
    heatmap_start = today - timedelta(days=41)
    done_statuses = {"done", "completed", "finished"}

    def as_aware(value):
        if not value:
            return None
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            value = parsed
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def day_key(value):
        dt = as_aware(value)
        return dt.date().isoformat() if dt else ""

    def safe_int(value, default=0):
        try:
            if value is None:
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    def safe_float(value, default=0.0):
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def clamp_percent(value):
        return max(0, min(100, round(safe_float(value), 1)))

    def parse_json(value):
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def normalize_title(value):
        text = (value or "").strip()
        if not text or text in {"测试", "test", "未命名知识点", "未知知识点", "无"}:
            return ""
        return text

    def course_name(course_id):
        return course_id or ""

    def add_activity(
        activities,
        activity_type,
        title,
        created_at,
        *,
        subtitle="",
        course_id="",
        knowledge_point_id=None,
        material_id=None,
        target_page="",
        target_params=None,
        study_minutes=0,
        completed_tasks=0,
        practice_count=0,
        ai_question_count=0,
    ):
        dt = as_aware(created_at)
        clean_title = (title or "").strip()
        if not dt or not clean_title:
            return
        activities.append({
            "id": f"{activity_type}-{len(activities) + 1}",
            "type": activity_type,
            "title": clean_title,
            "subtitle": subtitle or "",
            "course_id": course_id or "",
            "course_name": course_name(course_id),
            "knowledge_point_id": knowledge_point_id,
            "material_id": material_id,
            "created_at": serialize_datetime(dt),
            "target_page": target_page,
            "target_params": target_params or {},
            "_dt": dt,
            "_study_minutes": max(0, safe_int(study_minutes)),
            "_completed_tasks": max(0, safe_int(completed_tasks)),
            "_practice_count": max(0, safe_int(practice_count)),
            "_ai_question_count": max(0, safe_int(ai_question_count)),
        })

    materials = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.username == user.username,
        models.StudyMaterial.is_deleted.is_(False),
    ).all()
    knowledge_points = db.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == user.username,
    ).all()
    progress_rows = db.query(models.UserKnowledgeProgress).filter(
        models.UserKnowledgeProgress.username == user.username,
    ).all()
    progress_events = db.query(models.KnowledgeProgressEvent).filter(
        models.KnowledgeProgressEvent.username == user.username,
    ).all()
    tasks = db.query(models.LearningTask).filter(
        models.LearningTask.username == user.username,
    ).all()
    records = db.query(models.LearningRecord).filter(
        models.LearningRecord.user_id == user.id,
        models.LearningRecord.is_deleted.is_(False),
    ).all()
    questions = db.query(models.Question).filter(
        models.Question.username == user.username,
    ).all()
    attempts = db.query(models.QuestionAttempt).filter(
        models.QuestionAttempt.username == user.username,
    ).all()
    code_sessions = db.query(models.CodeSession).filter(
        models.CodeSession.username == user.username,
    ).all()
    code_attempts = db.query(models.CodeChallengeAttempt).filter(
        models.CodeChallengeAttempt.username == user.username,
    ).all()
    code_challenges = db.query(models.CodeChallenge).filter(
        models.CodeChallenge.username == user.username,
    ).all()
    reports = db.query(models.LearningReport).filter(
        models.LearningReport.username == user.username,
    ).all()
    chat_rows = (
        db.query(models.ChatMessage, models.ChatSession)
        .join(models.ChatSession, models.ChatMessage.session_id == models.ChatSession.id)
        .filter(models.ChatMessage.user_id == user.id)
        .all()
    )

    kp_by_id = {kp.id: kp for kp in knowledge_points}
    course_ids = set()
    for item in materials:
        if item.subject:
            course_ids.add(item.subject)
    for item in knowledge_points:
        if item.course_id:
            course_ids.add(item.course_id)
    for item in progress_rows:
        if item.course_id:
            course_ids.add(item.course_id)
    for item in tasks:
        if item.course_id:
            course_ids.add(item.course_id)
    for item in questions:
        if item.course_id:
            course_ids.add(item.course_id)
    for item in attempts:
        if item.course_id:
            course_ids.add(item.course_id)
    for item in code_sessions:
        if item.course_id:
            course_ids.add(item.course_id)
    for item in code_challenges:
        if item.course_id:
            course_ids.add(item.course_id)
    for item in reports:
        if item.course_id:
            course_ids.add(item.course_id)
    for _, session in chat_rows:
        cid = normalize_subject(session.subject or session.course or "", default="")
        if cid:
            course_ids.add(cid)

    practice_total = 0
    practice_correct = 0
    practice_minutes = 0
    practice_by_course = defaultdict(lambda: {"total": 0, "correct": 0, "count": 0, "minutes": 0})
    wrong_by_kp = defaultdict(int)
    attempts_by_kp = defaultdict(int)
    activities = []

    for record in records:
        tags = parse_json(record.tags)
        duration_seconds = safe_int(tags.get("duration_seconds"))
        minutes = round(duration_seconds / 60) if duration_seconds else safe_int(tags.get("duration_minutes") or tags.get("minutes"))
        if minutes:
            practice_minutes += minutes
        if record.record_type == "practice":
            total = safe_int(tags.get("total_questions", tags.get("total", 0)))
            graded = safe_int(tags.get("graded_questions", total))
            correct = safe_int(tags.get("correct", 0))
            if graded > 0:
                practice_total += graded
                practice_correct += min(correct, graded)
            cid = record.subject or ""
            practice_by_course[cid]["total"] += graded
            practice_by_course[cid]["correct"] += min(correct, graded)
            practice_by_course[cid]["count"] += 1
            practice_by_course[cid]["minutes"] += minutes
            add_activity(
                activities,
                "practice",
                record.question or "完成练习",
                record.created_at,
                subtitle=f"完成 {total} 题" if total else "练习记录",
                course_id=cid,
                target_page="practiceCenter",
                target_params={"courseId": cid},
                study_minutes=minutes,
                practice_count=1,
            )
        elif minutes:
            add_activity(
                activities,
                "learning_record",
                record.question or "保存学习记录",
                record.created_at,
                subtitle="学习记录",
                course_id=record.subject or "",
                target_page="records",
                target_params={"recordId": record.id},
                study_minutes=minutes,
            )

    for attempt in attempts:
        result = (attempt.self_result or "").lower()
        is_graded = result in {"correct", "incorrect", "wrong", "right", "partial"}
        if is_graded:
            practice_total += 1
            if result in {"correct", "right"}:
                practice_correct += 1
            else:
                if attempt.knowledge_point_id:
                    wrong_by_kp[attempt.knowledge_point_id] += 1
            if attempt.knowledge_point_id:
                attempts_by_kp[attempt.knowledge_point_id] += 1
            cid = attempt.course_id or ""
            practice_by_course[cid]["total"] += 1
            practice_by_course[cid]["correct"] += 1 if result in {"correct", "right"} else 0
            practice_by_course[cid]["count"] += 1
        add_activity(
            activities,
            "question_attempt",
            "完成练习作答",
            attempt.created_at,
            subtitle="正确" if result in {"correct", "right"} else ("待复盘" if is_graded else "已作答"),
            course_id=attempt.course_id or "",
            knowledge_point_id=attempt.knowledge_point_id,
            target_page="practiceCenter",
            target_params={"courseId": attempt.course_id or "", "knowledgePointId": attempt.knowledge_point_id},
            practice_count=1,
        )

    completed_tasks = 0
    pending_tasks = 0
    for task in tasks:
        status = (task.status or "").lower()
        is_done = status in done_statuses
        completed_tasks += 1 if is_done else 0
        pending_tasks += 0 if is_done else 1
        activity_date = task.completed_at or task.updated_at or task.created_at
        add_activity(
            activities,
            "task_done" if is_done else "task_created",
            task.title,
            activity_date,
            subtitle="已完成任务" if is_done else "学习任务",
            course_id=task.course_id or "",
            knowledge_point_id=task.knowledge_point_id,
            target_page="taskCenter",
            target_params={"taskId": task.id, "courseId": task.course_id or ""},
            completed_tasks=1 if is_done else 0,
        )

    ai_question_count = 0
    for message, session in chat_rows:
        if message.role == "user":
            ai_question_count += 1
            cid = normalize_subject(message.subject if hasattr(message, "subject") else "", default="")
            if not cid:
                cid = normalize_subject(session.subject or session.course or "", default="")
            add_activity(
                activities,
                "chat",
                "AI 问答",
                message.created_at,
                subtitle=(message.content or "")[:40],
                course_id=cid,
                target_page="chat",
                target_params={"sessionId": message.session_id, "courseId": cid},
                ai_question_count=1,
            )

    for material in materials:
        add_activity(
            activities,
            "material_uploaded",
            material.original_filename,
            material.created_at,
            subtitle="上传资料",
            course_id=material.subject or "",
            material_id=material.id,
            target_page="workspaceMaterials",
            target_params={"materialId": material.id, "courseId": material.subject or ""},
        )

    for event in progress_events:
        kp = kp_by_id.get(event.knowledge_point_id)
        title = normalize_title(kp.title if kp else "")
        if not title:
            continue
        add_activity(
            activities,
            "knowledge_progress",
            title,
            event.created_at,
            subtitle=event.reason or event.event_type or "知识点学习",
            course_id=event.course_id or (kp.course_id if kp else ""),
            knowledge_point_id=event.knowledge_point_id,
            target_page="knowledgeLearning",
            target_params={"knowledgePointId": event.knowledge_point_id, "courseId": event.course_id or ""},
        )

    for session in code_sessions:
        add_activity(
            activities,
            "code_session",
            session.title,
            session.created_at,
            subtitle=session.language or "编程练习",
            course_id=session.course_id or "",
            target_page="codeStudio",
            target_params={"sessionId": session.id, "courseId": session.course_id or ""},
        )

    for attempt in code_attempts:
        title = "提交编程练习"
        challenge = next((c for c in code_challenges if c.id == attempt.challenge_id), None)
        if challenge:
            title = challenge.title
        add_activity(
            activities,
            "code_attempt",
            title,
            attempt.created_at,
            subtitle=attempt.status or "编程提交",
            course_id=challenge.course_id if challenge else "",
            target_page="codeStudio",
            target_params={"challengeId": attempt.challenge_id, "sessionId": attempt.session_id},
        )

    for report in reports:
        add_activity(
            activities,
            "report",
            report.title,
            report.created_at,
            subtitle="生成学习报告",
            course_id=report.course_id or "",
            target_page="learningReportCenter",
            target_params={"reportId": report.id, "courseId": report.course_id or ""},
        )

    trend_map = {}
    for index in range(7):
        day = week_start + timedelta(days=index)
        trend_map[day.date().isoformat()] = {
            "date": day.date().isoformat(),
            "study_minutes": 0,
            "completed_tasks": 0,
            "practice_count": 0,
            "ai_question_count": 0,
        }
    heatmap_map = {}
    for index in range(42):
        day = heatmap_start + timedelta(days=index)
        heatmap_map[day.date().isoformat()] = {
            "date": day.date().isoformat(),
            "activity_count": 0,
            "study_minutes": 0,
            "level": 0,
        }
    for activity in activities:
        key = day_key(activity["_dt"])
        if key in trend_map:
            trend_map[key]["study_minutes"] += activity["_study_minutes"]
            trend_map[key]["completed_tasks"] += activity["_completed_tasks"]
            trend_map[key]["practice_count"] += activity["_practice_count"]
            trend_map[key]["ai_question_count"] += activity["_ai_question_count"]
        if key in heatmap_map:
            heatmap_map[key]["activity_count"] += 1
            heatmap_map[key]["study_minutes"] += activity["_study_minutes"]
    for item in heatmap_map.values():
        count = item["activity_count"]
        item["level"] = 0 if count == 0 else 1 if count <= 2 else 2 if count <= 5 else 3 if count <= 9 else 4

    total_study_minutes = sum(a["_study_minutes"] for a in activities)
    week_study_minutes = sum(item["study_minutes"] for item in trend_map.values())
    active_dates = {day_key(a["_dt"]) for a in activities if as_aware(a["_dt"]) and as_aware(a["_dt"]) >= week_start}
    all_activity_dates = sorted({day_key(a["_dt"]) for a in activities if day_key(a["_dt"])}, reverse=True)
    streak_days = 0
    cursor = today.date()
    date_set = set(all_activity_dates)
    while cursor.isoformat() in date_set:
        streak_days += 1
        cursor -= timedelta(days=1)
    best_streak_days = 0
    current_streak = 0
    previous = None
    for key in sorted(date_set):
        current_date = date.fromisoformat(key)
        if previous and (current_date - previous).days == 1:
            current_streak += 1
        else:
            current_streak = 1
        best_streak_days = max(best_streak_days, current_streak)
        previous = current_date

    practice_accuracy = round(practice_correct / practice_total * 100, 1) if practice_total else 0
    completed_reports_count = len(reports)

    course_summaries = []
    for cid in sorted(course_ids):
        cid_progress = [p for p in progress_rows if p.course_id == cid]
        cid_scores = [safe_int(p.mastery_score) for p in cid_progress if p.mastery_score is not None]
        cid_attempts = [a for a in attempts if (a.course_id or "") == cid]
        cid_practice = practice_by_course[cid]
        cid_practice_total = cid_practice["total"]
        cid_practice_correct = cid_practice["correct"]
        avg_mastery = round(sum(cid_scores) / len(cid_scores), 1) if cid_scores else 0
        if not cid_scores and cid_practice_total:
            avg_mastery = round(cid_practice_correct / cid_practice_total * 100, 1)
        cid_activity_dates = [
            a["_dt"] for a in activities
            if a.get("course_id") == cid and a.get("_dt")
        ]
        weak_count = sum(1 for p in cid_progress if safe_int(p.mastery_score, 100) < 70)
        course_summaries.append({
            "course_id": cid,
            "course_name": course_name(cid),
            "study_minutes": cid_practice["minutes"],
            "task_count": len([t for t in tasks if (t.course_id or "") == cid]),
            "completed_task_count": len([t for t in tasks if (t.course_id or "") == cid and (t.status or "").lower() in done_statuses]),
            "practice_count": cid_practice["count"] + len(cid_attempts),
            "practice_accuracy": round(cid_practice_correct / cid_practice_total * 100, 1) if cid_practice_total else 0,
            "average_mastery": avg_mastery,
            "weak_point_count": weak_count,
            "material_count": len([m for m in materials if (m.subject or "") == cid]),
            "knowledge_point_count": len([kp for kp in knowledge_points if (kp.course_id or "") == cid]),
            "last_activity_at": serialize_datetime(max(cid_activity_dates)) if cid_activity_dates else None,
        })

    weak_candidates = []
    for progress in progress_rows:
        kp = kp_by_id.get(progress.knowledge_point_id)
        title = normalize_title(kp.title if kp else "")
        if not title:
            continue
        mastery = clamp_percent(progress.mastery_score if progress.mastery_score is not None else 0)
        if mastery < 70 or (progress.status or "") in {"not_started", "learning", "reviewing"}:
            weak_candidates.append({
                "knowledge_point_id": progress.knowledge_point_id,
                "knowledge_point_name": title,
                "title": title,
                "course_id": progress.course_id or (kp.course_id if kp else ""),
                "course_name": course_name(progress.course_id or (kp.course_id if kp else "")),
                "mastery": mastery,
                "mastery_score": mastery,
                "practice_count": safe_int(progress.practice_count),
                "wrong_count": wrong_by_kp.get(progress.knowledge_point_id, 0),
                "reason": "掌握度低" if mastery < 70 else "仍在学习中",
                "source": "user_knowledge_progress",
            })
    for kp_id, wrong_count in wrong_by_kp.items():
        kp = kp_by_id.get(kp_id)
        title = normalize_title(kp.title if kp else "")
        if not title or any(item["knowledge_point_id"] == kp_id for item in weak_candidates):
            continue
        total = attempts_by_kp.get(kp_id, wrong_count)
        error_rate = round(wrong_count / total * 100, 1) if total else 0
        if error_rate >= 40:
            weak_candidates.append({
                "knowledge_point_id": kp_id,
                "knowledge_point_name": title,
                "title": title,
                "course_id": kp.course_id if kp else "",
                "course_name": course_name(kp.course_id if kp else ""),
                "mastery": max(0, 100 - error_rate),
                "mastery_score": max(0, 100 - error_rate),
                "practice_count": total,
                "wrong_count": wrong_count,
                "reason": "错题较多",
                "source": "question_attempts",
            })
    weak_points = sorted(
        weak_candidates,
        key=lambda item: (safe_float(item["mastery"], 100), -safe_int(item["wrong_count"])),
    )[:5]

    parsed_learning_goals = []
    if user.learning_goals:
        try:
            parsed = json.loads(user.learning_goals)
            parsed_learning_goals = parsed if isinstance(parsed, list) else []
        except Exception:
            parsed_learning_goals = []
    goals_configured = False
    goals = {
        "configured": goals_configured,
        "source": "profile_learning_goals" if parsed_learning_goals else "",
        "learning_goals": parsed_learning_goals,
        "study_minutes_goal": None,
        "task_goal": None,
        "practice_accuracy_goal": None,
        "ai_question_goal": None,
        "reference_study_minutes_goal": 300,
        "reference_task_goal": 5,
        "reference_practice_accuracy_goal": 80,
        "reference_ai_question_goal": 10,
        "current_study_minutes": week_study_minutes,
        "current_completed_tasks": sum(item["completed_tasks"] for item in trend_map.values()),
        "current_practice_accuracy": practice_accuracy,
        "current_ai_questions": sum(item["ai_question_count"] for item in trend_map.values()),
    }

    recommendations = []
    def add_recommendation(rec_id, title, reason, action_text, target_page, priority=50, target_params=None):
        if any(item["id"] == rec_id for item in recommendations):
            return
        recommendations.append({
            "id": rec_id,
            "title": title,
            "reason": reason,
            "action_text": action_text,
            "target_page": target_page,
            "target_params": target_params or {},
            "priority": priority,
        })

    if weak_points:
        top = weak_points[0]
        add_recommendation(
            "weak-point-review",
            f"优先复习：{top['knowledge_point_name']}",
            top["reason"],
            "去知识点学习",
            "knowledgeLearning",
            10,
            {"courseId": top["course_id"], "knowledgePointId": top["knowledge_point_id"]},
        )
    if practice_total and practice_accuracy < 70:
        add_recommendation("practice-low-accuracy", "练习正确率偏低", f"当前正确率 {practice_accuracy}%", "去专项练习", "practiceCenter", 20)
    elif practice_total == 0:
        add_recommendation("start-practice", "完成一次练习建立基线", "暂无真实练习记录", "去练习中心", "practiceCenter", 25)
    if len(active_dates) < 3:
        add_recommendation("keep-active", "保持连续学习", f"本周活跃 {len(active_dates)} 天", "查看学习任务", "taskCenter", 30)
    if pending_tasks >= 3:
        add_recommendation("pending-tasks", "处理待完成任务", f"还有 {pending_tasks} 个待完成任务", "去任务中心", "taskCenter", 15)
    low_course = next((c for c in sorted(course_summaries, key=lambda x: x["average_mastery"]) if c["average_mastery"] and c["average_mastery"] < 70), None)
    if low_course:
        add_recommendation("low-course-mastery", f"加强 {low_course['course_name']} 掌握度", f"平均掌握度 {low_course['average_mastery']}%", "去课程工作台", "dashboard", 35, {"courseId": low_course["course_id"]})
    if len(materials) >= 3 and ai_question_count == 0:
        add_recommendation("ask-with-materials", "用资料库开始 AI 问答", "已有资料但暂无 AI 提问记录", "去 AI 问答", "chat", 40)
    if not activities:
        add_recommendation("first-activity", "先建立第一条学习数据", "暂无学习活动", "上传资料", "workspaceMaterials", 5)

    activities.sort(key=lambda item: item["_dt"], reverse=True)
    recent_activities = []
    for item in activities[:12]:
        clean = {k: v for k, v in item.items() if not k.startswith("_")}
        recent_activities.append(clean)

    overview = {
        "total_study_minutes": total_study_minutes,
        "week_study_minutes": week_study_minutes,
        "active_days_this_week": len(active_dates),
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "practice_total": practice_total,
        "practice_correct": practice_correct,
        "practice_accuracy": practice_accuracy,
        "ai_question_count": ai_question_count,
        "streak_days": streak_days,
        "best_streak_days": best_streak_days,
        "uploaded_material_count": len(materials),
        "completed_reports_count": completed_reports_count,
        "course_count": len(course_ids),
        "knowledge_point_count": len(knowledge_points),
    }

    return {
        "overview": overview,
        "trend": list(trend_map.values()),
        "course_summaries": course_summaries,
        "weak_points": weak_points,
        "heatmap": list(heatmap_map.values()),
        "recent_activities": recent_activities,
        "goals": goals,
        "recommendations": sorted(recommendations, key=lambda item: item["priority"])[:5],
    }


@app.get("/learning/report")
def get_learning_report(
    username: str,
    start: str = "",
    end: str = "",
    db: Session = Depends(get_db),
):
    dashboard = get_learning_dashboard(username=username, db=db)
    overview = dashboard.get("overview") or {}
    weak_points = dashboard.get("weak_points") or []
    recommendations = dashboard.get("recommendations") or []

    def _format_minutes(minutes):
        total = max(0, int(minutes or 0))
        hours = total // 60
        mins = total % 60
        if hours <= 0:
            return f"{mins} 分钟"
        if mins == 0:
            return f"{hours} h"
        return f"{hours} h {mins} m"

    def _format_percent(value):
        try:
            return f"{round(float(value), 1)}%"
        except (TypeError, ValueError):
            return "--"

    weak_titles = [
        (item.get("knowledge_point_name") or item.get("title") or "").strip()
        for item in weak_points[:5]
        if isinstance(item, dict)
    ]
    weak_titles = [title for title in weak_titles if title]

    strengths = []
    if overview.get("completed_tasks"):
        strengths.append(f"已完成 {overview.get('completed_tasks')} 个学习任务")
    if overview.get("practice_accuracy", 0) >= 70:
        strengths.append(f"练习正确率达到 {_format_percent(overview.get('practice_accuracy'))}")
    if overview.get("active_days_this_week"):
        strengths.append(f"本阶段保持 {overview.get('active_days_this_week')} 天学习记录")
    if not strengths:
        strengths.append("已有学习记录可用于持续分析")

    suggestions = []
    for item in recommendations[:5]:
        if isinstance(item, dict):
            title = (item.get("title") or item.get("action_text") or "").strip()
            if title:
                suggestions.append(title)
        elif item:
            suggestions.append(str(item))
    if not suggestions:
        suggestions = [f"优先复习「{title}」并完成对应练习" for title in weak_titles[:3]]
    if not suggestions:
        suggestions = ["继续完成学习任务，并保持错题复盘节奏"]

    total_minutes = overview.get("total_study_minutes", 0)
    accuracy = overview.get("practice_accuracy", 0)
    summary_text = (
        f"所选时间范围内累计学习 {_format_minutes(total_minutes)}，"
        f"练习正确率为 {_format_percent(accuracy)}。"
        f"{' 当前需要重点关注：' + '、'.join(weak_titles[:3]) + '。' if weak_titles else ' 当前暂无明显薄弱知识点。'}"
    )

    return {
        "start": start,
        "end": end,
        "summary": {
            "overall_summary": summary_text,
            "strengths": strengths,
            "weaknesses": weak_titles or ["当前范围内暂无明确薄弱知识点"],
            "suggestions": suggestions,
        },
        "metrics": {
            "study_time": _format_minutes(total_minutes),
            "knowledge_points": str(overview.get("completed_tasks", "--")),
            "accuracy": _format_percent(accuracy),
            "study_days": f"{overview.get('active_days_this_week', '--')} 天",
        },
        "trend": dashboard.get("trend") or [],
        "errors": [
            {
                "knowledge_point": item.get("knowledge_point_name") or item.get("title") or "",
                "count": item.get("wrong_count") or item.get("practice_count") or 0,
                "mastery": item.get("mastery") or item.get("mastery_score"),
            }
            for item in weak_points
            if isinstance(item, dict)
        ],
    }


@app.post("/learning-report/ai-generate")
def ai_generate_learning_report(req: schemas.LearningReportAiGenerateRequest, db: Session = Depends(get_db)):
    """Generate an AI-powered learning report for the given time range.
    Returns structured data; frontend handles display formatting."""
    user = get_user_by_username(req.username, db)
    range_type = (req.range_type or "7d").strip()
    now = utc_now()

    # Resolve date range
    if range_type == "custom" and req.start_date and req.end_date:
        start = datetime.fromisoformat(str(req.start_date).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(req.end_date).replace("Z", "+00:00"))
    elif range_type == "15d":
        start = now - timedelta(days=15)
        end = now
    elif range_type == "30d":
        start = now - timedelta(days=30)
        end = now
    elif range_type == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    else:  # 7d default
        start = now - timedelta(days=7)
        end = now

    range_label = {
        "7d": "近7天", "15d": "近15天", "30d": "近30天",
        "month": "本月", "custom": "自定义",
    }.get(range_type, "近7天")

    # Build real data using existing function
    report_data = build_learning_report_data(
        user.username, "weekly", "", start, end, db
    )

    # ── Structured metrics (numbers only, no display strings) ──
    study_minutes = int(report_data["practice"].get("duration_minutes", 0))
    mastered_count = int(report_data["knowledge"].get("mastered", 0))
    total_kp = int(report_data["knowledge"].get("total_points", 0))
    practice_acc = float(report_data["practice"].get("practice_accuracy", 0))
    practice_sessions = int(report_data["practice"].get("sessions", 0))

    # Count actual study days from practice records in the date range
    actual_study_days = 0
    if practice_sessions > 0:
        # approximate: count unique days with any activity
        actual_study_days = min(practice_sessions, (end - start).days + 1)

    metrics = {
        "study_minutes": study_minutes,
        "completed_knowledge_count": mastered_count,
        "practice_accuracy": round(practice_acc, 1) if practice_sessions > 0 else None,
        "study_days": actual_study_days,
        "total_knowledge_points": total_kp,
        "practice_sessions": practice_sessions,
    }

    # ── Trend data ──
    trend: list[dict] = []
    # Always build a daily structure; zero values are fine
    from datetime import timedelta as td
    day = start
    while day <= end:
        trend.append({
            "date": day.strftime("%Y-%m-%d"),
            "study_minutes": 0,
            "completed_count": 0,
            "accuracy": None,
        })
        day += td(days=1)

    # ── AI prompt ──
    has_data = study_minutes > 0 or practice_sessions > 0
    weak_titles = [w.get("title", "") for w in (report_data["knowledge"].get("weak_points") or [])[:3]]
    acc_str = f"{practice_acc}%" if practice_sessions > 0 else "暂无练习数据"
    hours = study_minutes // 60
    mins = study_minutes % 60
    time_str = f"{hours}小时{mins}分钟" if study_minutes > 0 else "0分钟（暂无学习时长记录）"

    prompt = f"""时间范围：{range_label}（{start.strftime('%Y-%m-%d')} 至 {end.strftime('%Y-%m-%d')}）

【学习数据统计】
- 学习时长：{time_str}
- 知识点：已记录 {mastered_count}/{total_kp} 个
- 练习次数：{practice_sessions} 次
- 练习正确率：{acc_str}
- 薄弱知识点：{json.dumps(weak_titles, ensure_ascii=False) if weak_titles else '暂无'}

【重要提示——必须严格遵守】
- 如果学习时长为0且练习次数为0，优势中严禁写"知识点掌握完整"或"无薄弱环节"。
  应写"已完成的知识点记录较完整，但由于缺少学习时长和练习数据，掌握程度需要通过练习验证。"
  薄弱中应写"缺少学习时长记录"和"缺少练习数据，暂时无法判断真实掌握程度"。
- 如果练习正确率为"暂无练习数据"，优势中严禁写任何关于正确率的结论。
- 所有建议必须具体可执行，禁止空泛的"保持学习"。
- 禁止编造不存在的数据。

请输出 JSON（不要加```json标记）：
{{"summary":"整体总结(200字内)","strengths":["优势1","优势2"],"weaknesses":["薄弱1","薄弱2"],"suggestions":["具体建议1","具体建议2","具体建议3"]}}"""

    # Try AI generation
    ai_summary = None
    try:
        raw = call_deepseek([
            {"role": "system", "content": "你是一个专业学习教练。只输出JSON，不要加```json标记。严格按照提示中的约束进行分析。"},
            {"role": "user", "content": prompt},
        ], timeout_seconds=60)
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1] if "```" in text[3:] else text[3:]
            if text.startswith("json"):
                text = text[4:]
        ai_summary = json.loads(text)
        record_ai_usage(user.username, "learning_report_ai_generate", db,
                        estimated_tokens=estimate_tokens_from_text(prompt) + estimate_tokens_from_text(raw),
                        status="success")
    except Exception:
        # Fallback with data-aware logic
        if not has_data:
            ai_summary = {
                "summary": f"在{range_label}内尚未记录学习时长和练习数据。已有{mastered_count}个知识点的基础记录，但掌握程度仍需通过练习验证。建议先开始学习并完成练习来积累分析数据。",
                "strengths": ["已完成的知识点记录较完整"] if mastered_count > 0 else ["具备继续分析的基础数据"],
                "weaknesses": ["缺少学习时长记录", "缺少练习数据，暂时无法判断真实掌握程度"],
                "suggestions": ["先完成一次基础练习，建立正确率基线", "每天至少记录15分钟学习时长", "优先复盘已完成知识点对应的题目"],
            }
        else:
            acc_text = f"练习正确率{practice_acc}%" if practice_sessions > 0 else "暂无练习数据"
            ai_summary = {
                "summary": f"在{range_label}内学习{time_str}，完成{mastered_count}个知识点，{acc_text}。{'继续保持节奏！' if practice_acc >= 70 else '建议加强练习提升正确率。'}",
                "strengths": [f"已掌握 {mastered_count} 个知识点"] if mastered_count > 0 else ["暂无足够数据判断优势"],
                "weaknesses": weak_titles or (["缺少练习数据"] if practice_sessions == 0 else ["暂无明确薄弱环节"]),
                "suggestions": [
                    "每天保留20分钟复盘错题" if practice_sessions > 0 else "先完成一次基础练习建立基线",
                    "优先学习当前未掌握的知识点",
                    "定期回顾已掌握内容避免遗忘",
                ],
            }

    return {
        "range": {
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "label": range_label,
        },
        "metrics": metrics,
        "ai_report": ai_summary or {},
        "trend": trend,
        "errors": [
            {"knowledge_point": w.get("title", ""), "count": 0, "mastery": w.get("score", 0) or 0}
            for w in (report_data["knowledge"].get("weak_points") or [])
        ],
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

    user_grade = (user.grade or "").strip()
    user_major = (user.major or "").strip()
    profile_context = ""
    if user_grade or user_major:
        parts = []
        if user_grade:
            parts.append(f"年级：{user_grade}")
        if user_major:
            parts.append(f"专业：{user_major}")
        profile_context = "用户画像：" + "，".join(parts) + "\n"

    user_prompt = f"""课程：{course_name or '未指定'}
编程语言：{language or '未指定'}
{profile_context}
{chr(10) + "薄弱知识点参考：" + chr(10) + weak_points_context + chr(10) if weak_points_context else ""}
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
                "status": normalize_knowledge_status(progress_map[p.id].status) if p.id in progress_map else "not_started",
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

    # Dedup by node_key first (stable identity) — if a point with this node_key
    # already exists for this user+course, return it instead of creating a duplicate.
    if req.node_key:
        existing = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.username == user.username,
                models.KnowledgePoint.course_id == normalized_course,
                models.KnowledgePoint.node_key == req.node_key,
            )
            .first()
        )
        if existing:
            progress = (
                db.query(models.UserKnowledgeProgress)
                .filter(
                    models.UserKnowledgeProgress.username == user.username,
                    models.UserKnowledgeProgress.knowledge_point_id == existing.id,
                )
                .first()
            )
            return {
                "success": True,
                "knowledge_point": serialize_knowledge_point(
                    existing,
                    progress_info={"mastery_score": progress.mastery_score if progress else 0,
                                   "status": progress.status if progress else "not_started"},
                ),
            }
    else:
        legacy_existing = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.username == user.username,
                models.KnowledgePoint.course_id == normalized_course,
                models.KnowledgePoint.title == req.title,
                models.KnowledgePoint.parent_id == req.parent_id,
            )
            .first()
        )
        if legacy_existing:
            progress = (
                db.query(models.UserKnowledgeProgress)
                .filter(
                    models.UserKnowledgeProgress.username == user.username,
                    models.UserKnowledgeProgress.knowledge_point_id == legacy_existing.id,
                )
                .first()
            )
            return {
                "success": True,
                "knowledge_point": serialize_knowledge_point(
                    legacy_existing,
                    progress_info={
                        "mastery_score": progress.mastery_score if progress else 0,
                        "status": progress.status if progress else "not_started",
                    },
                ),
            }

    parent_id = req.parent_id
    if not parent_id and req.parent_node_key:
        parent_by_node = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.username == user.username,
                models.KnowledgePoint.course_id == normalized_course,
                models.KnowledgePoint.node_key == req.parent_node_key,
            )
            .first()
        )
        if parent_by_node:
            parent_id = parent_by_node.id

    if parent_id:
        parent = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.id == parent_id,
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
        if parent_id:
            parent = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id == parent_id).first()
            level = (parent.level or 0) + 1 if parent else 0
        else:
            level = 0

    point = models.KnowledgePoint(
        username=user.username,
        course_id=normalized_course,
        parent_id=parent_id,
        title=req.title,
        description=req.description or "",
        order_index=req.order_index if req.order_index is not None else max_order,
        level=level,
        node_key=req.node_key,
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
    if req.node_key is not None:
        point.node_key = req.node_key
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


def normalize_knowledge_status(status: str | None) -> str:
    """Map any legacy status into the 3-state model: not_started | learning | mastered."""
    if not status:
        return "not_started"
    s = status.strip()
    # Direct 3-state values
    if s in ("not_started", "learning", "mastered"):
        return s
    # Chinese 3-state
    if s in ("未开始",):
        return "not_started"
    if s in ("学习中",):
        return "learning"
    if s in ("已掌握",):
        return "mastered"
    # Legacy → learning
    if s in ("need_review", "需要复习", "待复习", "review", "reviewing", "needs_review",
             "not_understood", "还没理解", "weak", "薄弱", "confused",
             "in_progress", "studying"):
        return "learning"
    # Legacy → mastered
    if s in ("done", "completed"):
        return "mastered"
    # Legacy → not_started
    if s in ("later", "稍后再学", "postponed"):
        return "not_started"
    # Unknown → not_started
    return "not_started"


KNOWLEDGE_MAP_SEED_DIR = BASE_DIR / "seed_data" / "knowledge_maps"


def _knowledge_map_seed_path(course_id: str) -> Path:
    safe_course_id = re.sub(r"[^a-zA-Z0-9_-]", "", course_id or "")
    return KNOWLEDGE_MAP_SEED_DIR / f"{safe_course_id}.json"


def _count_knowledge_map_points(nodes: list[dict], include_chapters: bool = False) -> int:
    total = 0
    for node in nodes:
        children = node.get("children") or []
        # Only count leaf nodes (terminal knowledge points)
        if children:
            total += _count_knowledge_map_points(children, True)
        elif include_chapters or "chapter_no" not in node:
            total += 1
    return total


def _is_leaf_node(node: dict) -> bool:
    """A leaf node has no children — it is a terminal knowledge point."""
    return not bool(node.get("children"))


def _collect_leaf_statuses(node: dict) -> dict[str, int]:
    """Recursively collect leaf-node status counts under this node."""
    counts = {"not_started": 0, "learning": 0, "mastered": 0, "review_due": 0}
    children = node.get("children") or []
    if not children:
        # This is a leaf — count itself
        status = str(node.get("status") or "not_started").strip()
        if status in counts:
            counts[status] = 1
        return counts
    for child in children:
        child_counts = _collect_leaf_statuses(child)
        for key in counts:
            counts[key] += child_counts.get(key, 0)
    return counts


def _compute_aggregate_status(node: dict) -> str:
    """Derive a parent node's status from all descendant leaves."""
    children = node.get("children") or []
    if not children:
        return str(node.get("status") or "not_started").strip()
    leaf_counts = _collect_leaf_statuses(node)
    if leaf_counts.get("review_due", 0) > 0:
        return "review_due"
    if leaf_counts.get("learning", 0) > 0:
        return "learning"
    total_leaves = sum(leaf_counts.values())
    if total_leaves > 0 and leaf_counts.get("mastered", 0) == total_leaves:
        return "mastered"
    return "not_started"


def _normalize_map_node_status(status: str | None) -> str:
    normalized = normalize_knowledge_status(status)
    if normalized in {"mastered", "learning", "not_started"}:
        return normalized
    if str(status or "").strip() == "review_due":
        return "review_due"
    return "not_started"


def _build_knowledge_map_index(nodes: list[dict], index: dict[str, dict] | None = None) -> dict[str, dict]:
    index = index or {}
    for node in nodes or []:
        code = str(node.get("code") or "").strip()
        if code:
            index[code] = node
        _build_knowledge_map_index(node.get("children") or [], index)
    return index


def _build_enriched_map_index(nodes: list[dict]) -> dict[str, dict]:
    """Build a flat code→node index that also includes auto-generated
    codes for leaf nodes that have no explicit code in the seed data."""
    index: dict[str, dict] = {}

    def walk(items: list[dict], path_prefix: str = ""):
        for i, node in enumerate(items or [], start=1):
            node_path = f"{path_prefix}.{i}" if path_prefix else str(i)
            code = str(node.get("code") or "").strip()
            if not code and not (node.get("children") or []):
                code = f"_leaf:{node_path}"
            if code:
                index[code] = node
            walk(node.get("children") or [], node_path)

    walk(nodes)
    return index


def _display_map_progress_status(progress: models.UserKnowledgeProgress | None, now: datetime | None = None) -> str:
    if not progress:
        return "not_started"
    status = _normalize_map_node_status(progress.status)
    due_at = getattr(progress, "review_due_at", None)
    if status == "mastered" and due_at:
        now = now or utc_now()
        if now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        if due_at.tzinfo is not None:
            due_at = due_at.astimezone(timezone.utc).replace(tzinfo=None)
        if now >= due_at:
            return "review_due"
    return status


def _serialize_map_progress(progress: models.UserKnowledgeProgress | None, display_status: str | None = None) -> dict:
    if not progress:
        return {}
    return {
        "id": progress.id,
        "course_id": progress.course_id,
        "knowledge_point_code": getattr(progress, "knowledge_point_code", "") or "",
        "knowledge_point_title": getattr(progress, "knowledge_point_title", "") or "",
        "status": display_status or _display_map_progress_status(progress),
        "stored_status": progress.status or "not_started",
        "learned_at": serialize_datetime(getattr(progress, "learned_at", None)) if getattr(progress, "learned_at", None) else None,
        "review_due_at": serialize_datetime(getattr(progress, "review_due_at", None)) if getattr(progress, "review_due_at", None) else None,
        "review_interval_days": getattr(progress, "review_interval_days", None) or 7,
        "updated_at": serialize_datetime(progress.updated_at) if progress.updated_at else None,
    }


def _attach_knowledge_map_status(nodes: list[dict], progress_by_code: dict[str, models.UserKnowledgeProgress], path_prefix: str = "") -> list[dict]:
    result = []
    now = utc_now()
    for index, node in enumerate(nodes, start=1):
        item = dict(node)
        node_path = f"{path_prefix}.{index}" if path_prefix else str(index)
        item["id"] = item.get("id") or f"seed:{node_path}"
        code = str(item.get("code") or "").strip()

        # Recursively process children first
        children = _attach_knowledge_map_status(item.get("children") or [], progress_by_code, node_path)
        item["children"] = children
        item["is_leaf"] = len(children) == 0

        # Leaf nodes without a code get a stable derived code so the PATCH
        # endpoint can identify them and persist user progress.
        if not code and item["is_leaf"]:
            code = f"_leaf:{node_path}"
            item["code"] = code

        progress = progress_by_code.get(code)
        display_status = _display_map_progress_status(progress, now)
        item["status"] = display_status
        item["stored_status"] = progress.status if progress else "not_started"
        if progress:
            item["progress"] = _serialize_map_progress(progress, display_status)
            item["learned_at"] = item["progress"].get("learned_at")
            item["review_due_at"] = item["progress"].get("review_due_at")
            item["review_interval_days"] = item["progress"].get("review_interval_days")

        # For parent nodes: compute aggregate status from descendant leaves
        if not item["is_leaf"]:
            aggregate_status = _compute_aggregate_status(item)
            item["status"] = aggregate_status
            item["status_counts"] = _collect_leaf_statuses(item)
        else:
            item["status_counts"] = _collect_leaf_statuses(item)  # single leaf = itself

        result.append(item)
    return result


def _get_review_setting(db: Session, username: str, course_id: str) -> models.UserKnowledgeReviewSetting | None:
    return (
        db.query(models.UserKnowledgeReviewSetting)
        .filter(
            models.UserKnowledgeReviewSetting.username == username,
            models.UserKnowledgeReviewSetting.course_id == course_id,
        )
        .first()
    )


def _get_review_interval_days(db: Session, username: str, course_id: str) -> int:
    setting = _get_review_setting(db, username, course_id)
    value = setting.review_interval_days if setting else 7
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 7
    return min(max(value, 1), 365)


@app.get("/knowledge-map")
def get_knowledge_map(course_id: str, username: str = "", db: Session = Depends(get_db)):
    normalized_course = (course_id or "").strip()
    if not normalized_course:
        raise HTTPException(status_code=400, detail="course_id 不能为空")

    seed_path = _knowledge_map_seed_path(normalized_course)
    if not seed_path.exists():
        raise HTTPException(status_code=404, detail="知识脉络数据不存在")

    try:
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="知识脉络数据格式错误")

    progress_by_code: dict[str, models.UserKnowledgeProgress] = {}
    review_interval_days = 7
    if username:
        user = get_user_by_username(username, db)
        review_interval_days = _get_review_interval_days(db, user.username, normalized_course)
        progress_rows = (
            db.query(models.UserKnowledgeProgress)
            .filter(
                models.UserKnowledgeProgress.username == user.username,
                models.UserKnowledgeProgress.course_id == normalized_course,
            )
            .all()
        )
        progress_by_code = {
            str(getattr(progress, "knowledge_point_code", "") or "").strip(): progress
            for progress in progress_rows
            if str(getattr(progress, "knowledge_point_code", "") or "").strip()
        }

    chapters = _attach_knowledge_map_status(payload.get("chapters") or [], progress_by_code)
    total = _count_knowledge_map_points(chapters)
    mastered = 0
    learning = 0
    review_due = 0
    not_started = 0

    def tally(nodes: list[dict]):
        nonlocal mastered, learning, review_due, not_started
        for node in nodes:
            children = node.get("children") or []
            if children:
                tally(children)
            else:
                # Only count leaf nodes (terminal knowledge points)
                status = str(node.get("status") or "not_started").strip()
                if status == "mastered":
                    mastered += 1
                elif status == "learning":
                    learning += 1
                elif status == "review_due":
                    review_due += 1
                elif status == "not_started":
                    not_started += 1

    for chapter in chapters:
        tally(chapter.get("children") or [])

    return {
        "course_id": payload.get("course_id") or normalized_course,
        "course_name": payload.get("course_name") or "11408 数据结构",
        "source": payload.get("source") or "",
        "stats": {
            "total": total,
            "mastered": mastered,
            "learning": learning,
            "review_due": review_due,
            "not_started": not_started,
        },
        "review_interval_days": review_interval_days,
        "chapters": chapters,
    }


@app.patch("/knowledge-map/progress")
def update_knowledge_map_progress(req: schemas.KnowledgeMapProgressUpdate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    course_id = (req.course_id or "").strip()
    code = (req.knowledge_point_code or "").strip()
    title = (req.knowledge_point_title or "").strip()
    next_status = (req.status or "").strip()
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id is required")
    if next_status == "review_due":
        raise HTTPException(status_code=400, detail="review_due is system-generated and cannot be set manually")
    if next_status not in {"not_started", "learning", "mastered"}:
        raise HTTPException(status_code=400, detail="invalid status")

    seed_path = _knowledge_map_seed_path(course_id)
    if not seed_path.exists():
        raise HTTPException(status_code=404, detail="knowledge map not found")
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    # Build index that includes auto-generated codes for leaf nodes without codes
    node_index = _build_enriched_map_index(payload.get("chapters") or [])
    node = node_index.get(code)
    if not node:
        raise HTTPException(status_code=404, detail="knowledge point is not in this course map")
    # Only leaf nodes (no children) can be manually updated
    if not _is_leaf_node(node):
        raise HTTPException(status_code=400, detail="Only leaf knowledge points can be manually updated")
    canonical_title = str(node.get("title") or title or "").strip()

    progress = (
        db.query(models.UserKnowledgeProgress)
        .filter(
            models.UserKnowledgeProgress.username == user.username,
            models.UserKnowledgeProgress.course_id == course_id,
            models.UserKnowledgeProgress.knowledge_point_code == code,
        )
        .first()
    )
    now = utc_now()
    if not progress:
        progress = models.UserKnowledgeProgress(
            username=user.username,
            course_id=course_id,
            knowledge_point_id=0,
            knowledge_point_code=code,
            knowledge_point_title=canonical_title,
            mastery_score=0,
            status="not_started",
            practice_count=0,
            task_count=0,
            created_at=now,
        )
        db.add(progress)

    progress.knowledge_point_code = code
    progress.knowledge_point_title = canonical_title
    progress.status = next_status
    progress.updated_at = now
    progress.last_studied_at = now

    if next_status == "not_started":
        progress.mastery_score = 0
        progress.learned_at = None
        progress.review_due_at = None
        progress.review_interval_days = None
    elif next_status == "learning":
        progress.mastery_score = progress.mastery_score if progress.mastery_score is not None else 30
        progress.learned_at = None
        progress.review_due_at = None
        progress.review_interval_days = None
    elif next_status == "mastered":
        interval_days = _get_review_interval_days(db, user.username, course_id)
        progress.mastery_score = 100
        progress.learned_at = now
        progress.review_interval_days = interval_days
        progress.review_due_at = now + timedelta(days=interval_days)

    db.commit()
    db.refresh(progress)
    display_status = _display_map_progress_status(progress)
    return {
        "success": True,
        "progress": _serialize_map_progress(progress, display_status),
        "node": {
            "code": code,
            "title": canonical_title,
            "status": display_status,
            "stored_status": progress.status,
            "learned_at": serialize_datetime(progress.learned_at) if progress.learned_at else None,
            "review_due_at": serialize_datetime(progress.review_due_at) if progress.review_due_at else None,
            "review_interval_days": progress.review_interval_days or _get_review_interval_days(db, user.username, course_id),
        },
    }


@app.get("/knowledge-map/review-settings")
def get_knowledge_map_review_settings(course_id: str, username: str = "", db: Session = Depends(get_db)):
    course_id = (course_id or "").strip()
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id is required")
    if not _knowledge_map_seed_path(course_id).exists():
        raise HTTPException(status_code=404, detail="knowledge map not found")
    user = get_user_by_username(username, db) if username else None
    interval = _get_review_interval_days(db, user.username, course_id) if user else 7
    return {"course_id": course_id, "review_interval_days": interval}


@app.patch("/knowledge-map/review-settings")
def update_knowledge_map_review_settings(req: schemas.KnowledgeMapReviewSettingsUpdate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    course_id = (req.course_id or "").strip()
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id is required")
    if not _knowledge_map_seed_path(course_id).exists():
        raise HTTPException(status_code=404, detail="knowledge map not found")
    try:
        interval = int(req.review_interval_days)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="review_interval_days must be an integer")
    if interval < 1 or interval > 365:
        raise HTTPException(status_code=400, detail="review_interval_days must be between 1 and 365")

    now = utc_now()
    setting = _get_review_setting(db, user.username, course_id)
    if not setting:
        setting = models.UserKnowledgeReviewSetting(
            username=user.username,
            course_id=course_id,
            review_interval_days=interval,
            created_at=now,
        )
        db.add(setting)
    setting.review_interval_days = interval
    setting.updated_at = now
    db.commit()
    return {"success": True, "course_id": course_id, "review_interval_days": interval}


# ── 11408 Study Plan (Knowledge-Point-Based) ────────────────

def _get_exam_study_plan_settings(username: str, subject_key: str, db: Session):
    return db.query(models.ExamStudyPlanSetting).filter(
        models.ExamStudyPlanSetting.username == username,
        models.ExamStudyPlanSetting.subject_key == subject_key,
    ).first()


def _get_exam_study_plan_chapter_practices(username: str, subject_key: str, db: Session):
    rows = db.query(models.ExamStudyPlanChapterPractice).filter(
        models.ExamStudyPlanChapterPractice.username == username,
        models.ExamStudyPlanChapterPractice.subject_key == subject_key,
    ).all()
    return {row.section_code: row for row in rows}


def _build_study_plan_tree(chapters: list[dict], chapter_practice_by_code: dict) -> list[dict]:
    """Build the study plan tree from already-enriched knowledge map chapters.

    Expects chapters to already have user progress attached via _attach_knowledge_map_status.
    """
    result = []
    for chapter_raw in chapters:
        chapter = dict(chapter_raw)
        chapter_children = []
        for section_raw in (chapter.get("children") or []):
            section = dict(section_raw)

            # Leaf statuses are already computed on the enriched nodes
            leaf_statuses = _collect_leaf_statuses(section)
            total_leaves = sum(leaf_statuses.values())
            mastered = leaf_statuses.get("mastered", 0)
            learning_count = leaf_statuses.get("learning", 0)

            # Chapter practice status
            section_code = str(section.get("code") or "").strip()
            cp_record = chapter_practice_by_code.get(section_code)
            cp_completed = cp_record.completed if cp_record else False

            # Section status computation
            all_leaves_done = (total_leaves > 0 and mastered == total_leaves)
            if all_leaves_done and cp_completed:
                section_status = "completed"
            elif mastered > 0 or learning_count > 0 or cp_completed:
                section_status = "learning"
            else:
                section_status = "not_started"
            section["leaf_stats"] = {
                "total": total_leaves,
                "mastered": mastered,
                "learning": learning_count,
                "not_started": leaf_statuses.get("not_started", 0),
                "review_due": leaf_statuses.get("review_due", 0),
            }
            section["chapter_practice_completed"] = cp_completed
            section["section_status"] = section_status
            section["completion_rate"] = round(mastered / total_leaves * 100) if total_leaves > 0 else 0
            chapter_children.append(section)

        # Chapter-level stats
        all_sections_done = all(
            s.get("section_status") == "completed"
            for s in chapter_children
        )
        chapter_total_leaves = sum(s["leaf_stats"]["total"] for s in chapter_children)
        chapter_mastered = sum(s["leaf_stats"]["mastered"] for s in chapter_children)
        chapter_learning = sum(s["leaf_stats"]["learning"] for s in chapter_children)

        chapter["children"] = chapter_children
        chapter["chapter_completion_rate"] = round(chapter_mastered / chapter_total_leaves * 100) if chapter_total_leaves > 0 else 0
        chapter["chapter_status"] = "completed" if all_sections_done else ("learning" if chapter_mastered > 0 or chapter_learning > 0 else "not_started")
        chapter["section_count"] = len(chapter_children)
        chapter["sections_completed"] = sum(1 for s in chapter_children if s.get("section_status") == "completed")
        result.append(chapter)

    return result


@app.get("/exam/11408/subjects/{subject_key}/study-plan")
def get_exam_subject_study_plan(subject_key: str, username: str = "", db: Session = Depends(get_db)):
    """Get the full study plan for a 11408 subject, including knowledge map,
    user progress, settings, and chapter practice status."""
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")

    username = (username or "").strip()
    course_id = f"{subject_key}_11408"
    subject_name = EXAM_SUBJECT_DIRS[subject_key]

    # Load knowledge map seed data
    seed_path = _knowledge_map_seed_path(course_id)
    if not seed_path.exists():
        raise HTTPException(status_code=404, detail="知识脉络数据不存在")

    try:
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="知识脉络数据格式错误")

    # User progress
    progress_by_code: dict[str, models.UserKnowledgeProgress] = {}
    review_interval_days = 7
    if username:
        user = get_user_by_username(username, db)
        review_interval_days = _get_review_interval_days(db, user.username, course_id)
        progress_rows = (
            db.query(models.UserKnowledgeProgress)
            .filter(
                models.UserKnowledgeProgress.username == user.username,
                models.UserKnowledgeProgress.course_id == course_id,
            )
            .all()
        )
        progress_by_code = {
            str(getattr(p, "knowledge_point_code", "") or "").strip(): p
            for p in progress_rows
            if str(getattr(p, "knowledge_point_code", "") or "").strip()
        }

    # Chapter practice records
    chapter_practice_by_code: dict[str, models.ExamStudyPlanChapterPractice] = {}
    if username:
        chapter_practice_by_code = _get_exam_study_plan_chapter_practices(username, subject_key, db)

    # Plan settings
    plan_settings = None
    if username:
        plan_settings = _get_exam_study_plan_settings(username, subject_key, db)

    # Load stage tasks for this subject
    tasks = []
    if username:
        task_rows = db.query(models.ExamStudyPlanTask).filter(
            models.ExamStudyPlanTask.username == username,
            models.ExamStudyPlanTask.subject_key == subject_key,
        ).order_by(models.ExamStudyPlanTask.created_at.desc()).all()
        tasks = [_serialize_task(t) for t in task_rows]

    # First attach user progress at the ROOT level so all leaf codes
    # are globally scoped and consistent with _build_enriched_map_index
    enriched_chapters = _attach_knowledge_map_status(
        payload.get("chapters") or [], progress_by_code
    )

    # Build study plan tree from already-enriched chapters
    study_plan_tree = _build_study_plan_tree(enriched_chapters, chapter_practice_by_code)

    # Compute overall stats
    total_leaves = sum(
        s["leaf_stats"]["total"]
        for ch in study_plan_tree
        for s in (ch.get("children") or [])
    )
    total_mastered = sum(
        s["leaf_stats"]["mastered"]
        for ch in study_plan_tree
        for s in (ch.get("children") or [])
    )
    total_sections = sum(len(ch.get("children") or []) for ch in study_plan_tree)
    sections_completed = sum(
        1 for ch in study_plan_tree
        for s in (ch.get("children") or [])
        if s.get("section_status") == "completed"
    )
    sections_learning = sum(
        1 for ch in study_plan_tree
        for s in (ch.get("children") or [])
        if s.get("section_status") == "learning"
    )

    overall_progress = round(total_mastered / total_leaves * 100) if total_leaves > 0 else 0
    overall_status = "completed" if sections_completed == total_sections and total_sections > 0 else (
        "learning" if sections_completed > 0 or sections_learning > 0 else "not_started"
    )

    return {
        "course_id": course_id,
        "course_name": payload.get("course_name") or subject_name,
        "subject_key": subject_key,
        "subject_name": subject_name,
        "settings": {
            "learning_goal": plan_settings.learning_goal if plan_settings else "",
            "start_date": plan_settings.start_date if plan_settings else "",
            "daily_hours": plan_settings.daily_hours if plan_settings else "",
            "weekly_days": plan_settings.weekly_days if plan_settings else 5,
            "review_strategy": plan_settings.review_strategy if plan_settings else "sequential",
            "show_completed": plan_settings.show_completed if plan_settings else True,
        },
        "stats": {
            "total_knowledge_points": total_leaves,
            "mastered": total_mastered,
            "total_sections": total_sections,
            "sections_completed": sections_completed,
            "sections_learning": sections_learning,
            "sections_not_started": total_sections - sections_completed - sections_learning,
            "overall_progress": overall_progress,
            "overall_status": overall_status,
        },
        "review_interval_days": review_interval_days,
        "chapters": study_plan_tree,
        "tasks": tasks,
    }


@app.patch("/exam/11408/subjects/{subject_key}/study-plan/settings")
def update_exam_study_plan_settings(
    subject_key: str,
    req: schemas.ExamStudyPlanSettingsUpdate,
    db: Session = Depends(get_db),
):
    """Update study plan settings for a 11408 subject."""
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")

    user = get_user_by_username(req.username, db)
    now = utc_now()

    setting = db.query(models.ExamStudyPlanSetting).filter(
        models.ExamStudyPlanSetting.username == user.username,
        models.ExamStudyPlanSetting.subject_key == subject_key,
    ).first()

    if not setting:
        setting = models.ExamStudyPlanSetting(
            username=user.username,
            subject_key=subject_key,
            created_at=now,
        )
        db.add(setting)

    if req.learning_goal is not None:
        setting.learning_goal = req.learning_goal
    if req.start_date is not None:
        setting.start_date = req.start_date
    if req.daily_hours is not None:
        setting.daily_hours = req.daily_hours
    if req.weekly_days is not None:
        setting.weekly_days = req.weekly_days
    if req.review_strategy is not None:
        setting.review_strategy = req.review_strategy
    if req.show_completed is not None:
        setting.show_completed = req.show_completed

    setting.updated_at = now
    db.commit()
    db.refresh(setting)

    return {
        "success": True,
        "settings": {
            "learning_goal": setting.learning_goal or "",
            "start_date": setting.start_date or "",
            "daily_hours": setting.daily_hours or "",
            "weekly_days": setting.weekly_days or 5,
            "review_strategy": setting.review_strategy or "sequential",
            "show_completed": setting.show_completed if setting.show_completed is not None else True,
        },
    }


@app.patch("/exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{item_code:path}")
def update_exam_study_plan_knowledge_item(
    subject_key: str,
    item_code: str,
    req: schemas.ExamStudyPlanKnowledgeItemUpdate,
    db: Session = Depends(get_db),
):
    """Update a leaf knowledge point status within the study plan.
    Wraps the existing knowledge-map/progress endpoint but validates
    against the 11408 subject context."""
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")

    course_id = f"{subject_key}_11408"

    # Validate status
    valid_statuses = {"not_started", "learning", "mastered"}
    if req.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status: {req.status}")

    user = get_user_by_username(req.username, db)

    seed_path = _knowledge_map_seed_path(course_id)
    if not seed_path.exists():
        raise HTTPException(status_code=404, detail="knowledge map not found")

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    node_index = _build_enriched_map_index(payload.get("chapters") or [])
    node = node_index.get(item_code)
    if not node:
        raise HTTPException(status_code=404, detail="knowledge point is not in this course map")
    if not _is_leaf_node(node):
        raise HTTPException(status_code=400, detail="Only leaf knowledge points can be manually updated")

    canonical_title = str(node.get("title") or req.knowledge_point_title or "").strip()

    progress = (
        db.query(models.UserKnowledgeProgress)
        .filter(
            models.UserKnowledgeProgress.username == user.username,
            models.UserKnowledgeProgress.course_id == course_id,
            models.UserKnowledgeProgress.knowledge_point_code == item_code,
        )
        .first()
    )

    now = utc_now()
    if not progress:
        progress = models.UserKnowledgeProgress(
            username=user.username,
            course_id=course_id,
            knowledge_point_id=0,
            knowledge_point_code=item_code,
            knowledge_point_title=canonical_title,
            mastery_score=0,
            status="not_started",
            practice_count=0,
            task_count=0,
            created_at=now,
        )
        db.add(progress)

    progress.knowledge_point_code = item_code
    progress.knowledge_point_title = canonical_title
    progress.status = req.status
    progress.updated_at = now
    progress.last_studied_at = now

    if req.status == "not_started":
        progress.mastery_score = 0
        progress.learned_at = None
        progress.review_due_at = None
        progress.review_interval_days = None
    elif req.status == "learning":
        progress.mastery_score = progress.mastery_score if progress.mastery_score is not None else 30
        progress.learned_at = None
        progress.review_due_at = None
        progress.review_interval_days = None
    elif req.status == "mastered":
        interval_days = _get_review_interval_days(db, user.username, course_id)
        progress.mastery_score = 100
        progress.learned_at = now
        progress.review_interval_days = interval_days
        progress.review_due_at = now + timedelta(days=interval_days)

    db.commit()
    db.refresh(progress)
    display_status = _display_map_progress_status(progress)

    return {
        "success": True,
        "knowledge_point_code": item_code,
        "knowledge_point_title": canonical_title,
        "status": display_status,
        "stored_status": progress.status,
    }


@app.patch("/exam/11408/subjects/{subject_key}/study-plan/chapter-practice/{node_code:path}")
def update_exam_study_plan_chapter_practice(
    subject_key: str,
    node_code: str,
    req: schemas.ExamStudyPlanChapterPracticeUpdate,
    db: Session = Depends(get_db),
):
    """Update chapter practice completion status for a section (二级知识点)."""
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")

    user = get_user_by_username(req.username, db)
    now = utc_now()

    record = db.query(models.ExamStudyPlanChapterPractice).filter(
        models.ExamStudyPlanChapterPractice.username == user.username,
        models.ExamStudyPlanChapterPractice.subject_key == subject_key,
        models.ExamStudyPlanChapterPractice.section_code == node_code,
    ).first()

    if not record:
        record = models.ExamStudyPlanChapterPractice(
            username=user.username,
            subject_key=subject_key,
            section_code=node_code,
            section_title=req.section_title or "",
            created_at=now,
        )
        db.add(record)

    record.section_title = req.section_title or record.section_title or ""
    record.completed = req.completed
    record.completed_at = now if req.completed else None
    record.updated_at = now

    db.commit()
    db.refresh(record)

    return {
        "success": True,
        "section_code": node_code,
        "completed": record.completed,
        "completed_at": serialize_datetime(record.completed_at) if record.completed_at else None,
    }


@app.get("/exam/11408/study-plan/summary")
def get_exam_study_plan_summary(username: str = "", db: Session = Depends(get_db)):
    """Get a four-subject summary of study plan progress for the 11408 home page."""
    username = (username or "").strip()
    subjects = []

    for subject_key, subject_name in EXAM_SUBJECT_DIRS.items():
        course_id = f"{subject_key}_11408"
        seed_path = _knowledge_map_seed_path(course_id)

        total_sections = 0
        sections_completed = 0
        total_leaves = 0
        mastered_leaves = 0
        learning_leaves = 0

        if seed_path.exists():
            try:
                payload = json.loads(seed_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {"chapters": []}

            raw_chapters = payload.get("chapters") or []

            # Count sections and leaf stats from seed data
            for chapter in raw_chapters:
                for section in (chapter.get("children") or []):
                    total_sections += 1
                    leaf_counts = _collect_leaf_statuses(section)
                    total_leaves += sum(leaf_counts.values())

            if username:
                user = get_user_by_username(username, db)
                # Progress from user_knowledge_progress
                progress_rows = (
                    db.query(models.UserKnowledgeProgress)
                    .filter(
                        models.UserKnowledgeProgress.username == user.username,
                        models.UserKnowledgeProgress.course_id == course_id,
                    )
                    .all()
                )
                for p in progress_rows:
                    status = _display_map_progress_status(p)
                    if status == "mastered":
                        mastered_leaves += 1

        # Determine which sections have chapter practice completed
        sections_completed = 0
        if username:
            cp_rows = db.query(models.ExamStudyPlanChapterPractice).filter(
                models.ExamStudyPlanChapterPractice.username == username,
                models.ExamStudyPlanChapterPractice.subject_key == subject_key,
                models.ExamStudyPlanChapterPractice.completed == True,
            ).all()
            sections_completed = len(cp_rows)

        # Overall progress as percentage
        overall_progress = round(mastered_leaves / total_leaves * 100) if total_leaves > 0 else 0
        is_completed = sections_completed >= total_sections and total_sections > 0 and mastered_leaves >= total_leaves

        subjects.append({
            "subject_key": subject_key,
            "subject_name": subject_name,
            "overall_progress": overall_progress,
            "total_sections": total_sections,
            "sections_completed": sections_completed,
            "total_knowledge_points": total_leaves,
            "mastered_knowledge_points": mastered_leaves,
            "is_completed": is_completed,
        })

    total_all_progress = round(
        sum(s["overall_progress"] for s in subjects) / len(subjects)
    ) if subjects else 0

    return {
        "subjects": subjects,
        "total_progress": total_all_progress,
        "total_subjects_completed": sum(1 for s in subjects if s["is_completed"]),
    }


# ── 11408 Study Plan Tasks ──────────────────────────────


def _compute_task_completion(
    task: "models.ExamStudyPlanTask",
    db: Session,
) -> tuple[str, str, str]:
    """Compute a task's real completion status from knowledge map and chapter practice data.

    Returns (computed_status, completion_reason, action_target).
    """
    username = task.username
    subject_key = task.subject_key
    course_id = f"{subject_key}_11408"
    kp_name = (task.knowledge_point_name or "").strip()
    scope = (task.scope_type or "single").strip()
    task_type = (task.task_type or "knowledge").strip()

    # Load all user progress for this subject
    progress_rows = (
        db.query(models.UserKnowledgeProgress)
        .filter(
            models.UserKnowledgeProgress.username == username,
            models.UserKnowledgeProgress.course_id == course_id,
        )
        .all()
    )
    progress_by_code: dict[str, str] = {}
    for p in progress_rows:
        code = str(getattr(p, "knowledge_point_code", "") or "").strip()
        p_status = _display_map_progress_status(p)
        progress_by_code[code] = p_status

    # Load chapter practice records
    cp_rows = db.query(models.ExamStudyPlanChapterPractice).filter(
        models.ExamStudyPlanChapterPractice.username == username,
        models.ExamStudyPlanChapterPractice.subject_key == subject_key,
    ).all()
    cp_completed_codes = {r.section_code for r in cp_rows if r.completed}

    # Build knowledge map index to resolve scope
    seed_path = _knowledge_map_seed_path(course_id)
    seed_data = {"chapters": []}
    if seed_path.exists():
        try:
            seed_data = json.loads(seed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    chapters = seed_data.get("chapters") or []

    # Use _build_enriched_map_index for globally-consistent leaf codes,
    # then build a section→leaf mapping from the index.
    enriched_index = _build_enriched_map_index(chapters)
    section_leaf_codes: dict[str, list[str]] = {}
    all_leaf_codes: list[str] = []
    section_code_by_title: dict[str, str] = {}

    # Build section titles from seed chapters
    for ch in chapters:
        for sec in (ch.get("children") or []):
            sec_code = str(sec.get("code") or "").strip()
            sec_title = str(sec.get("title") or "").strip()
            if sec_code:
                section_leaf_codes[sec_code] = []
                section_code_by_title[sec_title] = sec_code

    # Assign each leaf code to its section by walking the tree
    def _assign_leaves_to_sections(nodes, parent_sec_code="", path_prefix=""):
        for i, node in enumerate(nodes or [], start=1):
            node_path = f"{path_prefix}.{i}" if path_prefix else str(i)
            code = str(node.get("code") or "").strip()
            children = node.get("children") or []

            # Track the section this node belongs to
            if code:
                if code in section_leaf_codes:
                    parent_sec_code = code
                title = str(node.get("title") or "").strip()
                if title and parent_sec_code:
                    section_code_by_title[title] = parent_sec_code

            if not children:
                # Use the globally-scoped code from enriched_index or generate locally
                leaf_code = code if (code and code in enriched_index) else None
                if not leaf_code:
                    for ek, ev in enriched_index.items():
                        if ev.get("title") == node.get("title") and _is_leaf_node(ev):
                            leaf_code = ek
                            break
                if not leaf_code:
                    leaf_code = code if code else f"_leaf:{node_path}"
                all_leaf_codes.append(leaf_code)
                if parent_sec_code and parent_sec_code in section_leaf_codes:
                    section_leaf_codes[parent_sec_code].append(leaf_code)
            else:
                _assign_leaves_to_sections(children, parent_sec_code, node_path)

    for ch in chapters:
        _assign_leaves_to_sections(ch.get("children") or [], "", "")

    # Determine relevant leaf codes for this task
    relevant_codes: list[str] = []
    if scope == "all" or not kp_name:
        relevant_codes = list(all_leaf_codes)
    else:
        # Match by section title first, then by section code
        matched_code = section_code_by_title.get(kp_name, "")
        if not matched_code:
            matched_code = kp_name  # might be the code itself
        if matched_code in section_leaf_codes:
            relevant_codes = list(section_leaf_codes[matched_code])

    if not relevant_codes:
        # No matching knowledge points — task is effectively pending
        return ("not_started", "等待知识脉络数据加载", "knowledge_map")

    # Collect statuses for relevant leaves
    leaf_statuses = [progress_by_code.get(c, "not_started") for c in relevant_codes]
    total = len(leaf_statuses)
    mastered = sum(1 for s in leaf_statuses if s == "mastered")
    review_due = sum(1 for s in leaf_statuses if s == "review_due")

    if task_type == "knowledge":
        # Knowledge learning: all leaves mastered → completed
        if total > 0 and mastered == total:
            return ("completed", "所有知识点均已掌握", "knowledge_map")
        elif mastered > 0:
            return ("in_progress", f"已掌握 {mastered}/{total} 个知识点，等待知识脉络中标记为已学习", "knowledge_map")
        else:
            return ("not_started", "等待知识脉络中该知识点标记为已学习", "knowledge_map")

    elif task_type == "chapter_practice":
        # Chapter practice: check ExamQuestionDoneRecord for practiced questions
        # Find questions for the relevant knowledge points
        kp_ids = set()
        if scope == "all" or not kp_name:
            # All knowledge points in this subject
            q_rows = db.query(models.ExamQuestionBank).filter(
                models.ExamQuestionBank.subject_key == subject_key,
                models.ExamQuestionBank.source_type == "chapter",
                models.ExamQuestionBank.is_active == True,
            ).all()
        else:
            # Find questions matching this knowledge_point_name or related section codes
            q_rows = db.query(models.ExamQuestionBank).filter(
                models.ExamQuestionBank.subject_key == subject_key,
                models.ExamQuestionBank.source_type == "chapter",
                models.ExamQuestionBank.is_active == True,
            ).all()
            # Filter to matching knowledge points (by name or section code)
            matching_kp_ids = set()
            for sec_code in section_leaf_codes:
                if kp_name in sec_code or sec_code in kp_name:
                    matching_kp_ids.add(sec_code)
            matching_kp_ids.add(kp_name)
            for title, code in section_code_by_title.items():
                if kp_name in title:
                    matching_kp_ids.add(code)
            q_rows = [
                q for q in q_rows
                if (q.knowledge_point_id or "") in matching_kp_ids
                or (q.knowledge_point_name or "") == kp_name
            ]

        if not q_rows:
            return ("not_started", "该知识点暂无章节练习题目", "practice_center")

        # Get done records for these questions
        q_ids = [q.id for q in q_rows]
        done_rows = db.query(models.ExamQuestionDoneRecord).filter(
            models.ExamQuestionDoneRecord.username == username,
            models.ExamQuestionDoneRecord.subject_key == subject_key,
            models.ExamQuestionDoneRecord.practice_type == "chapter",
            models.ExamQuestionDoneRecord.question_bank_id.in_(q_ids),
        ).all()
        done_q_ids = {r.question_bank_id for r in done_rows}

        total_q = len(q_ids)
        practiced_q = sum(1 for qid in q_ids if qid in done_q_ids)

        if total_q > 0 and practiced_q == total_q:
            return ("completed", f"全部 {total_q} 题已练习", "practice_center")
        elif practiced_q > 0:
            return ("in_progress", f"已练习 {practiced_q}/{total_q} 题，前往练习中心继续练习", "practice_center")
        else:
            return ("not_started", f"共 {total_q} 题待练习，前往练习中心开始", "practice_center")

    elif task_type == "review":
        # Stage review: no review_due leaves, all mastered
        if review_due == 0 and total > 0 and mastered == total:
            return ("completed", "该知识点暂无待复习项，全部已掌握", "knowledge_map")
        elif review_due > 0:
            return ("in_progress", f"有 {review_due} 个知识点待复习，前往知识脉络复习", "knowledge_map")
        elif mastered > 0:
            return ("in_progress", f"已掌握 {mastered}/{total}，部分知识点仍需学习", "knowledge_map")
        else:
            return ("not_started", "等待知识脉络中标记学习状态", "knowledge_map")

    return ("not_started", "等待开始", "knowledge_map")


def _serialize_task(task: models.ExamStudyPlanTask, db: Session | None = None) -> dict:
    computed_status, reason, action_target = "not_started", "", "knowledge_map"
    if db is not None:
        computed_status, reason, action_target = _compute_task_completion(task, db)

    return {
        "id": task.id,
        "username": task.username,
        "subject_key": task.subject_key,
        "subject_name": EXAM_SUBJECT_DIRS.get(task.subject_key, task.subject_key),
        "title": task.title,
        "knowledge_point_name": task.knowledge_point_name or task.secondary_knowledge or "",
        "scope_type": task.scope_type or "single",
        "task_type": task.task_type or "knowledge",
        "computed_status": computed_status,
        "completion_reason": reason,
        "action_target": action_target,
        "due_date": task.due_date or "",
        "note": task.note or "",
        "created_at": serialize_datetime(task.created_at) if task.created_at else None,
        "updated_at": serialize_datetime(task.updated_at) if task.updated_at else None,
        # Legacy field for backward compat
        "status": computed_status,
        "primary_knowledge": task.primary_knowledge or "",
        "secondary_knowledge": task.secondary_knowledge or "",
    }


@app.post("/exam/11408/subjects/{subject_key}/study-plan/tasks")
def create_exam_study_plan_task(
    subject_key: str,
    req: schemas.ExamStudyPlanTaskCreate,
    db: Session = Depends(get_db),
):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    if not (req.knowledge_point_name or "").strip() and (req.scope_type or "single") != "all":
        raise HTTPException(status_code=400, detail="knowledge_point_name is required when scope_type is not 'all'")
    user = get_user_by_username(req.username, db)
    now = utc_now()
    kp_name = req.knowledge_point_name or ""
    task = models.ExamStudyPlanTask(
        username=user.username,
        subject_key=subject_key,
        title=req.title,
        knowledge_point_name=kp_name,
        scope_type=req.scope_type or "single",
        task_type=req.task_type or "knowledge",
        status="not_started",
        due_date=req.due_date or "",
        note=req.note or "",
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"success": True, "task": _serialize_task(task, db)}


@app.patch("/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}")
def update_exam_study_plan_task(
    subject_key: str,
    task_id: int,
    req: schemas.ExamStudyPlanTaskUpdate,
    db: Session = Depends(get_db),
):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    user = get_user_by_username(req.username, db)
    task = db.query(models.ExamStudyPlanTask).filter(
        models.ExamStudyPlanTask.id == task_id,
        models.ExamStudyPlanTask.username == user.username,
        models.ExamStudyPlanTask.subject_key == subject_key,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    now = utc_now()
    if req.title is not None:
        task.title = req.title
    if req.knowledge_point_name is not None:
        task.knowledge_point_name = req.knowledge_point_name
    if req.scope_type is not None:
        task.scope_type = req.scope_type
    if req.task_type is not None:
        task.task_type = req.task_type
    if req.due_date is not None:
        task.due_date = req.due_date
    if req.note is not None:
        task.note = req.note
    task.updated_at = now
    db.commit()
    db.refresh(task)
    return {"success": True, "task": _serialize_task(task, db)}


@app.delete("/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}")
def delete_exam_study_plan_task(
    subject_key: str,
    task_id: int,
    username: str = "",
    db: Session = Depends(get_db),
):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    user = get_user_by_username(username, db)
    task = db.query(models.ExamStudyPlanTask).filter(
        models.ExamStudyPlanTask.id == task_id,
        models.ExamStudyPlanTask.username == user.username,
        models.ExamStudyPlanTask.subject_key == subject_key,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"success": True, "deleted_id": task_id}


@app.get("/exam/11408/study-plan/tasks/summary")
def get_exam_study_plan_tasks_summary(username: str = "", db: Session = Depends(get_db)):
    """Get all current-stage tasks across all four 11408 subjects for the home page."""
    username = (username or "").strip()
    if not username:
        return {"tasks": [], "by_subject": {}}
    user = get_user_by_username(username, db)
    tasks = db.query(models.ExamStudyPlanTask).filter(
        models.ExamStudyPlanTask.username == user.username,
    ).order_by(models.ExamStudyPlanTask.created_at.desc()).all()

    task_list = [_serialize_task(t, db) for t in tasks]
    by_subject: dict[str, list] = {}
    for t in task_list:
        sk = t["subject_key"]
        if sk not in by_subject:
            by_subject[sk] = []
        by_subject[sk].append(t)

    return {
        "tasks": task_list,
        "by_subject": by_subject,
        "total": len(task_list),
        "by_status": {
            "not_started": sum(1 for t in task_list if t["computed_status"] == "not_started"),
            "in_progress": sum(1 for t in task_list if t["computed_status"] == "in_progress"),
            "completed": sum(1 for t in task_list if t["computed_status"] == "completed"),
        },
    }


# ── 11408 Subject Dashboard Summary ──────────────────────


@app.get("/exam/11408/subjects/{subject_key}/dashboard-summary")
def get_exam_subject_dashboard_summary(subject_key: str, username: str = "", db: Session = Depends(get_db)):
    """Return a lightweight dashboard summary for the 11408 subject home page."""
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    user = get_user_by_username(username, db) if username else None

    course_id = f"{subject_key}_11408"
    subject_name = EXAM_SUBJECT_DIRS[subject_key]

    # ── 1. Overview ──
    seed_path = _knowledge_map_seed_path(course_id)
    total_chapters = 0
    total_knowledge_points = 0
    learned_percent = 0
    study_minutes = 0

    if seed_path.exists():
        try:
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"chapters": []}
        raw_chapters = payload.get("chapters") or []
        total_chapters = len(raw_chapters)
        total_knowledge_points = _count_knowledge_map_points(raw_chapters)

    if user:
        progress_rows = (
            db.query(models.UserKnowledgeProgress)
            .filter(
                models.UserKnowledgeProgress.username == user.username,
                models.UserKnowledgeProgress.course_id == course_id,
            )
            .all()
        )
        mastered_count = sum(
            1 for p in progress_rows
            if _display_map_progress_status(p) == "mastered"
        )
        learned_percent = round(mastered_count / total_knowledge_points * 100) if total_knowledge_points > 0 else 0

        # Study minutes from practice attempts in this subject
        attempts = db.query(models.ExamPracticeAttempt).filter(
            models.ExamPracticeAttempt.username == user.username,
            models.ExamPracticeAttempt.subject_key == subject_key,
            models.ExamPracticeAttempt.status == "submitted",
        ).all()
        study_minutes = sum(
            _minutes_between(a.started_at, a.submitted_at)
            for a in attempts
            if a.started_at and a.submitted_at
        )

    overview = {
        "total_chapters": total_chapters,
        "total_knowledge_points": total_knowledge_points,
        "learned_percent": learned_percent,
        "study_minutes": study_minutes,
    }

    # ── 2. Today's plan (tasks from study plan, max 3) ──
    today_plan = []
    if user:
        task_rows = db.query(models.ExamStudyPlanTask).filter(
            models.ExamStudyPlanTask.username == user.username,
            models.ExamStudyPlanTask.subject_key == subject_key,
        ).order_by(models.ExamStudyPlanTask.created_at.desc()).limit(3).all()
        today_plan = [
            {
                "id": t.id,
                "title": t.title,
                "knowledge_point_name": t.knowledge_point_name or t.secondary_knowledge or "",
                "task_type": t.task_type or "knowledge",
                "computed_status": _compute_task_completion(t, db)[0] if t.task_type else "not_started",
                "due_date": t.due_date or "",
            }
            for t in task_rows
        ]

    # ── 3. Materials ──
    materials = {
        "lecture_notes": 0,
        "exercises": 0,
        "references": 0,
        "code_examples": 0,
        "total_materials": 0,
    }
    if user:
        course_name = f"11408 {subject_name}"
        mat_rows = db.query(models.StudyMaterial).filter(
            models.StudyMaterial.username.in_([user.username, "system"]),
            models.StudyMaterial.subject == course_name,
            models.StudyMaterial.is_deleted == False,
        ).all()
        for m in mat_rows:
            ft = (m.file_type or "").strip()
            if ft == "lecture" or ft == "courseware":
                materials["lecture_notes"] += 1
            elif ft == "exercise" or ft == "exam":
                materials["exercises"] += 1
            elif ft == "reference" or ft == "reference_metadata":
                materials["references"] += 1
            elif ft == "code" or ft == "example":
                materials["code_examples"] += 1
            else:
                materials["references"] += 1
        materials["total_materials"] = len(mat_rows)

    # ── 4. Quota ──
    quota = {
        "ai_chat": {"used": 0, "limit": 50, "remaining": 50},
        "ai_question": {"used": 0, "limit": 5, "remaining": 5},
        "material_upload": {"used": 0, "limit": 100, "remaining": 100},
    }
    if user:
        track = db.query(models.UserLearningTrack).filter(
            models.UserLearningTrack.user_id == user.id,
            models.UserLearningTrack.track_type == "exam_408",
        ).first()
        pkg = normalize_exam_package(track.package_type) if track else "free"
        pkg_quota = EXAM_PACKAGE_QUOTA.get(pkg, EXAM_PACKAGE_QUOTA["free"])

        # AI usage today — feature names: "chat", "question_generate"
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        ai_today = db.query(models.AiUsageLog).filter(
            models.AiUsageLog.username == user.username,
            models.AiUsageLog.created_at >= today_start,
            models.AiUsageLog.status == "success",
        ).all()

        # AI chat: feature == "chat" (includes all normal chat calls)
        chat_used = sum(1 for a in ai_today if (a.feature or "").strip() == "chat")
        # AI question generation: feature == "question_generate"
        question_used = sum(1 for a in ai_today if (a.feature or "").strip() == "question_generate")

        chat_limit = int(pkg_quota.get("ai_chat_daily_limit", 50))
        q_limit = int(pkg_quota.get("ai_question_daily_limit", 5))

        # Material upload: sum file_size in bytes → MB for today's uploads
        today_uploads = db.query(models.StudyMaterial).filter(
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.is_deleted == False,
            models.StudyMaterial.created_at >= today_start,
        ).all()
        today_bytes = sum(m.file_size or 0 for m in today_uploads)
        material_used_mb = round(today_bytes / (1024 * 1024), 2)

        mat_limit_mb = int(pkg_quota.get("material_upload_limit_mb", 100))

        quota = {
            "ai_chat": {
                "used": chat_used,
                "limit": chat_limit,
                "remaining": max(0, chat_limit - chat_used),
                "unit": "次",
            },
            "ai_question": {
                "used": question_used,
                "limit": q_limit,
                "remaining": max(0, q_limit - question_used),
                "unit": "次",
            },
            "material_upload": {
                "used": material_used_mb,
                "limit": mat_limit_mb,
                "remaining": max(0, mat_limit_mb - material_used_mb),
                "unit": "MB",
            },
        }

    return {
        "subject_key": subject_key,
        "subject_name": subject_name,
        "overview": overview,
        "today_plan": today_plan,
        "materials": materials,
        "quota": quota,
    }


# ── 11408 Past Papers ───────────────────────────────────────

import exam_paper_parser

EXAM_RESOURCES_DIR = BASE_DIR / "exam_resources"
EXAM_11408_DIR = EXAM_RESOURCES_DIR / "11408"

EXAM_SUBJECT_DIRS = {
    "data_structure": "数据结构",
    "computer_organization": "计算机组成原理",
    "operating_system": "操作系统",
    "computer_network": "计算机网络",
}

# Static exam paper images — served via nginx, not FastAPI mount
# (Mount conflicts with route matching on some configurations)
# import exam_paper_parser as _ep
# _exam_static = _ep.STATIC_DIR
# if _exam_static.exists():
#     app.mount("/static/exam_papers", StaticFiles(directory=str(_exam_static)), name="exam_static")

# Past paper images for all 11408 subjects
_PAST_PAPER_IMAGES_DIR = BASE_DIR / "exam_resources" / "11408"

@app.get("/exam/11408/past-paper-images/{subject_key}/{year}/{filename:path}")
def serve_past_paper_image(subject_key: str, year: int, filename: str):
    """Serve past paper question images from exam_resources assets."""
    # Try legacy assets path first (OS format: assets/{year}/{filename})
    img_path = _PAST_PAPER_IMAGES_DIR / subject_key / "past_papers" / "assets" / str(year) / filename
    if not img_path.exists():
        # Try new images path (CN/OS format: images/{filename})
        img_path = BASE_DIR / f"exam_resources/11408/{subject_key}/past_papers/images" / filename
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(img_path))


@app.get("/exam/11408/{subject_key}/past-papers")
def get_exam_past_papers(subject_key: str):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    return exam_paper_parser.get_subject_past_papers(subject_key)


def _minutes_between(start, end) -> int:
    if not start or not end:
        return 0
    try:
        seconds = max(0, (end - start).total_seconds())
        return int(round(seconds / 60))
    except Exception:
        return 0


@app.get("/exam/11408/{subject_key}/practice/stats")
def get_exam_practice_stats(subject_key: str, username: str, db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")

    breakdown = {
        "past_paper": {"total": 0, "completed": 0},
        "chapter": {"total": 0, "completed": 0},
        "ai_generated": {"total": 0, "completed": 0},
        "wrong": {"total": 0, "completed": 0},
        "favorite": {"total": 0, "completed": 0},
    }

    attempts = db.query(models.PastPaperAttempt).filter(
        models.PastPaperAttempt.username == username,
        models.PastPaperAttempt.subject_key == subject_key,
    ).all()
    breakdown["past_paper"]["total"] = len(attempts)
    completed_attempts = [a for a in attempts if (a.status or "").lower() in {"submitted", "completed"}]
    breakdown["past_paper"]["completed"] = len(completed_attempts)

    ai_questions = db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.username == username,
        models.AIGeneratedQuestion.subject_key == subject_key,
    ).count()
    breakdown["ai_generated"]["total"] = ai_questions
    breakdown["ai_generated"]["completed"] = 0

    wrong_questions = db.query(models.PastPaperWrongQuestion).filter(
        models.PastPaperWrongQuestion.username == username,
        models.PastPaperWrongQuestion.subject_key == subject_key,
    ).count()
    breakdown["wrong"]["total"] = wrong_questions
    breakdown["wrong"]["completed"] = 0

    favorite_questions = db.query(models.ExamFavoriteQuestion).filter(
        models.ExamFavoriteQuestion.username == username,
        models.ExamFavoriteQuestion.subject_key == subject_key,
    ).count()
    breakdown["favorite"]["total"] = favorite_questions
    breakdown["favorite"]["completed"] = 0

    total_score = 0.0
    max_score = 0.0
    correct_choices = 0
    total_choices = 0
    for attempt in completed_attempts:
        if attempt.total_score is not None and attempt.max_score:
            total_score += float(attempt.total_score or 0)
            max_score += float(attempt.max_score or 0)
        elif attempt.result_json:
            try:
                result = json.loads(attempt.result_json)
                correct_choices += int(result.get("choice_correct") or 0)
                total_choices += int(result.get("choice_total") or 0)
            except Exception:
                pass

    if max_score > 0:
        accuracy = round(total_score / max_score * 100)
    elif total_choices > 0:
        accuracy = round(correct_choices / total_choices * 100)
    else:
        accuracy = 0  # TODO: include chapter/wrong/favorite practice accuracy once those attempts exist.

    duration_minutes = sum(_minutes_between(a.started_at, a.submitted_at) for a in completed_attempts)
    total_practices = sum(item["total"] for item in breakdown.values())
    completed_practices = breakdown["past_paper"]["completed"]

    return {
        "subject_key": subject_key,
        "subject_name": EXAM_SUBJECT_DIRS.get(subject_key, subject_key),
        "total_practices": total_practices,
        "completed_practices": completed_practices,
        "accuracy": accuracy,
        "total_duration_minutes": duration_minutes,
        "source_breakdown": breakdown,
    }


@app.get("/exam/11408/{subject_key}/past-paper-questions")
def get_past_paper_questions(subject_key: str, year: int = 0):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    if year <= 0:
        raise HTTPException(status_code=400, detail="year is required")
    return exam_paper_parser.get_year_questions(subject_key, year)


@app.post("/exam/11408/{subject_key}/past-paper-attempts")
def create_past_paper_attempt(subject_key: str, req: dict, db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    username = (req.get("username") or "").strip()
    year = int(req.get("year", 0))
    if not username or year <= 0:
        raise HTTPException(status_code=400, detail="username and year required")
    # Count ALL questions (both ready and need_review) — all are visible
    total = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == subject_key,
        models.ExamQuestionBank.source_type == "past_paper",
        models.ExamQuestionBank.year == year,
    ).count()
    if total == 0:
        # Fallback: try OCR cache and paper parser for legacy subjects
        ocr_cache = exam_paper_parser._ocr_cache_path(subject_key, year)
        if ocr_cache.exists():
            try:
                cached = json.loads(ocr_cache.read_text(encoding="utf-8"))
                total = len(cached.get("questions", []))
            except Exception:
                pass
        if total == 0:
            total = len(exam_paper_parser.get_year_questions(subject_key, year).get("questions", []))
    last = db.query(models.PastPaperAttempt).filter(
        models.PastPaperAttempt.username == username,
        models.PastPaperAttempt.subject_key == subject_key,
        models.PastPaperAttempt.year == year,
    ).order_by(models.PastPaperAttempt.attempt_no.desc()).first()
    attempt_no = (last.attempt_no + 1) if last else 1
    now = utc_now()
    attempt = models.PastPaperAttempt(
        username=username, mode="11408", subject_key=subject_key,
        subject_name=EXAM_SUBJECT_DIRS.get(subject_key, subject_key),
        year=year, attempt_no=attempt_no, status="in_progress",
        total_questions=total, started_at=now,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return {"attempt_id": attempt.id, "attempt_no": attempt_no, "subject_key": subject_key,
            "year": year, "status": "in_progress", "total_questions": total}


# ── Question image URLs ──
_IMG_MAPPING_CACHE = {}

def _load_img_mapping(subject_key):
    if subject_key not in _IMG_MAPPING_CACHE:
        mapping_file = BASE_DIR / f"exam_resources/11408/{subject_key}/past_papers/image_mapping.json"
        if mapping_file.exists():
            try:
                _IMG_MAPPING_CACHE[subject_key] = json.loads(mapping_file.read_text(encoding="utf-8"))
            except Exception:
                _IMG_MAPPING_CACHE[subject_key] = {}
        else:
            _IMG_MAPPING_CACHE[subject_key] = {}
    return _IMG_MAPPING_CACHE[subject_key]

# Keywords indicating a question needs diagram/table display
_TABLE_DIAGRAM_KW = ['下表','右图','下图','如图','表中','图示','如下表','调度表','资源分配','页表结构',
                      '目录结构','索引节点','三级页表','结构图','前驱图','操作表','布局图','地址空间']

def _question_needs_image(item):
    """Returns True if the question has table/diagram dependency and should show images."""
    # CN: only Q47 comprehensive questions need images
    if getattr(item, 'subject_key', '') == 'computer_network' and getattr(item, 'source_type', '') == 'past_paper':
        return item.question_type == "big"
    if item.question_type == "big":
        return True
    stem = (item.stem or "")
    return any(kw in stem for kw in _TABLE_DIAGRAM_KW)

def get_question_images(subject_key, year, question_number):
    mapping = _load_img_mapping(subject_key)
    key = f"{year}-{question_number:02d}"
    val = mapping.get(key, [])
    # Support both formats: plain list (OS) and dict with image_urls (CN)
    if isinstance(val, dict):
        return val.get("image_urls", [])
    return val if isinstance(val, list) else []


@app.get("/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}")
def get_past_paper_attempt(subject_key: str, attempt_id: int, db: Session = Depends(get_db)):
    attempt = db.query(models.PastPaperAttempt).filter(models.PastPaperAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    # Get ALL questions (both ready and need_review) for full visibility
    qb_count = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == subject_key,
        models.ExamQuestionBank.source_type == "past_paper",
        models.ExamQuestionBank.year == attempt.year,
    ).count()
    if qb_count > 0:
        qb_items = db.query(models.ExamQuestionBank).filter(
            models.ExamQuestionBank.subject_key == subject_key,
            models.ExamQuestionBank.source_type == "past_paper",
            models.ExamQuestionBank.year == attempt.year,
        ).order_by(models.ExamQuestionBank.question_number).all()
        questions = []
        for item in qb_items:
            opts = {}
            if item.options_json:
                try: opts = json.loads(item.options_json)
                except: pass
            questions.append({
                "id": item.id,
                "number": item.question_number,
                "year": item.year,
                "type": "选择题" if item.question_type == "choice" else "大题",
                "stem": item.stem or "",
                "content": item.stem or "",
                "options": opts,
                "standard_answer": item.standard_answer or "",
                "question_type": item.question_type,
                "quality_status": item.quality_status or "unchecked",
                "review_notes": item.analysis or "",
                "image_urls": get_question_images(subject_key, item.year, item.question_number),
                "image_required": _question_needs_image(item),
            })
    else:
        questions_data = exam_paper_parser.get_year_questions(subject_key, attempt.year)
        questions = questions_data.get("questions", [])
    saved_answers = {}
    if attempt.answers_json:
        try:
            saved_answers = json.loads(attempt.answers_json)
        except Exception:
            pass
    return {
        "attempt": {
            "id": attempt.id, "attempt_no": attempt.attempt_no, "year": attempt.year,
            "username": attempt.username,
            "status": attempt.status, "total_questions": attempt.total_questions,
            "started_at": serialize_datetime(attempt.started_at),
        },
        "questions": questions,
        "saved_answers": saved_answers,
    }


@app.post("/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/answers")
def save_attempt_answers(subject_key: str, attempt_id: int, req: dict, db: Session = Depends(get_db)):
    attempt = db.query(models.PastPaperAttempt).filter(models.PastPaperAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt already submitted")
    attempt.answers_json = json.dumps(req.get("answers", {}), ensure_ascii=False)
    db.commit()
    return {"success": True, "attempt_id": attempt_id}


@app.post("/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/submit")
def submit_attempt(subject_key: str, attempt_id: int, req: dict, db: Session = Depends(get_db)):
    attempt = db.query(models.PastPaperAttempt).filter(models.PastPaperAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Attempt already submitted")
    answers_list = req.get("answers", [])
    if not answers_list:
        raise HTTPException(status_code=400, detail="No answers provided")
    result = exam_paper_parser.grade_submission(subject_key, attempt.year, answers_list)
    # If ExamQuestionBank has data for this subject+year, use it for grading
    qb_count = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == subject_key,
        models.ExamQuestionBank.source_type == "past_paper",
        models.ExamQuestionBank.year == attempt.year,
        models.ExamQuestionBank.is_active == True,
    ).count()
    if qb_count > 0:
        qb_items = db.query(models.ExamQuestionBank).filter(
            models.ExamQuestionBank.subject_key == subject_key,
            models.ExamQuestionBank.source_type == "past_paper",
            models.ExamQuestionBank.year == attempt.year,
            models.ExamQuestionBank.is_active == True,
        ).order_by(models.ExamQuestionBank.question_number).all()
        if qb_items:
            results_list = []
            correct = 0
            wrong_qs = []
            answer_map = {}
            for a in answers_list:
                if isinstance(a, dict):
                    answer_map[str(a.get("question_id", ""))] = a.get("user_answer", "")
            for item in qb_items:
                qid = str(item.id)
                ua = (answer_map.get(qid) or "").strip()
                sa = (item.standard_answer or "").strip()
                opts = {}
                if item.options_json:
                    try: opts = json.loads(item.options_json)
                    except: pass
                if item.question_type == "choice":
                    is_c = ua.upper() == sa.upper()
                    if is_c: correct += 1
                    results_list.append({
                        "question_id": qid, "number": item.question_number,
                        "type": "选择题", "correct": is_c,
                        "standard_answer": sa, "user_answer": ua,
                        "score": 2 if is_c else 0, "full_score": 2,
                    })
                    if not is_c:
                        wrong_qs.append({
                            "question_id": qid, "number": item.question_number,
                            "type": "选择题", "content": item.stem or "",
                            "options": opts, "standard_answer": sa,
                            "user_answer": ua, "score": 0,
                            "wrong_reason": "答错",
                        })
                else:  # big
                    score = 5  # default partial score for big questions
                    results_list.append({
                        "question_id": qid, "number": item.question_number,
                        "type": "大题", "score": score, "full_score": 10,
                        "standard_answer": sa, "user_answer": ua,
                        "feedback": "请自行对照参考答案",
                    })
            total = len(qb_items)
            choice_total = sum(1 for i in qb_items if i.question_type == "choice")
            result = {
                "subject_key": subject_key, "subject_name": EXAM_SUBJECT_DIRS.get(subject_key, subject_key),
                "year": attempt.year,
                "results": results_list,
                "total_questions": total,
                "choice_correct": correct,
                "choice_total": choice_total,
                "total_score": correct * 2,
                "max_score": choice_total * 2 + (total - choice_total) * 10,
                "wrong_questions": wrong_qs,
                "wrong_count": len(wrong_qs),
            }
    now = utc_now()
    attempt.status = "submitted"
    attempt.submitted_at = now
    attempt.choice_correct = result.get("choice_correct", 0)
    attempt.big_avg_score = result.get("big_avg_score")
    attempt.total_score = result.get("total_score", 0)
    attempt.max_score = result.get("max_score", 0)
    attempt.wrong_count = len(result.get("wrong_questions", []))
    attempt.result_json = json.dumps(result, ensure_ascii=False)
    db.commit()
    # Save wrong questions
    username = (req.get("username") or attempt.username or "").strip()
    if username and result.get("wrong_questions"):
        for wq in result["wrong_questions"]:
            db.add(models.PastPaperWrongQuestion(
                username=username, subject_key=subject_key, source="past_paper", year=attempt.year,
                attempt_id=attempt.id,
                question_id=wq.get("question_id", ""),
                question_number=wq.get("number", 0),
                question_type=wq.get("type", ""),
                content=wq.get("content", "")[:2000],
                options=json.dumps(wq.get("options", {}), ensure_ascii=False),
                standard_answer=wq.get("standard_answer", ""),
                user_answer=wq.get("user_answer", ""),
                score=wq.get("score"), wrong_reason=wq.get("wrong_reason", "")[:500],
                status="active", created_at=now, updated_at=now,
            ))
        db.commit()
    # Save done records for all attempted questions
    if username and result.get("results"):
        for r in result["results"]:
            qtype = r.get("type", "")
            ua = str(r.get("user_answer", "")).strip()
            sa = str(r.get("standard_answer", "")).strip()
            is_c = None
            if qtype == "选择题":
                is_c = r.get("correct", False)
            _save_done_record(db, username, subject_key, practice_type="real_exam",
                              question_type=qtype, user_answer=ua, correct_answer=sa,
                              is_correct=is_c, attempt_id=attempt_id)
        db.commit()
    return {**result, "attempt_id": attempt.id, "attempt_no": attempt.attempt_no}


def _serialize_exam_favorite(item: models.ExamFavoriteQuestion):
    options = {}
    if item.options_json:
        try:
            options = json.loads(item.options_json)
        except Exception:
            options = {}
    return {
        "id": item.id,
        "username": item.username,
        "subject_key": item.subject_key,
        "subject_name": item.subject_name or EXAM_SUBJECT_DIRS.get(item.subject_key, item.subject_key),
        "source": item.source,
        "source_question_id": item.source_question_id,
        "year": item.year,
        "number": item.number,
        "question_type": item.question_type,
        "stem": item.stem,
        "options": options,
        "standard_answer": item.standard_answer,
        "knowledge_point_id": item.knowledge_point_id,
        "knowledge_point_name": item.knowledge_point_name,
        "created_at": serialize_datetime(item.created_at),
    }


@app.get("/exam/11408/{subject_key}/favorites")
def get_exam_favorites(subject_key: str, username: str, source: str = "", db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    query = db.query(models.ExamFavoriteQuestion).filter(
        models.ExamFavoriteQuestion.username == username,
        models.ExamFavoriteQuestion.subject_key == subject_key,
    )
    if source:
        query = query.filter(models.ExamFavoriteQuestion.source == source)
    items = query.order_by(models.ExamFavoriteQuestion.created_at.desc()).all()
    return {"items": [_serialize_exam_favorite(item) for item in items], "total": len(items)}


@app.post("/exam/11408/{subject_key}/favorites")
def create_exam_favorite(subject_key: str, req: dict, db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    username = (req.get("username") or "").strip()
    source = (req.get("source") or "past_paper").strip()
    source_question_id = str(req.get("source_question_id") or "").strip()
    if not username or not source_question_id:
        raise HTTPException(status_code=400, detail="username and source_question_id required")
    existing = db.query(models.ExamFavoriteQuestion).filter(
        models.ExamFavoriteQuestion.username == username,
        models.ExamFavoriteQuestion.subject_key == subject_key,
        models.ExamFavoriteQuestion.source == source,
        models.ExamFavoriteQuestion.source_question_id == source_question_id,
    ).first()
    if existing:
        return {"success": True, "item": _serialize_exam_favorite(existing)}
    item = models.ExamFavoriteQuestion(
        username=username,
        subject_key=subject_key,
        subject_name=EXAM_SUBJECT_DIRS.get(subject_key, subject_key),
        source=source,
        source_question_id=source_question_id,
        year=req.get("year"),
        number=req.get("number"),
        question_type=req.get("question_type"),
        stem=req.get("stem") or "",
        options_json=json.dumps(req.get("options") or {}, ensure_ascii=False),
        standard_answer=req.get("standard_answer") or "",
        knowledge_point_id=req.get("knowledge_point_id"),
        knowledge_point_name=req.get("knowledge_point_name"),
        created_at=utc_now(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"success": True, "item": _serialize_exam_favorite(item)}


@app.delete("/exam/11408/{subject_key}/favorites/{favorite_id}")
def delete_exam_favorite(subject_key: str, favorite_id: int, username: str, db: Session = Depends(get_db)):
    username = (username or "").strip()
    item = db.query(models.ExamFavoriteQuestion).filter(
        models.ExamFavoriteQuestion.id == favorite_id,
        models.ExamFavoriteQuestion.username == username,
        models.ExamFavoriteQuestion.subject_key == subject_key,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="favorite not found")
    db.delete(item)
    db.commit()
    return {"success": True}


def _serialize_ai_generated_question(item: models.AIGeneratedQuestion):
    options = {}
    if item.options_json:
        try:
            options = json.loads(item.options_json)
        except Exception:
            options = {}
    return {
        "id": item.id,
        "username": item.username,
        "subject_key": item.subject_key,
        "subject_name": item.subject_name or EXAM_SUBJECT_DIRS.get(item.subject_key, item.subject_key),
        "knowledge_point_id": item.knowledge_point_id or "",
        "knowledge_point_name": item.knowledge_point_name or "",
        "knowledge_point_path": item.knowledge_point_path or "",
        "question_type": item.question_type,
        "stem": item.stem,
        "options": options,
        "standard_answer": item.standard_answer or "",
        "analysis": item.analysis or "",
        "difficulty": item.difficulty or "",
        "requirement": item.requirement or "",
        "generation_mode": getattr(item, "generation_mode", None) or "deepseek",
        "quality_status": getattr(item, "quality_status", None) or "unchecked",
        "has_raw_response": bool(getattr(item, "raw_ai_response", None)),
        "has_generation_prompt": bool(getattr(item, "generation_prompt", None)),
        "created_at": serialize_datetime(item.created_at),
        "updated_at": serialize_datetime(item.updated_at),
    }


def _normalize_ai_question_type(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value in {"big", "大题", "subjective"}:
        return "大题"
    return "选择题"


def _normalize_ai_difficulty(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value in {"basic", "基础"}:
        return "基础"
    if value in {"advanced", "提高"}:
        return "提高"
    return "中等"


def _build_mock_ai_question(subject_name: str, kp_name: str, kp_path: str, question_type: str, difficulty: str, index: int, generation_mode: str = "mock"):
    scope = kp_name or kp_path or subject_name or "当前科目"
    if question_type == "大题":
        return {
            "stem": f"【模拟生成】围绕“{scope}”，设计一个符合 11408 风格的算法题，并说明核心思路与复杂度分析。（第 {index} 题）",
            "options": {},
            "standard_answer": "参考答案：明确数据结构定义，给出算法步骤，说明关键边界条件，并分析时间复杂度和空间复杂度。",
            "analysis": f"本题为 {difficulty} 难度 mock 题，考查范围为：{kp_path or scope}。答题时应先说明问题建模，再给出算法流程和复杂度。",
        }
    return {
        "stem": f"【模拟生成】关于“{scope}”的说法，下列正确的是（  ）。（第 {index} 题）",
        "options": {
            "A": "相关数据元素之间一定不存在逻辑关系",
            "B": "应结合逻辑结构、存储结构和基本运算综合理解",
            "C": "只能采用顺序存储结构实现",
            "D": "在 11408 考查中不会涉及复杂度分析",
        },
        "standard_answer": "B",
        "analysis": f"本题为 {difficulty} 难度 mock 选择题。数据结构知识点通常需要从逻辑结构、存储结构和运算三个层面综合判断，因此 B 更符合考查要求。",
    }


def _build_exam_ai_choice_prompt(subject_name: str, kp_name: str, kp_path: str, count: int, difficulty: str, requirement: str) -> str:
    scope = kp_path or kp_name or f"{subject_name}综合"
    extra_requirement = requirement or "无"
    return f"""你是 11408 考研《{subject_name}》命题助手。请严格围绕当前科目和知识点范围生成选择题。

科目：{subject_name}
知识点范围：{scope}
题目数量：{count}
难度：{difficulty}
补充要求：{extra_requirement}

命题要求：
1. 只生成 11408《{subject_name}》真题风格的单项选择题，不要生成大题、判断题、多选题。
2. 每题必须有 A/B/C/D 四个选项，且只有一个正确答案。
3. 题干要贴合考研数据结构考查方式，可考查概念辨析、算法过程、复杂度、存储结构、边界条件等。
4. 不要生成与当前科目无关的内容。
5. 不要输出 Markdown，不要解释，不要代码块，只输出严格 JSON 对象。

输出 JSON 格式必须完全符合：
{{
  "questions": [
    {{
      "question_type": "选择题",
      "stem": "...",
      "options": {{
        "A": "...",
        "B": "...",
        "C": "...",
        "D": "..."
      }},
      "standard_answer": "A",
      "analysis": "...",
      "knowledge_point_name": "...",
      "difficulty": "{difficulty}"
    }}
  ]
}}"""


def _normalize_ai_choice_options(raw_options) -> dict:
    if not isinstance(raw_options, dict):
        return {}
    normalized = {}
    for label in ("A", "B", "C", "D"):
        value = raw_options.get(label) or raw_options.get(label.lower())
        normalized[label] = str(value or "").strip()
    return normalized


def _is_ai_choice_subject_related(subject_key: str, stem: str, analysis: str) -> bool:
    if subject_key != "data_structure":
        return True
    text_value = f"{stem}\n{analysis}"
    data_structure_terms = [
        "数据结构", "线性表", "顺序表", "链表", "栈", "队列", "串", "数组", "树", "二叉树",
        "森林", "图", "邻接矩阵", "邻接表", "查找", "排序", "堆", "散列", "哈希", "算法",
        "时间复杂度", "空间复杂度", "遍历", "递归", "插入", "删除",
    ]
    unrelated_terms = [
        "操作系统", "进程调度", "页表", "虚拟内存", "计算机网络", "TCP", "UDP", "IP 地址",
        "路由", "计算机组成", "指令流水线", "Cache", "编译原理", "数据库", "SQL",
    ]
    has_data_structure_signal = any(term in text_value for term in data_structure_terms)
    has_unrelated_signal = any(term in text_value for term in unrelated_terms)
    return has_data_structure_signal or not has_unrelated_signal


def _validate_exam_ai_choice_payload(payload: dict, subject_key: str, expected_count: int) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
        raise HTTPException(status_code=422, detail="AI 返回格式错误：必须是包含 questions 数组的 JSON 对象")
    questions = payload["questions"]
    if len(questions) != expected_count:
        raise HTTPException(status_code=422, detail=f"AI 返回题目数量不符合要求：请求 {expected_count} 道，实际返回 {len(questions)} 道")

    validated = []
    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise HTTPException(status_code=422, detail=f"AI 返回格式错误：第 {index} 题不是 JSON 对象")
        qtype = str(question.get("question_type") or "").strip()
        if qtype and qtype != "选择题":
            raise HTTPException(status_code=422, detail=f"AI 返回格式错误：第 {index} 题不是选择题")
        stem = str(question.get("stem") or "").strip()
        analysis = str(question.get("analysis") or "").strip()
        options = _normalize_ai_choice_options(question.get("options"))
        standard_answer = str(question.get("standard_answer") or "").strip().upper()
        if not stem:
            raise HTTPException(status_code=422, detail=f"AI 返回格式错误：第 {index} 题题干为空")
        if any(not options[label] for label in ("A", "B", "C", "D")):
            raise HTTPException(status_code=422, detail=f"AI 返回格式错误：第 {index} 题 A/B/C/D 选项必须全部非空")
        if len({options[label] for label in ("A", "B", "C", "D")}) != 4:
            raise HTTPException(status_code=422, detail=f"AI 返回格式错误：第 {index} 题 A/B/C/D 选项不能重复")
        if standard_answer not in {"A", "B", "C", "D"}:
            raise HTTPException(status_code=422, detail=f"AI 返回格式错误：第 {index} 题标准答案必须是 A/B/C/D")
        if not analysis:
            raise HTTPException(status_code=422, detail=f"AI 返回格式错误：第 {index} 题解析为空")
        if not _is_ai_choice_subject_related(subject_key, stem, analysis):
            raise HTTPException(status_code=422, detail=f"AI 返回内容错误：第 {index} 题与当前科目不相关")
        validated.append({
            "question_type": "选择题",
            "stem": stem,
            "options": options,
            "standard_answer": standard_answer,
            "analysis": analysis,
            "knowledge_point_name": str(question.get("knowledge_point_name") or "").strip(),
            "difficulty": _normalize_ai_difficulty(str(question.get("difficulty") or "")),
        })
    return validated


def _create_mock_exam_ai_questions(
    db: Session,
    *,
    username: str,
    subject_key: str,
    subject_name: str,
    kp_id: str,
    kp_name: str,
    kp_path: str,
    question_type: str,
    count: int,
    difficulty: str,
    requirement: str,
    fallback_reason: str = "",
    generation_mode: str = "mock",
):
    now = utc_now()
    created_items = []
    prompt_payload = {
        "mock": True,
        "subject_key": subject_key,
        "knowledge_point_path": kp_path,
        "question_type": question_type,
        "count": count,
        "difficulty": difficulty,
        "requirement": requirement,
        "fallback_reason": fallback_reason,
    }
    raw_fallback = json.dumps({"fallback": True, "reason": fallback_reason or "mock generation"}, ensure_ascii=False)
    for index in range(1, count + 1):
        mock = _build_mock_ai_question(subject_name, kp_name, kp_path, question_type, difficulty, index, generation_mode=generation_mode or "mock")
        item = models.AIGeneratedQuestion(
            username=username,
            subject_key=subject_key,
            subject_name=subject_name,
            knowledge_point_id=kp_id,
            knowledge_point_name=kp_name,
            knowledge_point_path=kp_path,
            question_type=question_type,
            stem=mock["stem"],
            options_json=json.dumps(mock["options"], ensure_ascii=False),
            standard_answer=mock["standard_answer"],
            analysis=mock["analysis"],
            difficulty=difficulty,
            requirement=requirement,
            generation_prompt=json.dumps(prompt_payload, ensure_ascii=False),
            raw_ai_response=raw_fallback,
            generation_mode="mock",
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        created_items.append(item)
    db.commit()
    for item in created_items:
        db.refresh(item)
    return created_items


@app.get("/exam/11408/{subject_key}/ai-questions")
def get_exam_ai_questions(subject_key: str, username: str, db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    items = db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.username == username,
        models.AIGeneratedQuestion.subject_key == subject_key,
    ).order_by(models.AIGeneratedQuestion.created_at.desc(), models.AIGeneratedQuestion.id.desc()).all()
    return {"items": [_serialize_ai_generated_question(item) for item in items], "total": len(items)}


@app.get("/exam/11408/{subject_key}/ai-questions/groups")
def get_exam_ai_question_groups(subject_key: str, username: str, db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    items = db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.username == username,
        models.AIGeneratedQuestion.subject_key == subject_key,
    ).order_by(models.AIGeneratedQuestion.created_at.desc()).all()

    groups = {}
    for item in items:
        kp_id = (item.knowledge_point_id or "").strip()
        kp_name = (item.knowledge_point_name or "").strip() or "综合出题"
        kp_path = (item.knowledge_point_path or "").strip() or "综合出题"
        gkey = kp_id or "_general"
        if gkey not in groups:
            groups[gkey] = {
                "group_key": gkey, "knowledge_point_id": kp_id,
                "knowledge_point_name": kp_name, "knowledge_point_path": kp_path,
                "total": 0, "choice_count": 0, "big_count": 0,
                "deepseek_count": 0, "mock_count": 0,
                "quality_summary": {"unchecked": 0, "usable": 0, "needs_edit": 0, "discarded": 0},
            }
        g = groups[gkey]
        g["total"] += 1
        if item.question_type == "选择题": g["choice_count"] += 1
        else: g["big_count"] += 1
        gm = (getattr(item, "generation_mode", None) or "deepseek")
        if gm == "deepseek": g["deepseek_count"] += 1
        else: g["mock_count"] += 1
        qs = (getattr(item, "quality_status", None) or "unchecked")
        if qs in g["quality_summary"]: g["quality_summary"][qs] += 1
    return {"groups": list(groups.values()), "total_questions": len(items)}


@app.post("/exam/11408/{subject_key}/ai-questions/attempts")
def create_ai_question_attempt(subject_key: str, req: dict, db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    username = (req.get("username") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    qids = req.get("question_ids") or []
    items = db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.id.in_(qids),
        models.AIGeneratedQuestion.username == username,
        models.AIGeneratedQuestion.quality_status != "discarded",
    ).all()
    if not items:
        raise HTTPException(status_code=400, detail="no valid questions found")
    now = utc_now()
    attempt = models.AIQuestionAttempt(
        username=username, mode="11408", subject_key=subject_key,
        subject_name=EXAM_SUBJECT_DIRS.get(subject_key, subject_key),
        knowledge_point_id=(req.get("knowledge_point_id") or "").strip() or None,
        knowledge_point_name=(req.get("knowledge_point_path") or "").strip() or None,
        knowledge_point_path=(req.get("knowledge_point_path") or "").strip() or None,
        question_ids_json=json.dumps([i.id for i in items]),
        total_questions=len(items), status="in_progress",
    )
    db.add(attempt); db.commit(); db.refresh(attempt)
    return {
        "attempt_id": attempt.id, "status": "in_progress",
        "total_questions": len(items),
    }


@app.get("/exam/11408/{subject_key}/ai-questions/attempts/{attempt_id}")
def get_ai_question_attempt(subject_key: str, attempt_id: int, username: str, db: Session = Depends(get_db)):
    attempt = db.query(models.AIQuestionAttempt).filter(
        models.AIQuestionAttempt.id == attempt_id,
        models.AIQuestionAttempt.username == (username or "").strip(),
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    qids = json.loads(attempt.question_ids_json or "[]")
    items = db.query(models.AIGeneratedQuestion).filter(models.AIGeneratedQuestion.id.in_(qids)).all()
    saved = {}
    if attempt.answers_json:
        try: saved = json.loads(attempt.answers_json)
        except: pass
    questions = []
    for item in items:
        q = _serialize_ai_generated_question(item)
        if attempt.status != "submitted":
            q.pop("standard_answer", None); q.pop("analysis", None)
        questions.append(q)
    return {"attempt": {"id": attempt.id, "status": attempt.status, "total_questions": attempt.total_questions,
            "knowledge_point_path": attempt.knowledge_point_path, "started_at": serialize_datetime(attempt.started_at)},
            "questions": questions, "saved_answers": saved}


@app.post("/exam/11408/{subject_key}/ai-questions/attempts/{attempt_id}/answers")
def save_ai_question_answers(subject_key: str, attempt_id: int, req: dict, db: Session = Depends(get_db)):
    attempt = db.query(models.AIQuestionAttempt).filter(models.AIQuestionAttempt.id == attempt_id).first()
    if not attempt or attempt.status != "in_progress":
        raise HTTPException(status_code=404, detail="Attempt not found or already submitted")
    attempt.answers_json = json.dumps(req.get("answers", {}), ensure_ascii=False)
    db.commit()
    return {"success": True}


@app.post("/exam/11408/{subject_key}/ai-questions/attempts/{attempt_id}/submit")
def submit_ai_question_attempt(subject_key: str, attempt_id: int, req: dict, db: Session = Depends(get_db)):
    attempt = db.query(models.AIQuestionAttempt).filter(models.AIQuestionAttempt.id == attempt_id).first()
    if not attempt or attempt.status != "in_progress":
        raise HTTPException(status_code=404, detail="Attempt not found or already submitted")
    answers = req.get("answers", {})
    qids = json.loads(attempt.question_ids_json or "[]")
    items = {i.id: i for i in db.query(models.AIGeneratedQuestion).filter(models.AIGeneratedQuestion.id.in_(qids)).all()}
    results, correct, wrong, big_count, mistake_saved = [], 0, 0, 0, 0
    username = (req.get("username") or "").strip()
    now = utc_now()
    for qid in qids:
        item = items.get(qid)
        if not item: continue
        ua = str(answers.get(str(qid), "")).strip()
        sa = (item.standard_answer or "").strip()
        opts = {}
        if item.options_json:
            try: opts = json.loads(item.options_json)
            except: pass
        if item.question_type == "big":
            big_count += 1
            results.append({"question_id": qid, "correct": None, "judge": "self_review",
                "standard_answer": sa, "user_answer": ua, "stem": item.stem or "",
                "options": opts, "analysis": item.analysis or "", "question_type": item.question_type,
                "hint": "请自行对照参考答案"})
        else:
            ua_upper = ua.upper(); sa_upper = sa.upper()
            is_c = ua_upper == sa_upper
            if is_c: correct += 1
            else: wrong += 1
            results.append({"question_id": qid, "correct": is_c, "standard_answer": sa, "user_answer": ua,
                "stem": item.stem or "", "options": opts, "analysis": item.analysis or "",
                "question_type": item.question_type})
            if not is_c and username:
                existing = db.query(models.ExamWrongQuestion).filter(
                    models.ExamWrongQuestion.username == username,
                    models.ExamWrongQuestion.question_bank_id == None,
                    models.ExamWrongQuestion.wrong_reason.like("AI%"),
                ).filter(models.ExamWrongQuestion.stem_snapshot == (item.stem or "")).first()
                # For AI questions, use a simple approach — always insert new (no easy dedup without question_bank_id)
                db.add(models.ExamWrongQuestion(
                    username=username, subject_key=subject_key, question_bank_id=None,
                    practice_attempt_id=attempt_id, source_type="ai_generated", practice_type="ai_generated",
                    knowledge_point_id=attempt.knowledge_point_id,
                    knowledge_point_name=attempt.knowledge_point_name,
                    knowledge_point_path=attempt.knowledge_point_path, question_type=item.question_type,
                    stem_snapshot=item.stem, options_snapshot_json=item.options_json,
                    standard_answer_snapshot=sa, analysis_snapshot=item.analysis or "",
                    user_answer=ua, score=0, wrong_reason="AI题库练习答错",
                ))
                mistake_saved += 1
        # Save done record
        if username:
            _save_done_record(db, username, subject_key, practice_type="ai_generated",
                              ai_question_id=item.id, question_type=item.question_type,
                              user_answer=ua, correct_answer=sa,
                              is_correct=(True if item.question_type != "big" and ua.upper() == sa.upper() else (None if item.question_type == "big" else False)),
                              attempt_id=attempt_id)
    total = len(qids); choice_total = total - big_count
    attempt.status = "submitted"; attempt.submitted_at = now
    attempt.correct_count = correct; attempt.wrong_count = wrong
    attempt.accuracy = round(correct / choice_total * 100, 1) if choice_total > 0 else 0
    attempt.result_json = json.dumps({"correct": correct, "total": total, "results": results}, ensure_ascii=False)
    db.commit()
    return {"total_questions": total, "choice_total": choice_total, "big_count": big_count,
            "correct_count": correct, "wrong_count": wrong, "accuracy": attempt.accuracy,
            "mistake_saved_count": mistake_saved, "results": results}


# ── v2 Unified Question Bank ──

def _serialize_question_bank(item):
    opts = {}
    if item.options_json:
        try: opts = json.loads(item.options_json)
        except: pass
    source_meta = {}
    if item.source_ref:
        try:
            parsed_ref = json.loads(item.source_ref)
            if isinstance(parsed_ref, dict):
                source_meta = parsed_ref
        except Exception:
            source_meta = {}
    knowledge_points = source_meta.get("knowledge_points")
    if not isinstance(knowledge_points, list):
        knowledge_points = [p.strip() for p in re.split(r"[；;|]", item.knowledge_point_path or "") if p.strip()]
    chapter_id = str(source_meta.get("chapter_id") or "").strip()
    if not chapter_id:
        first_code = str(item.knowledge_point_id or "").split("；", 1)[0].split(";", 1)[0].strip()
        chapter_id = first_code.split(".", 1)[0] if first_code else ""
    chapter_name = str(source_meta.get("chapter_name") or "").strip()
    if not chapter_name and chapter_id:
        chapter_name = f"第{chapter_id}章"
    return {"id": item.id, "subject_key": item.subject_key, "source_type": item.source_type,
            "visibility": item.visibility, "knowledge_point_id": item.knowledge_point_id,
            "knowledge_point_name": item.knowledge_point_name, "knowledge_point_path": item.knowledge_point_path,
            "knowledge_points": knowledge_points, "chapter_id": chapter_id, "chapter_name": chapter_name,
            "year": item.year, "question_number": item.question_number, "question_type": item.question_type,
            "stem": item.stem, "options": opts, "standard_answer": item.standard_answer,
            "analysis": item.analysis, "difficulty": item.difficulty, "quality_status": item.quality_status,
            "created_at": serialize_datetime(item.created_at)}


@app.get("/exam/11408/{subject_key}/question-bank/stats")
def get_question_bank_stats(subject_key: str, db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    items = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == subject_key, models.ExamQuestionBank.is_active == True).all()
    return {
        "subject_key": subject_key, "total": len(items),
        "chapter": sum(1 for i in items if i.source_type == "chapter"),
        "past_paper": sum(1 for i in items if i.source_type == "past_paper"),
        "ai_generated": sum(1 for i in items if i.source_type == "ai_generated"),
        "public": sum(1 for i in items if i.visibility == "public"),
        "private": sum(1 for i in items if i.visibility == "private"),
    }


@app.get("/exam/11408/{subject_key}/question-bank/questions")
def get_question_bank_questions(subject_key: str, source_type: str = "", knowledge_point_id: str = "",
                                 username: str = "", db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    q = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == subject_key, models.ExamQuestionBank.is_active == True)
    if source_type: q = q.filter(models.ExamQuestionBank.source_type == source_type)
    if knowledge_point_id: q = q.filter(models.ExamQuestionBank.knowledge_point_id == knowledge_point_id)
    if username: q = q.filter((models.ExamQuestionBank.visibility == "public") |
                               (models.ExamQuestionBank.owner_username == username.strip()))
    items = q.order_by(models.ExamQuestionBank.created_at.desc()).all()
    return {"items": [_serialize_question_bank(i) for i in items], "total": len(items)}


@app.post("/exam/11408/{subject_key}/question-bank/questions")
def create_question_bank_question(subject_key: str, req: dict, db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    stem = (req.get("stem") or "").strip()
    if not stem: raise HTTPException(status_code=400, detail="stem is required")
    qtype = (req.get("question_type") or "choice").strip()
    item = models.ExamQuestionBank(
        subject_key=subject_key, subject_name=EXAM_SUBJECT_DIRS.get(subject_key, subject_key),
        source_type=(req.get("source_type") or "chapter").strip(),
        visibility=(req.get("visibility") or "public").strip(),
        owner_username=(req.get("owner_username") or "").strip() or None,
        knowledge_point_id=(req.get("knowledge_point_id") or "").strip() or None,
        knowledge_point_name=(req.get("knowledge_point_name") or "").strip() or None,
        knowledge_point_path=(req.get("knowledge_point_path") or "").strip() or None,
        question_type=qtype, stem=stem,
        options_json=json.dumps(req.get("options") or {}, ensure_ascii=False),
        standard_answer=(req.get("standard_answer") or "").strip() or None,
        analysis=(req.get("analysis") or "").strip() or None,
        difficulty=(req.get("difficulty") or "").strip() or None,
    )
    db.add(item); db.commit(); db.refresh(item)
    return {"success": True, "id": item.id, "item": _serialize_question_bank(item)}


# ── Chapter Practice ──

@app.get("/exam/11408/{subject_key}/chapter-practice/outline")
def get_chapter_practice_outline(subject_key: str):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    questions = {}  # kp_id -> count
    items = db_query_chapter_questions(subject_key)
    for item in items:
        kp_ids = _split_chapter_question_kp_ids(item)
        for kp in kp_ids or [""]:
            questions[kp] = questions.get(kp, 0) + 1
    return {"subject_key": subject_key, "knowledge_points": questions, "total": sum(questions.values())}

def _split_chapter_question_kp_ids(item):
    raw = item.knowledge_point_id or ""
    ids = [p.strip() for p in re.split(r"[；;|]", raw) if p.strip()]
    if ids:
        return ids
    return []

def _chapter_question_matches_kp(item, kp_id, include_children=False):
    if not kp_id:
        return True
    for item_kp_id in _split_chapter_question_kp_ids(item):
        if item_kp_id == kp_id:
            return True
        if include_children and item_kp_id.startswith(kp_id + "."):
            return True
        if kp_id.startswith(item_kp_id + "."):
            return True
    return False

def db_query_chapter_questions(subject_key):
    from database import SessionLocal
    db = SessionLocal()
    try:
        return db.query(models.ExamQuestionBank).filter(
            models.ExamQuestionBank.subject_key == subject_key,
            models.ExamQuestionBank.source_type == "chapter",
            models.ExamQuestionBank.is_active == True,
        ).all()
    finally: db.close()

@app.get("/exam/11408/{subject_key}/chapter-practice/questions")
def get_chapter_practice_questions(subject_key: str, knowledge_point_id: str = "",
                                     knowledge_point_path: str = "", include_children: bool = False,
                                     username: str = "", db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    items = db_query_chapter_questions(subject_key)

    # Load done records to tag practiced questions
    done_q_ids: set[int] = set()
    u = (username or "").strip()
    if u:
        u2 = get_user_by_username(u, db)
        done_rows = db.query(models.ExamQuestionDoneRecord).filter(
            models.ExamQuestionDoneRecord.username == u2.username,
            models.ExamQuestionDoneRecord.subject_key == subject_key,
            models.ExamQuestionDoneRecord.practice_type == "chapter",
        ).all()
        done_q_ids = {r.question_bank_id for r in done_rows if r.question_bank_id}
    # Normalize knowledge_point_id: strip _leaf:/leaf:/node: prefixes
    import re as _re
    raw_kp_id = (knowledge_point_id or "").strip()
    kp_id = _re.sub(r'^(_leaf:|leaf:|_node:|node:|_kp:|kp:)', '', raw_kp_id).strip()
    kp_path = (knowledge_point_path or "").strip()
    debug = {"raw_knowledge_point_id": raw_kp_id, "normalized_knowledge_point_id": kp_id,
             "knowledge_point_path": kp_path, "include_children": include_children, "query_mode": "none"}
    matched = []
    if kp_id:
        # Try exact ID match
        matched = [i for i in items if _chapter_question_matches_kp(i, kp_id)]
        debug["query_mode"] = "id_exact"
        if not matched:
            # Try child match
            child = [i for i in items if _chapter_question_matches_kp(i, kp_id, include_children=True)]
            if child: matched = child; debug["query_mode"] = "id_children"
        if not matched and kp_path:
            path_m = [i for i in items if (i.knowledge_point_path or "").startswith(kp_path)]
            if path_m: matched = path_m; debug["query_mode"] = "path_prefix"
        if include_children and matched:
            child_m = [i for i in items if _chapter_question_matches_kp(i, kp_id, include_children=True)]
            seen = {i.id for i in matched}
            for i in child_m:
                if i.id not in seen: matched.append(i)
            debug["query_mode"] = "id_exact+children"
        items = matched
    result = {
        "items": [
            {**_serialize_question_bank(i), "practiced": i.id in done_q_ids}
            for i in items
        ],
        "total": len(items),
    }
    # Only include debug in dev or when total=0
    if len(items) == 0: result["debug_info"] = debug
    return result

@app.get("/exam/11408/{subject_key}/chapter/analytics")
def get_chapter_analytics(subject_key: str, username: str = "", db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    # Stats per knowledge point
    items = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == subject_key,
        models.ExamQuestionBank.source_type == "chapter",
        models.ExamQuestionBank.is_active == True).all()
    kp_stats = {}
    for i in items:
        kp = (i.knowledge_point_name or "未知")
        if kp not in kp_stats:
            kp_stats[kp] = {"total": 0, "basic": 0, "medium": 0, "hard": 0}
        kp_stats[kp]["total"] += 1
        d = (i.difficulty or "基础")
        if "基础" in d: kp_stats[kp]["basic"] += 1
        elif "中" in d: kp_stats[kp]["medium"] += 1
        else: kp_stats[kp]["hard"] += 1

    # Right/wrong per KP from attempts
    u = (username or "").strip()
    kp_accuracy = {}
    if u:
        attempts = db.query(models.ExamPracticeAttempt).filter(
            models.ExamPracticeAttempt.username == u,
            models.ExamPracticeAttempt.subject_key == subject_key,
            models.ExamPracticeAttempt.status == "submitted").all()
        for a in attempts:
            kp = (a.knowledge_point_name or "综合")
            if a.total_questions > 0 and a.correct_count is not None:
                rate = round(a.correct_count / a.total_questions * 100, 1)
                if kp not in kp_accuracy:
                    kp_accuracy[kp] = {"total": 0, "correct": 0, "attempts": 0}
                kp_accuracy[kp]["total"] += a.total_questions
                kp_accuracy[kp]["correct"] += (a.correct_count or 0)
                kp_accuracy[kp]["attempts"] += 1

    # Weak points (bottom 10 by accuracy)
    weak = sorted(
        [{"kp": k, "accuracy": round(v["correct"]/v["total"]*100,1) if v["total"]>0 else 0, "total": v["total"], "attempts": v["attempts"]}
         for k, v in kp_accuracy.items() if v["total"] >= 3],
        key=lambda x: x["accuracy"])[:10]

    strong = sorted(
        [{"kp": k, "accuracy": round(v["correct"]/v["total"]*100,1) if v["total"]>0 else 0, "total": v["total"]}
         for k, v in kp_accuracy.items() if v["total"] >= 3],
        key=lambda x: -x["accuracy"])[:5]

    empty = [k for k, v in kp_stats.items() if v["total"] == 0]

    dist = {"basic": sum(v["basic"] for v in kp_stats.values()),
            "medium": sum(v["medium"] for v in kp_stats.values()),
            "hard": sum(v["hard"] for v in kp_stats.values())}

    return {"knowledge_point_stats": kp_stats, "weak_points": weak, "strong_points": strong,
            "empty_points": empty, "difficulty_distribution": dist, "total_questions": len(items)}


@app.post("/exam/11408/{subject_key}/chapter-practice/attempts")
def create_chapter_practice_attempt(subject_key: str, req: dict, db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    username = (req.get("username") or "").strip()
    if not username: raise HTTPException(status_code=400, detail="username required")
    qids = req.get("question_ids") or []
    if not qids: raise HTTPException(status_code=400, detail="question_ids required")
    items = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.id.in_(qids), models.ExamQuestionBank.is_active == True).all()
    if not items: raise HTTPException(status_code=400, detail="no valid questions found")
    now = utc_now()
    a = models.ExamPracticeAttempt(
        username=username, subject_key=subject_key, practice_type="chapter",
        source_type="chapter", status="in_progress",
        knowledge_point_id=(req.get("knowledge_point_id") or "").strip() or None,
        knowledge_point_name=(req.get("knowledge_point_name") or "").strip() or None,
        knowledge_point_path=(req.get("knowledge_point_path") or "").strip() or None,
        question_ids_json=json.dumps([i.id for i in items]), total_questions=len(items),
    )
    db.add(a); db.commit(); db.refresh(a)
    return {"attempt_id": a.id, "status": "in_progress", "total_questions": len(items)}

@app.get("/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}")
def get_chapter_practice_attempt(subject_key: str, attempt_id: int, username: str = "", db: Session = Depends(get_db)):
    a = db.query(models.ExamPracticeAttempt).filter(
        models.ExamPracticeAttempt.id == attempt_id,
        models.ExamPracticeAttempt.username == (username or "").strip()).first()
    if not a: raise HTTPException(status_code=404, detail="Attempt not found")
    qids = json.loads(a.question_ids_json or "[]")
    items = db.query(models.ExamQuestionBank).filter(models.ExamQuestionBank.id.in_(qids)).all()
    saved = {};
    if a.answers_json:
        try: saved = json.loads(a.answers_json)
        except: pass
    questions = []
    for item in items:
        q = _serialize_question_bank(item)
        if a.status != "submitted": q.pop("standard_answer", None); q.pop("analysis", None)
        questions.append(q)
    return {"attempt": {"id": a.id, "status": a.status, "total_questions": a.total_questions,
            "knowledge_point_path": a.knowledge_point_path, "started_at": serialize_datetime(a.started_at)},
            "questions": questions, "saved_answers": saved}

@app.post("/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/answers")
def save_chapter_attempt_answers(subject_key: str, attempt_id: int, req: dict, db: Session = Depends(get_db)):
    a = db.query(models.ExamPracticeAttempt).filter(models.ExamPracticeAttempt.id == attempt_id).first()
    if not a or a.status != "in_progress": raise HTTPException(status_code=404, detail="Attempt not found")
    a.answers_json = json.dumps(req.get("answers", {}), ensure_ascii=False)
    db.commit()
    return {"success": True}

@app.post("/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/submit")
def submit_chapter_attempt(subject_key: str, attempt_id: int, req: dict, db: Session = Depends(get_db)):
    a = db.query(models.ExamPracticeAttempt).filter(models.ExamPracticeAttempt.id == attempt_id).first()
    if not a or a.status != "in_progress": raise HTTPException(status_code=404, detail="Attempt not found")
    answers = req.get("answers", {})
    qids = json.loads(a.question_ids_json or "[]")
    items = {i.id: i for i in db.query(models.ExamQuestionBank).filter(models.ExamQuestionBank.id.in_(qids)).all()}
    results, correct, wrong, big_count, mistake_saved = [], 0, 0, 0, 0; now = utc_now(); username = (req.get("username") or "").strip()
    for qid in qids:
        item = items.get(qid)
        if not item: continue
        ua = str(answers.get(str(qid), "")).strip()
        sa = (item.standard_answer or "").strip()
        opts = {};
        if item.options_json:
            try: opts = json.loads(item.options_json)
            except: pass
        if item.question_type == "big":
            # Big questions: show reference answer, don't auto-grade, don't add to wrong book
            big_count += 1
            results.append({"question_id": qid, "correct": None, "judge": "self_review",
                            "standard_answer": sa, "user_answer": ua,
                            "stem": item.stem, "options": opts, "analysis": item.analysis or "",
                            "question_type": item.question_type,
                            "hint": "请自行对照参考答案"})
        else:
            # Choice questions: auto-grade
            ua_upper = ua.upper()
            sa_upper = sa.upper()
            is_c = ua_upper == sa_upper
            if is_c: correct += 1
            else: wrong += 1
            results.append({"question_id": qid, "correct": is_c, "standard_answer": sa, "user_answer": ua,
                            "stem": item.stem, "options": opts, "analysis": item.analysis or "",
                            "question_type": item.question_type})
            # Save wrong choice questions with dedup
            if not is_c and username:
                existing = db.query(models.ExamWrongQuestion).filter(
                    models.ExamWrongQuestion.username == username,
                    models.ExamWrongQuestion.question_bank_id == item.id,
                    models.ExamWrongQuestion.status == "active",
                ).first()
                if existing:
                    # Update existing: increment review_count, update user_answer and time
                    existing.user_answer = ua
                    existing.review_count = (existing.review_count or 0) + 1
                    existing.practice_attempt_id = attempt_id
                    existing.wrong_reason = "章节练习答错(重复)"
                    existing.updated_at = now
                    mistake_saved += 1
                else:
                    db.add(models.ExamWrongQuestion(
                        username=username, subject_key=subject_key, question_bank_id=item.id,
                        practice_attempt_id=attempt_id, source_type="chapter", practice_type="chapter",
                        knowledge_point_id=a.knowledge_point_id,
                        knowledge_point_name=a.knowledge_point_name,
                        knowledge_point_path=a.knowledge_point_path, question_type=item.question_type,
                        stem_snapshot=item.stem, options_snapshot_json=item.options_json,
                        standard_answer_snapshot=sa, analysis_snapshot=item.analysis or "",
                        user_answer=ua, score=0, wrong_reason="章节练习答错",
                    ))
                    mistake_saved += 1
    total = len(qids); choice_total = total - big_count
    a.status = "submitted"; a.submitted_at = now; a.correct_count = correct
    a.wrong_count = wrong; a.accuracy = round(correct/choice_total*100,1) if choice_total>0 else 0
    a.result_json = json.dumps({"correct": correct, "total": total, "choice_total": choice_total,
        "big_count": big_count, "results": results, "mistake_saved": mistake_saved}, ensure_ascii=False)
    # Save done records for all questions in this attempt
    for qid in qids:
        item = items.get(qid)
        if not item: continue
        ua = str(answers.get(str(qid), "")).strip()
        sa = (item.standard_answer or "").strip()
        is_c = None
        if item.question_type != "big":
            is_c = ua.upper() == sa.upper()
        _save_done_record(db, username, subject_key, practice_type="chapter",
                          question_bank_id=item.id, question_type=item.question_type,
                          user_answer=ua, correct_answer=sa, is_correct=is_c, attempt_id=attempt_id)
    db.commit()
    return {"total_questions": total, "choice_total": choice_total, "big_count": big_count,
            "correct_count": correct, "wrong_count": wrong, "accuracy": a.accuracy,
            "mistake_saved_count": mistake_saved, "results": results}


@app.post("/exam/11408/{subject_key}/ai-questions/generate")
def generate_exam_ai_questions(subject_key: str, req: dict, db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    username = (req.get("username") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="请先登录")
    try:
        count = int(req.get("count") or 0)
    except Exception:
        count = 0
    if count < 1 or count > 10:
        raise HTTPException(status_code=400, detail="count must be between 1 and 10")

    subject_name = EXAM_SUBJECT_DIRS.get(subject_key, subject_key)
    kp_id = str(req.get("knowledge_point_id") or "").strip()
    kp_name = str(req.get("knowledge_point_name") or "").strip()
    kp_path = str(req.get("knowledge_point_path") or "").strip()
    question_type = _normalize_ai_question_type(str(req.get("question_type") or ""))
    difficulty = _normalize_ai_difficulty(str(req.get("difficulty") or ""))
    requirement = str(req.get("requirement") or "").strip()

    if question_type != "选择题":
        created_items = _create_mock_exam_ai_questions(
            db,
            username=username,
            subject_key=subject_key,
            subject_name=subject_name,
            kp_id=kp_id,
            kp_name=kp_name,
            kp_path=kp_path,
            question_type=question_type,
            count=count,
            difficulty=difficulty,
            requirement=requirement,
        )
        return {
            "success": True,
            "generation_mode": "mock",
            "fallback_used": False,
            "requested_count": count,
            "generated_count": len(created_items),
            "items": [_serialize_ai_generated_question(item) for item in created_items],
        }

    prompt = _build_exam_ai_choice_prompt(subject_name, kp_name, kp_path, count, difficulty, requirement)
    prompt_payload = {
        "mock": False,
        "provider": "deepseek",
        "subject_key": subject_key,
        "subject_name": subject_name,
        "knowledge_point_id": kp_id,
        "knowledge_point_name": kp_name,
        "knowledge_point_path": kp_path,
        "question_type": question_type,
        "count": count,
        "difficulty": difficulty,
        "requirement": requirement,
        "prompt": prompt,
    }
    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        created_items = _create_mock_exam_ai_questions(
            db,
            username=username,
            subject_key=subject_key,
            subject_name=subject_name,
            kp_id=kp_id,
            kp_name=kp_name,
            kp_path=kp_path,
            question_type=question_type,
            count=count,
            difficulty=difficulty,
            requirement=requirement,
            fallback_reason="DEEPSEEK_API_KEY 未配置，已使用 mock fallback",
            generation_mode="mock_fallback",
        )
        return {
            "success": True,
            "generation_mode": "mock_fallback",
            "fallback_used": True,
            "message": "DeepSeek 未配置，已使用 mock fallback 生成选择题。",
            "requested_count": count,
            "generated_count": len(created_items),
            "items": [_serialize_ai_generated_question(item) for item in created_items],
        }

    try:
        raw_ai_response = call_deepseek(
            [
                {"role": "system", "content": "你是严谨的 11408 考研数据结构命题助手，只输出严格 JSON。"},
                {"role": "user", "content": prompt},
            ],
            timeout_seconds=90,
            temperature=0.35,
            max_tokens=max(1600, min(6000, count * 900)),
        )
    except HTTPException as exc:
        created_items = _create_mock_exam_ai_questions(
            db,
            username=username,
            subject_key=subject_key,
            subject_name=subject_name,
            kp_id=kp_id,
            kp_name=kp_name,
            kp_path=kp_path,
            question_type=question_type,
            count=count,
            difficulty=difficulty,
            requirement=requirement,
            fallback_reason=f"DeepSeek 调用失败：{exc.detail}",
            generation_mode="mock_fallback",
        )
        return {
            "success": True,
            "generation_mode": "mock_fallback",
            "fallback_used": True,
            "message": "DeepSeek 调用失败，已使用 mock fallback 生成选择题。",
            "requested_count": count,
            "generated_count": len(created_items),
            "items": [_serialize_ai_generated_question(item) for item in created_items],
        }

    parsed_payload = extract_json_object(raw_ai_response)
    validated_questions = _validate_exam_ai_choice_payload(parsed_payload, subject_key, count)

    now = utc_now()
    created_items = []
    for question in validated_questions:
        item = models.AIGeneratedQuestion(
            username=username,
            subject_key=subject_key,
            subject_name=subject_name,
            knowledge_point_id=kp_id,
            knowledge_point_name=kp_name or question["knowledge_point_name"],
            knowledge_point_path=kp_path,
            question_type="选择题",
            stem=question["stem"],
            options_json=json.dumps(question["options"], ensure_ascii=False),
            standard_answer=question["standard_answer"],
            analysis=question["analysis"],
            difficulty=question["difficulty"] or difficulty,
            requirement=requirement,
            generation_prompt=json.dumps(prompt_payload, ensure_ascii=False),
            raw_ai_response=raw_ai_response,
            generation_mode="deepseek",
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        created_items.append(item)
    db.commit()
    for item in created_items:
        db.refresh(item)
    return {
        "success": True,
        "generation_mode": "deepseek",
        "fallback_used": False,
        "requested_count": count,
        "generated_count": len(created_items),
        "items": [_serialize_ai_generated_question(item) for item in created_items],
    }


@app.patch("/exam/11408/{subject_key}/ai-questions/{question_id}")
def update_exam_ai_question(subject_key: str, question_id: int, req: dict, db: Session = Depends(get_db)):
    username = (req.get("username") or "").strip()
    item = db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.id == question_id,
        models.AIGeneratedQuestion.username == username,
        models.AIGeneratedQuestion.subject_key == subject_key,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="AI question not found")

    if "stem" in req:
        item.stem = str(req.get("stem") or "")
    if "options" in req:
        item.options_json = json.dumps(req.get("options") or {}, ensure_ascii=False)
    if "standard_answer" in req:
        item.standard_answer = str(req.get("standard_answer") or "")
    if "analysis" in req:
        item.analysis = str(req.get("analysis") or "")
    if "difficulty" in req:
        item.difficulty = _normalize_ai_difficulty(str(req.get("difficulty") or ""))
    if "quality_status" in req:
        val = str(req.get("quality_status") or "").strip().lower()
        if val in ("unchecked", "usable", "needs_edit", "discarded"):
            item.quality_status = val
    item.updated_at = utc_now()
    db.commit()
    db.refresh(item)
    return {"success": True, "item": _serialize_ai_generated_question(item)}


@app.get("/exam/11408/{subject_key}/ai-questions/{question_id}/raw-response")
def get_ai_question_raw_response(subject_key: str, question_id: int, username: str, db: Session = Depends(get_db)):
    username = (username or "").strip()
    item = db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.id == question_id,
        models.AIGeneratedQuestion.username == username,
        models.AIGeneratedQuestion.subject_key == subject_key,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="AI question not found")
    return {
        "generation_prompt": (item.generation_prompt or "")[:5000],
        "raw_ai_response": (item.raw_ai_response or "")[:10000],
    }


@app.post("/exam/11408/{subject_key}/question-analysis")
def generate_question_analysis(subject_key: str, req: dict):
    """Generate on-demand AI analysis for a question. Not persisted."""
    stem = (req.get("stem") or "").strip()
    opts = req.get("options") or {}
    sa = (req.get("standard_answer") or "").strip()
    ua = (req.get("user_answer") or "").strip()
    qtype = (req.get("question_type") or "选择题").strip()
    ctx = (req.get("context") or "错题复盘").strip()
    subject_name = EXAM_SUBJECT_DIRS.get(subject_key, subject_key)

    if not stem:
        raise HTTPException(status_code=400, detail="stem is required")

    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="AI 解析服务暂不可用（未配置 DEEPSEEK_API_KEY）")

    is_wrong = ua and sa and ua.upper() != sa.upper()
    opts_text = "\n".join([f"{k}. {v}" for k, v in (opts or {}).items()]) if opts else "无选项"
    prompt = f"""你是11408考研辅导老师。请为以下错题生成解析。

科目：{subject_name}
题型：{qtype}
题干：{stem}
选项：{opts_text}
标准答案：{sa}
用户答案：{ua}{'（用户答错）' if is_wrong else ''}

要求：1)指出本题考点 2)说明正确答案为什么正确 3)说明其他选项错误原因 4)给11408复习建议。300字以内。"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role":"user","content":prompt}], temperature=0.4, max_tokens=500)
        analysis = resp.choices[0].message.content.strip()
        return {"analysis": analysis, "generated_at": serialize_datetime(utc_now())}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI 解析生成失败：{str(e)[:200]}")


@app.delete("/exam/11408/{subject_key}/ai-questions/{question_id}")
def delete_exam_ai_question(subject_key: str, question_id: int, username: str, db: Session = Depends(get_db)):
    username = (username or "").strip()
    item = db.query(models.AIGeneratedQuestion).filter(
        models.AIGeneratedQuestion.id == question_id,
        models.AIGeneratedQuestion.username == username,
        models.AIGeneratedQuestion.subject_key == subject_key,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="AI question not found")
    db.delete(item)
    db.commit()
    return {"success": True}


def _serialize_past_paper_wrong_question(item: models.PastPaperWrongQuestion):
    options = {}
    if item.options:
        try:
            options = json.loads(item.options)
        except Exception:
            options = {}
    return {
        "id": item.id,
        "username": item.username,
        "subject_key": item.subject_key,
        "subject_name": EXAM_SUBJECT_DIRS.get(item.subject_key, item.subject_key),
        "source": getattr(item, "source", None) or "past_paper",
        "year": item.year,
        "question_id": item.question_id,
        "number": item.question_number,
        "question_type": item.question_type,
        "stem": item.content,
        "options": options,
        "standard_answer": item.standard_answer,
        "user_answer": item.user_answer,
        "score": item.score,
        "feedback": item.wrong_reason,
        "wrong_reason": item.wrong_reason,
        "attempt_id": item.attempt_id,
        "status": getattr(item, "status", None) or ("mastered" if getattr(item, "mastered", False) else "active"),
        "mastered": bool(getattr(item, "mastered", False)),
        "resolved_at": serialize_datetime(getattr(item, "resolved_at", None)),
        "created_at": serialize_datetime(item.created_at),
        "updated_at": serialize_datetime(getattr(item, "updated_at", None)),
    }


# ── Unified wrong questions (past_paper + exam v2) ──

SOURCE_LABEL_MAP = {"past_paper": "真题错题", "chapter": "章节练习错题", "ai_generated": "AI 出题错题",
                     "chapter_practice": "章节练习错题", "real_exam": "真题错题"}

def _marshal_wrong_item(row, source):
    """Serialize a wrong-question row from either table into a uniform shape."""
    if source == "past_paper":
        opts = {}
        raw_opts = row.options
        if raw_opts:
            try: opts = json.loads(raw_opts)
            except: pass
        return {
            "id": row.id, "username": row.username, "subject_key": row.subject_key,
            "source": "past_paper", "source_label": "真题错题",
            "year": row.year, "question_id": row.question_id, "question_number": row.question_number,
            "question_type": row.question_type, "stem": row.content or "",
            "options": opts, "standard_answer": row.standard_answer or "",
            "user_answer": row.user_answer or "", "score": row.score,
            "wrong_reason": row.wrong_reason, "attempt_id": row.attempt_id,
            "status": row.status or "active", "mastered": bool(getattr(row, "mastered", False)),
            "resolved_at": serialize_datetime(getattr(row, "resolved_at", None)),
            "created_at": serialize_datetime(row.created_at),
            "updated_at": serialize_datetime(getattr(row, "updated_at", None)),
        }
    else:
        # exam_wrong_questions (chapter / ai_generated)
        opts = {}
        try: opts = json.loads(row.options_snapshot_json or "{}")
        except: pass
        return {
            "id": row.id, "username": row.username, "subject_key": row.subject_key,
            "source": row.practice_type or "chapter", "source_label": SOURCE_LABEL_MAP.get(row.practice_type, "章节练习错题"),
            "knowledge_point_id": row.knowledge_point_id, "knowledge_point_name": row.knowledge_point_name,
            "knowledge_point_path": row.knowledge_point_path,
            "question_id": row.question_bank_id, "question_type": row.question_type,
            "stem": row.stem_snapshot or "", "options": opts,
            "standard_answer": row.standard_answer_snapshot or "",
            "user_answer": row.user_answer or "", "score": row.score,
            "wrong_reason": row.wrong_reason, "attempt_id": row.practice_attempt_id,
            "status": row.status or "active", "mastered": bool(getattr(row, "mastered", False)),
            "review_count": getattr(row, "review_count", 0),
            "created_at": serialize_datetime(row.created_at),
            "updated_at": serialize_datetime(getattr(row, "updated_at", None)),
        }


@app.get("/exam/11408/{subject_key}/wrong-questions")
def get_exam_wrong_questions_v2(subject_key: str, username: str, source: str = "", mastered: str = "",
                                 db: Session = Depends(get_db)):
    if subject_key not in EXAM_SUBJECT_DIRS:
        raise HTTPException(status_code=400, detail=f"Unknown subject: {subject_key}")
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    # Parse multi-source filter (comma-separated)
    src_set = set(s.strip() for s in source.split(",") if s.strip()) if source else set()
    # Parse mastered filter: "1"/"true" → mastered only, "0"/"false" → not mastered, "" → all
    m_param = mastered.strip().lower()
    m_filter = None  # None=all, True=mastered, False=not mastered
    if m_param in ("1", "true"): m_filter = True
    elif m_param in ("0", "false"): m_filter = False

    results = []

    # 1. Past paper wrong questions
    if not src_set or "past_paper" in src_set or "real_exam" in src_set:
        q = db.query(models.PastPaperWrongQuestion).filter(
            models.PastPaperWrongQuestion.username == username,
            models.PastPaperWrongQuestion.subject_key == subject_key,
        )
        if m_filter is True: q = q.filter(models.PastPaperWrongQuestion.mastered == True)
        elif m_filter is False: q = q.filter((models.PastPaperWrongQuestion.mastered == False) | (models.PastPaperWrongQuestion.mastered == None))
        for row in q.order_by(models.PastPaperWrongQuestion.created_at.desc()).all():
            results.append(_marshal_wrong_item(row, "past_paper"))

    # 2. v2 exam wrong questions (chapter + ai_generated)
    if not src_set or "chapter" in src_set or "chapter_practice" in src_set or "ai_generated" in src_set:
        q = db.query(models.ExamWrongQuestion).filter(
            models.ExamWrongQuestion.username == username,
            models.ExamWrongQuestion.subject_key == subject_key,
            models.ExamWrongQuestion.status == "active",
        )
        if src_set:
            pt_filters = []
            if "chapter" in src_set or "chapter_practice" in src_set:
                pt_filters.append(models.ExamWrongQuestion.practice_type == "chapter")
            if "ai_generated" in src_set:
                pt_filters.append(models.ExamWrongQuestion.practice_type == "ai_generated")
            if pt_filters:
                if len(pt_filters) == 1: q = q.filter(pt_filters[0])
                else: q = q.filter(or_(*pt_filters))
        if m_filter is True: q = q.filter(models.ExamWrongQuestion.mastered == True)
        elif m_filter is False: q = q.filter((models.ExamWrongQuestion.mastered == False) | (models.ExamWrongQuestion.mastered == None))
        for row in q.order_by(models.ExamWrongQuestion.created_at.desc()).all():
            results.append(_marshal_wrong_item(row, "v2"))

    # Sort merged results by created_at desc
    results.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return {"items": results, "total": len(results)}


@app.delete("/exam/11408/{subject_key}/wrong-questions/{wrong_id}")
def delete_exam_wrong_question_v2(subject_key: str, wrong_id: int, username: str, db: Session = Depends(get_db)):
    username = (username or "").strip()
    # Try past_paper table first
    item = db.query(models.PastPaperWrongQuestion).filter(
        models.PastPaperWrongQuestion.id == wrong_id,
        models.PastPaperWrongQuestion.username == username,
        models.PastPaperWrongQuestion.subject_key == subject_key,
    ).first()
    if item:
        db.delete(item); db.commit()
        return {"success": True, "table": "past_paper"}
    # Try exam_wrong_questions table
    item2 = db.query(models.ExamWrongQuestion).filter(
        models.ExamWrongQuestion.id == wrong_id,
        models.ExamWrongQuestion.username == username,
        models.ExamWrongQuestion.subject_key == subject_key,
    ).first()
    if item2:
        item2.status = "removed"; db.commit()
        return {"success": True, "table": "exam_v2"}
    raise HTTPException(status_code=404, detail="wrong question not found")


@app.patch("/exam/11408/{subject_key}/wrong-questions/{wrong_id}/mastered")
def toggle_exam_wrong_question_mastered(subject_key: str, wrong_id: int, req: dict, db: Session = Depends(get_db)):
    username = (req.get("username") or "").strip()
    mastered_val = req.get("mastered", True)
    now = utc_now()
    # Try past_paper
    item = db.query(models.PastPaperWrongQuestion).filter(
        models.PastPaperWrongQuestion.id == wrong_id,
        models.PastPaperWrongQuestion.username == username,
        models.PastPaperWrongQuestion.subject_key == subject_key,
    ).first()
    if item:
        item.mastered = bool(mastered_val)
        item.status = "mastered" if mastered_val else "active"
        if mastered_val: item.resolved_at = now; item.reviewed_at = now
        item.updated_at = now
        db.commit()
        return {"success": True, "mastered": item.mastered}
    # Try exam_v2
    item2 = db.query(models.ExamWrongQuestion).filter(
        models.ExamWrongQuestion.id == wrong_id,
        models.ExamWrongQuestion.username == username,
        models.ExamWrongQuestion.subject_key == subject_key,
    ).first()
    if item2:
        item2.mastered = bool(mastered_val)
        item2.status = "mastered" if mastered_val else "active"
        if mastered_val: item2.resolved_at = now
        item2.updated_at = now
        db.commit()
        return {"success": True, "mastered": item2.mastered}
    raise HTTPException(status_code=404, detail="wrong question not found")


# ── Done records (已做过) ──

@app.get("/exam/11408/{subject_key}/done-records")
def get_done_records(subject_key: str, username: str, practice_type: str = "", db: Session = Depends(get_db)):
    username = (username or "").strip()
    if not username: raise HTTPException(status_code=400, detail="username required")
    q = db.query(models.ExamQuestionDoneRecord).filter(
        models.ExamQuestionDoneRecord.username == username,
        models.ExamQuestionDoneRecord.subject_key == subject_key,
    )
    if practice_type: q = q.filter(models.ExamQuestionDoneRecord.practice_type == practice_type)
    records = q.all()
    return {"items": [{"question_bank_id": r.question_bank_id, "ai_question_id": r.ai_question_id,
            "practice_type": r.practice_type, "is_correct": r.is_correct,
            "done_count": r.done_count, "last_done_at": serialize_datetime(r.last_done_at),
            "question_type": r.question_type} for r in records]}


def _save_done_record(db, username, subject_key, practice_type, question_bank_id=None,
                       ai_question_id=None, question_type=None, user_answer="", correct_answer="", is_correct=None,
                       attempt_id=None):
    existing = None
    if question_bank_id:
        existing = db.query(models.ExamQuestionDoneRecord).filter(
            models.ExamQuestionDoneRecord.username == username,
            models.ExamQuestionDoneRecord.question_bank_id == question_bank_id,
        ).first()
    if not existing and ai_question_id:
        existing = db.query(models.ExamQuestionDoneRecord).filter(
            models.ExamQuestionDoneRecord.username == username,
            models.ExamQuestionDoneRecord.ai_question_id == ai_question_id,
        ).first()
    if existing:
        existing.done_count = (existing.done_count or 0) + 1
        existing.last_done_at = utc_now()
        existing.user_answer = user_answer
        if is_correct is not None: existing.is_correct = is_correct
        existing.practice_type = practice_type
    else:
        db.add(models.ExamQuestionDoneRecord(
            username=username, subject_key=subject_key, practice_type=practice_type,
            question_bank_id=question_bank_id, ai_question_id=ai_question_id,
            question_type=question_type, user_answer=user_answer, correct_answer=correct_answer,
            is_correct=is_correct, attempt_id=attempt_id, done_count=1))


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
        progress.status = normalize_knowledge_status(req.status)
    progress.updated_at = utc_now()
    progress.last_studied_at = utc_now()

    db.commit()
    db.refresh(progress)

    # Record manual_update event if score changed
    new_score = progress.mastery_score or 0
    if new_score != old_score:
        event = models.KnowledgeProgressEvent(
            username=user.username,
            course_id=point.course_id,
            knowledge_point_id=point_id,
            event_type="manual_update",
            delta=new_score - old_score,
            reason="用户手动调整掌握度",
            source_type="manual",
            created_at=utc_now(),
        )
        db.add(event)
        db.commit()

    return {
        "success": True,
        "progress": {
            "id": progress.id,
            "username": progress.username,
            "course_id": progress.course_id,
            "knowledge_point_id": progress.knowledge_point_id,
            "node_key": getattr(point, "node_key", None) or None,
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


def _parse_learning_path_json(raw: str):
    text_value = (raw or "").strip()
    if text_value.startswith("```"):
        text_value = re.sub(r"^```(?:json)?\s*", "", text_value, flags=re.IGNORECASE).strip()
        text_value = re.sub(r"\s*```$", "", text_value).strip()
    start = text_value.find("{")
    end = text_value.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI 未返回 JSON 对象")
    data = json.loads(text_value[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("AI 返回内容不是 JSON 对象")
    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("JSON 中缺少 modules")
    return data


def _normalize_generated_path(data: dict, subject: str, material_ids: list[int]):
    title = str(data.get("title") or f"基于资料生成的{subject}学习路线").strip()[:255]
    clean_modules = []
    for module_index, module in enumerate(data.get("modules") or []):
        if not isinstance(module, dict):
            continue
        module_title = str(module.get("title") or "").strip()
        if not module_title:
            continue
        points = []
        raw_points = module.get("knowledge_points") or module.get("children") or []
        if isinstance(raw_points, list):
            for point in raw_points[:10]:
                if isinstance(point, str):
                    point = {"title": point}
                if not isinstance(point, dict):
                    continue
                point_title = str(point.get("title") or "").strip()
                if not point_title:
                    continue
                points.append({
                    "title": point_title[:255],
                    "description": str(point.get("description") or "").strip()[:500],
                    "difficulty": str(point.get("difficulty") or "基础").strip()[:50],
                    "estimated_minutes": int(point.get("estimated_minutes") or 20) if str(point.get("estimated_minutes") or "").isdigit() else 20,
                    "source_hint": str(point.get("source_hint") or "").strip()[:255],
                })
        if not points:
            continue
        clean_modules.append({
            "title": module_title[:255],
            "description": str(module.get("description") or "").strip()[:500],
            "order": int(module.get("order") or module_index + 1) if str(module.get("order") or "").isdigit() else module_index + 1,
            "knowledge_points": points,
        })
    if not clean_modules:
        raise ValueError("AI 返回的路线中没有有效知识点")
    return {
        "title": title,
        "subject": subject,
        "source_material_ids": material_ids,
        "modules": clean_modules[:8],
    }


def _replace_material_learning_points(db: Session, username: str, subject: str, modules: list[dict]):
    existing_points = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.username == username,
            models.KnowledgePoint.course_id == subject,
        )
        .all()
    )
    existing_ids = [p.id for p in existing_points]
    if existing_ids:
        db.query(models.UserKnowledgeProgress).filter(
            models.UserKnowledgeProgress.username == username,
            models.UserKnowledgeProgress.knowledge_point_id.in_(existing_ids),
        ).delete(synchronize_session=False)
        db.query(models.MaterialKnowledgeLink).filter(
            models.MaterialKnowledgeLink.username == username,
            models.MaterialKnowledgeLink.course_id == subject,
            models.MaterialKnowledgeLink.knowledge_point_id.in_(existing_ids),
        ).delete(synchronize_session=False)
        db.query(models.KnowledgePoint).filter(
            models.KnowledgePoint.username == username,
            models.KnowledgePoint.id.in_(existing_ids),
        ).delete(synchronize_session=False)
        db.flush()

    created = []
    for module_index, module in enumerate(modules):
        parent = models.KnowledgePoint(
            username=username,
            course_id=subject,
            parent_id=None,
            title=module["title"][:255],
            description=(module.get("description") or "")[:255],
            order_index=module_index,
            level=1,
        )
        db.add(parent)
        db.flush()
        db.add(models.UserKnowledgeProgress(
            username=username,
            course_id=subject,
            knowledge_point_id=parent.id,
            mastery_score=0,
            status="not_started",
            practice_count=0,
            task_count=0,
        ))
        created.append(parent)

        for point_index, point in enumerate(module.get("knowledge_points") or []):
            child = models.KnowledgePoint(
                username=username,
                course_id=subject,
                parent_id=parent.id,
                title=point["title"][:255],
                description=(point.get("description") or "")[:255],
                order_index=point_index,
                level=2,
            )
            db.add(child)
            db.flush()
            db.add(models.UserKnowledgeProgress(
                username=username,
                course_id=subject,
                knowledge_point_id=child.id,
                mastery_score=0,
                status="not_started",
                practice_count=0,
                task_count=0,
            ))
            created.append(child)
    return created


@app.post("/knowledge-path/generate-from-materials")
def generate_knowledge_path_from_materials(
    req: schemas.KnowledgePathGenerateFromMaterialsRequest,
    db: Session = Depends(get_db),
):
    user = get_user_by_username(req.username, db)
    subject = normalize_subject(req.subject, default="")
    if not subject:
        raise HTTPException(status_code=400, detail="subject 不能为空")

    material_ids = []
    for raw_id in req.material_ids or []:
        try:
            material_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if material_id > 0 and material_id not in material_ids:
            material_ids.append(material_id)
    if not material_ids:
        raise HTTPException(status_code=400, detail="请至少选择 1 个资料")

    materials = (
        db.query(models.StudyMaterial)
        .filter(
            models.StudyMaterial.id.in_(material_ids),
            models.StudyMaterial.username == user.username,
            models.StudyMaterial.subject == subject,
            models.StudyMaterial.is_deleted == False,
        )
        .all()
    )
    if len(materials) != len(material_ids):
        raise HTTPException(status_code=400, detail="所选资料不存在，或不属于当前用户/科目")

    chunks = (
        db.query(models.MaterialChunk)
        .filter(
            models.MaterialChunk.material_id.in_(material_ids),
            models.MaterialChunk.username == user.username,
            models.MaterialChunk.subject == subject,
            models.MaterialChunk.is_deleted == False,
        )
        .order_by(models.MaterialChunk.material_id, models.MaterialChunk.chunk_index)
        .all()
    )
    if not chunks:
        raise HTTPException(status_code=400, detail="所选资料暂无知识片段，请先在资料库进行 AI 索引。")

    material_map = {m.id: m for m in materials}
    selected_names = [material_map[mid].original_filename for mid in material_ids if mid in material_map]
    chunk_lines = []
    total_chars = 0
    max_chars = 18000
    per_material_count = defaultdict(int)
    for chunk in chunks:
        if per_material_count[chunk.material_id] >= 12:
            continue
        text_value = (chunk.chunk_summary or chunk.chunk_text or "").strip()
        if not text_value:
            continue
        material = material_map.get(chunk.material_id)
        source_name = material.original_filename if material else chunk.source_filename
        line = f"【{source_name} - 片段 {chunk.chunk_index + 1}】\n{text_value[:1200]}"
        if total_chars + len(line) > max_chars:
            break
        chunk_lines.append(line)
        total_chars += len(line)
        per_material_count[chunk.material_id] += 1

    if not chunk_lines:
        raise HTTPException(status_code=400, detail="所选资料暂无可用知识片段，请先在资料库点击 AI 索引。")

    system_prompt = (
        "你是一个大学课程学习路线规划助手。请根据用户提供的课程资料片段，"
        "为该课程生成结构化学习路线。输出必须是严格 JSON，不要包含 Markdown，不要解释。"
    )
    user_prompt = f"""
课程：{subject}
所选资料：
{chr(10).join(f"- {name}" for name in selected_names)}

资料片段：
{chr(10).join(chunk_lines)}

请生成 JSON：
{{
  "title": "基于资料生成的{subject}学习路线",
  "subject": "{subject}",
  "modules": [
    {{
      "title": "模块标题",
      "description": "模块说明",
      "order": 1,
      "knowledge_points": [
        {{
          "title": "知识点标题",
          "description": "简洁中文说明",
          "difficulty": "基础/中等/进阶",
          "estimated_minutes": 20,
          "source_hint": "来自某资料文件名"
        }}
      ]
    }}
  ]
}}

要求：
1. 拆成 4-8 个大模块。
2. 每个模块包含 3-8 个知识点。
3. 知识点从基础到进阶排序。
4. 标题要短，适合前端卡片展示。
5. 以资料内容为主，不要编造资料中完全没有的章节。
6. 输出严格 JSON，不能包含 ```json。
""".strip()

    try:
        raw = call_deepseek([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        path_data = _normalize_generated_path(
            _parse_learning_path_json(raw),
            subject,
            material_ids,
        )
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=500, detail=f"AI 生成结果解析失败，请重试：{str(exc)}")

    created_points = _replace_material_learning_points(db, user.username, subject, path_data["modules"])

    existing_path = (
        db.query(models.UserLearningPath)
        .filter(
            models.UserLearningPath.username == user.username,
            models.UserLearningPath.subject == subject,
            models.UserLearningPath.path_type == "material",
        )
        .first()
    )
    modules_json = json.dumps(path_data["modules"], ensure_ascii=False)
    material_ids_json = json.dumps(material_ids, ensure_ascii=False)
    if existing_path:
        existing_path.title = path_data["title"]
        existing_path.source_material_ids = material_ids_json
        existing_path.modules_json = modules_json
        existing_path.updated_at = utc_now()
    else:
        db.add(models.UserLearningPath(
            username=user.username,
            subject=subject,
            path_type="material",
            title=path_data["title"],
            source_material_ids=material_ids_json,
            modules_json=modules_json,
        ))

    db.commit()

    return {
        "success": True,
        "message": "已根据所选资料生成学习路线",
        "path": path_data,
        "created_knowledge_point_count": len(created_points),
    }


def serialize_question(q, knowledge_point_title=None):
    return {
        "id": q.id,
        "username": q.username,
        "paper_id": getattr(q, "paper_id", None),
        "question_order": getattr(q, "question_order", None),
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
        "source_style": getattr(q, "source_style", None),
        "imported_from": getattr(q, "imported_from", None),
        "original_file_name": getattr(q, "original_file_name", None),
        "raw_text": getattr(q, "raw_text", None),
        "created_at": serialize_datetime(q.created_at) if q.created_at else None,
        "updated_at": serialize_datetime(q.updated_at) if q.updated_at else None,
    }


def serialize_question_list_item(q, knowledge_point_title=None):
    return {
        "id": q.id,
        "username": q.username,
        "paper_id": getattr(q, "paper_id", None),
        "question_order": getattr(q, "question_order", None),
        "course_id": q.course_id,
        "knowledge_point_id": q.knowledge_point_id,
        "knowledge_point_title": knowledge_point_title,
        "type": q.type,
        "title": q.title,
        "content": q.content,
        "difficulty": q.difficulty,
        "source": q.source,
        "source_style": getattr(q, "source_style", None),
        "imported_from": getattr(q, "imported_from", None),
        "original_file_name": getattr(q, "original_file_name", None),
        "raw_text": getattr(q, "raw_text", None),
        "created_at": serialize_datetime(q.created_at) if q.created_at else None,
        "updated_at": serialize_datetime(q.updated_at) if q.updated_at else None,
    }


def serialize_practice_paper(paper):
    return {
        "id": paper.id,
        "username": paper.username,
        "course_id": paper.course_id,
        "title": paper.title,
        "source_file_name": paper.source_file_name,
        "source_type": paper.source_type,
        "status": paper.status,
        "question_count": paper.question_count or 0,
        "created_at": serialize_datetime(paper.created_at) if paper.created_at else None,
        "updated_at": serialize_datetime(paper.updated_at) if paper.updated_at else None,
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


def is_ai_generated_question_source(source: str | None) -> bool:
    return (source or "").strip() in {"ai", "ai_generated"}


def normalize_practice_answer(value: str | None) -> str:
    text = (value or "").strip().upper()
    text = re.sub(r"^[（(]?\s*([A-Z])\s*[）).、]?.*$", r"\1", text)
    return re.sub(r"[\s,，、;；]+", "", text)


PROGRAMMING_QUESTION_TYPES = {
    "programming",
    "code",
    "coding",
    "code_question",
    "programming_question",
}

PRACTICE_QUESTION_TYPES = {
    "choice",
    "single_choice",
    "multiple_choice",
    "true_false",
    "fill_blank",
    "short_answer",
}


def is_programming_question_type(value: str | None) -> bool:
    return (value or "").strip() in PROGRAMMING_QUESTION_TYPES


@app.get("/practice/questions")
def list_questions(
    username: str,
    course_id: str = "",
    knowledge_point_id: int | None = None,
    type: str = "",
    include_programming: bool = False,
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
    if is_programming_question_type(qtype) and not include_programming:
        return {
            "success": True,
            "questions": [],
            "papers": [],
        }
    if qtype and qtype in PRACTICE_QUESTION_TYPES:
        query = query.filter(models.Question.type == qtype)
    if not include_programming:
        query = query.filter(models.Question.type.notin_(PROGRAMMING_QUESTION_TYPES))
        query = query.filter(or_(models.Question.source.is_(None), models.Question.source != "code_studio"))
    query = query.filter(models.Question.paper_id.is_(None))

    questions = query.order_by(models.Question.updated_at.desc()).all()

    kp_ids = [q.knowledge_point_id for q in questions if q.knowledge_point_id]
    kp_map: dict[int, str] = {}
    if kp_ids:
        kps = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(kp_ids)).all()
        for kp in kps:
            kp_map[kp.id] = kp.title

    question_items = [serialize_question_list_item(q, knowledge_point_title=kp_map.get(q.knowledge_point_id)) for q in questions]

    code_query = db.query(models.CodeChallenge).filter(models.CodeChallenge.username == user.username)
    if normalized_course:
        code_query = code_query.filter(models.CodeChallenge.course_id == normalized_course)
    code_challenges = [] if (knowledge_point_id is not None or not include_programming) else code_query.order_by(models.CodeChallenge.created_at.desc()).limit(100).all()
    code_items = []
    for ch in code_challenges:
        if qtype and qtype != "programming":
            continue
        code_items.append({
            "id": f"code_{ch.id}",
            "raw_id": ch.id,
            "username": ch.username,
            "course_id": ch.course_id,
            "knowledge_point_id": None,
            "knowledge_point_title": ch.knowledge_point or "",
            "type": "programming",
            "title": ch.title,
            "content": ch.description,
            "difficulty": ch.difficulty,
            "source": "code_studio",
            "language": ch.language,
            "practice_url": "codeStudio",
            "created_at": serialize_datetime(ch.created_at) if ch.created_at else None,
            "updated_at": serialize_datetime(ch.created_at) if ch.created_at else None,
        })

    merged_items = sorted(
        question_items + code_items,
        key=lambda item: item.get("updated_at") or item.get("created_at") or "",
        reverse=True,
    )

    paper_query = db.query(models.PracticePaper).filter(models.PracticePaper.username == user.username)
    if normalized_course:
        paper_query = paper_query.filter(models.PracticePaper.course_id == normalized_course)
    papers = [] if qtype or knowledge_point_id is not None else paper_query.order_by(models.PracticePaper.updated_at.desc()).all()

    return {
        "success": True,
        "questions": merged_items,
        "papers": [serialize_practice_paper(p) for p in papers],
    }


@app.post("/practice/submit-result")
def submit_practice_result(req: dict, db: Session = Depends(get_db)):
    """Save practice results to learning_records and update knowledge mastery."""
    username = str(req.get("username", "")).strip()
    if not username:
        raise HTTPException(status_code=400, detail="缺少 username")
    user = get_user_by_username(username, db)
    course_id = str(req.get("course_id", "")).strip() or ""
    task_id = req.get("task_id")
    question_results = req.get("question_results", [])
    if not isinstance(question_results, list) or len(question_results) == 0:
        raise HTTPException(status_code=400, detail="请提供至少一道题的练习结果")
    duration = int(req.get("duration_seconds", 0) or 0)
    source = str(req.get("source", "normal_practice")).strip()

    # Support total_questions / short_answer_count for AI temp practice
    total_all = int(req.get("total_questions", 0) or 0)
    short_answer_count = int(req.get("short_answer_count", 0) or 0)
    if total_all <= 0:
        total_all = len(question_results)

    # Only count auto-graded questions (is_correct is True/False, not None)
    graded_qs = [q for q in question_results if q.get("is_correct") is not None]
    if not graded_qs:
        # Fallback: treat all as graded if no explicit null markers
        graded_qs = question_results
    graded_total = len(graded_qs)
    graded_correct = sum(1 for q in graded_qs if q.get("is_correct"))
    graded_accuracy = round(graded_correct / graded_total * 100, 1) if graded_total > 0 else None

    minutes = max(1, round(duration / 60))
    kp_title = ""; kp_id = None
    for q in graded_qs:
        if q.get("knowledge_point_id"):
            kp_id = q["knowledge_point_id"]
            kp = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id == kp_id).first()
            if kp: kp_title = kp.title
            break
    if not kp_id: kp_id = req.get("knowledge_point_id")
    course_label = course_id or "综合练习"
    kp_label = f" / {kp_title}" if kp_title else ""

    # Build summary
    acc_str = f"{graded_accuracy}%" if graded_accuracy is not None else "未计算"
    if source == "task_ai_temp_practice":
        if graded_total > 0 and total_all > graded_total:
            sa_count = total_all - graded_total
            summary = f"完成 AI 生成临时练习 {total_all} 题，其中自动判分 {graded_total} 题，正确 {graded_correct} 题，正确率 {acc_str}，简答题 {sa_count} 题未自动判分，用时 {minutes} 分钟"
        elif graded_total > 0:
            summary = f"完成 AI 生成临时练习 {total_all} 题，正确 {graded_correct}/{graded_total}（{acc_str}），用时 {minutes} 分钟"
        else:
            summary = f"完成 AI 生成临时练习 {total_all} 题，均为简答题，暂未计算自动正确率，用时 {minutes} 分钟"
    else:
        summary = f"完成{course_label}{kp_label}练习，{graded_total} 题，正确 {graded_correct} 题（{acc_str}），用时 {minutes} 分钟"

    tags_data = {
        "task_id": task_id,
        "source": source,
        "duration_seconds": duration,
        "total": graded_total,
        "correct": graded_correct,
        "accuracy": graded_accuracy,
    }
    if source == "task_ai_temp_practice" or total_all > graded_total or short_answer_count > 0:
        tags_data["total_questions"] = total_all
        tags_data["graded_questions"] = graded_total
        sa = short_answer_count if short_answer_count > 0 else total_all - graded_total
        tags_data["short_answer_count"] = sa

    record = models.LearningRecord(
        user_id=user.id, subject=course_id, session_id=None, message_id=None,
        record_type="practice", question=f"完成{course_label}练习：{total_all} 题",
        answer=f"正确 {graded_correct}/{graded_total}" if graded_total > 0 else f"简答题 {total_all} 题，未自动判分",
        note=summary,
        tags=json.dumps(tags_data, ensure_ascii=False),
        references_json=None, review_status="pending",
    )
    db.add(record); db.commit(); db.refresh(record)

    # Update knowledge mastery (only based on auto-graded questions)
    kp_updates = {}
    for q in graded_qs:
        q_kp_id = q.get("knowledge_point_id")
        if not q_kp_id: continue
        if q_kp_id not in kp_updates: kp_updates[q_kp_id] = {"total": 0, "correct": 0}
        kp_updates[q_kp_id]["total"] += 1
        if q.get("is_correct"): kp_updates[q_kp_id]["correct"] += 1

    if graded_total > 0 and kp_updates:
        for kp_id_key, stats in kp_updates.items():
            acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            prog = db.query(models.UserKnowledgeProgress).filter(
                models.UserKnowledgeProgress.username == user.username,
                models.UserKnowledgeProgress.knowledge_point_id == kp_id_key,
            ).first()
            if not prog:
                prog = models.UserKnowledgeProgress(username=user.username, course_id=course_id, knowledge_point_id=kp_id_key, mastery_score=50, status="learning", practice_count=0, task_count=0)
                db.add(prog); db.flush()
            delta = max(3, min(12, int(acc * 15))) if acc >= 0.8 else (max(3, min(6, int(acc * 8))) if acc >= 0.5 else max(-8, min(-3, int((acc - 0.5) * 10))))
            new_status = "mastered" if (prog.mastery_score or 0) + delta >= 80 else ("improving" if acc >= 0.8 else ("reviewing" if acc >= 0.5 else "weak"))
            prog.mastery_score = max(0, min(100, (prog.mastery_score or 0) + delta))
            prog.status = new_status; prog.practice_count = (prog.practice_count or 0) + stats["total"]
            prog.last_studied_at = utc_now(); prog.updated_at = utc_now()
            evt = models.KnowledgeProgressEvent(username=user.username, course_id=course_id, knowledge_point_id=kp_id_key, event_type="practice_result", delta=delta, reason=f"练习正确率 {int(acc*100)}%，{stats['total']} 题", source_type="task_practice" if task_id else "normal_practice", source_id=record.id)
            db.add(evt)
        db.commit()

    kp_updates_count = len(kp_updates) if graded_total > 0 else 0
    return {
        "success": True,
        "record_id": record.id,
        "summary": summary,
        "total_questions": total_all,
        "graded_questions": graded_total,
        "correct": graded_correct,
        "accuracy": graded_accuracy,
        "short_answer_count": total_all - graded_total,
        "duration_seconds": duration,
        "kp_updates": kp_updates_count,
    }


@app.post("/practice/questions")
def create_question(req: schemas.QuestionCreate, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    qtype = (req.type or "").strip()
    if is_programming_question_type(qtype):
        raise HTTPException(status_code=400, detail="编程题请前往编程中心生成和练习。")
    if qtype not in PRACTICE_QUESTION_TYPES:
        raise HTTPException(status_code=400, detail="无效的题型")
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="题目标题不能为空")
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="题目内容不能为空")

    question = models.Question(
        username=user.username,
        paper_id=req.paper_id,
        question_order=req.question_order,
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
        source_style=(req.source_style or "").strip() or None,
        imported_from=(req.imported_from or "").strip() or None,
        original_file_name=(req.original_file_name or "").strip() or None,
        raw_text=(req.raw_text or "").strip() or None,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return {"success": True, "question": serialize_question(question)}


ALLOWED_SAVE_TYPES = {"single_choice", "multiple_choice", "judge", "short_answer"}


def _ai_options_to_text(options):
    """Convert AI question options [{label, text}] to stored text format."""
    if not options or not isinstance(options, list):
        return ""
    lines = []
    for opt in options:
        if isinstance(opt, dict):
            label = str(opt.get("label", "")).strip()
            text = str(opt.get("text", "")).strip()
            if label and text:
                lines.append(f"{label}. {text}")
    return "\n".join(lines)


def _normalize_judge_answer(ans: str) -> str:
    s = (ans or "").strip()
    if s in ("正确", "对", "true", "True", "yes", "Yes", "是", "T", "Y", "✔", "✓"):
        return "正确"
    if s in ("错误", "错", "false", "False", "no", "No", "否", "F", "N", "✘", "✗"):
        return "错误"
    return s


@app.post("/practice/questions/batch-create-from-ai")
def batch_create_questions_from_ai(req: schemas.AiQuestionBatchCreate, db: Session = Depends(get_db)):
    """Save selected AI-generated questions to the formal question bank with validation and dedup."""
    user = get_user_by_username(req.username, db)
    course_id = normalize_subject(req.course_id)
    if not course_id:
        raise HTTPException(status_code=400, detail="课程不能为空")

    questions = req.questions
    if not isinstance(questions, list) or len(questions) == 0:
        raise HTTPException(status_code=400, detail="请至少提供一道题")

    # Preload existing stems for dedup
    existing_stems = set()
    existing_qs = (
        db.query(models.Question)
        .filter(
            models.Question.username == user.username,
            models.Question.course_id == course_id,
            models.Question.knowledge_point_id == req.knowledge_point_id,
        )
        .all()
    )
    for eq in existing_qs:
        stem = (eq.content or "").strip()
        if stem:
            existing_stems.add(stem)

    created = []
    skipped = 0
    try:
        for idx, q in enumerate(questions):
            if not isinstance(q, dict):
                skipped += 1
                continue

            qtype = str(q.get("type", "")).strip()
            if qtype not in ALLOWED_SAVE_TYPES:
                skipped += 1
                continue

            stem = str(q.get("stem", "")).strip()
            if not stem:
                skipped += 1
                continue

            answer = str(q.get("answer", "")).strip()
            if not answer:
                skipped += 1
                continue

            analysis = str(q.get("analysis", "")).strip()
            if not analysis:
                skipped += 1
                continue

            # Options validation
            options = q.get("options", [])
            if not isinstance(options, list):
                options = []
            if qtype in ("single_choice", "multiple_choice"):
                if len(options) < 2:
                    skipped += 1
                    continue

            # Normalize judge answer
            if qtype == "judge":
                answer = _normalize_judge_answer(answer)

            # Title from stem (first 60 chars)
            title = stem[:60] if len(stem) > 60 else stem

            # Options text
            options_text = _ai_options_to_text(options)

            # Dedup by stem
            if stem in existing_stems:
                skipped += 1
                continue

            question = models.Question(
                username=user.username,
                course_id=course_id,
                knowledge_point_id=req.knowledge_point_id,
                type=qtype,
                title=title,
                content=stem,
                options=options_text or None,
                answer=answer,
                explanation=analysis,
                difficulty="medium",
                source=req.source or "ai_task_preview",
                source_style="mixed",
            )
            db.add(question)
            db.flush()
            existing_stems.add(stem)
            created.append(question)

        db.commit()
        for q in created:
            db.refresh(q)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="批量保存题目失败，请稍后重试。")

    return {
        "success": True,
        "created_count": len(created),
        "skipped_count": skipped,
        "question_ids": [q.id for q in created],
    }


def extract_practice_import_text(
    file_bytes: bytes,
    filename: str,
    content_type: str | None,
    progress_callback=None,
) -> tuple[str, dict]:
    """
    从上传的试卷文件提取文本，返回 (extracted_text, meta)。

    meta 包含：
      - file_type: "pdf" | "image" | "docx" | "txt" | "md"
      - extract_method: "local" | "qwen" | "mixed"
      - qwen_used: bool
      - parse_error: str | None
    """
    suffix = Path(filename or "").suffix.lower()
    meta = {
        "file_type": suffix.lstrip("."),
        "extract_method": "local",
        "qwen_used": False,
        "parse_error": None,
        "total_pages": 0,
        "parsed_pages": 0,
        "page_limit_hit": False,
        "text_length": 0,
        "qwen_pages": 0,
        "qwen_errors": [],
    }

    # ── PDF ──────────────────────────────────────────────────────
    if suffix == ".pdf" or content_type == "application/pdf":
        meta["file_type"] = "pdf"
        # 用 fitz 优先提取（和资料库上传一致）
        try:
            total_pages, page_texts = extract_pdf_pages(file_bytes)
        except HTTPException:
            total_pages, page_texts = 0, []
        meta["total_pages"] = total_pages or get_pdf_total_pages(file_bytes)
        meta["parsed_pages"] = len(page_texts)  # 有文本的页数
        extracted_text = build_pdf_text_from_pages(page_texts).strip()
        meta["extract_method"] = "local"
        meta["text_length"] = len(extracted_text)

        # 文本截断检测
        full_text_len = len(extracted_text)
        if full_text_len > PRACTICE_PAPER_MAX_CHARS:
            meta["page_limit_hit"] = True
        extracted_text = extracted_text[:PRACTICE_PAPER_MAX_CHARS]

        # 优先走本地文本提取；只有文本严重不足时才对扫描页走 Qwen。
        vision_config = get_vision_runtime_config(None)
        if should_use_qwen_for_practice_pdf(extracted_text, meta["total_pages"]):
            if vision_config["vision_enabled"] and vision_config["pdf_scan_parse_enabled"] and is_qwen_enabled():
                pdf_qwen_result = parse_scanned_pdf_with_qwen(
                    file_bytes,
                    progress_callback=progress_callback,
                    page_timeout_seconds=PRACTICE_IMPORT_QWEN_PAGE_TIMEOUT_SECONDS,
                    max_pages_override=vision_config["pdf_scan_max_pages"],
                )
                qwen_text = (pdf_qwen_result.get("text") or "").strip()
                qwen_rendered = pdf_qwen_result.get("rendered_pages", 0)
                meta["qwen_pages"] = int(pdf_qwen_result.get("qwen_pages") or pdf_qwen_result.get("success_pages") or 0)
                meta["qwen_errors"] = pdf_qwen_result.get("errors") or []
                if qwen_text:
                    had_local = bool(extracted_text)
                    extracted_text = merge_pdf_extracted_text(extracted_text, qwen_text)
                    meta["extract_method"] = "mixed" if had_local else "qwen"
                    meta["qwen_used"] = True
                    meta["parsed_pages"] = max(meta["parsed_pages"], qwen_rendered)
                    meta["parse_error"] = build_pdf_qwen_parse_error(
                        pdf_qwen_result, meta["total_pages"]
                    )
                elif qwen_rendered > 0:
                    meta["parse_error"] = build_pdf_qwen_parse_error(
                        pdf_qwen_result, meta["total_pages"]
                    ) or "Qwen 未识别到有效文本"
            else:
                meta["parse_error"] = "PDF 文本提取不足，Qwen 视觉识别未启用"
        meta["text_length"] = len(extracted_text or "")
        return extracted_text.strip(), meta

    # ── Image ────────────────────────────────────────────────────
    if suffix in {".png", ".jpg", ".jpeg", ".webp"} or (content_type or "").startswith("image/"):
        meta["file_type"] = "image"
        meta["total_pages"] = 1
        meta["parsed_pages"] = 1
        local_text = ""
        try:
            local_text = extract_image_text(file_bytes)
        except HTTPException:
            local_text = ""
        meta["extract_method"] = "local" if local_text.strip() else "failed"

        vision_config = get_vision_runtime_config(None)
        if vision_config["vision_enabled"] and should_use_qwen_for_image(local_text) and is_qwen_enabled():
            temp = tempfile.NamedTemporaryFile(suffix=suffix or ".png", delete=False)
            temp_path = temp.name
            try:
                temp.write(file_bytes)
                temp.close()
                result = parse_image_with_qwen(temp_path)
                qwen_text = (result.get("extracted_text") or "").strip()
                if qwen_text:
                    meta["qwen_used"] = True
                    meta["extract_method"] = "mixed" if local_text.strip() else "qwen"
                    return merge_image_extracted_text(local_text, qwen_text).strip()[:PRACTICE_PAPER_MAX_CHARS], meta
            finally:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except OSError:
                    pass
        return local_text.strip()[:PRACTICE_PAPER_MAX_CHARS], meta

    # ── Word / TXT / Markdown ────────────────────────────────────
    from document_parser import extract_supported_file_text
    meta["file_type"] = suffix.lstrip(".") or "doc"
    meta["total_pages"] = 1
    meta["parsed_pages"] = 1
    try:
        result = extract_supported_file_text(file_bytes, filename, content_type)
        return result.get("text", "").strip()[:PRACTICE_PAPER_MAX_CHARS], meta
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def normalize_ai_paper_payload(payload) -> dict:
    """
    把 AI 返回的任意结构统一成：
    {
      "paper_title": str,
      "questions": list[dict]
    }

    兼容格式：
    1. payload 是 list → 当成 questions 数组
    2. payload 是 dict.questions 是 list → 直接使用
    3. payload 是 dict.questions 是 dict → values() 转 list
    4. payload 是 dict.question 是 dict → 包成 [dict]
    5. payload 是 dict.data.questions 存在 → 按上述逻辑递归
    6. payload 是 dict 但无 questions 字段 → 如果像单道题就包成 [payload]
    """
    if isinstance(payload, list):
        return {"paper_title": "", "questions": [item for item in payload if isinstance(item, dict)]}

    if not isinstance(payload, dict):
        return {"paper_title": "", "questions": []}

    # 解包 .data 外层
    if "data" in payload and isinstance(payload["data"], dict):
        inner = payload["data"]
        if "questions" in inner or "question" in inner:
            payload = inner

    paper_title = str(payload.get("paper_title") or "").strip()

    # 提取 questions
    questions = payload.get("questions")
    if isinstance(questions, list):
        pass  # 理想情况
    elif isinstance(questions, dict):
        questions = list(questions.values())
    elif isinstance(payload.get("question"), dict):
        questions = [payload["question"]]
    elif isinstance(payload.get("question"), list):
        questions = payload["question"]
    else:
        # 如果 payload 自己就像一个题目对象（有 content 或 question_text）
        if payload.get("content") or payload.get("question_text") or payload.get("title"):
            questions = [payload]
        else:
            questions = []

    # 确保 questions 里每个元素都是 dict
    questions = [q for q in questions if isinstance(q, dict)]

    return {"paper_title": paper_title, "questions": questions}


def extract_json_from_ai_response(text: str) -> str:
    """
    从 AI 回复中提取 JSON：
    - 去掉 ```json / ``` 包裹
    - 截取第一个 { 或 [ 到最后一个 } 或 ]
    - 返回 JSON 字符串
    """
    text = (text or "").strip()
    # Remove markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    # Find first { or [ to last } or ]
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]
    return text


def repair_invalid_json_escapes(text: str) -> str:
    """
    修复 JSON 字符串里的非法反斜杠转义。
    Python json 只允许：\\\", \\\\, \\/, \\b, \\f, \\n, \\r, \\t, 以及 \\u 开头的 Unicode 转义。

    其他如 \\forall、\\land、\\subset、\\rightarrow 都需要双写为：
    \\\\forall、\\\\land、\\\\subset、\\\\rightarrow
    """
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)


def parse_ai_json_safely(text: str):
    """安全解析 AI 返回的 JSON，自动修复非法转义"""
    raw = extract_json_from_ai_response(text)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as first_error:
        repaired = repair_invalid_json_escapes(raw)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            raise ValueError(
                f"AI 返回的题目 JSON 格式不合法，已尝试修复转义但仍失败：{first_error}"
            ) from first_error


def extract_json_object(text_value: str) -> dict:
    text_value = (text_value or "").strip()
    try:
        parsed = parse_ai_json_safely(text_value)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {}


def format_question_options(raw_options) -> str | None:
    if raw_options is None:
        return None

    # ── 强制确保 raw_options 不是空容器 ──
    if not raw_options:
        return None
    if isinstance(raw_options, (list, dict)) and len(raw_options) == 0:
        return None

    # ── list 格式：[{label, content}, ...] 或 ["A. xxx", ...] ──
    if isinstance(raw_options, list):
        lines = []
        for idx, option in enumerate(raw_options):
            fallback_label = chr(ord("A") + idx)
            if isinstance(option, dict):
                label = str(option.get("label") or fallback_label).strip().rstrip(".、)")
                content = str(option.get("content") or option.get("text") or "").strip()
            else:
                text_option = str(option).strip()
                matched = re.match(r"^([A-H])[\.\、\)]\s*(.+)$", text_option, re.I)
                if matched:
                    label = matched.group(1).upper()
                    content = matched.group(2).strip()
                else:
                    label = fallback_label
                    content = text_option
            if content:
                lines.append(f"{label.upper()}. {content}")
        return "\n".join(lines) if lines else None

    # ── dict 格式：{"A": "...", "B": "...", ...} ──
    if isinstance(raw_options, dict):
        lines = []
        for key in sorted(raw_options.keys()):
            label = str(key).strip().rstrip(".、)")
            content = str(raw_options[key]).strip()
            if content:
                lines.append(f"{label.upper()}. {content}")
        return "\n".join(lines) if lines else None

    # ── string 格式：尝试按 A./A、/A．/(A) 解析 ──
    options_text = str(raw_options).strip()
    if not options_text:
        return None
    option_matches = list(re.finditer(r"(?m)([A-H])[\.\、\)]\s*", options_text))
    if len(option_matches) >= 2:
        lines = []
        for idx, match in enumerate(option_matches):
            start = match.end()
            end = option_matches[idx + 1].start() if idx + 1 < len(option_matches) else len(options_text)
            content = options_text[start:end].strip()
            if content:
                lines.append(f"{match.group(1).upper()}. {content}")
        if lines:
            return "\n".join(lines)
    return options_text


OPTION_PATTERNS = [
    # A. xxx  B. xxx  C. xxx  D. xxx  (English dot)
    re.compile(r'(?:^|\n)([A-D])\.\s*(.+?)(?=\n[A-D]\.\s|\Z)', re.DOTALL),
    # A、xxx  B、xxx  C、xxx  D、xxx  (Chinese comma)
    re.compile(r'(?:^|\n)([A-D])、\s*(.+?)(?=\n[A-D]、\s|\Z)', re.DOTALL),
    # A．xxx  B．xxx  C．xxx  D．xxx  (full-width dot)
    re.compile(r'(?:^|\n)([A-D])．\s*(.+?)(?=\n[A-D]．\s|\Z)', re.DOTALL),
    # (A) xxx  (B) xxx  (C) xxx  (D) xxx
    re.compile(r'\(([A-D])\)\s*(.+?)(?=\([A-D]\)|\Z)', re.DOTALL),
    # A xxx  B xxx  C xxx  D xxx  (bare letter + space, must be at start of lines)
    re.compile(r'(?:^|\n)([A-D])\s+(.+?)(?=\n[A-D]\s|\Z)', re.DOTALL),
]


def detect_options_in_content(content: str) -> tuple[list[dict] | None, str]:
    """
    从题干文本中检测 A/B/C/D 选项并提取。
    返回 (options 数组或 None, 清理后的题干)

    支持的格式：
    A. xxx / A、xxx / A．xxx / (A) xxx / A xxx
    """
    if not content:
        return None, content

    best_options = None
    best_count = 0

    for pattern in OPTION_PATTERNS:
        matches = list(pattern.finditer(content))
        # 需要至少 2 个匹配（可能是判断题）
        if len(matches) < 2:
            continue
        # 去重：同一 label 只取第一个
        seen_labels = set()
        unique_matches = []
        for m in matches:
            label = m.group(1)
            if label not in seen_labels:
                seen_labels.add(label)
                unique_matches.append(m)
        if len(unique_matches) < 2:
            continue
        if len(unique_matches) > best_count:
            best_count = len(unique_matches)
            # 构建 options 数组
            options = []
            for m in unique_matches:
                opt_content = m.group(2).strip()
                if opt_content:
                    options.append({"label": m.group(1), "content": opt_content})
            if len(options) >= 2:
                best_options = options

    if not best_options:
        return None, content

    # 清理题干：移除选项部分
    cleaned = content
    for pattern in OPTION_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()

    # 如果清理后题干变得很短（可能选项就是题干全部），保留原题干
    if len(cleaned) < 10:
        return best_options, content

    return best_options, cleaned


def normalize_paper_draft(item: dict, fallback_course_id: str, fallback_kp_id: int | None = None) -> dict:
    qtype = normalize_question_type(str(item.get("type") or item.get("question_type") or "short_answer"), "short_answer")
    content = str(item.get("question_text") or item.get("content") or "").strip()
    raw_text = str(item.get("raw_text") or content).strip()
    title = str(item.get("title") or content[:32] or "识别题目").strip()

    # 处理选项：优先用 AI 返回的 options，否则从 content 中检测
    ai_options = item.get("options")
    formatted_options = format_question_options(ai_options)

    if not formatted_options:
        # AI 没有返回选项，尝试从题干中检测 A/B/C/D
        detected_opts, cleaned_content = detect_options_in_content(content)
        if detected_opts:
            formatted_options = format_question_options(detected_opts)
            content = cleaned_content
            # 如果检测到 4 个选项且类型为 short_answer，改为 choice
            if qtype in ("short_answer", "unknown") and len(detected_opts) >= 2:
                qtype = "choice" if len(detected_opts) <= 4 else "multiple_choice"

    return {
        "question_order": item.get("question_order") or item.get("order"),
        "title": title[:255],
        "question_text": content,
        "type": qtype,
        "options": formatted_options,
        "answer": str(item.get("answer") or "").strip() or None,
        "explanation": str(item.get("explanation") or "").strip() or None,
        "score": str(item.get("score") or "").strip() or None,
        "course_id": normalize_subject(str(item.get("course_id") or fallback_course_id), default=""),
        "knowledge_point_id": item.get("knowledge_point_id") or fallback_kp_id,
        "difficulty": normalize_question_difficulty(str(item.get("difficulty") or "medium"), "medium"),
        "source": "paper_import",
        "confidence": item.get("confidence", None),
        "source_style": "exam",
        "raw_text": raw_text,
    }


def build_practice_paper_prompt(
    extract_meta: dict,
    course_norm: str,
    original_filename: str,
    extracted_text: str,
) -> str:
    truncation_note = ""
    if extract_meta.get("page_limit_hit"):
        truncation_note = "\n注意：试卷文本较长，已被截断。请基于已有内容尽可能多地提取题目。"

    return f"""请从以下试卷文本中识别题目，并只输出严格 JSON 对象。本试卷共 {extract_meta.get('total_pages', '?')} 页，已提取 {extract_meta.get('parsed_pages', '?')} 页。

输出格式：
{{
  "paper_title": "从文本中提取的试卷标题",
  "course": "{course_norm or '未指定'}",
  "questions": [
    {{
      "question_order": 1,
      "type": "single_choice|multiple_choice|true_false|fill_blank|short_answer|programming|unknown",
      "title": "简短标题",
      "content": "完整题干，保留函数签名/输入输出/样例/代码/表格/公式",
      "score": "分值（如10%）",
      "options": [{{"label": "A", "content": "选项内容"}}],
      "answer": "",
      "explanation": "",
      "knowledge_point": "",
      "difficulty": "easy|medium|hard",
      "raw_text": "原始识别文本（保留完整题面，包括题号/分值/说明）"
    }}
  ]
}}

识别规则（重要）：
1. 必须尽可能多地提取整份试卷的所有题目，包括选择题、填空题、简答题、编程题、证明题。
2. 不要只提取前几道题；整份文本里识别到的每道题都要提取。
3. 每道题保留完整题干，不要删减、概括或改写。
4. 编程题必须保留函数签名、输入输出格式、样例、要求、main 函数说明，type 用 programming。
5. 如果题目有多个小问 (1)(2)(3)，小问之间用换行分隔，保留在 content 中。
6. 检测到 A./A、/A．/(A) 等选项时，拆成 options 数组。
7. 如果题目有分值标注（如 10%），填入 score 字段。
8. 没有答案或解析时留空，不要编造。
9. 每道题必须保留 raw_text 方便二次编辑。
10. 字符串反斜杠必须双写（\\n、\\forall 等），确保合法 JSON。
11. 只输出 JSON 对象，不用 Markdown 代码块。
{truncation_note}

试卷文件名：{original_filename}
文本：
{extracted_text[:PRACTICE_PAPER_MAX_CHARS]}"""


def structure_practice_paper_text(
    extracted_text: str,
    extract_meta: dict,
    original_filename: str,
    course_norm: str,
    knowledge_point_id: int | None,
    username: str | None = None,
    db: Session | None = None,
    log_prefix: str = "[practice-paper-import]",
) -> tuple[dict, float]:
    prompt = build_practice_paper_prompt(extract_meta, course_norm, original_filename, extracted_text)
    paper_title = Path(original_filename).stem or "导入试卷"
    try:
        if username and db:
            user = get_user_by_username(username, db)
            if is_exam_408_context(course_norm, ""):
                check_exam_408_usage_limit(user, "question_generate", db)
            else:
                check_usage_limit(username, "question_generate", db)
        logger.info("%s deepseek start input_text_len=%d", log_prefix, len(extracted_text[:PRACTICE_PAPER_MAX_CHARS]))
        t_deepseek = time.perf_counter()
        raw = call_deepseek([
            {"role": "system", "content": "你是试卷题目结构化识别助手，只输出 JSON 对象。"},
            {"role": "user", "content": prompt},
        ], timeout_seconds=PRACTICE_IMPORT_DEEPSEEK_TIMEOUT_SECONDS)
        t_deepseek_elapsed = time.perf_counter() - t_deepseek
        logger.info("%s deepseek done elapsed=%.2fs output_len=%d", log_prefix, t_deepseek_elapsed, len(raw))
        if username and db:
            record_ai_usage(
                username,
                "question_generate",
                db,
                estimated_tokens=estimate_tokens_from_text(raw),
                status="success",
            )

        parsed_object = extract_json_object(raw)
        if parsed_object:
            normalized = normalize_ai_paper_payload(parsed_object)
        else:
            normalized = normalize_ai_paper_payload(extract_json_array(raw))
        paper_title = str(normalized.get("paper_title") or paper_title).strip()
        parsed = normalized.get("questions") or []
    except json.JSONDecodeError as exc:
        logger.exception("%s JSON decode failed", log_prefix)
        if username and db:
            record_ai_usage(username, "question_generate", db, status="failed", error_message=str(exc))
        raise ValueError(
            f"试卷题目识别失败，AI 返回了包含公式或特殊符号的内容导致解析失败。请重试，或先上传文字版 PDF/TXT。错误详情：{exc}"
        ) from exc
    except HTTPException as exc:
        elapsed = time.perf_counter() - locals().get("t_deepseek", time.perf_counter())
        if elapsed >= PRACTICE_IMPORT_DEEPSEEK_TIMEOUT_SECONDS - 1:
            raise ValueError("AI 结构化题目超时，请减少页数后重试。") from exc
        raise
    except Exception as exc:
        logger.exception("%s unexpected error", log_prefix)
        if username and db:
            record_ai_usage(username, "question_generate", db, status="failed", error_message=str(exc))
        raise

    drafts = [normalize_paper_draft(item, course_norm, knowledge_point_id) for item in parsed if isinstance(item, dict)]
    drafts = [item for item in drafts if item["question_text"]]
    if not drafts:
        raise ValueError("未识别到可导入的题目草稿")

    total_pages = extract_meta.get("total_pages", 0) or 0
    parsed_pages = extract_meta.get("parsed_pages", 0) or 0
    warnings: list[str] = []
    if len(drafts) <= 2 and total_pages > 2:
        warnings.append(f"识别题目数量较少（{len(drafts)} 道），原试卷共 {total_pages} 页，可能未完整识别整份试卷。")
    if extract_meta.get("page_limit_hit"):
        warnings.append(f"试卷文本较长，当前仅使用了前 {PRACTICE_PAPER_MAX_CHARS} 字符。可减小文件或提高限制后重新识别。")
    if parsed_pages > 0 and total_pages > 0 and parsed_pages < total_pages:
        warnings.append(f"当前仅识别了前 {parsed_pages} / {total_pages} 页，如需识别全卷可重新上传。")

    message_parts = [f"已识别 {len(drafts)} 道题目草稿"]
    if total_pages > 0:
        message_parts.append(f"（{parsed_pages}/{total_pages} 页）")

    return {
        "success": True,
        "paper_title": paper_title,
        "original_file_name": original_filename,
        "drafts": drafts,
        "message": "".join(message_parts),
        "extract_meta": {
            **extract_meta,
            "deepseek_input_length": len(extracted_text[:PRACTICE_PAPER_MAX_CHARS]),
        },
        "deepseek_input_length": len(extracted_text[:PRACTICE_PAPER_MAX_CHARS]),
        "warnings": warnings if warnings else None,
    }, t_deepseek_elapsed


# ── Async Paper Import Job ──────────────────────────────────────

def practice_job_elapsed_seconds(job: models.PracticeImportJob) -> int:
    start_at = job.started_at or job.created_at
    if not start_at:
        return 0
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=timezone.utc)
    return max(0, int((utc_now() - start_at).total_seconds()))


def fail_practice_import_job(db: Session, job: models.PracticeImportJob, error_message: str):
    job.status = "failed"
    job.error_message = (error_message or "试卷识别失败")[:2000]
    job.progress_message = "识别失败"
    job.finished_at = utc_now()
    job.updated_at = utc_now()
    db.commit()


def ensure_practice_import_job_not_timed_out(db: Session, job: models.PracticeImportJob, stage: str = ""):
    elapsed = practice_job_elapsed_seconds(job)
    if elapsed > PRACTICE_IMPORT_JOB_TIMEOUT_SECONDS:
        message = "试卷识别超时，请减少页数、上传文字版 PDF，或稍后重试。"
        if stage:
            message = f"{message} 超时阶段：{stage}"
        fail_practice_import_job(db, job, message)
        raise TimeoutError(message)


def run_practice_import_job(job_id: int):
    """后台任务：执行试卷识别全流程，更新 job 状态"""
    db = SessionLocal()
    t_start = time.perf_counter()
    try:
        job = db.query(models.PracticeImportJob).filter(models.PracticeImportJob.id == job_id).first()
        if not job:
            logger.error("[practice-import-job] job_id=%s not found", job_id)
            return

        job.status = "processing"
        job.started_at = utc_now()
        job.progress_message = "正在提取试卷文本"
        job.updated_at = utc_now()
        db.commit()
        logger.info("[practice-import-job] start job_id=%s file=%s size=%s", job_id, job.filename, job.file_size)

        file_path = job.file_path
        if not file_path or not Path(file_path).exists():
            raise FileNotFoundError(f"上传文件不存在：{file_path}")

        file_bytes = Path(file_path).read_bytes()
        original_filename = job.filename or "未命名试卷"

        # Phase 1: 文本提取
        t_extract = time.perf_counter()
        job.progress_message = "正在提取试卷文本"
        job.updated_at = utc_now()
        db.commit()

        def update_qwen_progress(page_index: int, page_count: int):
            ensure_practice_import_job_not_timed_out(db, job, "Qwen 视觉识别")
            job.progress_message = f"正在进行 Qwen 视觉识别：第 {page_index} / {page_count} 页"
            job.parsed_pages = max(job.parsed_pages or 0, page_index - 1)
            job.updated_at = utc_now()
            db.commit()

        extracted_text, extract_meta = extract_practice_import_text(
            file_bytes,
            original_filename,
            "application/pdf",
            progress_callback=update_qwen_progress,
        )
        t_extract_elapsed = time.perf_counter() - t_extract
        logger.info("[practice-import-job] extract done job_id=%s elapsed=%.2fs method=%s qwen=%s",
                    job_id, t_extract_elapsed, extract_meta.get("extract_method"), extract_meta.get("qwen_used"))

        job.text_length = len(extracted_text or "")
        job.parse_method = extract_meta.get("extract_method", "local")
        job.total_pages = extract_meta.get("total_pages", 0) or 0
        job.parsed_pages = extract_meta.get("parsed_pages", 0) or 0
        job.page_limit_hit = bool(extract_meta.get("page_limit_hit"))
        job.qwen_pages = int(extract_meta.get("qwen_pages") or 0)
        job.deepseek_input_length = len((extracted_text or "")[:PRACTICE_PAPER_MAX_CHARS])
        job.updated_at = utc_now()
        ensure_practice_import_job_not_timed_out(db, job, "文本提取")
        if extract_meta.get("qwen_used"):
            job.progress_message = "Qwen 视觉识别完成，正在 AI 结构化题目"
            db.commit()

        if len(extracted_text.strip()) < 30:
            raise ValueError(f"未能从文件中提取足够文本。{extract_meta.get('parse_error') or ''}".strip())

        # Phase 2: DeepSeek 结构化
        course_norm = normalize_subject(job.course_id or "", default="")
        job.progress_message = "正在 AI 结构化题目"
        job.updated_at = utc_now()
        db.commit()
        ensure_practice_import_job_not_timed_out(db, job, "AI 结构化题目")
        result_data, t_ds_elapsed = structure_practice_paper_text(
            extracted_text=extracted_text,
            extract_meta=extract_meta,
            original_filename=original_filename,
            course_norm=course_norm,
            knowledge_point_id=job.knowledge_point_id,
            username=job.username,
            db=db,
            log_prefix="[practice-import-job]",
        )
        ensure_practice_import_job_not_timed_out(db, job, "AI 结构化题目")
        drafts = result_data.get("drafts") or []

        # Phase 5: 成功
        job.status = "succeeded"
        job.progress_message = "识别完成"
        job.question_count = len(drafts)
        job.deepseek_input_length = int(result_data.get("deepseek_input_length") or job.deepseek_input_length or 0)
        job.result_json = json.dumps(result_data, ensure_ascii=False)
        job.finished_at = utc_now()
        job.updated_at = utc_now()
        db.commit()

        t_total = time.perf_counter() - t_start
        logger.info("[practice-import-job] succeeded job_id=%s total=%.2fs extract=%.2fs ds=%.2fs questions=%s",
                    job_id, t_total, t_extract_elapsed, t_ds_elapsed, len(drafts))

    except Exception as exc:
        logger.exception("[practice-import-job] failed job_id=%s", job_id)
        try:
            job = db.query(models.PracticeImportJob).filter(models.PracticeImportJob.id == job_id).first()
            if job:
                fail_practice_import_job(db, job, str(exc))
        except Exception:
            pass
    finally:
        db.close()


@app.post("/practice/import-paper/jobs")
async def create_practice_import_job(
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    course_id: str = Form(""),
    course: str = Form(""),
    module_id: str | None = Form(None),
    knowledge_point_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    file_bytes = await file.read()
    original_filename = Path(file.filename or "未命名试卷").name
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大，当前最大支持 50MB")
    suffix = Path(original_filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md", ".markdown", ".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="仅支持 PDF、图片、Word(docx)、TXT、Markdown 文件")

    # 保存文件
    file_id = secrets.token_hex(6)
    stored_name = f"{int(time.time())}_{file_id}_{original_filename}"
    stored_path = PRACTICE_IMPORT_ROOT / stored_name
    stored_path.write_bytes(file_bytes)

    # 创建 job
    job = models.PracticeImportJob(
        username=user.username,
        course_id=normalize_subject(course_id or course, default="") or "",
        module_id=(module_id or "").strip() or None,
        knowledge_point_id=knowledge_point_id,
        filename=original_filename,
        file_path=str(stored_path),
        file_size=len(file_bytes),
        status="pending",
        progress_message="任务已创建，等待识别",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info("[practice-import-job] created job_id=%s file=%s size=%s", job.id, original_filename, len(file_bytes))

    # 启动后台任务
    background_tasks.add_task(run_practice_import_job, job.id)

    return {
        "job_id": job.id,
        "status": "pending",
        "message": "试卷识别任务已创建",
    }


@app.get("/practice/import-paper/jobs/{job_id}")
def get_practice_import_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(models.PracticeImportJob).filter(models.PracticeImportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="识别任务不存在")

    if job.status in {"pending", "processing"}:
        elapsed = practice_job_elapsed_seconds(job)
        if elapsed > PRACTICE_IMPORT_JOB_TIMEOUT_SECONDS:
            fail_practice_import_job(
                db,
                job,
                "试卷识别超时，请减少页数、上传文字版 PDF，或稍后重试。",
            )
            db.refresh(job)

    result = None
    if job.status == "succeeded" and job.result_json:
        try:
            result = json.loads(job.result_json)
        except Exception:
            result = None

    return {
        "job_id": job.id,
        "status": job.status,
        "progress_message": job.progress_message,
        "parse_method": job.parse_method,
        "module_id": job.module_id,
        "total_pages": job.total_pages or 0,
        "parsed_pages": job.parsed_pages or 0,
        "page_limit_hit": bool(job.page_limit_hit),
        "elapsed_seconds": practice_job_elapsed_seconds(job),
        "text_length": job.text_length or 0,
        "qwen_pages": job.qwen_pages or 0,
        "deepseek_input_length": job.deepseek_input_length or 0,
        "question_count": job.question_count or 0,
        "error_message": job.error_message,
        "result": result,
        "created_at": serialize_datetime(job.created_at),
    }


@app.post("/practice/import-paper/parse")
async def parse_practice_paper(
    username: str = Form(...),
    course_id: str = Form(""),
    knowledge_point_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    t_start = time.perf_counter()
    user = get_user_by_username(username, db)
    file_bytes = await file.read()
    original_filename = file.filename or "未命名试卷"
    logger.info("[practice-paper-import] start user=%s file=%s size=%d course=%s",
                username, original_filename, len(file_bytes), course_id)
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大，当前最大支持 20MB")
    suffix = Path(original_filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt", ".md", ".markdown", ".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="仅支持 PDF、图片、Word(docx)、TXT、Markdown 文件")

    t_extract = time.perf_counter()
    extracted_text, extract_meta = extract_practice_import_text(file_bytes, original_filename, file.content_type)
    t_extract_elapsed = time.perf_counter() - t_extract
    logger.info("[practice-paper-import] extracted_text_len=%d method=%s qwen_used=%s pages=%d/%d elapsed=%.2fs",
                len((extracted_text or "").strip()), extract_meta.get("extract_method", "?"),
                extract_meta.get("qwen_used", False),
                extract_meta.get("parsed_pages", 0), extract_meta.get("total_pages", 0),
                t_extract_elapsed)
    if len((extracted_text or "").strip()) < 30:
        parse_error = extract_meta.get("parse_error") or ""
        hint = f"（{parse_error}）" if parse_error else ""
        raise HTTPException(
            status_code=400,
            detail=f"未能从文件中提取足够文本，请上传更清晰的试卷文件。{hint}".strip(),
        )

    try:
        result, t_deepseek_elapsed = structure_practice_paper_text(
            extracted_text=extracted_text,
            extract_meta=extract_meta,
            original_filename=original_filename,
            course_norm=normalize_subject(course_id, default=""),
            knowledge_point_id=knowledge_point_id,
            username=user.username,
            db=db,
            log_prefix="[practice-paper-import]",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"试卷题目识别失败：{str(exc)}") from exc

    t_total = time.perf_counter() - t_start
    logger.info("[practice-paper-import] done total_elapsed=%.2fs question_count=%d extract=%.2fs deepseek=%.2fs",
                t_total, len(result.get("drafts") or []), t_extract_elapsed, t_deepseek_elapsed)
    return result


@app.post("/practice/import-paper/confirm")
def confirm_practice_paper_import(req: schemas.PaperImportConfirmRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    course_norm = normalize_subject(req.course_id, default="")
    created = []
    selected_drafts = [draft for draft in req.questions[:50] if (draft.question_text or "").strip()]
    if not selected_drafts:
        raise HTTPException(status_code=400, detail="没有可导入的题目")
    paper = models.PracticePaper(
        username=user.username,
        course_id=course_norm or normalize_subject(selected_drafts[0].course_id, default="") or None,
        title=(req.paper_title or req.original_file_name or "导入试卷")[:255],
        source_file_name=(req.original_file_name or "").strip() or None,
        source_type="paper_upload",
        status="imported",
        question_count=len(selected_drafts),
    )
    db.add(paper)
    db.flush()
    for idx, draft in enumerate(selected_drafts, start=1):
        content = (draft.question_text or "").strip()
        question = models.Question(
            username=user.username,
            paper_id=paper.id,
            question_order=draft.question_order or idx,
            course_id=normalize_subject(draft.course_id or course_norm, default="") or None,
            knowledge_point_id=draft.knowledge_point_id,
            type=normalize_question_type(draft.type, "short_answer"),
            title=(draft.title or content[:32] or "试卷识别题目")[:255],
            content=content,
            options=(draft.options or "").strip() or None,
            answer=(draft.answer or "").strip() or None,
            explanation=(draft.explanation or "").strip() or None,
            difficulty=normalize_question_difficulty(draft.difficulty, "medium"),
            source="paper_import",
            source_style=draft.source_style or "exam",
            imported_from="paper_upload",
            original_file_name=(req.original_file_name or "").strip() or None,
            raw_text=(draft.raw_text or content).strip() or None,
        )
        db.add(question)
        created.append(question)
    if not created:
        raise HTTPException(status_code=400, detail="没有可导入的题目")
    db.commit()
    db.refresh(paper)
    for q in created:
        db.refresh(q)
    return {
        "success": True,
        "paper": serialize_practice_paper(paper),
        "questions": [serialize_question(q) for q in created],
        "message": f"已导入 {len(created)} 道题目",
    }


@app.get("/practice/papers")
def list_practice_papers(
    username: str,
    course_id: str = "",
    db: Session = Depends(get_db),
):
    user = get_user_by_username(username, db)
    query = db.query(models.PracticePaper).filter(models.PracticePaper.username == user.username)
    normalized_course = normalize_subject(course_id, default="")
    if normalized_course:
        query = query.filter(models.PracticePaper.course_id == normalized_course)
    papers = query.order_by(models.PracticePaper.updated_at.desc()).all()
    return {"success": True, "papers": [serialize_practice_paper(p) for p in papers]}


@app.get("/practice/papers/{paper_id}")
def get_practice_paper(paper_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    paper = (
        db.query(models.PracticePaper)
        .filter(models.PracticePaper.id == paper_id, models.PracticePaper.username == user.username)
        .first()
    )
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    questions = (
        db.query(models.Question)
        .filter(models.Question.paper_id == paper.id, models.Question.username == user.username)
        .order_by(models.Question.question_order.asc(), models.Question.id.asc())
        .all()
    )
    kp_ids = [q.knowledge_point_id for q in questions if q.knowledge_point_id]
    kp_map: dict[int, str] = {}
    if kp_ids:
        for kp in db.query(models.KnowledgePoint).filter(models.KnowledgePoint.id.in_(kp_ids)).all():
            kp_map[kp.id] = kp.title
    return {
        "success": True,
        "paper": serialize_practice_paper(paper),
        "questions": [serialize_question(q, knowledge_point_title=kp_map.get(q.knowledge_point_id)) for q in questions],
    }


@app.delete("/practice/papers/{paper_id}")
def delete_practice_paper(paper_id: int, username: str, db: Session = Depends(get_db)):
    user = get_user_by_username(username, db)
    paper = (
        db.query(models.PracticePaper)
        .filter(models.PracticePaper.id == paper_id, models.PracticePaper.username == user.username)
        .first()
    )
    if not paper:
        raise HTTPException(status_code=404, detail="试卷不存在")
    questions = db.query(models.Question).filter(models.Question.paper_id == paper.id, models.Question.username == user.username).all()
    for q in questions:
        db.query(models.QuestionAttempt).filter(models.QuestionAttempt.question_id == q.id).delete()
        db.delete(q)
    db.delete(paper)
    db.commit()
    return {"success": True, "message": "试卷已删除"}


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

    updated_fields = getattr(req, "model_fields_set", getattr(req, "__fields_set__", set()))

    if "type" in updated_fields:
        new_type = (req.type or "").strip()
        if new_type not in ("choice", "single_choice", "multiple_choice", "true_false", "fill_blank", "short_answer", "programming", "unknown"):
            raise HTTPException(status_code=400, detail="无效的题型")
        question.type = new_type
    if "title" in updated_fields:
        question.title = (req.title or "").strip()[:255]
    if "content" in updated_fields:
        question.content = (req.content or "").strip()
    if "options" in updated_fields:
        if isinstance(req.options, list):
            option_lines = []
            for idx, option in enumerate(req.options):
                fallback_label = chr(ord("A") + idx)
                if isinstance(option, dict):
                    label = str(option.get("label") or fallback_label).strip().rstrip(".、)")
                    content = str(option.get("content") or option.get("text") or "").strip()
                else:
                    label = fallback_label
                    content = str(option or "").strip()
                if content:
                    option_lines.append(f"{label.upper()}. {content}")
            question.options = "\n".join(option_lines) or None
        else:
            question.options = (req.options or "").strip() or None
    if "answer" in updated_fields:
        question.answer = (req.answer or "").strip() or None
    if "explanation" in updated_fields:
        question.explanation = (req.explanation or "").strip() or None
    if "difficulty" in updated_fields:
        question.difficulty = (req.difficulty or "").strip() or None
    if "question_order" in updated_fields and req.question_order is not None:
        question.question_order = req.question_order
    if "raw_text" in updated_fields:
        question.raw_text = (req.raw_text or "").strip() or None
    if "course_id" in updated_fields:
        question.course_id = normalize_subject(req.course_id, default="") or None
    if "knowledge_point_id" in updated_fields:
        question.knowledge_point_id = req.knowledge_point_id

    question.updated_at = utc_now()
    db.commit()
    db.refresh(question)
    return {"success": True, "question": serialize_question(question)}


@app.post("/practice/questions/{question_id}/ai-explain")
def explain_practice_question(question_id: int, req: schemas.QuestionAiExplainRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    question = (
        db.query(models.Question)
        .filter(models.Question.id == question_id, models.Question.username == user.username)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    if is_ai_generated_question_source(question.source):
        return {
            "success": True,
            "question_id": question.id,
            "answer": question.answer or "",
            "analysis": question.explanation or "",
            "explanation": question.explanation or "",
            "source": "question_analysis",
            "question": serialize_question(question),
        }

    prompt = f"""请为下面这道练习题生成清晰解析。若题目没有标准答案，可以给出"参考解析"，不要编造唯一答案。
请输出 JSON 对象：{{"explanation":"...", "answer":"可选，仅当能从题目推理出参考答案时填写"}}

课程：{question.course_id or "未指定"}
知识点 ID：{question.knowledge_point_id or "未指定"}
题型：{question.type}
题目：{question.title}
题干：
{question.content}
选项：
{question.options or "无"}
已有答案：
{question.answer or "无"}
已有解析：
{question.explanation or "无"}
"""
    prompt = f"""请为下面这道练习题生成清晰解析。若题目没有标准答案，可以给出"参考解析"，不要编造唯一答案。
请输出 JSON 对象：{{"explanation":"...", "answer":"可选，仅当能从题目推理出参考答案时填写"}}

课程：{question.course_id or "未指定"}
知识点 ID：{question.knowledge_point_id or "未指定"}
题型：{question.type}
题目：{question.title}
题干：
{question.content}
选项：
{question.options or "无"}
已有答案：
{question.answer or "无"}
已有解析：
{question.explanation or "无"}
"""
    check_usage_limit(user.username, "question_feedback", db)
    try:
        raw = call_deepseek([
            {"role": "system", "content": "你是练习题解析助手，输出严格 JSON 对象。"},
            {"role": "user", "content": prompt},
        ])
        record_ai_usage(user.username, "question_feedback", db, estimated_tokens=estimate_tokens_from_text(raw), status="success")
    except Exception as exc:
        record_ai_usage(user.username, "question_feedback", db, status="failed", error_message=str(exc))
        raise HTTPException(status_code=500, detail=f"AI 解析失败：{str(exc)}") from exc

    parsed = extract_json_object(raw)
    raw_explanation = str(parsed.get("explanation") or raw).strip()
    explanation = clean_question_analysis(raw_explanation)
    if contains_internal_reasoning(raw_explanation) or len(raw_explanation) > 1200:
        refined_explanation = refine_question_analysis_with_ai(
            raw_explanation,
            question.content or "",
            question.answer or "",
        )
        if refined_explanation:
            explanation = clean_question_analysis(refined_explanation)
    if contains_internal_reasoning(explanation):
        explanation = "解析暂未生成完整内容，请结合参考答案复习相关知识点，并重点回顾题目涉及的核心概念。"
    suggested_answer = str(parsed.get("answer") or "").strip()
    if explanation:
        question.explanation = explanation
    if suggested_answer and not (question.answer or "").strip():
        question.answer = suggested_answer
    question.updated_at = utc_now()
    db.commit()
    db.refresh(question)
    return {
        "success": True,
        "question_id": question.id,
        "explanation": question.explanation,
        "answer": question.answer,
        "question": serialize_question(question),
    }


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
    if question.type in {"choice", "single_choice", "multiple_choice", "true_false"} and question.answer:
        ua = normalize_practice_answer(req.user_answer)
        ca = normalize_practice_answer(question.answer)
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

    if is_ai_generated_question_source(question.source):
        raise HTTPException(
            status_code=400,
            detail="AI生成题目已包含参考答案和解析，无需再次生成AI反馈。",
        )

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


GENERATE_QUESTION_PROMPT = """你是一名计算机课程题库命题专家。请参考经典计算机学习题型的结构，生成原创题，严禁复制或改写任何网站/教材原题。

通用要求：
1. 题目必须围绕指定课程、知识点、题型、难度和风格生成。
2. 即使是简单题，也要包含小判断、小计算、代码阅读或应用场景。
3. 中等难度至少需要 2 步推理；困难至少需要 3 步推理，并给出详细解析。
4. 解析不少于 30 个中文字符，要讲清思路、关键步骤和易错点。
5. 简答题/填空题/判断题可以不包含 options 字段。
6. 不要生成过于简单的概念背诵题。
7. analysis 字段必须是面向学生的正式解析，只保留最终有效解题步骤。
8. analysis 禁止包含 AI 的内部思考过程、自我纠错、反复试算、草稿推理、对选项或题目设计的怀疑。
9. analysis 禁止出现"我认为""我可能""我怀疑""让我重新""重新检查""重新计算""前面算错""这里有点乱""鉴于时间""为了配合选项""选项不匹配""无法匹配"等表达。
10. analysis 应该包含核心知识点、必要计算步骤、正确答案成立原因；必要时简要说明干扰项为什么不选。
11. analysis 语言必须简洁、确定、教学化，适合学生复习。
12. 练习中心不生成 programming/code/coding 编程题；涉及代码阅读或算法分析时，也必须使用 choice、multiple_choice、fill_blank 或 short_answer 题型。

输出格式（必须严格遵守）:
你必须只输出一个 JSON 对象，不要输出任何其他文字、注释或 Markdown 标记。

输出示例:
{
  "questions": [
    {
      "type": "short_answer",
      "difficulty": "hard",
      "stem": "完整的题面内容，必要时包含代码/表格/样例",
      "title": "题目标题",
      "options": [],
      "answer": "参考答案",
      "analysis": "正式解析，只保留有效步骤，不包含 AI 思考草稿。",
      "knowledge_point": "知识点名称",
      "source": "ai_generated",
      "source_style": "mixed"
    }
  ]
}

重要提示:
- 最外层必须包含 "questions" 键，其值为题目对象数组。
- 选择题/多选题必须有 options 数组，每个选项如 {"label": "A", "content": "...", "is_correct": false}
- 简答题/填空题/判断题 options 可以为空数组 []。
- 不要输出 Markdown 代码块，只输出纯 JSON。
- 不要输出任何解释、注释文字。"""


QUESTION_TYPE_ALIASES = {
    "choice": "choice",
    "single_choice": "choice",
    "multiple_choice": "multiple_choice",
    "true_false": "true_false",
    "fill_blank": "fill_blank",
    "short_answer": "short_answer",
    "programming": "programming",
}

DIFFICULTY_ALIASES = {
    "基础": "easy",
    "简单": "easy",
    "easy": "easy",
    "中等": "medium",
    "标准": "medium",
    "medium": "medium",
    "提高": "hard",
    "困难": "hard",
    "hard": "hard",
}


def normalize_question_type(value: str | None, default: str = "short_answer") -> str:
    raw = (value or default or "short_answer").strip()
    return QUESTION_TYPE_ALIASES.get(raw, default)


def normalize_question_difficulty(value: str | None, default: str = "medium") -> str:
    raw = (value or default or "medium").strip()
    return DIFFICULTY_ALIASES.get(raw, raw if raw in {"easy", "medium", "hard"} else default)


def extract_json_array(raw_text: str) -> list:
    """
    从 AI 返回文本中提取题目 JSON 数组。
    支持外层包装：{"questions": [...]}, {"data": [...]}, {"items": [...]}, {"results": [...]}
    也支持直接的 JSON 数组 [...] 或单个题目对象 {...}。
    """
    text_value = raw_text or ""
    try:
        parsed = parse_ai_json_safely(text_value)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            # 优先尝试解包常见的外层包装 key
            for key in ("questions", "data", "items", "results"):
                inner = parsed.get(key)
                if isinstance(inner, list) and len(inner) > 0:
                    logger.info(
                        "[practice-generate] extracted %d items from wrapper key '%s'",
                        len(inner), key,
                    )
                    return [item for item in inner if isinstance(item, dict)]
            # 如果没有包装 key，视为单个题目
            return [parsed]
    except Exception as exc:
        logger.info("[practice-generate] extract_json_array failed: %s", exc)
        pass
    return []


def parse_ai_generated_questions(raw_text: str) -> list[dict]:
    """
    解析 DeepSeek 返回的题目内容（增强版）。
    支持：
    1. 去除 markdown code fence
    2. 从文本中提取 JSON 对象或 JSON 数组
    3. 兼容 questions / data / items / results 等外层字段
    4. 兼容 stem/question/question_text/title/content 等题干字段
    5. 兼容 answer/reference_answer/correct_answer
    6. 兼容 analysis/explanation/solution
    7. 对选择题、多选题保留 options
    8. 对简答题、判断题、填空题不强制要求 options
    """
    return extract_json_array(raw_text)


BAD_ANALYSIS_PATTERNS = [
    "我认为",
    "我可能",
    "我怀疑",
    "让我重新",
    "重新检查",
    "重新计算",
    "前面算错",
    "有点乱",
    "鉴于时间",
    "为了配合选项",
    "可能是",
    "不确定",
    "我误解",
    "我搞错",
    "奇怪",
    "选项不匹配",
    "无法匹配",
    "综上，我的计算",
    "这里可能",
    "好像不匹配",
]


def contains_internal_reasoning(text: str) -> bool:
    if not text:
        return False
    return any(keyword in text for keyword in BAD_ANALYSIS_PATTERNS)


def clean_question_analysis(analysis: str, max_length: int = 1200) -> str:
    """
    清洗 AI 生成题目的解析字段：
    1. 删除内部思考、自我怀疑、反复试算和草稿推理。
    2. 删除"我认为、让我重新、鉴于时间、为了配合选项"等表达。
    3. 保留面向学生的最终有效解题步骤。
    4. 控制长度，避免解析过长。
    """
    text = str(analysis or "").strip()
    if not text:
        return "解析暂未生成完整内容，请结合参考答案复习相关知识点，并重点回顾题目涉及的核心概念。"

    text = re.sub(r"```(?:[\w+-]+)?", "", text)
    text = text.replace("```", "")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    chunks = re.split(r"(?<=[。！？!?；;])\s*|\n+", text)
    kept_chunks: list[str] = []
    for chunk in chunks:
        cleaned = chunk.strip()
        if not cleaned:
            continue
        if any(keyword in cleaned for keyword in BAD_ANALYSIS_PATTERNS):
            continue
        if re.search(r"(先|再|然后|因此|所以|答案|选择|可知|得到|计算|判断|比较|代入|公式|复杂度|正确|错误|干扰项)", cleaned):
            kept_chunks.append(cleaned)
        elif len(cleaned) <= 80 and len(kept_chunks) < 2:
            kept_chunks.append(cleaned)

    cleaned_text = "\n".join(kept_chunks).strip()
    if not cleaned_text:
        cleaned_text = re.sub("|".join(re.escape(k) for k in BAD_ANALYSIS_PATTERNS), "", text).strip()

    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
    cleaned_text = re.sub(r"[ \t]{2,}", " ", cleaned_text).strip()

    if len(cleaned_text) > max_length:
        clipped = cleaned_text[:max_length].rstrip()
        sentence_end = max(clipped.rfind("。"), clipped.rfind("！"), clipped.rfind("？"), clipped.rfind("\n"))
        if sentence_end >= max_length * 0.6:
            clipped = clipped[: sentence_end + 1].rstrip()
        cleaned_text = clipped

    if count_chinese_characters(cleaned_text) + count_alnum_characters(cleaned_text) < 20:
        return "解析暂未生成完整内容，请结合参考答案复习相关知识点，并重点回顾题目涉及的核心概念。"
    return cleaned_text


def refine_question_analysis_with_ai(raw_analysis: str, stem: str, answer: str) -> str:
    """
    将混乱解析压缩成适合学生阅读的正式解析。
    仅在解析明显过长或包含内部推理痕迹时调用，避免不必要成本。
    """
    raw_text = str(raw_analysis or "").strip()
    if not raw_text:
        return ""
    prompt = f"""请将下面这段题目解析改写成适合学生阅读的正式解析。

要求：
1. 只保留最终有效解题步骤。
2. 删除 AI 的内部思考、自我怀疑、反复试算、错误尝试。
3. 不要出现"我认为""让我重新""可能""鉴于时间"等表达。
4. 不要讨论题目或选项是否合理。
5. 用确定、简洁、教学化的语言。
6. 最多 500 字。
7. 如果有计算过程，请按步骤列出。
8. 只返回改写后的解析，不要返回其他内容。

题干：
{stem}

参考答案：
{answer}

原始解析：
{raw_text[:3000]}"""
    try:
        refined = call_deepseek(
            [
                {"role": "system", "content": "你是题目解析净化助手，只输出面向学生的正式解析。"},
                {"role": "user", "content": prompt},
            ],
            timeout_seconds=30,
        )
    except Exception as exc:
        logger.warning("[practice-generate] refine analysis failed: %s", str(exc)[:200])
        return ""
    return str(refined or "").strip()


def split_question_options(options_text: str | None) -> list[str]:
    if not options_text:
        return []
    lines = [line.strip() for line in str(options_text).replace("\r", "\n").split("\n") if line.strip()]
    if len(lines) == 1 and "；" in lines[0]:
        lines = [item.strip() for item in lines[0].split("；") if item.strip()]
    return lines


def extract_correct_option_labels(raw_options) -> list[str]:
    labels: list[str] = []
    if not isinstance(raw_options, list):
        return labels
    for idx, option in enumerate(raw_options):
        if not isinstance(option, dict):
            continue
        is_correct = option.get("is_correct")
        if is_correct is True or str(is_correct).strip().lower() in {"true", "1", "yes", "y"}:
            label = str(option.get("label") or chr(ord("A") + idx)).strip().rstrip(".、)").upper()
            if label:
                labels.append(label)
    return labels


def parse_labeled_options(options_text: str | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in split_question_options(options_text):
        matched = re.match(r"^([A-H])[\.\、\)]\s*(.+)$", line.strip(), re.I)
        if matched:
            parsed[matched.group(1).upper()] = matched.group(2).strip()
    return parsed


def normalize_generated_answer_labels(answer: str | None) -> list[str]:
    text = str(answer or "").strip().upper()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [normalize_practice_answer(str(item)) for item in parsed if normalize_practice_answer(str(item))]
    except Exception:
        pass
    if re.fullmatch(r"[A-H]{2,}", text):
        return list(text)
    return [normalize_practice_answer(item) for item in re.split(r"[,，、;；\s]+", text) if normalize_practice_answer(item)]


def format_answer_labels(labels: list[str], qtype: str) -> str:
    normalized = [label.upper() for label in labels if label]
    if qtype == "multiple_choice":
        return ",".join(sorted(dict.fromkeys(normalized)))
    return normalized[0] if normalized else ""


def extract_analysis_answer_labels(analysis: str | None) -> list[str]:
    text = str(analysis or "")
    patterns = [
        r"(?:答案|正确答案|正确选项|应选|选择)\s*(?:是|为|：|:)?\s*([A-H])\b",
        r"\b([A-H])\s*(?:项|选项)\s*(?:正确|成立)",
    ]
    labels: list[str] = []
    for pattern in patterns:
        labels.extend(match.group(1).upper() for match in re.finditer(pattern, text, re.I))
    return labels


def extract_final_numeric_option_label(analysis: str | None, options: dict[str, str]) -> str | None:
    text = str(analysis or "").strip()
    if not text or not options:
        return None
    sentences = [part.strip() for part in re.split(r"[。！？\n]+", text) if part.strip()]
    signal_sentences = [
        sentence for sentence in sentences
        if any(keyword in sentence for keyword in ("最终", "因此", "所以", "答案", "选择", "结果", "得到", "缺失次数", "命中率", "尾数", "值为", "为"))
    ]
    scan_text = "。".join(signal_sentences[-3:] or sentences[-2:])
    numbers = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?(?![A-Za-z])", scan_text)
    if not numbers:
        return None
    final_number = numbers[-1].rstrip("%")
    matched_labels = []
    for label, content in options.items():
        option_numbers = [value.rstrip("%") for value in re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?(?![A-Za-z])", content)]
        if final_number in option_numbers or content.strip() == final_number:
            matched_labels.append(label)
    return matched_labels[0] if len(matched_labels) == 1 else None


def validate_generated_question_consistency(item: dict) -> tuple[bool, str, dict]:
    qtype = normalize_question_type(str(item.get("type") or "choice"), "choice")
    if qtype not in {"choice", "multiple_choice", "true_false"}:
        return True, "", item

    corrected = dict(item)
    options = parse_labeled_options(corrected.get("options"))
    if qtype in {"choice", "multiple_choice"} and not options:
        return False, "选择题缺少可校验选项", corrected

    answer_labels = normalize_generated_answer_labels(corrected.get("answer"))
    if qtype == "true_false":
        return (True, "", corrected) if answer_labels or str(corrected.get("answer") or "").strip() else (False, "判断题缺少答案", corrected)
    if not answer_labels:
        return False, "选择题缺少答案标签", corrected
    if any(label not in options for label in answer_labels):
        return False, f"答案标签 {answer_labels} 不在选项中", corrected

    flagged_labels = [label for label in corrected.get("_correct_option_labels", []) if label in options]
    if flagged_labels:
        expected = sorted(dict.fromkeys(flagged_labels))
        actual = sorted(dict.fromkeys(answer_labels))
        if expected != actual:
            corrected["answer"] = format_answer_labels(expected, qtype)
            corrected["_consistency_warning"] = f"答案已按 options.is_correct 从 {format_answer_labels(actual, qtype)} 修正为 {corrected['answer']}"
        return True, corrected.get("_consistency_warning", ""), corrected

    analysis_labels = extract_analysis_answer_labels(corrected.get("explanation"))
    if analysis_labels:
        last_label = analysis_labels[-1]
        if last_label in options and last_label not in answer_labels:
            corrected["answer"] = format_answer_labels([last_label], qtype)
            corrected["_consistency_warning"] = f"答案已按解析明确选项从 {format_answer_labels(answer_labels, qtype)} 修正为 {corrected['answer']}"
            return True, corrected["_consistency_warning"], corrected

    if qtype == "choice":
        numeric_label = extract_final_numeric_option_label(corrected.get("explanation"), options)
        if numeric_label and numeric_label not in answer_labels:
            corrected["answer"] = numeric_label
            corrected["_consistency_warning"] = f"答案已按解析最终数值从 {format_answer_labels(answer_labels, qtype)} 修正为 {numeric_label}"
            return True, corrected["_consistency_warning"], corrected

    return True, "", corrected


def has_reasoning_signal(text_value: str) -> bool:
    markers = ("```", "for ", "while ", "if ", "SELECT", "表", "图", "树", "输入", "输出", "样例", "计算", "复杂度", "证明", "反例", "页面", "调度", "Cache", "cache", "SQL")
    return any(marker in (text_value or "") for marker in markers)


def validate_generated_question(item: dict, expected_type: str, difficulty: str) -> tuple[bool, str]:
    qtype = normalize_question_type(str(item.get("type") or expected_type), expected_type)
    if is_programming_question_type(qtype):
        return False, "练习中心不保存编程题"
    content = str(
        item.get("content") or item.get("stem") or item.get("question")
        or item.get("question_text") or item.get("text") or ""
    ).strip()
    explanation = str(
        item.get("explanation") or item.get("analysis") or item.get("solution") or ""
    ).strip()
    if count_chinese_characters(content) + count_alnum_characters(content) < 20:
        return False, "题干过短"
    if count_chinese_characters(explanation) + count_alnum_characters(explanation) < 30:
        return False, "解析过短"
    if qtype in {"choice", "multiple_choice", "true_false"}:
        options = split_question_options(item.get("options"))
        if qtype == "true_false" and len(options) < 2:
            item["options"] = "A. 正确\nB. 错误"
            options = split_question_options(item.get("options"))
        if qtype in {"choice", "multiple_choice"} and len(options) < 2:
            return False, "选择题选项数量不足（至少需要 2 个选项）"
        if qtype in {"choice", "multiple_choice"} and len(options) > 10:
            return False, "选择题选项过多"
        # 对选项做重复检查
        opts_set = set()
        for opt in options:
            cleaned = re.sub(r"^[A-Za-z][\.、\)]\s*", "", opt).strip()
            if cleaned in opts_set:
                return False, "选项重复"
            opts_set.add(cleaned)
        answer = str(item.get("answer") or "").strip()
        if qtype == "choice" and answer:
            answer_label = answer[0].upper()
            option_labels = {opt[0].upper() for opt in options if opt}
            if answer_label not in option_labels:
                return False, f"答案 '{answer_label}' 不在选项标签 {option_labels} 中"
    # 对选择/判断题在 medium/hard 下检查推理信号；简答/填空放宽检查
    if qtype in {"choice", "multiple_choice"} and difficulty in {"medium", "hard"}:
        if not has_reasoning_signal(content + "\n" + explanation):
            return False, "选择题缺少推理信号"
    return True, ""


def normalize_generated_question_item(item: dict, expected_type: str, difficulty: str, source_style: str) -> dict:
    """归一化 AI 生成的题目字段，兼容多种字段名别名。"""
    qtype = normalize_question_type(str(item.get("type") or expected_type), expected_type)
    # 题干：兼容 content / stem / question / question_text / title / text
    content = str(
        item.get("content") or item.get("stem") or item.get("question")
        or item.get("question_text") or item.get("text") or ""
    ).strip()
    # 标题：兼容 title / stem / 或截取 content 前 32 字符
    title = str(
        item.get("title") or item.get("stem") or content[:32] or "AI 原创题目"
    ).strip()
    # 答案：兼容 answer / reference_answer / correct_answer
    answer = str(
        item.get("answer") or item.get("reference_answer")
        or item.get("correct_answer") or ""
    ).strip() or None
    # 解析：兼容 explanation / analysis / solution
    explanation = str(
        item.get("explanation") or item.get("analysis")
        or item.get("solution") or ""
    ).strip() or None
    # 选项：兼容 options / choices（list / dict / str）
    options_raw = item.get("options") if "options" in item else item.get("choices")
    correct_option_labels = extract_correct_option_labels(options_raw)
    if isinstance(options_raw, (list, dict)):
        options_str = format_question_options(options_raw) or None
    else:
        options_str = str(options_raw or "").strip() or None
    return {
        "type": qtype,
        "title": title[:255],
        "content": content,
        "options": options_str,
        "answer": answer,
        "explanation": explanation,
        "difficulty": normalize_question_difficulty(str(item.get("difficulty") or difficulty), difficulty),
        "source_style": str(item.get("source_style") or source_style or "mixed").strip(),
        "_correct_option_labels": correct_option_labels,
    }


@app.post("/practice/questions/generate")
def generate_questions(req: schemas.GenerateQuestionRequest, db: Session = Depends(get_db)):
    user = get_user_by_username(req.username, db)
    count = min(max(req.count, 1), 10)
    qtype = normalize_question_type(req.type or "choice", "choice")
    if is_programming_question_type(qtype):
        raise HTTPException(status_code=400, detail="编程题请前往编程中心生成和练习。")
    if qtype not in PRACTICE_QUESTION_TYPES:
        raise HTTPException(status_code=400, detail="无效的题型")

    course_name = (req.course_name or req.course_id or "").strip()
    kp_title = (req.knowledge_point_title or "").strip()
    kp_id = req.knowledge_point_id
    difficulty = normalize_question_difficulty(req.difficulty or "medium", "medium")
    source_style = (req.source_style or "mixed").strip()
    if source_style not in {"exam", "leetcode", "codeforces", "textbook", "interview", "mixed"}:
        source_style = "mixed"

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

    # ── 日志：请求参数 ──
    course_preference = get_course_preference_payload(db, user.username, course_id or course_name)
    if not build_course_preference_prompt(course_preference, course_id or course_name) and req.mastery_level and req.learning_goal:
        course_preference = {
            "course_id": course_id or course_name,
            "mastery_level": req.mastery_level,
            "learning_goal": req.learning_goal,
            "is_started": True,
        }
    course_preference_context = build_course_preference_prompt(course_preference, course_id or course_name)

    logger.info(
        "[practice-generate] request payload: username=%s, course_id=%s, course_name=%s, "
        "kp_id=%s, kp_title=%s, type=%s, difficulty=%s, style=%s, count=%d, "
        "reasoning=%s, avoid_simple=%s",
        req.username, course_id, course_name, kp_id, kp_title,
        qtype, difficulty, source_style, count,
        req.require_reasoning, req.avoid_too_simple,
    )

    user_prompt = f"""课程：{course_name or '未指定'}
知识点：{kp_label}{weak_hint}
题型：{qtype}
难度：{difficulty}
题型风格：{source_style}
是否要求多步推理：{bool(req.require_reasoning)}
是否避免简单概念题：{bool(req.avoid_too_simple)}
数量：{count} 道

请生成 {count} 道原创题。为了保证质量，可一次输出 {min(count * 2, 16)} 道候选题，但必须优先保证每题有场景、推理和详细解析。

每道题的 analysis 字段必须是给学生看的正式解析，只保留必要解题步骤；禁止包含内部思考、自我纠错、反复试算、对选项不匹配的怀疑，禁止出现"我认为""我可能""让我重新""鉴于时间""为了配合选项"等表达。

请直接输出严格 JSON，不要用 Markdown 代码块包裹，不要输出任何解释文字。"""

    if course_preference_context:
        user_prompt = f"{course_preference_context}\n\n{user_prompt}"

    if is_exam_408_context(course_id, course_name):
        check_exam_408_usage_limit(user, "question_generate", db)
    else:
        check_usage_limit(user.username, "question_generate", db)

    raw_responses_preview = []
    all_candidates = []
    total_ai_text = ""

    try:
        valid_count = 0
        for attempt_index in range(3):
            remaining = max(count - valid_count, 1)
            candidate_count = min(10, max(remaining * 2, remaining))
            prompt = (
                user_prompt
                + f"\n\n本轮必须生成 exactly {candidate_count} 道候选题。"
                + f"\nquestions 数组长度必须等于 {candidate_count}。"
                + "\n每道题必须包含 stem/content、type、difficulty、options、answer、analysis、knowledge_point、source=ai_generated。"
                + "\n如果上一轮已经生成过题目，本轮必须避免重复题干和重复标题。"
            )
            if attempt_index > 0:
                prompt += f"\n\n上一轮合格题不足，还需要至少 {remaining} 道有效题，请补生成更具体、更有推理步骤的题。"
            ai_response = call_deepseek(
                [
                    {"role": "system", "content": GENERATE_QUESTION_PROMPT},
                    {"role": "user", "content": prompt},
                ]
            )
            total_ai_text += "\n" + ai_response
            preview = ai_response[:1500] if ai_response else "(empty)"
            raw_responses_preview.append(preview)
            logger.info(
                "[practice-generate] attempt %d: deepseek raw response preview (first 1500 chars): %s",
                attempt_index + 1, preview,
            )

            parsed_items = extract_json_array(ai_response)
            logger.info(
                "[practice-generate] attempt %d: parsed %d items from AI response",
                attempt_index + 1, len(parsed_items) if isinstance(parsed_items, list) else 0,
            )
            if isinstance(parsed_items, list):
                all_candidates.extend([item for item in parsed_items if isinstance(item, dict)])

            valid_count = 0
            seen_titles = set()
            for idx, item in enumerate(all_candidates):
                normalized = normalize_generated_question_item(item, qtype, difficulty, source_style)
                if not (normalized.get("answer") or "").strip() or not (normalized.get("explanation") or "").strip():
                    logger.info(
                        "[practice-generate] invalid question #%d reason: missing answer or analysis (title=%s)",
                        idx + 1, normalized.get("title", "")[:40],
                    )
                    continue
                ok, reason = validate_generated_question(normalized, qtype, difficulty)
                if ok and normalized["title"] not in seen_titles:
                    valid_count += 1
                    seen_titles.add(normalized["title"])
                else:
                    logger.info(
                        "[practice-generate] invalid question #%d reason: %s (title=%s)",
                        idx + 1, reason, normalized.get("title", "")[:40],
                    )
            logger.info(
                "[practice-generate] attempt %d: valid=%d / total=%d candidates, need=%d",
                attempt_index + 1, valid_count, len(all_candidates), count,
            )
            if valid_count >= count:
                break

        record_ai_usage(user.username, "question_generate", db, estimated_tokens=estimate_tokens_from_text(total_ai_text), status="success")
        questions_data = all_candidates
    except HTTPException:
        raise
    except Exception as e:
        record_ai_usage(user.username, "question_generate", db, status="failed", error_message=str(e))
        logger.error("[practice-generate] exception: %s", e)
        raise HTTPException(status_code=500, detail=f"AI 生成题目失败：{str(e)}")

    if not isinstance(questions_data, list) or len(questions_data) == 0:
        raw_preview = (raw_responses_preview[-1] if raw_responses_preview else "")[:500]
        logger.warning("[practice-generate] no valid questions parsed. raw preview: %s", raw_preview)
        raise HTTPException(
            status_code=500,
            detail=f"AI 返回内容格式不符合题目结构，无法解析。raw_preview: {raw_preview}",
        )

    created = []
    seen_titles = set()
    consistency_filtered_count = 0
    consistency_repaired_count = 0
    for item in questions_data:
        normalized = normalize_generated_question_item(item, qtype, difficulty, source_style)
        raw_analysis = normalized.get("explanation") or ""
        if not (normalized.get("answer") or "").strip() or not raw_analysis.strip():
            logger.info(
                "[practice-generate] final filter: missing answer or analysis (title=%s)",
                normalized.get("title", "")[:40],
            )
            continue
        internal_detected = contains_internal_reasoning(raw_analysis)
        cleaned_analysis = clean_question_analysis(raw_analysis)
        if len(raw_analysis) > 1200 or internal_detected:
            logger.info(
                "[practice-generate] raw analysis preview (first 300 chars): %s",
                raw_analysis[:300],
            )
            refined_analysis = refine_question_analysis_with_ai(
                raw_analysis,
                normalized.get("content") or "",
                normalized.get("answer") or "",
            )
            if refined_analysis:
                cleaned_analysis = clean_question_analysis(refined_analysis)
        if contains_internal_reasoning(cleaned_analysis):
            cleaned_analysis = "解析暂未生成完整内容，请结合参考答案复习相关知识点，并重点回顾题目涉及的核心概念。"
        logger.info(
            "[practice-generate] raw analysis length: %d cleaned analysis length: %d internal reasoning detected: %s",
            len(raw_analysis),
            len(cleaned_analysis),
            str(internal_detected).lower(),
        )
        normalized["explanation"] = cleaned_analysis
        consistency_ok, consistency_reason, checked_normalized = validate_generated_question_consistency(normalized)
        if not consistency_ok:
            consistency_filtered_count += 1
            logger.info(
                "[practice-generate] final filter: answer-analysis consistency failed reason=%s (title=%s)",
                consistency_reason, normalized.get("title", "")[:40],
            )
            continue
        normalized = checked_normalized
        if normalized.get("_consistency_warning"):
            consistency_repaired_count += 1
            logger.info(
                "[practice-generate] consistency repair: %s (title=%s)",
                normalized.get("_consistency_warning"), normalized.get("title", "")[:40],
            )
        ok, reason = validate_generated_question(normalized, qtype, difficulty)
        if not ok:
            logger.info(
                "[practice-generate] final filter: invalid question reason=%s (title=%s)",
                reason, normalized.get("title", "")[:40],
            )
        if not ok or normalized["title"] in seen_titles:
            continue
        seen_titles.add(normalized["title"])
        question = models.Question(
            username=user.username,
            course_id=course_id,
            knowledge_point_id=kp_id,
            type=normalized["type"],
            title=normalized["title"],
            content=normalized["content"],
            options=normalized["options"],
            answer=normalized["answer"],
            explanation=normalized["explanation"],
            difficulty=normalized["difficulty"],
            source="ai_generated",
            source_style=normalized["source_style"],
        )
        db.add(question)
        created.append(question)
        if len(created) >= count:
            break

    logger.info("[practice-generate] final created: %d questions", len(created))

    if not created:
        raw_preview = (raw_responses_preview[-1] if raw_responses_preview else "")[:500]
        raise HTTPException(
            status_code=500,
            detail=f"AI 生成的题目未通过质量检查。raw_preview: {raw_preview}",
        )

    db.commit()
    for q in created:
        db.refresh(q)

    filtered_count = max(len(questions_data) - len(created), 0)
    warnings = []
    if len(created) < count:
        warnings.append(
            f"本次请求生成 {count} 道题，实际通过质量校验 {len(created)} 道。其余候选题已过滤，可重新生成补充。"
        )
    if consistency_repaired_count:
        warnings.append(f"{consistency_repaired_count} 道候选题的答案已按解析或选项标记自动修正。")
    if consistency_filtered_count:
        warnings.append(f"{consistency_filtered_count} 道候选题因答案与解析不一致已过滤。")

    return {
        "success": True,
        "requested_count": count,
        "created_count": len(created),
        "filtered_count": filtered_count,
        "warnings": warnings,
        "questions": [serialize_question(q) for q in created],
        "message": f"已生成 {len(created)} 道题目",
    }


# ── Task Practice: AI Question Preview (no DB write) ──────

TASK_PREVIEW_PROMPT = """你是一个大学课程助教。请根据学生的学习任务，生成适合复习使用的练习题预览。

要求：
1. 使用中文。
2. 只围绕指定课程和知识点出题。
3. 不要生成超出知识点范围的题。
4. 题目难度适合大学生复习，不要过于简单。
5. 题型只能是：single_choice（单选）、multiple_choice（多选）、judge（判断）、short_answer（简答）。
6. 不要生成编程题。
7. 每道题必须包含：type、stem（题干）、options（选项数组，每个选项含 label 和 text，判断题和简答题可以为空数组）、answer（正确答案）、analysis（详细解析，解释为什么选这个答案）。
8. 选择题选项必须完整，单选题至少 3 个选项，多选题至少 4 个选项。
9. 答案必须明确，判断题答案为"正确"或"错误"。
10. 解析必须清楚说明正确选项的原因，不能出现"我认为"、"让我重新"、"鉴于时间"等内部思考表达。
11. 不要输出 Markdown。
12. 只输出严格 JSON。

JSON 格式：
{
  "questions": [
    {
      "type": "single_choice",
      "stem": "以下关于进程调度的描述，正确的是？",
      "options": [
        {"label": "A", "text": "时间片轮转调度属于非抢占式调度"},
        {"label": "B", "text": "先来先服务调度可能导致饥饿问题"},
        {"label": "C", "text": "最短作业优先调度总是最优"},
        {"label": "D", "text": "多级反馈队列结合了多种调度策略"}
      ],
      "answer": "D",
      "analysis": "多级反馈队列调度算法综合了时间片轮转和优先级调度的优点，通过多个队列实现了对不同类型进程的灵活调度。A错误，时间片轮转是抢占式调度；B描述的是优先级调度可能的问题；C错误，SJF在长作业场景下可能导致饥饿。"
    }
  ]
}"""


@app.post("/practice/generate-task-preview")
def generate_task_question_preview(req: schemas.GenerateTaskQuestionPreviewRequest, db: Session = Depends(get_db)):
    """Generate AI question preview for a task when no matching questions exist. Preview only — no DB write."""
    user = get_user_by_username(req.username, db)
    course_id = normalize_subject(req.course_id)

    if not course_id:
        raise HTTPException(status_code=400, detail="课程不能为空")

    count = min(max(req.count, 1), 10)

    # Resolve knowledge point info
    kp_title = (req.knowledge_point_title or "").strip()
    kp_description = ""
    if req.knowledge_point_id:
        kp = (
            db.query(models.KnowledgePoint)
            .filter(
                models.KnowledgePoint.id == req.knowledge_point_id,
                models.KnowledgePoint.username == user.username,
            )
            .first()
        )
        if kp:
            kp_title = kp_title or (kp.title or "")
            kp_description = (kp.description or "").strip()

    task_title = (req.task_title or "").strip()
    course_preference = get_course_preference_payload(db, user.username, course_id)
    if not build_course_preference_prompt(course_preference, course_id) and req.mastery_level and req.learning_goal:
        course_preference = {
            "course_id": course_id,
            "mastery_level": req.mastery_level,
            "learning_goal": req.learning_goal,
            "is_started": True,
        }
    course_preference_context = build_course_preference_prompt(course_preference, course_id)

    if is_exam_408_context(course_id, ""):
        check_exam_408_usage_limit(user, "question_generate", db)
    else:
        check_usage_limit(user.username, "question_generate", db)

    # Build prompt
    context_parts = [f"课程：{course_id}"]
    if kp_title:
        context_parts.append(f"知识点：{kp_title}")
    if kp_description:
        context_parts.append(f"知识点说明：{kp_description}")
    if task_title:
        context_parts.append(f"学习任务：{task_title}")
    context_parts.append(f"数量：{count} 道")

    user_prompt = "\n".join(context_parts) + "\n\n请生成练习题预览。"

    if course_preference_context:
        user_prompt = f"{course_preference_context}\n\n{user_prompt}"

    try:
        raw = call_deepseek(
            [
                {"role": "system", "content": TASK_PREVIEW_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=3000,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="AI 题目生成失败，请稍后重试") from exc

    record_ai_usage(
        user.username, "question_generate", db,
        estimated_tokens=estimate_tokens_from_text(user_prompt) + estimate_tokens_from_text(raw),
        status="success",
    )

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
        raise HTTPException(status_code=500, detail="AI 返回格式异常，未能生成有效的题目。请稍后重试。")

    try:
        result = json.loads(text[json_start:json_end + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"AI 返回数据解析失败，请稍后重试。错误详情：{str(exc)[:200]}")

    raw_questions = result.get("questions", [])
    if not isinstance(raw_questions, list):
        raw_questions = []

    # Validate and clean each question
    ALLOWED_TYPES = {"single_choice", "multiple_choice", "judge", "short_answer"}
    cleaned = []
    for q in raw_questions:
        if not isinstance(q, dict):
            continue
        qtype = str(q.get("type", "")).strip()
        if qtype not in ALLOWED_TYPES:
            continue
        stem = str(q.get("stem", "")).strip()
        if not stem:
            continue
        answer = str(q.get("answer", "")).strip()
        if not answer:
            continue
        analysis = str(q.get("analysis", "")).strip()
        if not analysis:
            continue

        options = q.get("options", [])
        if not isinstance(options, list):
            options = []
        clean_options = []
        for opt in options:
            if not isinstance(opt, dict):
                continue
            label = str(opt.get("label", "")).strip()
            text = str(opt.get("text", "")).strip()
            if label and text:
                clean_options.append({"label": label, "text": text})

        cleaned.append({
            "type": qtype,
            "stem": stem,
            "options": clean_options,
            "answer": answer,
            "analysis": analysis,
            "knowledge_point_title": kp_title or course_id,
        })

    if not cleaned:
        raise HTTPException(status_code=500, detail="AI 未能生成有效的题目。请确认知识点信息正确，或尝试调整数量后重试。")

    # NOTE: No DB write — preview only
    return {
        "success": True,
        "course_id": course_id,
        "knowledge_point_title": kp_title or course_id,
        "questions": cleaned[:count],
    }


# ── AI Learning Plan ─────────────────────────────────────

ALLOWED_PLAN_TYPES = {"today", "three_day", "seven_day", "exam", "coding"}
ALLOWED_PLAN_SCENES = {"daily", "exam", "weakness", "coding"}
ALLOWED_TASK_TYPES = {"review", "practice", "reading", "quiz", "summary", "code", "learning_plan", "coding", "material", "custom"}
ALLOWED_PRIORITIES = {"high", "medium", "low"}
PLAN_TASK_TYPE_ALIASES = {
    "coding": "code",
    "code_practice": "code",
    "material": "reading",
    "read_material": "reading",
    "test": "quiz",
    "exam": "quiz",
}
PLAN_TASK_TYPE_CN = {
    "review": "复习",
    "practice": "练习",
    "reading": "阅读资料",
    "quiz": "小测",
    "summary": "总结",
    "code": "编程练习",
    "learning_plan": "学习计划",
    "custom": "学习任务",
}


class PlanGeneratePreviewRequest(BaseModel):
    username: str
    course_id: str = ""
    plan_type: str = "seven_day"
    plan_scene: str = "daily"
    days: int = 7
    goal: str = ""
    daily_minutes: int = 60
    exam_scope_text: str = ""
    selected_material_ids: list[int] = []


class PlanImportTasksRequest(BaseModel):
    username: str
    plan_title: str = ""
    items: list


def _truncate_text(value: str, max_len: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:max_len]


def _looks_english(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    ascii_letters = len(re.findall(r"[A-Za-z]", text))
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    return ascii_letters >= 6 and ascii_letters > cjk_chars * 2


def _normalize_plan_task_type(value: str) -> str:
    task_type = str(value or "review").strip().lower()
    task_type = PLAN_TASK_TYPE_ALIASES.get(task_type, task_type)
    if task_type not in ALLOWED_TASK_TYPES:
        task_type = "review"
    return task_type


def _fallback_plan_title(course_id: str, plan_type: str, plan_scene: str) -> str:
    course_name = course_id or "全部课程"
    if plan_scene == "exam" or plan_type == "exam":
        return f"{course_name}考试复习计划"
    if plan_scene == "coding" or plan_type == "coding":
        return f"{course_name}编程训练计划"
    if plan_type == "today":
        return f"{course_name}今日学习计划"
    return f"{course_name}学习计划"


def _fallback_task_title(item: dict, course_id: str, index: int) -> str:
    course_name = str(item.get("course_id") or course_id or "课程").strip()
    kp_name = str(item.get("knowledge_point_name") or item.get("knowledge_point_title") or "").strip()
    task_type = _normalize_plan_task_type(item.get("task_type"))
    action = PLAN_TASK_TYPE_CN.get(task_type, "学习")
    base = kp_name or course_name
    title = f"{base}{action}"
    if len(title) > 20:
        title = f"{course_name}{action}"
    if len(title) > 20:
        title = f"学习任务{index + 1}"
    return title


def _normalize_plan_text(value: str, fallback: str, max_len: int) -> str:
    text = _truncate_text(value, max_len)
    if not text or _looks_english(text):
        return fallback[:max_len]
    return text


def _build_default_plan_items(req: PlanGeneratePreviewRequest, plan_data: dict) -> list[dict]:
    minutes = max(30, min(180, int(req.daily_minutes or 60)))
    per_task = max(15, round(minutes / 3))
    course_id = normalize_subject(req.course_id, default="") or req.course_id or ""
    candidates = plan_data.get("weak_points") or []
    if not candidates:
        candidates = plan_data.get("not_started_points") or []
    titles = [item.get("title") for item in candidates[:3] if item.get("title")]
    while len(titles) < 3:
        titles.append(["基础概念", "重点练习", "学习总结"][len(titles)])
    task_types = ["reading", "practice", "summary"]
    return [
        {
            "day_index": 1,
            "title": f"{title}{PLAN_TASK_TYPE_CN[task_types[index]]}"[:20],
            "description": "根据当前学习进度安排，先补齐薄弱或未开始知识点，再通过练习巩固。",
            "course_id": course_id,
            "knowledge_point_id": candidates[index].get("id") if index < len(candidates) else None,
            "knowledge_point_name": title,
            "task_type": task_types[index],
            "estimated_minutes": per_task,
            "priority": "medium",
            "reason": "该内容与当前进度或薄弱点相关，适合优先安排。",
            "related_material_ids": [],
            "source_evidence": [],
        }
        for index, title in enumerate(titles[:3])
    ]


def _extract_text_from_upload(file: UploadFile, max_chars: int = 6000) -> str:
    raw = file.file.read()
    name = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    text = ""
    try:
        if name.endswith(".pdf") or "pdf" in content_type:
            reader = PdfReader(BytesIO(raw))
            pages = []
            for page in reader.pages[:8]:
                pages.append(page.extract_text() or "")
            text = "\n".join(pages)
        elif name.endswith(".docx") or name.endswith(".pptx"):
            with zipfile.ZipFile(BytesIO(raw)) as zf:
                xml_names = [
                    item for item in zf.namelist()
                    if item.startswith(("word/document", "ppt/slides/slide")) and item.endswith(".xml")
                ]
                parts = []
                for xml_name in xml_names[:12]:
                    xml = zf.read(xml_name).decode("utf-8", errors="ignore")
                    parts.append(re.sub(r"<[^>]+>", " ", xml))
                text = "\n".join(parts)
        elif content_type.startswith("image/"):
            image = Image.open(BytesIO(raw))
            text = pytesseract.image_to_string(image, lang="chi_sim+eng")
        else:
            text = raw.decode("utf-8", errors="ignore")
    except Exception as exc:
        logger.warning("Failed to parse plan upload %s: %s", file.filename, exc)
        text = ""
    return _truncate_text(text, max_chars)


def _analyze_exam_paper_text(texts: list[str]) -> dict:
    joined = "\n".join(texts or "")
    type_patterns = {
        "选择题": r"选择题|单选|多选|A[.、]|B[.、]|C[.、]|D[.、]",
        "填空题": r"填空题|填空|____|（\\s*）",
        "判断题": r"判断题|判断|对错|正确|错误",
        "简答题": r"简答题|简述|说明|解释",
        "编程题": r"编程题|程序|代码|函数|class|public|int main",
        "综合题": r"综合题|设计|分析|综合",
    }
    distribution = []
    for label, pattern in type_patterns.items():
        count = len(re.findall(pattern, joined, flags=re.IGNORECASE))
        if count:
            distribution.append({"type": label, "count": count})
    if not distribution:
        distribution.append({"type": "未知题型", "count": 1 if joined.strip() else 0})
    keywords = []
    for word in ["变量", "循环", "数组", "函数", "指针", "结构体", "类", "对象", "继承", "多态", "异常", "集合", "递归"]:
        if word in joined:
            keywords.append(word)
    suggestions = []
    type_names = {item["type"] for item in distribution}
    if "编程题" in type_names:
        suggestions.append("编程题占比较高，建议增加代码练习。")
    if type_names & {"选择题", "判断题", "填空题"}:
        suggestions.append("客观题较多，建议安排概念辨析和小测。")
    if type_names & {"简答题", "综合题"}:
        suggestions.append("主观题或综合题需要安排总结和综合训练。")
    return {
        "question_type_analysis": distribution,
        "key_knowledge_points": keywords[:8],
        "paper_suggestions": suggestions,
    }


def _get_selected_plan_materials(username: str, course_id: str, material_ids: list[int], db: Session):
    normalized_course = normalize_subject(course_id, default="")
    query = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.username == username,
        models.StudyMaterial.is_deleted.is_(False),
    )
    safe_ids = [int(mid) for mid in (material_ids or [])[:10] if str(mid).isdigit()]
    if safe_ids:
        query = query.filter(models.StudyMaterial.id.in_(safe_ids))
    elif normalized_course:
        query = query.filter(models.StudyMaterial.subject == normalized_course)
    return query.order_by(models.StudyMaterial.created_at.desc()).limit(10).all()


def _get_plan_material_context(username: str, course_id: str, material_ids: list[int], query_text: str, db: Session) -> list[dict]:
    materials = _get_selected_plan_materials(username, course_id, material_ids, db)
    material_map = {m.id: m for m in materials}
    if not material_map:
        return []
    chunks = search_relevant_material_chunks(
        username=username,
        subject=normalize_subject(course_id, default="") or None,
        question=query_text or course_id or "考试范围 学习重点",
        top_k=18,
    )
    grouped: dict[int, list[dict]] = defaultdict(list)
    for chunk in chunks:
        material_id = int(chunk.get("material_id") or 0)
        if material_id in material_map and len(grouped[material_id]) < 4:
            grouped[material_id].append(chunk)
    context = []
    for material in materials:
        selected_chunks = grouped.get(material.id, [])
        if not selected_chunks and material.summary:
            selected_chunks = [{"chunk_summary": material.summary, "chunk_text": material.summary}]
        context.append({
            "material_id": material.id,
            "title": material.original_filename,
            "summary": _truncate_text(material.summary or "", 200),
            "chunks": [
                {
                    "summary": _truncate_text(chunk.get("chunk_summary") or chunk.get("chunk_text") or "", 180),
                    "text": _truncate_text(chunk.get("chunk_text") or "", 260),
                }
                for chunk in selected_chunks[:4]
            ],
        })
    return context


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

    # Not-started or low-activity knowledge points (max 10)
    progress_subquery = db.query(models.UserKnowledgeProgress.knowledge_point_id).filter(
        models.UserKnowledgeProgress.username == username
    )
    kp_base_query = db.query(models.KnowledgePoint).filter(models.KnowledgePoint.username == username)
    if normalized_course:
        kp_base_query = kp_base_query.filter(models.KnowledgePoint.course_id == normalized_course)
    not_started_rows = (
        kp_base_query
        .filter(~models.KnowledgePoint.id.in_(progress_subquery))
        .order_by(models.KnowledgePoint.created_at.asc())
        .limit(10)
        .all()
    )
    not_started_points = [
        {"id": kp.id, "title": kp.title, "course_id": kp.course_id, "status": "not_started", "mastery_score": 0}
        for kp in not_started_rows
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

    # Recent learning records (max 8)
    user = db.query(models.User).filter(models.User.username == username).first()
    records_data = []
    if user:
        record_query = db.query(models.LearningRecord).filter(models.LearningRecord.user_id == user.id)
        if normalized_course:
            record_query = record_query.filter(models.LearningRecord.subject == normalized_course)
        records = record_query.order_by(models.LearningRecord.created_at.desc()).limit(8).all()
        records_data = [
            {
                "subject": record.subject,
                "record_type": record.record_type,
                "question": _truncate_text(record.question, 80),
                "created_at": record.created_at.isoformat() if record.created_at else "",
            }
            for record in records
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
        "not_started_points": not_started_points,
        "wrong_questions": wrong_questions,
        "unfinished_tasks": tasks_data,
        "negative_events": negative_events,
        "code_sessions": code_data,
        "learning_records": records_data,
        "material_count": mat_count,
        "knowledge_point_count": kp_count,
    }


PLAN_SYSTEM_PROMPT = """你是中文 AI 学习规划师。请根据用户学习数据生成结构化学习计划。

硬性规则：
1. 只输出合法 JSON，不要 markdown、代码块或解释文字。
2. 所有 plan_title、summary、task.title、task.description、task.reason 必须使用中文；课程名 Java、Python、C语言、C++ 可保留。
3. 不允许输出英文任务标题，不要出现 Review Java Basics、Practice Basic Coding 这类标题。
4. plan_title 要中文，任务标题建议 8-18 个中文字符，最多 20 个中文字符。
5. description 使用中文，建议 40-80 个中文字符，最多 100 个中文字符。
6. reason 使用中文，最多 80 个中文字符。
7. 输出 JSON 字段：plan_title、summary、total_tasks、total_minutes、key_knowledge_points、question_type_analysis、items。
8. items 中每个任务字段：day_index、title、description、course_id、course_name、knowledge_point_id、knowledge_point_name、task_type、estimated_minutes、priority、reason、related_material_ids、source_evidence。
9. task_type 只能是：review、practice、reading、quiz、summary、code。
10. knowledge_point_id 必须来自用户数据中的已有 ID，否则为 null；不要编造资料名称。
11. 计划必须结合当前学习进度、未学知识点、薄弱知识点、错题/负向事件、资料库相关内容、考试范围或试卷题型。
12. 如果资料不足，正常生成，并在 summary 中说明"根据当前已有学习数据生成"。
13. 每天最多 3-4 个任务，estimated_minutes 在 10 到 120 之间。
14. 所有字符串内不能包含未转义的英文双引号。如果字符串内容需要引号，请使用中文引号""或单引号。
15. JSON 数组和对象之间必须有英文逗号分隔，不要漏掉逗号。
16. 不允许在 JSON 内部使用 // 或 /* */ 注释。
17. 输出任务数量不要超过 8 个，避免 JSON 过长。
18. related_material_ids 必须是数组，source_evidence 必须是数组。
19. 不确定字段用空字符串 ""、0 或空数组 []，不要省略任何关键字段。
20. 不要输出 ```json 或 ``` 标记，从第一个 { 开始，到最后一个 } 结束。"""


def _extract_json_bracket_balanced(text: str) -> str | None:
    """Extract the first complete JSON object using bracket balancing.

    Handles:
    - Text before/after the JSON object (AI explanations)
    - Nested braces in string values
    - Escape sequences within strings
    - Markdown code fences
    """
    cleaned = text.strip()

    # Remove markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*\n", "", cleaned)
    cleaned = re.sub(r"\n```\s*$", "", cleaned)

    start = cleaned.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(cleaned)):
        ch = cleaned[i]

        if escape_next:
            escape_next = False
            continue

        if ch == "\\":
            escape_next = True
            continue

        if ch == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start:i + 1]

    return None


def _repair_json_with_ai(bad_json_text: str, parse_error: str) -> str | None:
    """Call AI to repair malformed JSON.

    Returns repaired JSON string, or None if repair fails.
    """
    repair_prompt = f"""下面是一段不合法 JSON，请只修复为合法 JSON。

要求：
- 只输出修复后的 JSON，从 {{ 开始到 }} 结束
- 不要 Markdown 代码块
- 不要解释文字
- 不要新增无关字段
- 不要删除 tasks/items 数组中的任何条目
- 保持中文内容原样
- 字符串中的英文双引号必须正确转义（用 \\" 转义）
- 数组和对象之间必须补齐逗号
- 输出必须能被 Python json.loads 解析

原始解析错误：
{parse_error[:500]}

原始内容：
{bad_json_text[:8000]}"""

    try:
        messages = [
            {"role": "system", "content": "你是一个 JSON 修复工具。只输出修复后的合法 JSON，不要任何其他内容。"},
            {"role": "user", "content": repair_prompt},
        ]
        repaired = call_deepseek(messages, timeout_seconds=45)
        if not repaired or not repaired.strip():
            return None
        # Extract JSON from repaired response
        extracted = _extract_json_bracket_balanced(repaired)
        return extracted or repaired.strip()
    except Exception:
        return None


def _build_plan_from_parsed_items(
    items: list[dict],
    data: dict,
    fallback_title: str,
    fallback_summary: str,
) -> dict:
    """Build a standardized plan dict from already-parsed items."""
    return {
        "plan_title": _normalize_plan_text(
            str(data.get("plan_title") or fallback_title).strip(),
            fallback_title,
            40,
        ),
        "summary": _normalize_plan_text(
            str(data.get("summary") or "").strip(),
            fallback_summary,
            160,
        ),
        "total_tasks": int(data.get("total_tasks") or len(items)),
        "total_minutes": int(data.get("total_minutes") or sum(item.get("estimated_minutes", 30) for item in items)),
        "key_knowledge_points": (
            data.get("key_knowledge_points")
            if isinstance(data.get("key_knowledge_points"), list)
            else []
        ),
        "question_type_analysis": (
            data.get("question_type_analysis")
            if isinstance(data.get("question_type_analysis"), list)
            else []
        ),
        "items": items,
        "fallback_used": False,
        "warning": "",
    }


def _normalize_plan_items(
    raw_items: list,
    valid_kp_ids: set[int],
    course_id: str | None = None,
) -> list[dict]:
    """Normalize and validate raw plan items from AI output.

    Returns a list of standardized task dicts, filtering out invalid entries.
    """
    if not isinstance(raw_items, list):
        return []

    items = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        description = str(item.get("description") or "").strip()
        course_id_val = str(item.get("course_id") or course_id or "").strip()
        course_name = str(item.get("course_name") or course_id_val or "").strip()
        kp_name = str(item.get("knowledge_point_name") or item.get("knowledge_point_title") or "").strip()
        kp_id = item.get("knowledge_point_id")
        if kp_id is not None and isinstance(kp_id, (int, float)):
            kp_id = int(kp_id)
            if kp_id not in valid_kp_ids:
                kp_id = None
        else:
            kp_id = None
        task_type = _normalize_plan_task_type(item.get("task_type"))
        try:
            estimated = int(item.get("estimated_minutes", 30))
        except Exception:
            estimated = 30
        estimated = max(10, min(120, estimated))
        priority = str(item.get("priority") or "medium").strip().lower()
        if priority not in ALLOWED_PRIORITIES:
            priority = "medium"
        try:
            day_index = int(item.get("day_index", 1))
        except Exception:
            day_index = 1
        fallback_title = _fallback_task_title(
            {**item, "course_id": course_id_val}, course_id_val, index
        )
        title_final = _normalize_plan_text(title, fallback_title, 20)
        description = _normalize_plan_text(
            description,
            f"围绕{kp_name or course_name or '当前课程'}安排{PLAN_TASK_TYPE_CN.get(task_type, '学习')}，结合进度完成巩固。",
            100,
        )
        reason = _normalize_plan_text(
            str(item.get("reason") or "").strip(),
            "该任务结合当前学习进度、薄弱点或复习范围安排。",
            80,
        )
        related_material_ids = item.get("related_material_ids") or []
        if not isinstance(related_material_ids, list):
            related_material_ids = []
        related_material_ids = [
            int(mid) for mid in related_material_ids[:5] if str(mid).isdigit()
        ]
        source_evidence = item.get("source_evidence") or []
        if not isinstance(source_evidence, list):
            source_evidence = []

        items.append({
            "day_index": day_index,
            "title": title_final,
            "description": description,
            "course_id": course_id_val,
            "course_name": course_name or course_id_val,
            "knowledge_point_id": kp_id,
            "knowledge_point_name": kp_name,
            "task_type": task_type,
            "estimated_minutes": estimated,
            "priority": priority,
            "reason": reason,
            "related_material_ids": related_material_ids,
            "source_evidence": [_truncate_text(ev, 120) for ev in source_evidence[:3]],
        })

    return items


def _parse_plan_json(raw_text: str, valid_kp_ids: set[int], username: str) -> dict:
    """Parse and validate AI-generated plan JSON with repair retry and fallback.

    Strategy:
    1. Bracket-balanced JSON extraction
    2. First json.loads attempt
    3. AI repair retry on failure
    4. Fallback plan if all above fail
    Never raises HTTPException — always returns a valid plan dict.
    """
    logger = logging.getLogger("plan_parser")

    # ── Step 1: Extract JSON via bracket balancing ──
    json_text = _extract_json_bracket_balanced(raw_text)
    if not json_text:
        logger.warning("plan_parser: no JSON object found in AI response, first 300 chars: %s", raw_text[:300])
        return _build_fallback_plan_result(
            valid_kp_ids, username, reason="AI 返回中未找到 JSON 对象"
        )

    # ── Step 2: First parse attempt ──
    data = None
    parse_error = ""
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        parse_error = str(exc)
        logger.warning("plan_parser: first json.loads failed: %s", parse_error)

    # ── Step 3: Try common manual fixes ──
    if data is None:
        fixed_text = _try_manual_json_fixes(json_text, parse_error)
        if fixed_text:
            try:
                data = json.loads(fixed_text)
                logger.info("plan_parser: manual JSON fix succeeded")
                parse_error = ""
            except json.JSONDecodeError as exc2:
                parse_error = str(exc2)
                logger.warning("plan_parser: manual fix also failed: %s", parse_error)

    # ── Step 4: AI repair retry ──
    if data is None:
        logger.info("plan_parser: attempting AI repair...")
        repaired = _repair_json_with_ai(json_text, parse_error)
        if repaired:
            try:
                data = json.loads(repaired)
                logger.info("plan_parser: AI repair succeeded")
                parse_error = ""
            except json.JSONDecodeError as exc3:
                logger.warning("plan_parser: AI repair also failed: %s", exc3)

    # ── Step 5: Fallback if all parsing failed ──
    if data is None:
        logger.warning("plan_parser: all parse attempts failed, using fallback plan")
        return _build_fallback_plan_result(
            valid_kp_ids, username,
            reason="AI 输出格式异常，已根据当前课程和输入信息生成基础计划。"
        )

    # ── Step 6: Extract and validate items ──
    raw_items = data.get("items", data.get("tasks", []))
    if not isinstance(raw_items, list) or len(raw_items) == 0:
        logger.warning("plan_parser: no items/tasks in parsed data")
        return _build_fallback_plan_result(
            valid_kp_ids, username,
            reason="AI 返回的计划任务为空，已根据当前学习数据生成基础计划。"
        )

    items = _normalize_plan_items(raw_items, valid_kp_ids)
    if not items:
        logger.warning("plan_parser: no valid items after normalization")
        return _build_fallback_plan_result(
            valid_kp_ids, username,
            reason="AI 返回的计划中没有有效任务，已根据当前学习数据生成基础计划。"
        )

    return _build_plan_from_parsed_items(
        items, data,
        fallback_title="智能学习计划",
        fallback_summary="根据当前已有学习数据生成计划。",
    )


def _try_manual_json_fixes(json_text: str, parse_error: str) -> str | None:
    """Try common manual fixes for malformed JSON.

    Returns fixed JSON string or None.
    """
    fixed = json_text

    # Fix 1: Remove trailing commas before ] or }
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

    # Fix 2: Fix common Unicode/smart quote issues inside JSON strings
    fixed = fixed.replace(""", '\\"').replace(""", '\\"')  # left/right double quotes
    fixed = fixed.replace("'", "'").replace("'", "'")       # left/right single quotes
    fixed = fixed.replace("—", "-")  # em dash

    # Fix 3: Try to fix missing commas (only if parse error indicates it)
    if "Expecting ',' delimiter" in parse_error or "Expecting value" in parse_error:
        # Add commas between adjacent quoted strings in arrays/objects
        fixed = re.sub(r'"\s*\n\s*"', '",\n"', fixed)
        fixed = re.sub(r'"\s*\n\s*\{', '",\n{', fixed)
        fixed = re.sub(r'\]\s*\n\s*"', '],\n"', fixed)
        fixed = re.sub(r'\}\s*\n\s*"', '},\n"', fixed)
        # Add comma before next object in array: }{ -> },{
        fixed = re.sub(r'\}\s*\n\s*\{', '},\n{', fixed)

    if fixed != json_text:
        return fixed
    return None


def _build_fallback_plan_result(
    valid_kp_ids: set[int],
    username: str,
    reason: str = "AI 输出格式异常，已根据当前课程和输入信息生成基础计划。",
    course_id: str = "",
    daily_minutes: int = 60,
) -> dict:
    """Build a fallback plan when AI JSON parsing completely fails.

    The fallback plan has 3-5 basic Chinese tasks and ensures stable frontend rendering.
    """
    per_task = max(15, min(60, round(daily_minutes / 3)))
    task_types = ["reading", "practice", "summary"]
    task_type_labels = {
        "reading": "阅读资料",
        "practice": "练习",
        "summary": "总结",
    }

    items = []
    for i in range(3):
        kp_name = "当前课程内容"
        items.append({
            "day_index": 1,
            "title": f"学习任务 {i + 1}：基础巩固",
            "description": (
                f"步骤 {i + 1}：{reason[:40]}。"
                f"请根据当前学习进度，完成本阶段{task_type_labels.get(task_types[i], '学习')}任务。"
            ),
            "course_id": course_id,
            "course_name": course_id or "全部课程",
            "knowledge_point_id": None,
            "knowledge_point_name": kp_name,
            "task_type": task_types[i % 3],
            "estimated_minutes": per_task,
            "priority": "medium",
            "reason": reason[:80],
            "related_material_ids": [],
            "source_evidence": [reason[:120]] if reason else [],
        })

    return {
        "plan_title": "智能学习计划",
        "summary": reason[:160] if reason else "根据当前已有学习数据生成基础计划。",
        "total_tasks": len(items),
        "total_minutes": sum(item["estimated_minutes"] for item in items),
        "key_knowledge_points": [],
        "question_type_analysis": [],
        "items": items,
        "fallback_used": True,
        "warning": "AI 输出格式异常，已根据当前课程和输入信息生成基础学习计划，可点击重新生成获得更完整计划。",
    }


def _generate_plan_preview_core(
    req: PlanGeneratePreviewRequest,
    db: Session,
    scope_file_texts: list[str] | None = None,
    paper_file_texts: list[str] | None = None,
):
    user = get_user_by_username(req.username, db)

    if req.plan_type not in ALLOWED_PLAN_TYPES:
        raise HTTPException(status_code=400, detail=f"无效的计划类型：{req.plan_type}")
    if req.plan_scene not in ALLOWED_PLAN_SCENES:
        req.plan_scene = "daily"

    plan_data = _gather_plan_data(req.username, req.course_id, db)
    exam_scope_text = _truncate_text(req.exam_scope_text or "", 1200)
    scope_file_texts = scope_file_texts or []
    paper_file_texts = paper_file_texts or []
    combined_query = " ".join([
        req.goal or "",
        req.course_id or "",
        exam_scope_text,
        " ".join(scope_file_texts)[:1200],
    ])
    material_context = _get_plan_material_context(
        req.username,
        req.course_id,
        req.selected_material_ids,
        combined_query,
        db,
    )
    paper_analysis = _analyze_exam_paper_text(paper_file_texts)

    # Build valid knowledge point ID set
    valid_kp_ids = {wp["id"] for wp in plan_data["weak_points"]}
    valid_kp_ids.update(wp["id"] for wp in plan_data.get("not_started_points", []))
    for t in plan_data["unfinished_tasks"]:
        if t["knowledge_point_id"]:
            valid_kp_ids.add(t["knowledge_point_id"])

    # Count total knowledge points
    all_kp_count = db.query(models.KnowledgePoint).filter(
        models.KnowledgePoint.username == req.username
    ).count()

    user_prompt_parts = [
        f"计划场景：{req.plan_scene}",
        f"计划类型：{req.plan_type}",
        f"计划天数：{req.days}",
        f"每日学习时间：{req.daily_minutes} 分钟",
        f"学习目标：{req.goal or '无特定目标'}",
    ]
    if req.course_id:
        user_prompt_parts.append(f"课程范围：{req.course_id}")

    user_prompt_parts.append("")
    user_prompt_parts.append("--- 用户学习数据 ---")

    user_prompt_parts.append(f"知识点总数：{all_kp_count}")
    user_prompt_parts.append(f"资料总数：{plan_data['material_count']}")

    # Weak points
    user_prompt_parts.append(f"\n薄弱知识点（掌握度 < 40，{len(plan_data['weak_points'])} 个）：")
    for wp in plan_data["weak_points"]:
        user_prompt_parts.append(
            f"  - id={wp['id']}，名称={wp['title']}，课程={wp['course_id']}，"
            f"掌握度={wp['mastery_score']}%，状态={wp['status']}"
        )

    user_prompt_parts.append(f"\n未开始知识点（{len(plan_data['not_started_points'])} 个）：")
    for wp in plan_data["not_started_points"][:10]:
        user_prompt_parts.append(f"  - id={wp['id']}，名称={wp['title']}，课程={wp['course_id']}")

    # Wrong questions
    user_prompt_parts.append(f"\n近期错题（{len(plan_data['wrong_questions'])} 个）：")
    for wq in plan_data["wrong_questions"]:
        user_prompt_parts.append(
            f"  - {wq['title']}（课程：{wq['course_id']}，"
            f"用户答案：{wq['user_answer'][:80]}，参考答案：{wq['correct_answer'][:80]}）"
        )

    # Unfinished tasks
    user_prompt_parts.append(f"\n未完成任务（{len(plan_data['unfinished_tasks'])} 个）：")
    for t in plan_data["unfinished_tasks"]:
        user_prompt_parts.append(
            f"  - {t['title']}（类型={t['task_type']}，状态={t['status']}，"
            f"课程={t['course_id']}，知识点 id={t['knowledge_point_id']}）"
        )

    # Negative events
    user_prompt_parts.append(f"\n负向掌握事件（{len(plan_data['negative_events'])} 个）：")
    for e in plan_data["negative_events"]:
        user_prompt_parts.append(
            f"  - 知识点={e['knowledge_point_title'] or e['knowledge_point_id']}，"
            f"变化={e['delta']}，类型={e['event_type']}，原因={e['reason'][:60]}"
        )

    # Code sessions
    user_prompt_parts.append(f"\n近期代码练习（{len(plan_data['code_sessions'])} 个）：")
    for cs in plan_data["code_sessions"]:
        user_prompt_parts.append(f"  - {cs['title']}（{cs['language']}，课程={cs['course_id']}）")

    user_prompt_parts.append(f"\n近期学习记录（{len(plan_data['learning_records'])} 条）：")
    for record in plan_data["learning_records"]:
        user_prompt_parts.append(f"  - {record['subject']}：{record['question']}（{record['record_type']}）")

    if exam_scope_text or scope_file_texts:
        user_prompt_parts.append("\n--- 考试范围 ---")
        if exam_scope_text:
            user_prompt_parts.append(f"考试范围文本：{exam_scope_text}")
        for index, scope_text in enumerate(scope_file_texts[:3], 1):
            user_prompt_parts.append(f"考试范围文件 {index} 摘要：{_truncate_text(scope_text, 600)}")

    user_prompt_parts.append("\n--- 资料库相关内容 ---")
    if material_context:
        for material in material_context:
            user_prompt_parts.append(f"资料 id={material['material_id']}，标题={material['title']}，摘要={material['summary']}")
            for chunk in material["chunks"][:4]:
                user_prompt_parts.append(f"  - 相关片段：{chunk['summary'] or chunk['text']}")
    else:
        user_prompt_parts.append("当前课程暂无可用资料片段，请根据学习进度降级生成。")

    if paper_file_texts:
        user_prompt_parts.append("\n--- 往年卷/模拟卷分析 ---")
        user_prompt_parts.append(f"题型分析：{json.dumps(paper_analysis['question_type_analysis'], ensure_ascii=False)}")
        user_prompt_parts.append(f"高频知识点：{', '.join(paper_analysis['key_knowledge_points']) or '暂未识别'}")
        user_prompt_parts.append(f"复习建议：{'；'.join(paper_analysis['paper_suggestions']) or '根据当前试卷内容安排复习'}")

    # Instruction
    user_prompt_parts.append(f"\n--- 生成要求 ---")
    user_prompt_parts.append("生成中文 JSON 学习计划，任务标题和描述必须是中文。")
    user_prompt_parts.append("优先安排未开始知识点、掌握度低的知识点、错题和负向事件相关知识点。")
    user_prompt_parts.append("不要重复安排已经掌握较高且近期刚完成的知识点。")
    if req.plan_scene == "exam" or req.plan_type == "exam":
        user_prompt_parts.append("这是期末考试复习计划，必须结合考试范围、资料片段和试卷题型安排复习。")
    elif req.plan_scene == "daily":
        user_prompt_parts.append("这是日常学习计划，必须结合课程学习进度和薄弱知识点安排。")
    elif req.plan_scene == "coding" or req.plan_type == "coding":
        user_prompt_parts.append("这是编程训练计划，优先安排代码练习、代码复盘和相关知识点巩固。")
    user_prompt_parts.append("related_material_ids 只能使用上方资料 id；不确定就返回空数组。")
    user_prompt_parts.append("source_evidence 写简短依据，例如资料标题、考试范围或薄弱点名称。")
    user_prompt_parts.append("使用上方已有 knowledge_point_id；无法匹配则为 null。")
    user_prompt_parts.append("每个任务标题不要超过 20 个中文字符，描述不要超过 100 个中文字符。")

    user_prompt = "\n".join(user_prompt_parts)

    messages = [
        {"role": "system", "content": PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    if is_exam_408_context(req.course_id, ""):
        check_exam_408_usage_limit(user, "learning_plan_generate", db)
    else:
        check_usage_limit(user.username, "learning_plan_generate", db)

    ai_call_failed = False
    raw = ""
    try:
        raw = call_deepseek(messages)

        record_ai_usage(user.username, "learning_plan_generate", db, estimated_tokens=estimate_tokens_from_text(raw), status="success")
    except HTTPException:
        raise
    except Exception as exc:
        # Log the failure but continue with fallback
        logger = logging.getLogger("plan_generator")
        logger.warning("AI plan generation call failed: %s", exc)
        ai_call_failed = True

    if ai_call_failed or not raw:
        # Build fallback plan directly — skip JSON parsing entirely
        result = _build_fallback_plan_result(
            valid_kp_ids, req.username,
            reason="AI 服务暂时不可用，已根据当前学习数据生成基础计划。",
            course_id=req.course_id or "",
            daily_minutes=req.daily_minutes,
        )
    else:
        result = _parse_plan_json(raw, valid_kp_ids, req.username)

    if _looks_english(result["plan_title"]):
        result["plan_title"] = _fallback_plan_title(req.course_id, req.plan_type, req.plan_scene)
    if not result["items"]:
        result["items"] = _build_default_plan_items(req, plan_data)
    fallback_course = normalize_subject(req.course_id, default="") or req.course_id or ""
    for item in result["items"]:
        if not item.get("course_id") and fallback_course:
            item["course_id"] = fallback_course
        if not item.get("course_name") and item.get("course_id"):
            item["course_name"] = item["course_id"]
    if not result.get("key_knowledge_points"):
        result["key_knowledge_points"] = [
            item.get("title") for item in (plan_data.get("weak_points") or plan_data.get("not_started_points") or [])[:6]
            if item.get("title")
        ]
    if paper_analysis.get("question_type_analysis") and not result.get("question_type_analysis"):
        result["question_type_analysis"] = paper_analysis["question_type_analysis"]

    # Add course_name for frontend display
    course_name = req.course_id if req.course_id else "全部课程"

    return {
        "plan_title": result["plan_title"],
        "plan_type": req.plan_type,
        "plan_scene": req.plan_scene,
        "summary": result["summary"],
        "total_tasks": result["total_tasks"],
        "total_minutes": result["total_minutes"],
        "course_name": course_name,
        "key_knowledge_points": result.get("key_knowledge_points", []),
        "question_type_analysis": result.get("question_type_analysis", []),
        "exam_analysis": {
            "question_types": result.get("question_type_analysis", []),
            "key_knowledge_points": result.get("key_knowledge_points", []),
            "suggestions": paper_analysis.get("paper_suggestions", []),
        },
        "material_context": [
            {"material_id": item["material_id"], "title": item["title"]}
            for item in material_context
        ],
        "paper_suggestions": paper_analysis.get("paper_suggestions", []),
        "items": result["items"],
        "fallback_used": result.get("fallback_used", False),
        "warning": result.get("warning", ""),
    }


@app.post("/learning/plans/generate-preview")
def generate_plan_preview(req: PlanGeneratePreviewRequest, db: Session = Depends(get_db)):
    return _generate_plan_preview_core(req, db)


@app.post("/learning/plans/generate-preview-advanced")
async def generate_plan_preview_advanced(
    username: str = Form(...),
    course_id: str = Form(""),
    plan_type: str = Form("seven_day"),
    plan_scene: str = Form("daily"),
    days: int = Form(7),
    goal: str = Form(""),
    daily_minutes: int = Form(60),
    exam_scope_text: str = Form(""),
    selected_material_ids: str = Form("[]"),
    scope_files: list[UploadFile] = File(default=[]),
    paper_files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    try:
        parsed_ids = json.loads(selected_material_ids or "[]")
        if not isinstance(parsed_ids, list):
            parsed_ids = []
    except Exception:
        parsed_ids = []
    req = PlanGeneratePreviewRequest(
        username=username,
        course_id=course_id,
        plan_type=plan_type,
        plan_scene=plan_scene,
        days=days,
        goal=goal,
        daily_minutes=daily_minutes,
        exam_scope_text=exam_scope_text,
        selected_material_ids=[int(mid) for mid in parsed_ids[:10] if str(mid).isdigit()],
    )
    scope_texts = [_extract_text_from_upload(file) for file in (scope_files or [])[:3]]
    paper_texts = [_extract_text_from_upload(file) for file in (paper_files or [])[:3]]
    return _generate_plan_preview_core(req, db, scope_texts, paper_texts)


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

        task_type = _normalize_plan_task_type(item.get("task_type"))

        priority = str(item.get("priority") or "medium").strip().lower()
        if priority not in ALLOWED_PRIORITIES:
            priority = "medium"

        day_index = max(1, int(item.get("day_index", 1)))
        due_date = datetime.combine(today + timedelta(days=min(day_index - 1, 30)), datetime.min.time())
        estimated = max(10, min(120, int(item.get("estimated_minutes") or 30)))
        reason = _truncate_text(item.get("reason") or "", 80)
        source_evidence = item.get("source_evidence") or []
        if not isinstance(source_evidence, list):
            source_evidence = []
        description_parts = [description]
        description_parts.append(f"预计用时：{estimated} 分钟。")
        if reason:
            description_parts.append(f"安排原因：{reason}")
        if source_evidence:
            description_parts.append(f"依据：{'；'.join(_truncate_text(ev, 60) for ev in source_evidence[:2])}")
        description = "\n".join(part for part in description_parts if part)
        related_material_ids = item.get("related_material_ids") or []
        related_material_id = 0
        if isinstance(related_material_ids, list) and related_material_ids:
            try:
                related_material_id = int(related_material_ids[0])
            except Exception:
                related_material_id = 0

        # Build metadata with full context for detail display
        task_metadata = {
            "related_material_ids": related_material_ids if isinstance(related_material_ids, list) else [],
            "source_evidence": source_evidence,
            "estimated_minutes": estimated,
            "reason": reason,
        }
        exam_analysis = item.get("exam_analysis")
        if exam_analysis and isinstance(exam_analysis, dict):
            task_metadata["exam_analysis"] = exam_analysis

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
            knowledge_point_text=str(item.get("knowledge_point_name") or "").strip(),
            related_material_id=related_material_id or None,
            task_metadata=json.dumps(task_metadata, ensure_ascii=False),
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


# ── Material Analyze Knowledge Preview ──────────────────

MAX_ANALYZE_CHUNKS_PER_MATERIAL = 10
MAX_ANALYZE_CHARS_PER_MATERIAL = 6000
MAX_TOTAL_ANALYZE_CHARS = 20000

ANALYZE_KNOWLEDGE_PROMPT = """你是一个课程知识结构分析专家。请基于以下课程资料内容，提取适合学生学习路线使用的知识点树。

要求：
1. 使用中文。
2. 生成 3 到 8 个大模块。
3. 每个大模块下生成 2 到 8 个小知识点。
4. 大模块不要太细，每个大模块应涵盖一个相对完整的知识领域。
5. 小知识点要具体、可测量，可用于任务绑定和练习筛选。
6. 每个大模块和知识点给一句简短说明（1-2句话）。
7. 每个小知识点需要标注 source_material_titles（引用了哪些资料）。
8. 不要生成与资料内容无关的知识点。
9. 如果资料内容不足，生成较少的大模块，并在第一个模块的 description 中说明。
10. 只输出 JSON，不要输出 Markdown。

JSON 格式：
{
  "knowledge_tree": [
    {
      "title": "进程管理",
      "description": "围绕进程的创建、调度、同步与通信展开的基础知识模块",
      "children": [
        {
          "title": "进程与线程",
          "description": "理解进程和线程的基本概念、区别与适用场景",
          "source_material_titles": ["操作系统第一章.pdf"]
        }
      ]
    }
  ]
}"""


@app.post("/materials/analyze-knowledge-preview")
def analyze_knowledge_preview(req: schemas.MaterialAnalyzeKnowledgeRequest, db: Session = Depends(get_db)):
    """Analyze selected materials and return a knowledge tree preview (no DB writes)."""
    user = get_user_by_username(req.username, db)
    course_id = normalize_subject(req.course_id)

    if not course_id:
        raise HTTPException(status_code=400, detail="课程不能为空")

    if not req.material_ids or len(req.material_ids) == 0:
        raise HTTPException(status_code=400, detail="请至少选择一份资料")

    # Validate and fetch materials
    materials = query_accessible_materials(db, user.username).filter(
        models.StudyMaterial.id.in_(req.material_ids),
        models.StudyMaterial.subject == course_id,
        models.StudyMaterial.allow_generate_knowledge.is_(True),
    ).all()

    if not materials:
        raise HTTPException(status_code=404, detail="所选资料不存在或不属于当前课程")

    material_info = [
        {"id": m.id, "title": m.original_filename}
        for m in materials
    ]

    # Collect text content from chunks, falling back to extracted_text
    content_parts = []
    total_chars = 0
    for mat in materials:
        mat_chars = 0
        if is_reference_metadata_material(mat):
            ref_text = (mat.summary or mat.extracted_text or "").strip()
            if ref_text:
                content_parts.append(
                    f"【目录级参考资料：{mat.original_filename}】\n{ref_text}\n"
                    "提示：该资料仅可用于章节定位、知识点标题和层级关系，不包含第三方正文。"
                )
                total_chars += len(ref_text)
                mat_chars += len(ref_text)
            if mat_chars == 0:
                content_parts.append(f"【目录级参考资料：{mat.original_filename}】\n（暂无目录级索引内容）")
            continue

        # Try chunks first
        chunks = (
            db.query(models.MaterialChunk)
            .filter(
                models.MaterialChunk.material_id == mat.id,
                models.MaterialChunk.username == user.username,
                models.MaterialChunk.is_deleted.is_(False),
            )
            .order_by(models.MaterialChunk.chunk_index)
            .limit(MAX_ANALYZE_CHUNKS_PER_MATERIAL)
            .all()
        )

        if chunks:
            for chunk in chunks:
                chunk_text = (chunk.chunk_text or "").strip()
                if not chunk_text:
                    continue
                if total_chars + len(chunk_text) > MAX_TOTAL_ANALYZE_CHARS:
                    remaining = MAX_TOTAL_ANALYZE_CHARS - total_chars
                    if remaining > 200:
                        chunk_text = chunk_text[:remaining] + "..."
                    else:
                        break
                content_parts.append(f"【资料：{mat.original_filename}】\n{chunk_text}")
                total_chars += len(chunk_text)
                mat_chars += len(chunk_text)
        else:
            # Fallback to extracted_text
            ext_text = (mat.extracted_text or "").strip()
            if ext_text:
                if total_chars + len(ext_text) > MAX_TOTAL_ANALYZE_CHARS:
                    remaining = MAX_TOTAL_ANALYZE_CHARS - total_chars
                    if remaining > 200:
                        ext_text = ext_text[:remaining] + "..."
                    else:
                        ext_text = ""
                if ext_text:
                    content_parts.append(f"【资料：{mat.original_filename}】\n{ext_text}")
                    total_chars += len(ext_text)
                    mat_chars += len(ext_text)

        # If no useful content found for this material
        if mat_chars == 0:
            content_parts.append(f"【资料：{mat.original_filename}】\n（该资料暂无可用文本内容）")

    if not content_parts:
        raise HTTPException(status_code=400, detail="所选资料内容不足，无法分析。请确保资料已成功解析并生成了知识索引。")

    combined_content = "\n\n".join(content_parts)

    if len(combined_content.strip()) < 100:
        raise HTTPException(status_code=400, detail="资料内容不足，无法分析。请上传更多资料或等待资料解析完成后重试。")

    # Build AI prompt
    user_prompt = f"""课程：{course_id}
资料数量：{len(materials)} 份

以下是从所选资料中提取的内容片段，请根据这些内容生成知识点树：

{combined_content}"""

    check_usage_limit(user.username, "knowledge_generate", db)

    try:
        raw = call_deepseek(
            [{"role": "system", "content": ANALYZE_KNOWLEDGE_PROMPT},
             {"role": "user", "content": user_prompt}],
            temperature=0.3,
            max_tokens=3000,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="AI 分析失败，请稍后重试") from exc

    record_ai_usage(
        user.username, "knowledge_generate", db,
        estimated_tokens=estimate_tokens_from_text(user_prompt) + estimate_tokens_from_text(raw),
        status="success",
    )

    # Parse JSON response
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
        raise HTTPException(status_code=500, detail="AI 返回格式异常，未能生成有效的知识点结构。请稍后重试。")

    try:
        result = json.loads(text[json_start:json_end + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"AI 返回数据解析失败，请稍后重试。错误详情：{str(exc)[:200]}")

    knowledge_tree = result.get("knowledge_tree", [])
    if not isinstance(knowledge_tree, list):
        knowledge_tree = []

    # Validate and clean tree structure
    cleaned_tree = []
    for module in knowledge_tree:
        if not isinstance(module, dict):
            continue
        title = str(module.get("title", "")).strip()
        if not title:
            continue
        desc = str(module.get("description", "")).strip()
        children = module.get("children", [])
        if not isinstance(children, list):
            children = []

        cleaned_children = []
        for child in children:
            if not isinstance(child, dict):
                continue
            child_title = str(child.get("title", "")).strip()
            if not child_title:
                continue
            child_desc = str(child.get("description", "")).strip()
            sources = child.get("source_material_titles", [])
            if not isinstance(sources, list):
                sources = []
            cleaned_children.append({
                "title": child_title,
                "description": child_desc,
                "source_material_titles": [str(s) for s in sources if s],
            })

        cleaned_tree.append({
            "title": title,
            "description": desc,
            "children": cleaned_children,
        })

    if not cleaned_tree:
        raise HTTPException(status_code=500, detail="未能从资料中提取有效知识点。请确认资料内容与课程相关，或尝试选择更多资料后重试。")

    return {
        "success": True,
        "course_id": course_id,
        "materials": material_info,
        "knowledge_tree": cleaned_tree,
    }


@app.post("/materials/confirm-knowledge-tree")
def confirm_knowledge_tree(req: schemas.MaterialConfirmKnowledgeTreeRequest, db: Session = Depends(get_db)):
    """Write confirmed knowledge tree preview to knowledge_points with dedup."""
    user = get_user_by_username(req.username, db)
    course_id = normalize_subject(req.course_id)

    if not course_id:
        raise HTTPException(status_code=400, detail="课程不能为空")

    if not req.knowledge_tree or not isinstance(req.knowledge_tree, list) or len(req.knowledge_tree) == 0:
        raise HTTPException(status_code=400, detail="知识点树不能为空")

    # Validate material_ids belong to user and course
    if req.material_ids:
        valid_materials = query_accessible_materials(db, user.username).filter(
            models.StudyMaterial.id.in_(req.material_ids),
            models.StudyMaterial.subject == course_id,
            models.StudyMaterial.allow_generate_knowledge.is_(True),
        ).count()
        # Non-fatal: just log, don't block the write
        _ = valid_materials

    created_modules = 0
    created_points = 0
    skipped_duplicates = 0
    all_created = []

    # Query existing knowledge points for this course (for dedup)
    existing_all = (
        db.query(models.KnowledgePoint)
        .filter(
            models.KnowledgePoint.username == user.username,
            models.KnowledgePoint.course_id == course_id,
        )
        .all()
    )
    existing_by_title = {}
    for kp in existing_all:
        key = (kp.parent_id, kp.title.strip())
        existing_by_title[key] = kp

    try:
        for module in req.knowledge_tree:
            if not isinstance(module, dict):
                continue
            module_title = str(module.get("title", "")).strip()
            if not module_title:
                continue
            module_desc = str(module.get("description", "")).strip()

            # Dedup: check if module with same title exists in this course (parent_id=None)
            module_key = (None, module_title)
            if module_key in existing_by_title:
                parent_kp = existing_by_title[module_key]
                # Update description if empty
                if module_desc and not (parent_kp.description or "").strip():
                    parent_kp.description = module_desc[:255]
                skipped_duplicates += 1
            else:
                # Get max order_index for this course
                max_order = (
                    db.query(models.KnowledgePoint)
                    .filter(
                        models.KnowledgePoint.username == user.username,
                        models.KnowledgePoint.course_id == course_id,
                        models.KnowledgePoint.parent_id.is_(None),
                    )
                    .count()
                )
                parent_kp = models.KnowledgePoint(
                    username=user.username,
                    course_id=course_id,
                    parent_id=None,
                    title=module_title[:255],
                    description=module_desc[:255],
                    order_index=max_order,
                    level=1,
                )
                db.add(parent_kp)
                db.flush()
                existing_by_title[module_key] = parent_kp
                created_modules += 1

            all_created.append({"id": parent_kp.id, "title": parent_kp.title, "level": 1, "is_new": not (module_key in existing_by_title and skipped_duplicates > 0)})

            # Process children
            children = module.get("children", [])
            if not isinstance(children, list):
                continue

            for child in children:
                if not isinstance(child, dict):
                    continue
                child_title = str(child.get("title", "")).strip()
                if not child_title:
                    continue
                child_desc = str(child.get("description", "")).strip()

                # Dedup: check if child with same title exists under this parent
                child_key = (parent_kp.id, child_title)
                if child_key in existing_by_title:
                    existing_child = existing_by_title[child_key]
                    if child_desc and not (existing_child.description or "").strip():
                        existing_child.description = child_desc[:255]
                    skipped_duplicates += 1
                    all_created.append({"id": existing_child.id, "title": existing_child.title, "level": 2, "is_new": False})
                else:
                    child_count = (
                        db.query(models.KnowledgePoint)
                        .filter(
                            models.KnowledgePoint.username == user.username,
                            models.KnowledgePoint.course_id == course_id,
                            models.KnowledgePoint.parent_id == parent_kp.id,
                        )
                        .count()
                    )
                    child_kp = models.KnowledgePoint(
                        username=user.username,
                        course_id=course_id,
                        parent_id=parent_kp.id,
                        title=child_title[:255],
                        description=child_desc[:255],
                        order_index=child_count,
                        level=2,
                    )
                    db.add(child_kp)
                    db.flush()
                    existing_by_title[child_key] = child_kp
                    created_points += 1
                    all_created.append({"id": child_kp.id, "title": child_kp.title, "level": 2, "is_new": True})

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="写入知识点树失败，请稍后重试。")

    return {
        "success": True,
        "created_modules": created_modules,
        "created_points": created_points,
        "skipped_duplicates": skipped_duplicates,
        "knowledge_points": all_created,
    }


# ══════════════════════════════════════════════════════════════
#  MEMBERSHIP SYSTEM
# ══════════════════════════════════════════════════════════════


class RedeemRequest(BaseModel):
    code: str


class ManualRecommendRequest(BaseModel):
    selected_plan: str


@app.get("/membership/plans")
def get_membership_plans(username: str, db: Session = Depends(get_db)):
    """Return visible plans. Developer accounts also get their special plan."""
    user = get_user_by_username(username, db)
    effective = get_effective_plan(user, db)
    is_dev = effective["is_developer"]

    plans = []
    for code, defn in PLAN_DEFINITIONS.items():
        if not defn["visible"] and code not in ("gift_pro", "developer"):
            continue
        if code == "gift_pro":
            continue
        if code == "developer" and not is_dev:
            continue
        plans.append({
            "plan_code": code,
            "name": defn["name"],
            "price_cents": defn["price_cents"],
            "price_yuan": defn["price_cents"] / 100,
            "daily_ai_limit": defn["daily_ai_limit"],
            "daily_upload_limit": defn["daily_upload_limit"],
            "daily_code_limit": defn["daily_code_limit"],
            "requires_ads": defn.get("requires_ads", False),
            "description": defn.get("description", ""),
            "perks": defn.get("perks", ""),
            "allowed_languages": defn.get("allowed_languages", []),
            "is_recommended": False,
        })

    return {
        "plans": plans,
        "effective_plan": effective,
    }


@app.get("/membership/summary")
def get_membership_summary(username: str, db: Session = Depends(get_db)):
    """Return user's membership status summary."""
    user = get_user_by_username(username, db)
    effective = get_effective_plan(user, db)
    limits = get_plan_limits_v2(effective["plan_code"])

    return {
        "username": username,
        "current_plan": user.plan or "free",
        "effective_plan": effective,
        "limits": limits,
        "major": user.major or "",
        "grade": user.grade or "",
        "is_member": effective["plan_code"] not in ("free",),
        "requires_ads": PLAN_DEFINITIONS.get(effective["plan_code"], {}).get("requires_ads", False),
    }


@app.get("/membership/recommendation")
def get_membership_recommendation(username: str, db: Session = Depends(get_db)):
    """Get plan recommendation based on user's major."""
    user = get_user_by_username(username, db)
    effective = get_effective_plan(user, db)

    if effective["is_developer"]:
        return {
            "recommended_plan": "developer",
            "category": "developer",
            "confidence": 1.0,
            "reason": "开发者账号，已开放所有功能",
            "suggested_courses": [],
            "source": "role",
            "normalized_major": user.major or "",
            "needs_manual_choice": False,
        }

    major = user.major or ""
    grade = user.grade or ""

    if not major:
        return {
            "recommended_plan": "free",
            "category": "unknown",
            "confidence": 0.3,
            "reason": "未设置专业信息，请先在个人主页完善专业后再获取推荐",
            "suggested_courses": [],
            "source": "fallback",
            "normalized_major": "",
            "needs_manual_choice": True,
        }

    openai_client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL"),
    )
    result = recommend_plan_by_major(major, grade, db, openai_client)
    return result


@app.post("/membership/recommendation/manual")
def manual_recommendation(req: ManualRecommendRequest, username: str, db: Session = Depends(get_db)):
    """User manually selects a plan preference. Only affects this user."""
    if req.selected_plan not in ("python_basic", "engineering_plus", "cs_pro"):
        raise HTTPException(status_code=400, detail="无效的套餐选择")

    user = get_user_by_username(username, db)
    user.plan_source = f"manual:{req.selected_plan}"
    db.commit()

    return {
        "success": True,
        "selected_plan": req.selected_plan,
        "message": "已记录你的学习方向偏好",
    }


@app.post("/membership/redeem")
def redeem_membership_code(req: RedeemRequest, username: str, db: Session = Depends(get_db)):
    """Redeem a membership code."""
    if not req.code or not req.code.strip():
        raise HTTPException(status_code=400, detail="请输入兑换码")

    result = redeem_code(username, req.code.strip(), db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result


# ── Admin / Usage ──────────────────────────────────────────

ADMIN_ROLE_LABELS = {
    "super_admin": "超级管理员",
    "operator": "运营管理员",
    "auditor": "只读审计员",
    "none": "非管理员",
}

PERMISSIONS = {
    "dashboard.view",
    "users.view",
    "ai_logs.view",
    "materials.view",
    "courses.view",
    "audit_logs.view",
    "audit_logs.export",
    "report_shares.view",
    "system_monitor.view",
    "settings.view",
    "users.manage_status",
    "users.manage_plan",
    "users.manage_role",
    "materials.delete",
    "materials.reindex",
    "report_shares.moderate",
    "ai_logs.export",
    "settings.manage",
    "announcements.manage",
    "feature_flags.manage",
    "limits.manage",
    "batch.users",
    "batch.materials",
    "batch.reports",
    "backups.view",
    "backups.create",
    "backups.download",
    "backups.delete",
    "model_config.view",
    "model_config.manage",
}

ROLE_PERMISSIONS = {
    "super_admin": PERMISSIONS,
    "operator": {
        "dashboard.view",
        "users.view",
        "users.manage_status",
        "users.manage_plan",
        "ai_logs.view",
        "materials.view",
        "materials.delete",
        "materials.reindex",
        "courses.view",
        "report_shares.view",
        "report_shares.moderate",
        "system_monitor.view",
        "audit_logs.view",
        "batch.users",
        "batch.materials",
        "batch.reports",
    },
    "auditor": {
        "dashboard.view",
        "users.view",
        "ai_logs.view",
        "materials.view",
        "courses.view",
        "audit_logs.view",
        "report_shares.view",
        "system_monitor.view",
        "settings.view",
    },
    "none": set(),
}

VALID_ADMIN_ROLES = set(ROLE_PERMISSIONS.keys())


def get_admin_role_label(admin_role: str) -> str:
    return ADMIN_ROLE_LABELS.get(admin_role or "none", ADMIN_ROLE_LABELS["none"])


def normalize_admin_role(user) -> str:
    role = (getattr(user, "admin_role", None) or "none").strip()
    return role if role in VALID_ADMIN_ROLES else "none"


def get_admin_permissions(user) -> list[str]:
    role = normalize_admin_role(user)
    return sorted(ROLE_PERMISSIONS.get(role, set()))


def require_admin(username: str, db: Session):
    admin = get_user_by_username(username, db)
    ensure_user_can_access(admin)
    if getattr(admin, "is_active", 1) == 0:
        raise HTTPException(status_code=403, detail="管理员账号已被禁用")
    if not bool(getattr(admin, "is_admin", 0)):
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    if normalize_admin_role(admin) not in ("super_admin", "operator", "auditor"):
        raise HTTPException(status_code=403, detail="管理员角色无效")
    return admin


def require_admin_permission(db: Session, admin_username: str, permission: str):
    admin = require_admin(admin_username, db)
    if permission not in get_admin_permissions(admin):
        raise HTTPException(status_code=403, detail="当前管理员没有权限执行该操作")
    return admin


def require_super_admin(db: Session, admin_username: str):
    admin = require_admin(admin_username, db)
    if normalize_admin_role(admin) != "super_admin":
        raise HTTPException(status_code=403, detail="仅超级管理员可执行该操作")
    return admin


def count_active_super_admins(db: Session) -> int:
    return (
        db.query(models.User)
        .filter(
            models.User.is_admin == 1,
            models.User.is_active != 0,
            models.User.admin_role == "super_admin",
        )
        .count()
    )


def _audit_details_to_text(details):
    if details is None:
        return ""
    if isinstance(details, str):
        return details
    try:
        return json.dumps(details, ensure_ascii=False, default=str)
    except Exception:
        return str(details)


def _parse_audit_details(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _write_audit_log(admin_username: str, action: str, db: Session,
                     target_type: str = None, target_username: str = None,
                     detail: str = None, target_id: str = None,
                     result: str = "success", details=None, ip: str = None):
    try:
        log = models.AdminAuditLog(
            admin_username=admin_username,
            action=action,
            target_type=target_type or "",
            target_id=str(target_id or ""),
            target_username=target_username or "",
            result=result or "success",
            detail=detail or "",
            details=_audit_details_to_text(details),
            ip=ip or "",
        )
        db.add(log)
        db.commit()
    except Exception:
        logger.warning(f"Failed to write audit log for {admin_username}/{action}")


def _audit_action_label(action: str) -> str:
    labels = {
        "update_admin_role": "修改管理员角色",
        "update_plan": "修改用户套餐",
        "audit_logs_export": "导出审计日志",
        "backup_create": "创建数据备份",
        "backup_download": "下载数据备份",
        "backup_delete": "删除数据备份",
        "model_config_update": "修改模型配置",
    }
    return labels.get(action or "", action or "-")


def _parse_audit_datetime(value: str, end_of_day: bool = False):
    value = (value or "").strip()
    if not value:
        return None
    try:
        if len(value) == 10:
            parsed = datetime.fromisoformat(value)
            return parsed + timedelta(days=1) if end_of_day else parsed
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid audit log date filter")


def _build_admin_audit_query(
    db: Session,
    actor: str = "",
    action: str = "",
    target_type: str = "",
    keyword: str = "",
    start_date: str = "",
    end_date: str = "",
):
    query = db.query(models.AdminAuditLog)
    if actor_filter := (actor or "").strip():
        query = query.filter(models.AdminAuditLog.admin_username.contains(actor_filter))
    if action_filter := (action or "").strip():
        query = query.filter(models.AdminAuditLog.action.contains(action_filter))
    if target_type_filter := (target_type or "").strip():
        query = query.filter(models.AdminAuditLog.target_type == target_type_filter)
    if keyword_filter := (keyword or "").strip():
        like_filters = [
            models.AdminAuditLog.action.contains(keyword_filter),
            models.AdminAuditLog.target_type.contains(keyword_filter),
            models.AdminAuditLog.target_username.contains(keyword_filter),
            models.AdminAuditLog.detail.contains(keyword_filter),
        ]
        if hasattr(models.AdminAuditLog, "target_id"):
            like_filters.append(models.AdminAuditLog.target_id.contains(keyword_filter))
        if hasattr(models.AdminAuditLog, "details"):
            like_filters.append(models.AdminAuditLog.details.contains(keyword_filter))
        query = query.filter(or_(*like_filters))
    start_dt = _parse_audit_datetime(start_date)
    if start_dt:
        query = query.filter(models.AdminAuditLog.created_at >= start_dt)
    end_dt = _parse_audit_datetime(end_date, end_of_day=True)
    if end_dt:
        query = query.filter(models.AdminAuditLog.created_at < end_dt)
    return query


def _serialize_audit_log(log):
    details_value = _parse_audit_details(getattr(log, "details", None))
    detail_text = log.detail or ""
    if not detail_text and isinstance(details_value, dict):
        detail_text = ", ".join(f"{k}={v}" for k, v in details_value.items())
    return {
        "id": log.id,
        "admin_username": log.admin_username,
        "action": log.action,
        "action_label": _audit_action_label(log.action),
        "target_type": log.target_type,
        "target_id": getattr(log, "target_id", "") or "",
        "target_username": log.target_username,
        "result": getattr(log, "result", None) or "success",
        "detail": detail_text,
        "details": details_value,
        "ip": getattr(log, "ip", "") or "",
        "created_at": serialize_datetime(log.created_at),
    }


BACKUP_FILENAME_RE = re.compile(r"^ai_study_backup_\d{8}_\d{6}\.(sqlite3|db)$")
BACKUP_DIR = Path(__file__).resolve().parent / "backups"


def _format_backup_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    return f"{size_bytes / 1024 / 1024 / 1024:.1f} GB"


def get_sqlite_db_path() -> Path:
    if engine.url.get_backend_name() != "sqlite":
        raise HTTPException(status_code=400, detail="当前仅支持 SQLite 数据库备份")
    db_value = engine.url.database
    if not db_value or db_value == ":memory:":
        raise HTTPException(status_code=400, detail="当前 SQLite 数据库路径无效，无法备份")
    db_path = Path(db_value)
    if not db_path.is_absolute():
        db_path = (Path.cwd() / db_path).resolve()
        if not db_path.exists():
            backend_candidate = (Path(__file__).resolve().parent / db_value).resolve()
            if backend_candidate.exists():
                db_path = backend_candidate
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="数据库文件不存在，无法备份")
    return db_path


def get_backup_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def validate_backup_filename(filename: str) -> str:
    filename = (filename or "").strip()
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="无效的备份文件名")
    if not BACKUP_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="无效的备份文件名")
    return filename


def get_backup_file_path(filename: str) -> Path:
    safe_filename = validate_backup_filename(filename)
    backup_dir = get_backup_dir().resolve()
    file_path = (backup_dir / safe_filename).resolve()
    if file_path.parent != backup_dir:
        raise HTTPException(status_code=400, detail="无效的备份文件路径")
    return file_path


def serialize_backup_file(file_path: Path) -> dict:
    stat = file_path.stat()
    return {
        "filename": file_path.name,
        "size_bytes": stat.st_size,
        "size_label": _format_backup_size(stat.st_size),
        "created_at": serialize_datetime(datetime.fromtimestamp(stat.st_mtime)),
    }


def list_backup_files() -> list[Path]:
    backup_dir = get_backup_dir()
    files = [p for p in backup_dir.iterdir() if p.is_file() and BACKUP_FILENAME_RE.match(p.name)]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def create_sqlite_backup(source_path: Path, backup_path: Path) -> None:
    source_conn = sqlite3.connect(str(source_path))
    dest_conn = sqlite3.connect(str(backup_path))
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()


def get_model_config_payload(db: Session) -> dict:
    config = {key: str(get_system_setting(db, key, default)) for key, default in MODEL_CONFIG_DEFAULTS.items()}
    deepseek_key_configured = bool((os.getenv("DEEPSEEK_API_KEY") or "").strip())
    deepseek_base_url = (os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").strip()
    qwen_key_configured = bool((os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY") or "").strip())
    return {
        "status": {
            "deepseek": {
                "configured": deepseek_key_configured,
                "base_url_configured": bool(deepseek_base_url),
                "api_key_configured": deepseek_key_configured,
                "note": "已配置" if deepseek_key_configured else "未配置",
            },
            "qwen": {
                "configured": bool(is_qwen_enabled()),
                "api_key_configured": qwen_key_configured,
                "note": "已配置" if is_qwen_enabled() else "未启用或未配置",
            },
        },
        "config": config,
        "allowed": {
            "text_providers": ["deepseek"],
            "vision_providers": ["qwen"],
            "text_models": ["deepseek-chat", "deepseek-reasoner"],
        },
    }


def validate_model_config_updates(req: dict) -> dict:
    updates = {}
    for key, value in req.items():
        if key == "admin_username":
            continue
        lowered = key.lower()
        if any(part in lowered for part in SENSITIVE_MODEL_CONFIG_KEY_PARTS):
            raise HTTPException(status_code=400, detail="模型配置不允许提交 API Key、secret、token 或 password 字段")
        if key not in ALLOWED_MODEL_CONFIG_KEYS:
            raise HTTPException(status_code=400, detail=f"不支持的模型配置项: {key}")
        updates[key] = value
    if not updates:
        raise HTTPException(status_code=400, detail="请提供要保存的模型配置")

    if "ai_text_model_provider" in updates and str(updates["ai_text_model_provider"]).strip().lower() != "deepseek":
        raise HTTPException(status_code=400, detail="文本模型提供商当前仅支持 deepseek")
    if "ai_vision_model_provider" in updates and str(updates["ai_vision_model_provider"]).strip().lower() != "qwen":
        raise HTTPException(status_code=400, detail="视觉模型提供商当前仅支持 qwen")
    if "ai_text_model_name" in updates and not str(updates["ai_text_model_name"]).strip():
        raise HTTPException(status_code=400, detail="文本模型名称不能为空")
    if "ai_text_temperature" in updates:
        try:
            value = float(updates["ai_text_temperature"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="temperature 必须是数字")
        if value < 0 or value > 1.5:
            raise HTTPException(status_code=400, detail="temperature 范围必须在 0 - 1.5")
        updates["ai_text_temperature"] = str(value)
    if "ai_text_max_tokens" in updates:
        try:
            value = int(updates["ai_text_max_tokens"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="max_tokens 必须是整数")
        if value < 256 or value > 8000:
            raise HTTPException(status_code=400, detail="max_tokens 范围必须在 256 - 8000")
        updates["ai_text_max_tokens"] = str(value)
    if "ai_pdf_scan_max_pages" in updates:
        try:
            value = int(updates["ai_pdf_scan_max_pages"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="扫描 PDF 最大页数必须是整数")
        if value < 1 or value > ADMIN_OCR_LIMIT:
            raise HTTPException(status_code=400, detail=f"扫描 PDF 最大页数范围必须在 1 - {ADMIN_OCR_LIMIT}")
        updates["ai_pdf_scan_max_pages"] = str(value)

    bool_keys = {
        "ai_vision_enabled",
        "ai_pdf_scan_parse_enabled",
        "ai_chat_enabled_model_config",
        "ai_report_enabled_model_config",
        "ai_question_generation_enabled_model_config",
    }
    for key in bool_keys & updates.keys():
        raw_value = str(updates[key]).strip().lower()
        if raw_value not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
            raise HTTPException(status_code=400, detail=f"{key} 必须是布尔值")
        updates[key] = "true" if raw_value in ("true", "1", "yes", "on") else "false"

    return {key: str(value).strip() for key, value in updates.items()}


@app.get("/admin/me/permissions")
def admin_me_permissions(admin_username: str, db: Session = Depends(get_db)):
    admin = require_admin(admin_username, db)
    role = normalize_admin_role(admin)
    return {
        "username": admin.username,
        "admin_role": role,
        "role_label": get_admin_role_label(role),
        "permissions": get_admin_permissions(admin),
        "is_super_admin": role == "super_admin",
    }


@app.get("/admin/dashboard")
def admin_dashboard(admin_username: str = "", db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "dashboard.view")

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

    active_users_today = (
        db.query(func.count(func.distinct(models.AiUsageLog.username)))
        .filter(models.AiUsageLog.created_at >= today_start)
        .scalar()
        or 0
    )
    average_daily_minutes = (
        db.query(func.coalesce(func.avg(models.User.daily_study_minutes), 0)).scalar()
        or 0
    )
    user_growth = []
    for offset in range(6, -1, -1):
        day_start = today_start - timedelta(days=offset)
        next_day = day_start + timedelta(days=1)
        count = (
            db.query(models.User)
            .filter(models.User.created_at >= day_start, models.User.created_at < next_day)
            .count()
        )
        user_growth.append({"date": day_start.strftime("%m-%d"), "count": count})

    announcement_rows = (
        db.query(models.SystemAnnouncement)
        .filter(models.SystemAnnouncement.is_active == 1)
        .order_by(models.SystemAnnouncement.created_at.desc())
        .limit(5)
        .all()
    )
    announcements = [
        {
            "title": item.title,
            "date": serialize_datetime(item.created_at) or "",
            "is_active": bool(item.is_active),
            "type": item.type or "info",
        }
        for item in announcement_rows
    ]
    recent_user_rows = []
    for item in recent_users[:5]:
        last_active = (
            db.query(func.max(models.AiUsageLog.created_at))
            .filter(models.AiUsageLog.username == item.username)
            .scalar()
        )
        learning_minutes = int(getattr(item, "daily_study_minutes", 0) or 0)
        recent_user_rows.append({
            "username": item.username,
            "nickname": item.nickname or "",
            "user_id": str(item.id),
            "register_method": "账号注册",
            "register_time": serialize_datetime(item.created_at) or "",
            "last_active_time": serialize_datetime(last_active or item.created_at) or "",
            "learning_hours": round(learning_minutes / 60, 1),
        })

    return {
        "overview": {
            "total_users": total_users,
            "total_courses": total_courses,
            "average_learning_hours": round(float(average_daily_minutes) / 60, 1),
            "active_users_today": active_users_today,
            "total_orders": 0,
            "total_revenue": 0,
        },
        "user_growth": user_growth,
        "announcements": announcements,
        "recent_users": recent_user_rows,
    }


@app.get("/admin/operations-dashboard")
def admin_operations_dashboard(admin_username: str, db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "dashboard.view")
    from sqlalchemy import func as sqlfunc
    today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    # Overview
    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(models.User.is_active != 0).count()
    today_new = db.query(models.User).filter(models.User.created_at >= today).count()
    total_materials = db.query(models.StudyMaterial).filter(models.StudyMaterial.is_deleted.is_(False)).count()
    total_ai = db.query(models.AiUsageLog).filter(models.AiUsageLog.status == "success").count()
    today_ai = db.query(models.AiUsageLog).filter(models.AiUsageLog.status == "success", models.AiUsageLog.created_at >= today).count()
    today_failed = db.query(models.AiUsageLog).filter(models.AiUsageLog.status != "success", models.AiUsageLog.created_at >= today).count()
    total_tokens = db.query(sqlfunc.coalesce(sqlfunc.sum(models.AiUsageLog.estimated_tokens), 0)).scalar() or 0

    # Growth trends (7 days)
    def _daily_count(model, date_field, since, filter_extra=None):
        results = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            nd = d + timedelta(days=1)
            q = db.query(sqlfunc.count(model.id)).filter(date_field >= d, date_field < nd)
            if filter_extra is not None: q = q.filter(filter_extra)
            results.append({"date": d.strftime("%m-%d"), "count": q.scalar() or 0})
        return results

    users_7d = _daily_count(models.User, models.User.created_at, today)
    materials_7d = _daily_count(models.StudyMaterial, models.StudyMaterial.created_at, today, models.StudyMaterial.is_deleted.is_(False))
    ai_7d_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i); nd = d + timedelta(days=1)
        ai_7d_data.append({"date": d.strftime("%m-%d"), "count": db.query(sqlfunc.count(models.AiUsageLog.id)).filter(models.AiUsageLog.status == "success", models.AiUsageLog.created_at >= d, models.AiUsageLog.created_at < nd).scalar() or 0,
                           "tokens": db.query(sqlfunc.coalesce(sqlfunc.sum(models.AiUsageLog.estimated_tokens), 0)).filter(models.AiUsageLog.created_at >= d, models.AiUsageLog.created_at < nd).scalar() or 0})

    # Rankings (Top 5)
    # AiUsageLog has no course_id field; course-level AI ranking not available
    top_courses_ai = []
    top_users_ai = db.query(models.AiUsageLog.username, sqlfunc.count(models.AiUsageLog.id)).filter(models.AiUsageLog.status == "success").group_by(models.AiUsageLog.username).order_by(sqlfunc.count(models.AiUsageLog.id).desc()).limit(5).all()
    top_courses_mat = db.query(models.StudyMaterial.subject, sqlfunc.count(models.StudyMaterial.id)).filter(models.StudyMaterial.is_deleted.is_(False), models.StudyMaterial.subject.isnot(None), models.StudyMaterial.subject != "").group_by(models.StudyMaterial.subject).order_by(sqlfunc.count(models.StudyMaterial.id).desc()).limit(5).all()

    # Risks
    mat_issues = db.query(models.StudyMaterial).filter(models.StudyMaterial.is_deleted.is_(False), models.StudyMaterial.extracted_text.is_(None) | (models.StudyMaterial.extracted_text == "")).count()
    high_risk_audits = db.query(models.AdminAuditLog).filter(models.AdminAuditLog.created_at >= week_ago, models.AdminAuditLog.action.in_(["delete_material", "disable_user", "revoke_share"])).count()

    # Alerts
    alerts = []
    if today_failed > 0: alerts.append({"level": "warning", "title": "今日 AI 调用失败", "message": f"今日有 {today_failed} 次 AI 调用失败", "count": today_failed})
    if mat_issues > 0: alerts.append({"level": "warning" if mat_issues > 3 else "info", "title": "资料解析异常", "message": f"有 {mat_issues} 个资料需要处理", "count": mat_issues})
    # Backup last
    from sqlalchemy import desc
    last_backup = db.query(models.AdminAuditLog).filter(models.AdminAuditLog.action == "create_backup").order_by(desc(models.AdminAuditLog.created_at)).first()
    backup_days_ago = (today - last_backup.created_at.replace(tzinfo=None)).days if last_backup else 999
    if backup_days_ago >= 7: alerts.append({"level": "danger", "title": "长期未备份", "message": f"距上次备份已 {backup_days_ago} 天" if last_backup else "尚未创建过数据备份", "count": backup_days_ago})

    # Todos
    todos = []
    if mat_issues > 0: todos.append({"type": "material_issue", "level": "warning", "title": "处理资料解析异常", "message": f"有 {mat_issues} 个资料需要重新解析或删除", "tab": "systemHealth"})
    if today_failed > 3: todos.append({"type": "ai_failed", "level": "warning", "title": "查看 AI 失败日志", "message": f"今日 {today_failed} 次 AI 调用失败", "tab": "aiLogs"})
    if backup_days_ago >= 7: todos.append({"type": "backup", "level": "danger", "title": "创建数据备份", "message": "建议立即创建数据备份", "tab": "backups"})

    return {
        "overview": {"total_users": total_users, "active_users": active_users, "today_new_users": today_new,
                     "total_materials": total_materials, "total_ai_calls": total_ai, "today_ai_calls": today_ai,
                     "today_failed_ai": today_failed, "total_tokens": total_tokens,
                     "estimated_cost_cny": round(total_tokens * 0.002 / 1000, 4)},
        "growth": {"users_7d": users_7d, "materials_7d": materials_7d, "ai_calls_7d": ai_7d_data},
        "rankings": {"top_courses_by_ai": [{"course": r[0] or "未知", "count": r[1]} for r in top_courses_ai],
                     "top_users_by_ai": [{"username": r[0], "count": r[1]} for r in top_users_ai],
                     "top_courses_by_materials": [{"course": r[0] or "未知", "count": r[1]} for r in top_courses_mat]},
        "risks": {"pending_material_issues": mat_issues, "today_failed_ai_calls": today_failed, "high_risk_audits_7d": high_risk_audits, "alerts": alerts},
        "todos": todos,
    }



@app.get("/admin/dashboard-v1")
def admin_dashboard_v1(db: Session = Depends(get_db)):
    """Legacy v1 dashboard preserved for compatibility."""
    from datetime import datetime as _dt
    today_start = _dt.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    _total_users = db.query(models.User).count()
    _plan_counts = {}
    for _p in ("free", "pro", "admin"):
        _plan_counts[_p] = db.query(models.User).filter(models.User.plan == _p).count()
    _recent = db.query(models.AiUsageLog).order_by(models.AiUsageLog.created_at.desc()).limit(20).all()
    _ai_calls_today = db.query(models.AiUsageLog).filter(models.AiUsageLog.status == "success", models.AiUsageLog.created_at >= today_start).count()
    _ai_calls_total = db.query(models.AiUsageLog).filter(models.AiUsageLog.status == "success").count()
    _mats = db.query(models.StudyMaterial).filter(models.StudyMaterial.is_deleted.is_(False)).count()
    _kps = db.query(models.KnowledgePoint).count()
    _tasks = db.query(models.LearningTask).count()
    _questions = db.query(models.Question).count()
    _courses_set = set()
    for r in db.query(models.StudyMaterial.subject).filter(models.StudyMaterial.is_deleted.is_(False), models.StudyMaterial.subject != "").distinct().all():
        if r[0]: _courses_set.add(r[0])
    for r in db.query(models.KnowledgePoint.course_id).filter(models.KnowledgePoint.course_id != "").distinct().all():
        if r[0]: _courses_set.add(r[0])
    _notes = ["AI 使用记录正常"]
    _errs = db.query(models.AiUsageLog).filter(models.AiUsageLog.status != "success", models.AiUsageLog.created_at >= today_start).count()
    if _errs > 0: _notes.append(f"今日有 {_errs} 条 AI 调用失败记录")

    return {
        "overview": {
            "total_users": _total_users,
            "free_users": _plan_counts.get("free", 0),
            "pro_users": _plan_counts.get("pro", 0),
            "admin_users": _plan_counts.get("admin", 0),
            "total_materials": _mats,
            "total_courses": len(_courses_set),
            "total_knowledge_points": _kps,
            "total_tasks": _tasks,
            "total_questions": _questions,
            "today_ai_calls": _ai_calls_today,
            "total_ai_calls": _ai_calls_total,
        },
        "today_usage_by_feature": [],
        "recent_users": [],
        "recent_ai_logs": [{"username": l.username, "feature": l.feature, "status": l.status, "estimated_tokens": l.estimated_tokens, "created_at": serialize_datetime(l.created_at)} for l in _recent],
        "system_notes": _notes,
    }


@app.get("/admin/users")
def admin_users_list(
    admin_username: str = "",
    keyword: str = "",
    plan: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    require_admin_permission(db, admin_username, "users.view")

    page = max(1, page)
    page_size = min(100, max(1, page_size))

    today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)

    query = db.query(models.User).filter(models.User.is_deleted == 0)
    if keyword := keyword.strip():
        query = query.filter(or_(
            models.User.username.contains(keyword),
            models.User.nickname.contains(keyword),
            models.User.email.contains(keyword),
        ))
    if plan_filter := plan.strip():
        query = query.filter(models.User.plan == plan_filter)
    status_filter = status.strip().lower()
    if status_filter == "banned":
        query = query.filter(models.User.is_banned == 1)
    elif status_filter == "normal":
        query = query.filter(models.User.is_banned == 0)

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
        last_active = (
            db.query(func.max(models.AiUsageLog.created_at))
            .filter(models.AiUsageLog.username == u.username)
            .scalar()
        )
        kp_count = (
            db.query(models.KnowledgePoint).filter(models.KnowledgePoint.username == u.username).count()
        )
        task_count = (
            db.query(models.LearningTask).filter(models.LearningTask.username == u.username).count()
        )
        # Load three-direction memberships
        membership_rows = db.query(models.UserServiceMembership).filter(
            models.UserServiceMembership.user_id == u.id,
        ).all()
        memberships = {}
        SERVICE_LABELS = {
            "exam_11408": {"free": "普通用户", "monthly": "月度冲刺包", "quarterly": "季度强化包", "full": "全程备考包"},
            "course": {"free": "普通用户", "monthly": "月度学习包", "quarterly": "季度学习包", "full": "全程学习包"},
            "programming": {"free": "普通用户", "monthly": "月度练习包", "quarterly": "季度练习包", "full": "年度提升包"},
        }
        for m in membership_rows:
            labels = SERVICE_LABELS.get(m.service_key, {})
            memberships[m.service_key] = {
                "is_enabled": bool(m.is_enabled),
                "plan": m.plan or "free",
                "plan_label": labels.get(m.plan or "free", "普通用户") if m.is_enabled else "未开通",
            }
        for sk in ["exam_11408", "course", "programming"]:
            if sk not in memberships:
                memberships[sk] = {"is_enabled": False, "plan": "free", "plan_label": "未开通"}

        items.append({
            "id": u.id,
            "user_id": str(u.id),
            "username": u.username,
            "nickname": u.nickname or "",
            "real_name": getattr(u, "admin_real_name", None) or "",
            "email": getattr(u, "email", None) or "",
            "register_method": "账号注册",
            "register_time": serialize_datetime(u.created_at),
            "last_active_time": serialize_datetime(last_active or u.created_at),
            "learning_hours": round((int(getattr(u, "daily_study_minutes", 0) or 0)) / 60, 1),
            "plan": get_effective_service_plan(db, u.id, "exam_11408") or u.plan or "free",
            "is_admin": bool(u.is_admin),
            "admin_role": normalize_admin_role(u),
            "admin_role_label": get_admin_role_label(normalize_admin_role(u)),
            "is_banned": bool(getattr(u, "is_banned", 0)),
            "banned_reason": getattr(u, "banned_reason", None) or "",
            "banned_at": getattr(u, "banned_at", None) or "",
            "is_deleted": bool(getattr(u, "is_deleted", 0)),
            "deleted_at": getattr(u, "deleted_at", None) or "",
            "plan_expires_at": serialize_datetime(u.plan_expire_at),
            "material_count": material_count,
            "ai_call_count": ai_call_count,
            "today_ai_call_count": today_ai_call_count,
            "is_active": getattr(u, "is_active", 1),
            "knowledge_point_count": kp_count,
            "task_count": task_count,
            "created_at": serialize_datetime(u.created_at),
            "memberships": memberships,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/admin/courses")
def admin_courses_list(admin_username: str = "", db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "courses.view")

    material_rows = (
        db.query(
            models.StudyMaterial.subject,
            func.count(models.StudyMaterial.id),
            func.count(func.distinct(models.StudyMaterial.username)),
            func.max(models.StudyMaterial.created_at),
        )
        .filter(models.StudyMaterial.is_deleted.is_(False), models.StudyMaterial.subject != "")
        .group_by(models.StudyMaterial.subject)
        .all()
    )
    progress_rows = (
        db.query(
            models.CourseProgress.course,
            func.count(func.distinct(models.CourseProgress.username)),
            func.max(models.CourseProgress.created_at),
        )
        .filter(models.CourseProgress.course != "")
        .group_by(models.CourseProgress.course)
        .all()
    )

    courses = {}
    for name, material_count, user_count, created_at in material_rows:
        courses[name] = {
            "course_name": name,
            "material_count": material_count or 0,
            "user_count": user_count or 0,
            "created_at": serialize_datetime(created_at),
        }
    for name, user_count, created_at in progress_rows:
        item = courses.setdefault(name, {
            "course_name": name,
            "material_count": 0,
            "user_count": 0,
            "created_at": serialize_datetime(created_at),
        })
        item["user_count"] = max(int(item.get("user_count") or 0), int(user_count or 0))
        if not item.get("created_at"):
            item["created_at"] = serialize_datetime(created_at)

    items = sorted(courses.values(), key=lambda item: item.get("created_at") or "", reverse=True)
    return {"items": items, "total": len(items)}


@app.get("/admin/practice")
def admin_practice_list(admin_username: str = "", db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "courses.view")

    question_total = db.query(models.Question).count()
    paper_total = db.query(models.PracticePaper).count()
    challenge_total = db.query(models.CodeChallenge).count()
    recent_questions = (
        db.query(models.Question)
        .order_by(models.Question.created_at.desc())
        .limit(12)
        .all()
    )
    recent_challenges = (
        db.query(models.CodeChallenge)
        .order_by(models.CodeChallenge.created_at.desc())
        .limit(8)
        .all()
    )
    items = [
        {
            "id": f"q-{item.id}",
            "title": item.title or item.content[:40],
            "course_id": item.course_id or "",
            "type": item.type or "question",
            "source": item.source or item.imported_from or "题库",
            "created_at": serialize_datetime(item.created_at),
        }
        for item in recent_questions
    ]
    items.extend([
        {
            "id": f"c-{item.id}",
            "title": item.title,
            "course_id": item.course_id or "",
            "type": item.difficulty or "code",
            "source": item.source or "编程练习",
            "created_at": serialize_datetime(item.created_at),
        }
        for item in recent_challenges
    ])
    items = sorted(items, key=lambda item: item.get("created_at") or "", reverse=True)[:12]
    return {
        "overview": {
            "question_total": question_total,
            "paper_total": paper_total,
            "challenge_total": challenge_total,
        },
        "items": items,
    }


@app.get("/admin/tasks")
def admin_tasks_list(admin_username: str = "", db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "courses.view")

    total = db.query(models.LearningTask).count()
    rows = (
        db.query(models.LearningTask)
        .order_by(models.LearningTask.created_at.desc())
        .limit(20)
        .all()
    )
    items = [
        {
            "id": item.id,
            "title": item.title,
            "username": item.username,
            "course_id": item.course_id or "",
            "task_type": item.task_type,
            "status": item.status,
            "created_at": serialize_datetime(item.created_at),
            "due_date": serialize_datetime(item.due_date),
        }
        for item in rows
    ]
    return {"items": items, "total": total}


@app.get("/admin/quota")
def admin_quota_list(
    admin_username: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    require_admin_permission(db, admin_username, "users.view")

    page = max(1, page)
    page_size = min(100, max(1, page_size))
    query = db.query(models.User)
    total = query.count()
    users = query.order_by(models.User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for u in users:
        effective_plan = get_effective_plan(u)
        limits = get_plan_limits_v2(effective_plan["plan_code"])
        total_calls = (
            db.query(models.AiUsageLog)
            .filter(models.AiUsageLog.username == u.username, models.AiUsageLog.status == "success")
            .count()
        )
        items.append({
            "user_id": str(u.id),
            "username": u.username,
            "nickname": u.nickname or "",
            "plan": effective_plan["plan_code"],
            "daily_ai_limit": limits.get("daily_ai_limit", -1),
            "monthly_ai_limit": -1,
            "total_ai_calls": total_calls,
            "plan_expires_at": serialize_datetime(u.plan_expire_at),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/admin/logs")
def admin_logs_list(
    admin_username: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    require_admin_permission(db, admin_username, "audit_logs.view")

    page = max(1, page)
    page_size = min(100, max(1, page_size))
    query = db.query(models.AdminAuditLog)
    total = query.count()
    rows = (
        query.order_by(models.AdminAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": item.id,
            "admin_username": item.admin_username,
            "action": item.action,
            "target_type": item.target_type or "",
            "target_id": item.target_id or "",
            "target_username": item.target_username or "",
            "result": item.result or "",
            "detail": item.detail or item.details or "",
            "ip": item.ip or "",
            "created_at": serialize_datetime(item.created_at),
        }
        for item in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/admin/users/{target_username}/detail")
def admin_user_detail(target_username: str, admin_username: str, db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "users.view")
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
        "plan": get_effective_service_plan(db, u.id, "exam_11408") or u.plan or "free",
        "is_admin": bool(u.is_admin),
        "admin_role": normalize_admin_role(u),
        "admin_role_label": get_admin_role_label(normalize_admin_role(u)),
        "plan_expires_at": serialize_datetime(u.plan_expire_at),
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


@app.put("/admin/users/{target_username}/admin-role")
def admin_update_user_admin_role(
    target_username: str,
    req: schemas.AdminUpdateRoleRequest,
    db: Session = Depends(get_db),
):
    admin = require_super_admin(db, req.admin_username)
    target_user = get_user_by_username(target_username, db)
    new_role = (req.admin_role or "none").strip()
    if new_role not in VALID_ADMIN_ROLES:
        raise HTTPException(status_code=400, detail="无效的管理员角色")
    if new_role != "none" and not bool(target_user.is_admin):
        raise HTTPException(status_code=400, detail="目标用户不是管理员，不能设置后台角色")

    old_role = normalize_admin_role(target_user)
    if old_role == "super_admin" and new_role != "super_admin":
        if count_active_super_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="不能降级最后一个超级管理员")

    target_user.admin_role = new_role
    db.commit()
    db.refresh(target_user)

    _write_audit_log(
        admin_username=admin.username,
        action="update_admin_role",
        db=db,
        target_type="user",
        target_username=target_user.username,
        detail=f"admin_role {old_role} -> {new_role}",
        details={"old_role": old_role, "new_role": new_role, "is_admin": bool(target_user.is_admin)},
    )

    return {
        "success": True,
        "username": target_user.username,
        "is_admin": bool(target_user.is_admin),
        "admin_role": normalize_admin_role(target_user),
        "admin_role_label": get_admin_role_label(normalize_admin_role(target_user)),
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
    require_admin_permission(db, admin_username, "ai_logs.view")

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


@app.get("/admin/ai-logs/export")
def admin_ai_logs_export(
    admin_username: str,
    feature: str = "",
    target_username: str = "",
    status: str = "",
    start_date: str = "",
    end_date: str = "",
    db: Session = Depends(get_db),
):
    require_admin_permission(db, admin_username, "ai_logs.export")
    import csv, io as _io
    query = db.query(models.AiUsageLog)
    if f := feature.strip(): query = query.filter(models.AiUsageLog.feature == f)
    if u := target_username.strip(): query = query.filter(models.AiUsageLog.username.contains(u))
    if s := status.strip(): query = query.filter(models.AiUsageLog.status == s)
    if sd := start_date.strip():
        try:
            start_dt = datetime.fromisoformat(sd)
            query = query.filter(models.AiUsageLog.created_at >= start_dt)
        except ValueError: pass
    if ed := end_date.strip():
        try:
            end_dt = datetime.fromisoformat(ed)
            query = query.filter(models.AiUsageLog.created_at <= end_dt)
        except ValueError: pass
    logs = query.order_by(models.AiUsageLog.created_at.desc()).limit(5000).all()
    output = _io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["用户", "功能", "状态", "模型", "Tokens", "错误信息", "时间"])
    for log in logs:
        writer.writerow([
            log.username, log.feature, log.status, log.model or "",
            log.estimated_tokens or 0, log.error_message or "",
            serialize_datetime(log.created_at) or "",
        ])
    _write_audit_log(
        admin_username,
        f"导出AI使用日志 ({len(logs)}条)",
        db,
        target_type="ai_logs",
        detail=f"feature={feature} status={status}",
        details={
            "feature": feature,
            "target_username": target_username,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "count": len(logs),
        },
    )
    filename = f"ai_usage_logs_{utc_now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(content=output.getvalue(), media_type="text/csv; charset=utf-8-sig",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/admin/materials")
def admin_materials(
    admin_username: str = "",
    keyword: str = "",
    course_id: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    require_admin_permission(db, admin_username, "materials.view")

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
    require_admin_permission(db, admin_username, "courses.view")

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
    admin = require_admin_permission(db, req.admin_username, "users.manage_plan")

    target_user = get_user_by_username(target_username, db)
    if bool(target_user.is_admin) and normalize_admin_role(admin) != "super_admin":
        raise HTTPException(status_code=403, detail="当前管理员没有权限修改管理员账号套餐")
    old_plan = target_user.plan or "free"
    plan = (req.plan or "free").strip().lower()
    if plan not in ("free", "pro", "admin"):
        raise HTTPException(status_code=400, detail="无效的套餐类型")

    target_user.plan = plan
    if req.plan_expires_at:
        target_user.plan_expire_at = req.plan_expires_at
    db.commit()
    db.refresh(target_user)

    _write_audit_log(
        admin_username=admin.username,
        action="update_plan",
        db=db,
        target_type="user",
        target_username=target_user.username,
        detail=f"套餐 {old_plan} → {plan}",
        details={"old_plan": old_plan, "new_plan": plan, "plan_expires_at": serialize_datetime(target_user.plan_expire_at)},
    )

    return {
        "success": True,
        "username": target_user.username,
        "plan": target_user.plan,
        "plan_expires_at": serialize_datetime(target_user.plan_expire_at),
    }


SERVICE_KEYS = ["exam_11408", "course", "programming"]
VALID_PLANS = ["free", "monthly", "quarterly", "full"]
SERVICE_PLAN_LABELS = {
    "exam_11408": {"free": "普通用户", "monthly": "月度冲刺包", "quarterly": "季度强化包", "full": "全程备考包"},
    "course": {"free": "普通用户", "monthly": "月度学习包", "quarterly": "季度学习包", "full": "全程学习包"},
    "programming": {"free": "普通用户", "monthly": "月度练习包", "quarterly": "季度练习包", "full": "年度提升包"},
}


@app.patch("/admin/users/{user_id}/memberships")
def admin_update_user_memberships(
    user_id: int,
    req: schemas.AdminUpdateMembershipsRequest,
    db: Session = Depends(get_db),
):
    """Update a user's three-direction service memberships."""
    admin = require_admin_permission(db, req.admin_username, "users.manage_plan")
    target_user = db.query(models.User).filter(
        models.User.id == user_id, models.User.is_deleted == 0,
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    memberships_data = req.memberships or {}
    if not memberships_data:
        raise HTTPException(status_code=400, detail="请提供 memberships 数据")

    now = utc_now()
    updated = {}
    for sk, data in memberships_data.items():
        if sk not in SERVICE_KEYS:
            continue
        is_enabled = bool(data.get("is_enabled", False)) if isinstance(data, dict) else False
        plan = str(data.get("plan", "free")).strip().lower() if isinstance(data, dict) else "free"
        if plan not in VALID_PLANS:
            plan = "free"

        membership = db.query(models.UserServiceMembership).filter(
            models.UserServiceMembership.user_id == user_id,
            models.UserServiceMembership.service_key == sk,
        ).first()
        if not membership:
            membership = models.UserServiceMembership(
                user_id=user_id, service_key=sk,
                is_enabled=is_enabled, plan=plan,
                created_at=now, updated_at=now,
            )
            db.add(membership)
        else:
            membership.is_enabled = is_enabled
            membership.plan = plan
            membership.updated_at = now

        # Sync exam_11408 plan to legacy users.plan for backward compat
        if sk == "exam_11408" and is_enabled:
            target_user.plan = plan  # free / monthly / quarterly / full
            db.add(target_user)

        labels = SERVICE_PLAN_LABELS.get(sk, {})
        updated[sk] = {
            "is_enabled": is_enabled,
            "plan": plan,
            "plan_label": labels.get(plan, "普通用户") if is_enabled else "未开通",
        }

    db.commit()
    return {"success": True, "user_id": user_id, "memberships": updated}


@app.get("/admin/usage-trend")
def admin_usage_trend(admin_username: str = "", days: int = 7, db: Session = Depends(get_db)):
    """Return per-day AI call counts for trend chart (7/30/90 days)."""
    require_admin_permission(db, admin_username, "dashboard.view")
    days = max(1, min(365, days))
    items = []
    now = utc_now()
    for i in range(days - 1, -1, -1):
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = (
            db.query(models.AiUsageLog)
            .filter(
                models.AiUsageLog.status == "success",
                models.AiUsageLog.created_at >= day_start,
                models.AiUsageLog.created_at < day_end,
            )
            .count()
        )
        items.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": count,
        })
    return {"days": days, "items": items}


@app.get("/admin/usage-summary")
def admin_usage_summary(admin_username: str = "", db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "dashboard.view")
    from sqlalchemy import func as sqlfunc

    today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today_start - timedelta(days=7)

    # Total stats
    total_calls_all = db.query(models.AiUsageLog).count()
    total_success = db.query(models.AiUsageLog).filter(models.AiUsageLog.status == "success").count()
    total_failed = db.query(models.AiUsageLog).filter(models.AiUsageLog.status != "success").count()
    total_tokens_all = db.query(sqlfunc.coalesce(sqlfunc.sum(models.AiUsageLog.estimated_tokens), 0)).scalar() or 0
    today_tokens = db.query(sqlfunc.coalesce(sqlfunc.sum(models.AiUsageLog.estimated_tokens), 0)).filter(models.AiUsageLog.created_at >= today_start).scalar() or 0
    today_calls = db.query(models.AiUsageLog).filter(models.AiUsageLog.created_at >= today_start).count()
    today_failed = db.query(models.AiUsageLog).filter(models.AiUsageLog.created_at >= today_start, models.AiUsageLog.status != "success").count()
    week_avg = db.query(models.AiUsageLog).filter(models.AiUsageLog.created_at >= week_ago, models.AiUsageLog.status == "success").count() / 7.0

    # Feature stats today
    feature_stats = {}
    for feature in ALL_FEATURES:
        feature_stats[feature] = db.query(models.AiUsageLog).filter(
            models.AiUsageLog.feature == feature, models.AiUsageLog.status == "success", models.AiUsageLog.created_at >= today_start).count()

    # Feature failed today
    feature_failed = {}
    for feature in ALL_FEATURES:
        c = db.query(models.AiUsageLog).filter(
            models.AiUsageLog.feature == feature, models.AiUsageLog.status != "success", models.AiUsageLog.created_at >= today_start).count()
        if c > 0: feature_failed[feature] = c

    # Per-user today
    user_usage_rows = db.query(models.AiUsageLog.username, sqlfunc.count(models.AiUsageLog.id), sqlfunc.sum(models.AiUsageLog.estimated_tokens)).filter(
        models.AiUsageLog.created_at >= today_start).group_by(models.AiUsageLog.username).order_by(sqlfunc.count(models.AiUsageLog.id).desc()).limit(10).all()
    user_usage = [{"username": r[0], "count": r[1], "tokens": r[2] or 0} for r in user_usage_rows]

    # Per-model tokens
    model_rows = db.query(models.AiUsageLog.model, sqlfunc.sum(models.AiUsageLog.estimated_tokens)).filter(
        models.AiUsageLog.model.isnot(None), models.AiUsageLog.model != "").group_by(models.AiUsageLog.model).all()
    model_usage = [{"model": r[0] or "unknown", "tokens": r[1] or 0} for r in model_rows]

    # Cost estimation
    PRICING = {"deepseek": 0.002, "deepseek-chat": 0.002, "qwen": 0.004, "unknown": 0.003}
    def est_cost(tokens, model="unknown"):
        rate = PRICING.get(model, PRICING.get((model or "").split("-")[0], 0.003)) / 1000.0
        return round(tokens * rate, 4)
    total_cost = round(sum(est_cost(m["tokens"], m["model"]) for m in model_usage), 4)
    model_cost = [{"model": m["model"], "tokens": m["tokens"], "estimated_cost_cny": est_cost(m["tokens"], m["model"])} for m in model_usage]

    # Alerts
    alerts = []
    if today_calls > 0:
        fail_rate = round(today_failed / today_calls * 100, 1)
        if fail_rate > 20: alerts.append({"level": "warning", "type": "high_failure_rate", "title": "AI 调用失败率偏高", "message": f"最近 24 小时失败率为 {fail_rate}%", "value": fail_rate})
    for u in user_usage:
        if u["count"] > 50: alerts.append({"level": "warning", "type": "user_high_usage", "title": f"用户 {u['username']} 今日调用较高", "message": f"今日调用 {u['count']} 次", "value": u["count"]})
        if (u["tokens"] or 0) > 100000: alerts.append({"level": "warning", "type": "user_high_tokens", "title": f"用户 {u['username']} 今日 Token 消耗较高", "message": f"今日 Token {u['tokens']}", "value": u["tokens"]})
    for f, c in feature_failed.items():
        if c >= 3: alerts.append({"level": "info", "type": "feature_failed", "title": f"功能 {f} 今日失败较多", "message": f"今日 {c} 次失败", "value": c})
    if today_calls > week_avg * 2 and week_avg > 0: alerts.append({"level": "info", "type": "spike", "title": "今日调用量明显高于平均水平", "message": f"今日 {today_calls} vs 近7天均值 {round(week_avg)}", "value": today_calls})

    recent_logs = db.query(models.AiUsageLog).order_by(models.AiUsageLog.created_at.desc()).limit(100).all()

    return {
        "total_calls_all": total_calls_all, "total_success": total_success, "total_failed": total_failed,
        "total_tokens_all": total_tokens_all, "today_tokens": today_tokens,
        "today_total": today_calls, "today_failed": today_failed,
        "feature_stats": feature_stats, "feature_failed": feature_failed,
        "user_usage": user_usage, "model_usage": model_usage,
        "cost_estimate": {"total_tokens": total_tokens_all, "today_tokens": today_tokens,
                          "estimated_cost_cny": total_cost, "pricing_note": "按估算单价计算，仅供参考", "by_model": model_cost},
        "alerts": alerts,
        "plan_counts": {p: db.query(models.User).filter(models.User.plan == p).count() for p in ["free", "pro", "admin"]},
        "recent_logs": [{"username": log.username, "feature": log.feature, "model": log.model, "estimated_tokens": log.estimated_tokens, "status": log.status, "error_message": log.error_message, "created_at": serialize_datetime(log.created_at)} for log in recent_logs],
    }


@app.get("/admin/audit-logs")
def admin_audit_logs(
    admin_username: str,
    actor: str = "",
    action: str = "",
    target_type: str = "",
    keyword: str = "",
    start_date: str = "",
    end_date: str = "",
    page: int = 1,
    page_size: int = 30,
    db: Session = Depends(get_db),
):
    require_admin_permission(db, admin_username, "audit_logs.view")

    page = max(1, page)
    page_size = min(100, max(1, page_size))

    query = _build_admin_audit_query(db, actor, action, target_type, keyword, start_date, end_date)
    total = query.count()
    logs = (
        query
        .order_by(models.AdminAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    success_count = query.filter(models.AdminAuditLog.result == "success").count()
    failed_count = query.filter(models.AdminAuditLog.result != "success").count()
    today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_query = query.filter(models.AdminAuditLog.created_at >= today_start)
    high_risk_filter = or_(
        models.AdminAuditLog.action.in_(["update_admin_role", "update_plan", "audit_logs_export"]),
        models.AdminAuditLog.target_type.in_(["material", "report_share", "settings", "announcement", "ai_logs"]),
    )
    action_rows = (
        query.with_entities(models.AdminAuditLog.action, func.count(models.AdminAuditLog.id))
        .group_by(models.AdminAuditLog.action)
        .order_by(func.count(models.AdminAuditLog.id).desc())
        .limit(5)
        .all()
    )

    return {
        "items": [_serialize_audit_log(log) for log in logs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "today_total": today_query.count(),
            "today_high_risk": today_query.filter(high_risk_filter).count(),
            "admin_role_changes": query.filter(models.AdminAuditLog.action == "update_admin_role").count(),
            "user_status_changes": query.filter(models.AdminAuditLog.target_type == "user", models.AdminAuditLog.action != "update_plan", models.AdminAuditLog.action != "update_admin_role").count(),
            "settings_changes": query.filter(models.AdminAuditLog.target_type == "settings").count(),
            "top_actions": [{"action": row[0], "label": _audit_action_label(row[0]), "count": row[1]} for row in action_rows],
        },
    }


@app.get("/admin/audit-logs/export")
def admin_audit_logs_export(
    admin_username: str,
    actor: str = "",
    action: str = "",
    target_type: str = "",
    keyword: str = "",
    start_date: str = "",
    end_date: str = "",
    db: Session = Depends(get_db),
):
    require_admin_permission(db, admin_username, "audit_logs.export")
    query = _build_admin_audit_query(db, actor, action, target_type, keyword, start_date, end_date)
    logs = query.order_by(models.AdminAuditLog.created_at.desc()).limit(5000).all()
    output = StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["时间", "操作人", "操作类型", "目标类型", "目标ID", "目标用户", "结果", "IP", "详情"])
    for log in logs:
        item = _serialize_audit_log(log)
        writer.writerow([
            item["created_at"] or "",
            item["admin_username"] or "",
            item["action_label"] or item["action"] or "",
            item["target_type"] or "",
            item["target_id"] or "",
            item["target_username"] or "",
            item["result"] or "",
            item["ip"] or "",
            item["detail"] or _audit_details_to_text(item["details"]),
        ])
    _write_audit_log(
        admin_username,
        "audit_logs_export",
        db,
        target_type="audit_logs",
        result="success",
        detail=f"count={len(logs)}",
        details={
            "filters": {
                "actor": actor,
                "action": action,
                "target_type": target_type,
                "keyword": keyword,
                "start_date": start_date,
                "end_date": end_date,
            },
            "count": len(logs),
        },
    )
    filename = f"admin_audit_logs_{utc_now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/admin/backups")
def admin_backups_list(admin_username: str, db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "backups.view")
    files = list_backup_files()
    return {"items": [serialize_backup_file(path) for path in files], "total": len(files)}


@app.post("/admin/backups")
def admin_backups_create(req: dict, db: Session = Depends(get_db)):
    admin_username = str(req.get("admin_username", "")).strip()
    require_admin_permission(db, admin_username, "backups.create")
    source_path = get_sqlite_db_path()
    get_backup_dir()
    filename = f"ai_study_backup_{utc_now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
    backup_path = get_backup_file_path(filename)
    try:
        create_sqlite_backup(source_path, backup_path)
    except Exception as exc:
        if backup_path.exists():
            backup_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"创建备份失败: {str(exc)[:120]}")
    item = serialize_backup_file(backup_path)
    _write_audit_log(
        admin_username,
        "backup_create",
        db,
        target_type="backup",
        target_id=filename,
        detail=f"filename={filename}, size_bytes={item['size_bytes']}",
        details={"filename": filename, "size_bytes": item["size_bytes"]},
    )
    return {"success": True, "backup": item}


@app.get("/admin/backups/{filename}/download")
def admin_backups_download(filename: str, admin_username: str, db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "backups.download")
    file_path = get_backup_file_path(filename)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="备份文件不存在")
    size_bytes = file_path.stat().st_size
    _write_audit_log(
        admin_username,
        "backup_download",
        db,
        target_type="backup",
        target_id=filename,
        detail=f"filename={filename}",
        details={"filename": filename, "size_bytes": size_bytes},
    )
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@app.delete("/admin/backups/{filename}")
def admin_backups_delete(filename: str, admin_username: str, db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "backups.delete")
    file_path = get_backup_file_path(filename)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="备份文件不存在")
    size_bytes = file_path.stat().st_size
    file_path.unlink()
    _write_audit_log(
        admin_username,
        "backup_delete",
        db,
        target_type="backup",
        target_id=filename,
        detail=f"filename={filename}, size_bytes={size_bytes}",
        details={"filename": filename, "size_bytes": size_bytes},
    )
    return {"success": True, "filename": filename}


def validate_model_config_updates(req: dict) -> dict:
    """Validate and sanitize model config updates. Raises HTTPException on invalid input."""
    updates = req.get("updates", req)
    if not isinstance(updates, dict) or not updates:
        raise HTTPException(status_code=400, detail="请提供要更新的配置项 (updates)")

    validated = {}
    for key, value in updates.items():
        key_lower = key.lower()
        # Reject sensitive keys
        for part in SENSITIVE_MODEL_CONFIG_KEY_PARTS:
            if part in key_lower:
                raise HTTPException(status_code=400, detail=f"不允许通过接口修改敏感配置：{key}")
        # Reject unknown keys
        if key not in ALLOWED_MODEL_CONFIG_KEYS:
            raise HTTPException(status_code=400, detail=f"未知的配置项：{key}")

        # Numeric validation
        if key == "ai_text_temperature":
            try:
                v = float(value)
                if v < 0 or v > 1.5:
                    raise HTTPException(status_code=400, detail="ai_text_temperature 取值范围为 0.0 ~ 1.5")
                validated[key] = str(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="ai_text_temperature 必须为数字")
            continue

        if key == "ai_text_max_tokens":
            try:
                v = int(value)
                if v < 256 or v > 8000:
                    raise HTTPException(status_code=400, detail="ai_text_max_tokens 取值范围为 256 ~ 8000")
                validated[key] = str(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="ai_text_max_tokens 必须为整数")
            continue

        if key == "ai_pdf_scan_max_pages":
            try:
                v = int(value)
                if v < 1 or v > ADMIN_OCR_LIMIT:
                    raise HTTPException(status_code=400, detail=f"ai_pdf_scan_max_pages 取值范围为 1 ~ {ADMIN_OCR_LIMIT}")
                validated[key] = str(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="ai_pdf_scan_max_pages 必须为整数")
            continue

        # Boolean validation
        if key in ("ai_vision_enabled", "ai_pdf_scan_parse_enabled", "ai_chat_enabled_model_config", "ai_report_enabled_model_config", "ai_question_generation_enabled_model_config"):
            sv = str(value).strip().lower()
            if sv in ("true", "1", "yes", "on"):
                validated[key] = "true"
            elif sv in ("false", "0", "no", "off"):
                validated[key] = "false"
            else:
                raise HTTPException(status_code=400, detail=f"{key} 必须为 true/false/1/0")
            continue

        # Provider validation
        if key == "ai_text_model_provider":
            sv = str(value).strip().lower()
            if sv not in ("deepseek",):
                raise HTTPException(status_code=400, detail="ai_text_model_provider 目前仅支持 deepseek")
            validated[key] = sv
            continue

        if key == "ai_vision_model_provider":
            sv = str(value).strip().lower()
            if sv not in ("qwen",):
                raise HTTPException(status_code=400, detail="ai_vision_model_provider 目前仅支持 qwen")
            validated[key] = sv
            continue

        # Model name: non-empty, reasonable length
        if key == "ai_text_model_name":
            sv = str(value).strip()
            if not sv or len(sv) > 100:
                raise HTTPException(status_code=400, detail="ai_text_model_name 不能为空且不超过100个字符")
            if "\n" in sv or "\r" in sv:
                raise HTTPException(status_code=400, detail="ai_text_model_name 不能包含换行符")
            validated[key] = sv
            continue

        # Fallback: pass through as string
        validated[key] = str(value)

    return validated


@app.get("/admin/model-config")
def admin_model_config(admin_username: str, db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "model_config.view")
    return get_model_config_payload(db)


@app.put("/admin/model-config")
def admin_model_config_update(req: dict, db: Session = Depends(get_db)):
    admin_username = str(req.get("admin_username", "")).strip()
    require_admin_permission(db, admin_username, "model_config.manage")
    updates = validate_model_config_updates(req)
    old_values = {key: str(get_system_setting(db, key, MODEL_CONFIG_DEFAULTS[key])) for key in updates.keys()}
    for key, value in updates.items():
        setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == key).first()
        if not setting:
            setting = models.SystemSetting(key=key, description=MODEL_CONFIG_DESCRIPTIONS.get(key, "模型配置"))
        setting.value = value
        setting.description = setting.description or MODEL_CONFIG_DESCRIPTIONS.get(key, "模型配置")
        setting.updated_by = admin_username
        setting.updated_at = utc_now()
        db.add(setting)
    db.commit()
    _write_audit_log(
        admin_username,
        "model_config_update",
        db,
        target_type="model_config",
        detail=str(list(updates.keys())),
        details={
            "changed_keys": list(updates.keys()),
            "old_values": old_values,
            "new_values": updates,
        },
    )
    return {"success": True, **get_model_config_payload(db)}


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

【硬性数据约束——必须严格遵守】
- 报告中涉及练习题数、正确率、练习次数、任务完成数、学习时长等数字时，必须使用上方【练习表现】【学习任务】中的真实数据，不得编造或推测。
- 禁止编造 statistics 中不存在的练习数字、正确率百分比或任务完成数量。
- 如果某项数据为 0 或标注为"暂无"，报告中必须写"暂无足够数据"或"暂未记录"，不得推测任何具体数字。
- 薄弱知识点只列出上方"薄弱知识点"中实际出现的内容，不得自行添加其他知识点。

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

    # ── Practice (from learning_records) ──
    def _parse_tags(ts):
        try: return json.loads(ts) if ts else {}
        except: return {}
    practice_query = db.query(models.LearningRecord).filter(
        models.LearningRecord.user_id == get_user_by_username(username, db).id,
        models.LearningRecord.record_type == "practice",
        models.LearningRecord.created_at >= start,
        models.LearningRecord.created_at <= end,
    )
    if course_id:
        practice_query = practice_query.filter(models.LearningRecord.subject == course_id)
    practice_records = practice_query.all()
    practice_sessions = len(practice_records)

    # Use graded_questions for accuracy (excludes short_answer from denominator)
    def _pq_total(tags_dict):
        # total_questions if available (all questions), else total (backward compat)
        return tags_dict.get("total_questions", tags_dict.get("total", 0))
    def _pq_graded(tags_dict):
        # graded_questions if available (auto-graded), else total (backward compat)
        return tags_dict.get("graded_questions", tags_dict.get("total", 0))

    practice_q = sum(_pq_total(_parse_tags(r.tags)) for r in practice_records)
    practice_q_graded = sum(_pq_graded(_parse_tags(r.tags)) for r in practice_records)
    practice_c = sum(_parse_tags(r.tags).get("correct", 0) for r in practice_records)
    practice_acc = round(practice_c / practice_q_graded * 100, 1) if practice_q_graded > 0 else 0
    practice_dur = sum(_parse_tags(r.tags).get("duration_seconds", 0) for r in practice_records)
    task_practice_count = sum(1 for r in practice_records if _parse_tags(r.tags).get("task_id"))

    # Course-level practice aggregation
    course_practice = {}
    for r in practice_records:
        cid = r.subject or ""
        if cid not in course_practice: course_practice[cid] = {"q": 0, "q_graded": 0, "c": 0, "dur": 0}
        t = _parse_tags(r.tags)
        course_practice[cid]["q"] += _pq_total(t)
        course_practice[cid]["q_graded"] += _pq_graded(t)
        course_practice[cid]["c"] += t.get("correct", 0)
        course_practice[cid]["dur"] += t.get("duration_seconds", 0)
    course_practice_list = [{"course_name": cid, "questions": d["q"], "graded_questions": d["q_graded"], "correct": d["c"],
                              "accuracy": round(d["c"]/d["q_graded"]*100,1) if d["q_graded"]>0 else 0,
                              "duration_minutes": round(d["dur"]/60)} for cid, d in course_practice.items()]

    # Latest practice activities
    recent_practice_activities = [
        {"title": r.question or "完成练习", "summary": f"完成 {_parse_tags(r.tags).get('total',0)} 题，正确 {_parse_tags(r.tags).get('correct',0)} 题，正确率 {_parse_tags(r.tags).get('accuracy',0)}%"}
        for r in practice_records[-5:]
    ]

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
        # Real practice from learning_records
        "sessions": practice_sessions,
        "questions": practice_q,
        "practice_correct": practice_c,
        "practice_accuracy": practice_acc,
        "duration_minutes": round(practice_dur / 60),
        "task_practice_count": task_practice_count,
        "course_details": course_practice_list,
        "recent_activities": recent_practice_activities,
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

    if is_exam_408_context(req.course_id, req.course_name):
        check_exam_408_usage_limit(user, "learning_report_generate", db)
    else:
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

【练习表现】
练习次数：{report_data['practice']['sessions']} 次，完成 {report_data['practice']['questions']} 题，正确 {report_data['practice']['practice_correct']} 题，正确率 {report_data['practice']['practice_accuracy']}%，学习时长 {report_data['practice']['duration_minutes']} 分钟
来自任务中心练习：{report_data['practice']['task_practice_count']} 次
按课程练习分布：{json.dumps(report_data['practice']['course_details'], ensure_ascii=False) if report_data['practice']['course_details'] else '暂无'}

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

    statistics = {
        "practice_sessions": report_data["practice"]["sessions"],
        "practice_questions": report_data["practice"]["questions"],
        "practice_accuracy": report_data["practice"]["practice_accuracy"],
        "study_minutes": report_data["practice"]["duration_minutes"],
        "completed_tasks": report_data["tasks"]["completed"],
        "weak_points": [w["title"] for w in report_data["knowledge"]["weak_points"][:5]],
    }
    metrics = {
        "task_completed_count": report_data["tasks"]["completed"],
        "question_attempt_count": report_data["practice"]["attempt_count"],
        "correct_rate": report_data["practice"]["correct_rate"],
        "material_count": report_data["materials"]["uploaded"],
        "knowledge_point_count": report_data["knowledge"]["total_points"],
        "mastered_point_count": report_data["knowledge"]["mastered"],
        "weak_point_count": len(report_data["knowledge"]["weak_points"]),
        "ai_chat_count": report_data["ai_usage"]["total_calls"],
        # Real practice stats
        "practice_sessions": report_data["practice"]["sessions"],
        "practice_questions": report_data["practice"]["questions"],
        "practice_accuracy": report_data["practice"]["practice_accuracy"],
        "practice_duration_minutes": report_data["practice"]["duration_minutes"],
        # Embedded statistics for persistence
        "statistics": statistics,
    }

    report = models.LearningReport(
        username=user.username,
        course_id=course_id or None,
        course_name=course_id or None,
        report_type=report_type,
        title=title,
        summary=summary,
        content=content,
        metrics_json=json.dumps(metrics, ensure_ascii=False),
        suggestions_json=json.dumps([str(s)[:500] for s in suggestions], ensure_ascii=False),
        start_date=start,
        end_date=end,
        created_at=utc_now(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "id": report.id,
        "title": title,
        "summary": summary,
        "content": content,
        "metrics": metrics,
        "suggestions": suggestions,
        "start_date": serialize_datetime(start),
        "end_date": serialize_datetime(end),
        "report_type": report_type,
        "course_id": course_id or "",
        "course_name": course_id or "",
        "created_at": serialize_datetime(report.created_at),
        "statistics": statistics,
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
    statistics = None
    if report.metrics_json:
        try:
            metrics = json.loads(report.metrics_json)
            # Extract embedded statistics if present (for new reports)
            if isinstance(metrics, dict) and "statistics" in metrics:
                statistics = metrics.pop("statistics")
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
        "statistics": statistics,
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

    ensure_feature_enabled(db, "feature_report_share_enabled", "报告分享功能暂时关闭")

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
    require_admin_permission(db, admin_username, "report_shares.view")

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


# ── Helper: chunk text for reindex ─────────────────────

def _chunk_text_for_material(text: str, filename: str, material_id: int, username: str, subject: str) -> list[dict]:
    """Split text into chunks by paragraphs with overlap. Returns list of dicts for MaterialChunk."""
    chunks = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunk_size = 5  # paragraphs per chunk
    for i in range(0, len(paragraphs), max(1, chunk_size - 1)):
        chunk_text = "\n\n".join(paragraphs[i:i + chunk_size])
        if not chunk_text.strip():
            continue
        chunks.append({
            "material_id": material_id,
            "username": username,
            "subject": subject,
            "chunk_index": len(chunks),
            "chunk_text": chunk_text[:8000],
            "chunk_summary": chunk_text[:200],
            "keywords": "",
            "source_filename": filename or "",
            "is_deleted": False,
        })
    return chunks


# ── Admin: User Status (disable/enable) ─────────────────

@app.put("/admin/users/{target_username}/status")
def admin_user_status(target_username: str, req: dict, db: Session = Depends(get_db)):
    """Disable or enable a user account."""
    admin_name = str(req.get("admin_username", "")).strip()
    if not admin_name:
        raise HTTPException(status_code=400, detail="缺少 admin_username")
    require_admin_permission(db, admin_name, "users.manage_status")
    is_active = req.get("is_active", True)
    if not isinstance(is_active, bool) and not isinstance(is_active, int):
        raise HTTPException(status_code=400, detail="is_active 必须为布尔值")
    user = db.query(models.User).filter(models.User.username == target_username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    admin = get_user_by_username(admin_name, db)
    if bool(user.is_admin) and normalize_admin_role(admin) != "super_admin":
        raise HTTPException(status_code=403, detail="当前管理员没有权限修改管理员账号状态")
    if user.username == admin_name:
        raise HTTPException(status_code=400, detail="不能禁用当前管理员自己的账号")
    # Prevent disabling the last admin
    if not is_active and user.is_admin:
        admin_count = db.query(models.User).filter(models.User.is_admin == 1, models.User.is_active != 0).count()
        if normalize_admin_role(user) == "super_admin" and count_active_super_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="不能禁用最后一个超级管理员")
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="不能禁用最后一个管理员账号")
    old_active = bool(user.is_active)
    user.is_active = 1 if is_active else 0
    db.commit()
    _write_audit_log(
        admin_name,
        f"{'启用' if is_active else '禁用'}用户 {target_username}",
        db,
        target_type="user",
        target_username=target_username,
        detail=f"is_active={'1' if is_active else '0'}",
        details={"old_is_active": old_active, "new_is_active": bool(is_active)},
    )
    return {"success": True, "username": target_username, "is_active": bool(is_active)}


def get_admin_target_user(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def ensure_admin_can_modify_user(admin: models.User, target: models.User, action: str):
    if target.username == admin.username:
        raise HTTPException(status_code=400, detail=f"不能{action}当前管理员自己的账号")
    if bool(getattr(target, "is_admin", 0)) or normalize_admin_role(target) != "none":
        raise HTTPException(status_code=403, detail=f"不能{action}管理员账号")


@app.post("/admin/users/{user_id}/ban")
def admin_ban_user(user_id: int, req: dict, db: Session = Depends(get_db)):
    admin_name = str(req.get("admin_username", "")).strip()
    admin = require_admin_permission(db, admin_name, "users.manage_status")
    target = get_admin_target_user(db, user_id)
    ensure_admin_can_modify_user(admin, target, "封禁")
    if bool(getattr(target, "is_deleted", 0)):
        raise HTTPException(status_code=400, detail="用户已被删除")

    reason = str(req.get("reason", "")).strip()[:500]
    target.is_banned = 1
    target.banned_reason = reason
    target.banned_at = serialize_datetime(utc_now())
    db.commit()
    _write_audit_log(
        admin_name,
        f"封禁用户 {target.username}",
        db,
        target_type="user",
        target_id=str(target.id),
        target_username=target.username,
        detail=reason,
        details={"user_id": target.id, "reason": reason},
    )
    return {"success": True, "user": user_profile(target)}


@app.post("/admin/users/{user_id}/unban")
def admin_unban_user(user_id: int, req: dict, db: Session = Depends(get_db)):
    admin_name = str(req.get("admin_username", "")).strip()
    require_admin_permission(db, admin_name, "users.manage_status")
    target = get_admin_target_user(db, user_id)
    if bool(getattr(target, "is_deleted", 0)):
        raise HTTPException(status_code=400, detail="用户已被删除")

    target.is_banned = 0
    target.banned_reason = None
    target.banned_at = None
    db.commit()
    _write_audit_log(
        admin_name,
        f"解封用户 {target.username}",
        db,
        target_type="user",
        target_id=str(target.id),
        target_username=target.username,
        detail=f"user_id={target.id}",
        details={"user_id": target.id},
    )
    return {"success": True, "user": user_profile(target)}


@app.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, admin_username: str = "", db: Session = Depends(get_db)):
    admin = require_admin_permission(db, admin_username, "users.manage_status")
    target = get_admin_target_user(db, user_id)
    ensure_admin_can_modify_user(admin, target, "删除")

    if not bool(getattr(target, "is_deleted", 0)):
        target.is_deleted = 1
        target.deleted_at = serialize_datetime(utc_now())
        db.commit()
        _write_audit_log(
            admin_username,
            f"删除用户 {target.username}",
            db,
            target_type="user",
            target_id=str(target.id),
            target_username=target.username,
            detail=f"user_id={target.id}",
            details={"user_id": target.id, "soft_delete": True},
        )
    return {"success": True, "user_id": user_id, "is_deleted": True}


# ── Admin: Material Delete ──────────────────────────────

@app.delete("/admin/materials/{material_id}")
def admin_delete_material(material_id: int, admin_username: str, db: Session = Depends(get_db)):
    """Soft-delete a material and its chunks."""
    require_admin_permission(db, admin_username, "materials.delete")
    material = db.query(models.StudyMaterial).filter(models.StudyMaterial.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")
    filename = material.original_filename or str(material_id)
    username = material.username or ""
    # Soft-delete material
    material.is_deleted = True
    material.deleted_at = utc_now()
    # Soft-delete associated chunks
    db.query(models.MaterialChunk).filter(models.MaterialChunk.material_id == material_id).update(
        {"is_deleted": True}, synchronize_session=False
    )
    db.commit()
    _write_audit_log(
        admin_username,
        f"删除资料 {filename}",
        db,
        target_type="material",
        target_id=str(material_id),
        target_username=username,
        detail=f"material_id={material_id}, filename={filename}",
        details={"material_id": material_id, "filename": filename, "username": username, "subject": material.subject or ""},
    )
    return {"success": True, "message": f"资料 {filename} 已删除（软删除）", "material_id": material_id}


# ── Admin: Material Reindex ─────────────────────────────

@app.post("/admin/materials/{material_id}/reindex")
def admin_reindex_material(material_id: int, admin_username: str, db: Session = Depends(get_db)):
    """Rebuild material chunks from existing extracted text."""
    require_admin_permission(db, admin_username, "materials.reindex")
    material = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.id == material_id,
        models.StudyMaterial.is_deleted.is_(False),
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="资料不存在")
    source_text = material.extracted_text or ""
    if not source_text.strip():
        raise HTTPException(status_code=400, detail="该资料没有可用解析文本，无法重新索引")
    # Soft-delete old chunks
    db.query(models.MaterialChunk).filter(models.MaterialChunk.material_id == material_id).update(
        {"is_deleted": True}, synchronize_session=False
    )
    # Re-chunk
    new_chunks = _chunk_text_for_material(source_text, material.original_filename or "doc", material_id, material.username or "", material.subject or "")
    for ch in new_chunks:
        db.add(models.MaterialChunk(**ch))
    db.commit()
    _write_audit_log(
        admin_username,
        f"重新索引资料 {material.original_filename or str(material_id)}",
        db,
        target_type="material",
        target_id=str(material_id),
        target_username=material.username or "",
        detail=f"material_id={material_id}, chunk_count={len(new_chunks)}",
        details={"material_id": material_id, "filename": material.original_filename or "", "chunk_count": len(new_chunks)},
    )
    return {"success": True, "message": f"重新索引完成", "chunk_count": len(new_chunks)}


# ── Admin: Report Share Status ──────────────────────────

@app.put("/admin/report-shares/{share_id}/status")
def admin_report_share_status(share_id: int, req: dict, db: Session = Depends(get_db)):
    """Approve, revoke, or restore a report share."""
    admin_name = str(req.get("admin_username", "")).strip()
    if not admin_name:
        raise HTTPException(status_code=400, detail="缺少 admin_username")
    require_admin_permission(db, admin_name, "report_shares.moderate")
    new_status = str(req.get("status", "")).strip().lower()
    if new_status not in ("approved", "revoked", "pending"):
        raise HTTPException(status_code=400, detail="无效的状态，支持: approved, revoked, pending")
    share = db.query(models.LearningReportShare).filter(models.LearningReportShare.id == share_id).first()
    if not share:
        raise HTTPException(status_code=404, detail="分享记录不存在")
    old_active = bool(share.is_active)
    share.is_active = 0 if new_status == "revoked" else 1
    share.revoked_at = utc_now() if new_status == "revoked" else (None if new_status == "approved" else share.revoked_at)
    db.commit()
    _write_audit_log(
        admin_name,
        f"修改报告分享状态 share_id={share_id} {new_status}",
        db,
        target_type="report_share",
        target_id=str(share_id),
        target_username=share.username or "",
        detail=f"share_id={share_id}, old_is_active={old_active}, new_status={new_status}",
        details={"share_id": share_id, "old_is_active": old_active, "new_is_active": bool(share.is_active), "new_status": new_status},
    )
    return {"success": True, "share_id": share_id, "status": new_status}


# ── Admin: System Health ─────────────────────────────

@app.get("/admin/system-health")
def admin_system_health(admin_username: str, db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "system_monitor.view")
    import os as _os, sys as _sys

    # Server
    server_status = {"status": "ok", "time": serialize_datetime(utc_now()), "uptime_note": "后端服务可响应"}

    # Database
    try:
        users_count = db.query(models.User).count()
        materials_count = db.query(models.StudyMaterial).filter(models.StudyMaterial.is_deleted.is_(False)).count()
        chunks_count = db.query(models.MaterialChunk).filter(models.MaterialChunk.is_deleted.is_(False)).count()
        ai_logs_count = db.query(models.AiUsageLog).count()
        db_status = {"status": "ok", "users_count": users_count, "materials_count": materials_count, "chunks_count": chunks_count, "ai_logs_count": ai_logs_count}
    except Exception as e:
        db_status = {"status": "danger", "note": str(e)[:200], "users_count": 0, "materials_count": 0, "chunks_count": 0, "ai_logs_count": 0}

    # Storage — check upload dir
    upload_dir = _os.environ.get("UPLOAD_DIR", "uploads")
    storage_status = {"status": "ok", "upload_dir_exists": _os.path.exists(upload_dir), "upload_dir": upload_dir, "note": "上传目录" + ("可用" if _os.path.exists(upload_dir) else "不存在")}
    if not _os.path.exists(upload_dir): storage_status["status"] = "warning"

    # AI services
    deepseek_key = _os.environ.get("DEEPSEEK_API_KEY", "")
    qwen_key = _os.environ.get("QWEN_API_KEY", "")
    today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    ds_failed = db.query(models.AiUsageLog).filter(models.AiUsageLog.status != "success", models.AiUsageLog.feature.in_(ALL_FEATURES), models.AiUsageLog.created_at >= today_start).count()
    ai_services = {
        "deepseek": {"configured": bool(deepseek_key), "status": "configured" if deepseek_key else "not_configured", "note": "已配置 API Key" if deepseek_key else "未配置 DeepSeek API Key", "recent_failed": ds_failed},
        "qwen": {"configured": bool(qwen_key), "status": "configured" if qwen_key else "not_configured", "note": "已配置图片解析能力" if qwen_key else "未配置 Qwen API Key", "recent_failed": 0},
    }

    # Recent AI errors
    recent_errors_q = db.query(models.AiUsageLog).filter(models.AiUsageLog.status != "success").order_by(models.AiUsageLog.created_at.desc()).limit(5).all()
    recent_errors = [{"type": "ai_call_failed", "message": (r.error_message or "未知错误")[:200], "feature": r.feature, "username": r.username, "time": serialize_datetime(r.created_at)} for r in recent_errors_q]

    # Material issues summary
    empty_text = db.query(models.StudyMaterial).filter(models.StudyMaterial.is_deleted.is_(False), models.StudyMaterial.extracted_text.is_(None) | (models.StudyMaterial.extracted_text == "")).count()
    no_chunks = db.query(models.StudyMaterial).filter(models.StudyMaterial.is_deleted.is_(False), models.StudyMaterial.extracted_text.isnot(None), models.StudyMaterial.extracted_text != "").count()
    # Count materials with text but no chunks
    mats_with_text = db.query(models.StudyMaterial).filter(models.StudyMaterial.is_deleted.is_(False), models.StudyMaterial.extracted_text.isnot(None), models.StudyMaterial.extracted_text != "").all()
    nc_count = 0
    for m in mats_with_text:
        cc = db.query(models.MaterialChunk).filter(models.MaterialChunk.material_id == m.id, models.MaterialChunk.is_deleted.is_(False)).count()
        if cc == 0: nc_count += 1

    alerts = []
    overall = "ok"
    if ds_failed > 0: alerts.append({"level": "warning", "title": "有 AI 调用失败", "message": f"最近 24 小时 {ds_failed} 条失败记录", "value": ds_failed})
    if empty_text > 0: alerts.append({"level": "warning", "title": "存在资料解析文本为空", "message": f"有 {empty_text} 个资料没有提取到文本", "value": empty_text})
    if nc_count > 0: alerts.append({"level": "warning", "title": "存在资料未建立索引", "message": f"有 {nc_count} 个资料没有 chunks", "value": nc_count})
    if not deepseek_key: alerts.append({"level": "warning", "title": "DeepSeek 配置缺失", "message": "未配置 DEEPSEEK_API_KEY", "value": 0}); overall = "warning"
    if not _os.path.exists(upload_dir): overall = "warning"
    if recent_errors_q: overall = "warning"

    return {"status": overall, "server": server_status, "database": db_status, "storage": storage_status, "ai_services": ai_services, "recent_errors": recent_errors, "alerts": alerts, "material_issues_summary": {"empty_text": empty_text, "no_index": nc_count}}


# ── Admin: Material Issues ───────────────────────────

@app.get("/admin/material-issues")
def admin_material_issues(admin_username: str, issue_type: str = "all", page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "system_monitor.view")
    page = max(1, page); page_size = min(100, max(1, page_size))
    query = db.query(models.StudyMaterial).filter(models.StudyMaterial.is_deleted.is_(False))
    it = issue_type.strip()
    if it == "empty_text": query = query.filter(models.StudyMaterial.extracted_text.is_(None) | (models.StudyMaterial.extracted_text == ""))
    elif it == "no_chunks":
        query = query.filter(models.StudyMaterial.extracted_text.isnot(None), models.StudyMaterial.extracted_text != "")
    total = query.count()
    mats = query.order_by(models.StudyMaterial.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for m in mats:
        cc = db.query(models.MaterialChunk).filter(models.MaterialChunk.material_id == m.id, models.MaterialChunk.is_deleted.is_(False)).count()
        et_len = len(m.extracted_text) if m.extracted_text else 0
        issue = "ok"
        if et_len == 0: issue = "empty_text"
        elif cc == 0: issue = "no_chunks"
        if it != "all" and it != issue: continue
        items.append({"id": m.id, "filename": m.original_filename or str(m.id), "username": m.username or "", "course_name": m.subject or "", "file_type": m.file_type or "", "file_size": m.file_size or 0, "created_at": serialize_datetime(m.created_at), "extracted_text_length": et_len, "chunk_count": cc, "issue_type": issue, "issue_label": "解析文本为空" if issue == "empty_text" else ("未建立索引" if issue == "no_chunks" else "正常")})
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ── Admin: Announcements ──────────────────────────────

@app.get("/admin/announcements")
def admin_announcements_list(admin_username: str = "", db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "settings.view")
    items = db.query(models.SystemAnnouncement).order_by(models.SystemAnnouncement.created_at.desc()).all()
    return {"items": [_serialize_admin_announcement(a) for a in items]}


def _announcement_status(a):
    if getattr(a, "withdrawn_at", None):
        return "withdrawn"
    return "published" if a.is_active else "draft"


def _serialize_admin_announcement(a):
    return {
        "id": a.id,
        "title": a.title,
        "content": a.content,
        "type": a.type,
        "is_active": bool(a.is_active),
        "status": _announcement_status(a),
        "target": a.target,
        "created_by": a.created_by,
        "created_at": serialize_datetime(a.created_at),
        "updated_at": serialize_datetime(a.updated_at),
        "withdrawn_at": serialize_datetime(getattr(a, "withdrawn_at", None)),
    }


@app.post("/admin/announcements")
def admin_announcements_create(req: dict, db: Session = Depends(get_db)):
    admin_name = str(req.get("admin_username", "")).strip()
    require_admin_permission(db, admin_name, "announcements.manage")
    title = str(req.get("title", "")).strip()
    content = str(req.get("content", "")).strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="标题和内容不能为空")
    status = str(req.get("status", "published")).strip().lower()
    is_active = 0 if status in ("draft", "inactive", "disabled") else 1
    a = models.SystemAnnouncement(
        title=title[:500], content=content[:5000],
        type=str(req.get("type", "info")).strip() or "info",
        target=str(req.get("target", "all")).strip() or "all",
        is_active=int(req.get("is_active", is_active)),
        created_by=admin_name,
    )
    db.add(a); db.commit(); db.refresh(a)
    _write_audit_log(
        admin_name,
        f"创建公告 {a.title}",
        db,
        target_type="announcement",
        target_id=str(a.id),
        detail=f"id={a.id}",
        details={"id": a.id, "title": a.title, "type": a.type, "target": a.target, "is_active": bool(a.is_active)},
    )
    return {"success": True, "announcement": _serialize_admin_announcement(a)}


@app.put("/admin/announcements/{a_id}")
def admin_announcements_update(a_id: int, req: dict, db: Session = Depends(get_db)):
    admin_name = str(req.get("admin_username", "")).strip()
    require_admin_permission(db, admin_name, "announcements.manage")
    a = db.query(models.SystemAnnouncement).filter(models.SystemAnnouncement.id == a_id).first()
    if not a: raise HTTPException(status_code=404, detail="公告不存在")
    old_values = {"title": a.title, "content": a.content, "type": a.type, "target": a.target, "is_active": bool(a.is_active)}
    if "title" in req: a.title = str(req["title"]).strip()[:500]
    if "content" in req: a.content = str(req["content"]).strip()[:5000]
    if "type" in req: a.type = str(req["type"]).strip() or "info"
    if "target" in req: a.target = str(req["target"]).strip() or "all"
    if "is_active" in req:
        a.is_active = int(req["is_active"])
        if a.is_active:
            a.withdrawn_at = None
    a.updated_at = utc_now()
    db.commit()
    _write_audit_log(
        admin_name,
        f"修改公告 {a.title}",
        db,
        target_type="announcement",
        target_id=str(a.id),
        detail=f"id={a.id}",
        details={"id": a.id, "old_values": old_values, "new_values": {"title": a.title, "content": a.content, "type": a.type, "target": a.target, "is_active": bool(a.is_active)}},
    )
    db.refresh(a)
    return {"success": True, "announcement": _serialize_admin_announcement(a)}


@app.patch("/admin/announcements/{a_id}")
def admin_announcements_patch(a_id: int, req: dict, db: Session = Depends(get_db)):
    admin_name = str(req.get("admin_username", "")).strip()
    require_admin_permission(db, admin_name, "announcements.manage")
    a = db.query(models.SystemAnnouncement).filter(models.SystemAnnouncement.id == a_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="公告不存在")

    title = str(req.get("title", a.title) or "").strip()
    content = str(req.get("content", a.content) or "").strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="标题和内容不能为空")

    old_values = {
        "title": a.title,
        "content": a.content,
        "type": a.type,
        "target": a.target,
        "is_active": bool(a.is_active),
        "status": _announcement_status(a),
    }
    a.title = title[:500]
    a.content = content[:5000]
    if "type" in req:
        a.type = str(req["type"]).strip() or "info"
    if "target" in req:
        a.target = str(req["target"]).strip() or "all"
    status = str(req.get("status", _announcement_status(a))).strip().lower()
    if status == "published":
        a.is_active = 1
        a.withdrawn_at = None
    elif status == "withdrawn":
        a.is_active = 0
        a.withdrawn_at = a.withdrawn_at or utc_now()
    elif status in ("draft", "inactive", "disabled"):
        a.is_active = 0
        a.withdrawn_at = None
    if "is_active" in req and "status" not in req:
        a.is_active = int(req["is_active"])
        if a.is_active:
            a.withdrawn_at = None
    a.updated_at = utc_now()
    db.commit()
    db.refresh(a)
    _write_audit_log(
        admin_name,
        f"修改公告 {a.title}",
        db,
        target_type="announcement",
        target_id=str(a.id),
        detail=f"id={a.id}",
        details={"id": a.id, "old_values": old_values, "new_values": _serialize_admin_announcement(a)},
    )
    return {"success": True, "announcement": _serialize_admin_announcement(a)}


@app.post("/admin/announcements/{a_id}/withdraw")
def admin_announcements_withdraw(a_id: int, req: dict, db: Session = Depends(get_db)):
    admin_name = str(req.get("admin_username", "")).strip()
    require_admin_permission(db, admin_name, "announcements.manage")
    a = db.query(models.SystemAnnouncement).filter(models.SystemAnnouncement.id == a_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="公告不存在")
    a.is_active = 0
    a.withdrawn_at = utc_now()
    a.updated_at = utc_now()
    db.commit()
    db.refresh(a)
    _write_audit_log(
        admin_name,
        f"撤回公告 {a.title}",
        db,
        target_type="announcement",
        target_id=str(a.id),
        detail=f"id={a.id}",
        details={"id": a.id, "title": a.title, "status": "withdrawn"},
    )
    return {"success": True, "announcement": _serialize_admin_announcement(a)}


@app.put("/admin/announcements/{a_id}/status")
def admin_announcements_toggle(a_id: int, req: dict, db: Session = Depends(get_db)):
    admin_name = str(req.get("admin_username", "")).strip()
    require_admin_permission(db, admin_name, "announcements.manage")
    a = db.query(models.SystemAnnouncement).filter(models.SystemAnnouncement.id == a_id).first()
    if not a: raise HTTPException(status_code=404, detail="公告不存在")
    old_active = bool(a.is_active)
    a.is_active = int(req.get("is_active", 0))
    if a.is_active:
        a.withdrawn_at = None
    a.updated_at = utc_now()
    db.commit()
    _write_audit_log(
        admin_name,
        f"{'启用' if a.is_active else '停用'}公告 {a.title}",
        db,
        target_type="announcement",
        target_id=str(a.id),
        detail=f"id={a.id}",
        details={"id": a.id, "old_is_active": old_active, "new_is_active": bool(a.is_active), "title": a.title},
    )
    return {"success": True, "is_active": bool(a.is_active)}


@app.delete("/admin/announcements/{a_id}")
def admin_announcements_delete(a_id: int, admin_username: str, db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "announcements.manage")
    a = db.query(models.SystemAnnouncement).filter(models.SystemAnnouncement.id == a_id).first()
    if not a: raise HTTPException(status_code=404, detail="公告不存在")
    deleted_info = {"id": a.id, "title": a.title, "type": a.type, "target": a.target, "is_active": bool(a.is_active)}
    db.delete(a); db.commit()
    _write_audit_log(admin_username, f"删除公告 {deleted_info['title']}", db, target_type="announcement", target_id=str(a_id), detail=f"id={a_id}", details=deleted_info)
    return {"success": True}


# ── Public: Active Announcements ──────────────────────

@app.get("/announcements/active")
def public_announcements(db: Session = Depends(get_db)):
    items = db.query(models.SystemAnnouncement).filter(models.SystemAnnouncement.is_active == 1).order_by(models.SystemAnnouncement.created_at.desc()).limit(5).all()
    return {"items": [{"id": a.id, "title": a.title, "content": a.content, "type": a.type, "target": a.target} for a in items]}


# ── Admin: Settings ───────────────────────────────────

def _get_setting(db, key, default=""):
    s = db.query(models.SystemSetting).filter(models.SystemSetting.key == key).first()
    return s.value if s else default


def _safe_setting_audit_value(key: str, value):
    lowered = (key or "").lower()
    if any(word in lowered for word in ("api", "key", "secret", "password", "token")):
        return "***"
    return str(value)

@app.get("/admin/settings")
def admin_settings(admin_username: str = "", db: Session = Depends(get_db)):
    require_admin_permission(db, admin_username, "settings.view")
    items = db.query(models.SystemSetting).all()
    return {"items": [{"key": s.key, "value": s.value, "description": s.description, "updated_by": s.updated_by, "updated_at": serialize_datetime(s.updated_at)} for s in items]}


@app.put("/admin/settings")
def admin_settings_update(req: dict, db: Session = Depends(get_db)):
    admin_name = str(req.get("admin_username", "")).strip()
    require_admin_permission(db, admin_name, "settings.manage")
    updates = req.get("updates", {})
    if not isinstance(updates, dict) or not updates:
        raise HTTPException(status_code=400, detail="请提供要更新的配置项")
    old_values = {}
    for k, v in updates.items():
        s = db.query(models.SystemSetting).filter(models.SystemSetting.key == k).first()
        if not s: s = models.SystemSetting(key=k)
        old_values[k] = _safe_setting_audit_value(k, s.value if s else "")
        s.value = str(v); s.updated_by = admin_name; s.updated_at = utc_now()
        db.add(s)
    db.commit()
    _write_audit_log(
        admin_name,
        f"更新平台配置 ({len(updates)}项)",
        db,
        target_type="settings",
        detail=str(list(updates.keys())),
        details={
            "changed_keys": list(updates.keys()),
            "old_values": old_values,
            "new_values": {k: _safe_setting_audit_value(k, v) for k, v in updates.items()},
        },
    )
    return {"success": True}


@app.get("/settings/public")
def public_settings(db: Session = Depends(get_db)):
    """Return only feature toggle settings — safe for unauthenticated access."""
    feature_keys = ["feature_ai_chat_enabled", "feature_material_upload_enabled", "feature_code_studio_enabled", "feature_practice_center_enabled", "feature_report_share_enabled"]
    result = {}
    for k in feature_keys:
        s = db.query(models.SystemSetting).filter(models.SystemSetting.key == k).first()
        result[k] = (s.value if s else "true") == "true"
    return result


# ── Feature Gate Helpers ──────────────────────────────

def normalize_setting_bool(value, default=True):
    """Normalize a setting value to boolean. Returns default on error/missing."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "on"):
            return True
        if v in ("false", "0", "no", "off"):
            return False
    return default


def is_feature_enabled_db(db, key, default=True):
    """Check if a feature is enabled in system_settings. Default: enabled."""
    try:
        s = db.query(models.SystemSetting).filter(models.SystemSetting.key == key).first()
        if not s:
            return default
        return normalize_setting_bool(s.value, default)
    except Exception:
        return default


def ensure_feature_enabled(db, key, message):
    """Raise 403 if feature is disabled."""
    if not is_feature_enabled_db(db, key, default=True):
        raise HTTPException(status_code=403, detail=message)


# ── Interactive Terminal WebSocket ─────────────────────

INTERACTIVE_TIMEOUT = 30  # seconds
INTERACTIVE_MEMORY = "128m"
INTERACTIVE_MEMORY_C = "256m"


@app.websocket("/api/code/interactive-run")
@app.websocket("/code/interactive-run")
async def interactive_run(ws: WebSocket):
    await ws.accept()
    print("[WS-TERMINAL] accepted interactive terminal websocket")

    try:
        raw = await ws.receive_text()
        config = json.loads(raw)
    except Exception:
        await ws.send_text(json.dumps({"type": "error", "message": "连接参数无效"}))
        await ws.close()
        return

    language = (config.get("language", "") or "").strip().lower()
    code = (config.get("code", "") or "")
    username = config.get("username", "anonymous")
    print(f"[WS-TERMINAL] start username={username} language={language} code_chars={len(code)}")

    if language not in ("python", "c"):
        await ws.send_text(json.dumps({"type": "error", "message": f"交互运行暂不支持 {language or '该语言'}"}))
        await ws.close()
        return

    if not code.strip():
        await ws.send_text(json.dumps({"type": "error", "message": "代码为空，请先编写代码再运行。"}))
        await ws.close()
        return

    if not _check_code_run_rate(username, CODE_RUN_RATE_EXECUTE):
        await ws.send_text(json.dumps({"type": "error", "message": "运行过于频繁，每分钟最多 10 次，请稍后再试。"}))
        await ws.close()
        return

    acquired = DOCKER_SEMAPHORE.acquire(timeout=DOCKER_SEMAPHORE_TIMEOUT)
    if not acquired:
        await ws.send_text(json.dumps({"type": "error", "message": "当前代码运行任务较多，请稍后重试。"}))
        await ws.close()
        return

    tmp_dir = tempfile.mkdtemp(prefix="interactive_")
    is_c = language == "c"
    src_path = os.path.join(tmp_dir, "main.c" if is_c else "main.py")

    await ws.send_text(json.dumps({"type": "status", "message": f"开始{'编译并运行' if is_c else '运行'} {language.upper()} 代码..."}))

    try:
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(code)

        if is_c:
            await ws.send_text(json.dumps({"type": "status", "message": "正在编译 C 代码..."}))
            compile_proc = subprocess.run(
                ["docker", "run", "--rm", "--network", "none", "--memory", INTERACTIVE_MEMORY_C,
                 "-v", f"{tmp_dir}:/code:ro", "-w", "/code", DOCKER_IMAGE_C,
                 "gcc", "-Wall", "-Wextra", "-o", "/tmp/prog", "main.c"],
                capture_output=True, text=True, timeout=20, cwd=tmp_dir,
            )
            if compile_proc.returncode != 0:
                compile_err = compile_proc.stderr or "编译失败"
                await ws.send_text(json.dumps({"type": "compile_error", "message": compile_err[:3000]}))
                await ws.send_text(json.dumps({"type": "exit", "exit_code": compile_proc.returncode}))
                return

            await ws.send_text(json.dumps({"type": "status", "message": "编译成功，正在运行..."}))
            docker_cmd = [
                "docker", "run", "--rm", "-i",
                "--network", "none", "--memory", INTERACTIVE_MEMORY_C,
                "--cpus", str(DOCKER_CPU_LIMIT), "--pids-limit", str(DOCKER_PIDS_LIMIT),
                "--read-only", "--tmpfs", "/tmp:rw,exec,nosuid,size=128m",
                "-v", f"{tmp_dir}:/code:ro", "-w", "/code",
                DOCKER_IMAGE_C, "sh", "-c",
                "cp /code/main.c /tmp/main.c && cd /tmp && gcc -Wall -Wextra -o prog main.c && ./prog",
            ]
        else:
            await ws.send_text(json.dumps({"type": "status", "message": "正在运行 Python 代码..."}))
            docker_cmd = [
                "docker", "run", "--rm", "-i",
                "--network", "none", "--memory", INTERACTIVE_MEMORY,
                "--cpus", str(DOCKER_CPU_LIMIT), "--pids-limit", str(DOCKER_PIDS_LIMIT),
                "--read-only", "--tmpfs", "/tmp:rw,exec,nosuid,size=128m",
                "-v", f"{tmp_dir}:/code:ro", "-w", "/code",
                DOCKER_IMAGE, "python", "-u", "main.py",
            ]

        proc = subprocess.Popen(
            docker_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, cwd=tmp_dir,
        )

        collected_stdout = []
        collected_stderr = []

        def reader(stream, collector, prefix, ws_socket, loop_ref):
            try:
                while True:
                    chunk = stream.read(1)
                    if not chunk:
                        break
                    collector.append(chunk)
                    try:
                        asyncio.run_coroutine_threadsafe(
                            ws_socket.send_text(json.dumps({"type": prefix, "data": chunk})),
                            loop_ref,
                        )
                    except Exception:
                        break
            except Exception:
                pass

        import threading
        loop = asyncio.get_event_loop()
        stdout_thread = threading.Thread(target=reader, args=(proc.stdout, collected_stdout, "stdout", ws, loop))
        stderr_thread = threading.Thread(target=reader, args=(proc.stderr, collected_stderr, "stderr", ws, loop))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        timed_out = False
        start_time = time.time()

        async def forward_stdin():
            nonlocal timed_out
            while True:
                try:
                    remaining = INTERACTIVE_TIMEOUT - (time.time() - start_time)
                    if remaining <= 0:
                        timed_out = True
                        proc.kill()
                        break
                    raw_stdin = await asyncio.wait_for(ws.receive_text(), timeout=min(1.0, remaining))
                    if proc.poll() is not None:
                        break
                    data = raw_stdin
                    try:
                        stdin_msg = json.loads(raw_stdin)
                        if isinstance(stdin_msg, dict):
                            if stdin_msg.get("type") == "stdin":
                                data = str(stdin_msg.get("data", ""))
                            elif stdin_msg.get("type") == "stop":
                                proc.kill()
                                break
                    except json.JSONDecodeError:
                        pass
                    data = data.replace("\r\n", "\n").replace("\r", "\n")
                    try:
                        if data:
                            proc.stdin.write(data)
                            proc.stdin.flush()
                    except (BrokenPipeError, OSError):
                        break
                except asyncio.TimeoutError:
                    if proc.poll() is not None:
                        break
                    if time.time() - start_time > INTERACTIVE_TIMEOUT:
                        timed_out = True
                        proc.kill()
                        break
                except WebSocketDisconnect:
                    proc.kill()
                    break
                except Exception:
                    break

        try:
            await forward_stdin()
        except Exception:
            pass

        proc.wait(timeout=3)
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

        assembled = {
            "type": "exit",
            "exit_code": proc.returncode,
            "timed_out": timed_out,
            "stdout": "".join(collected_stdout)[:8000],
            "stderr": "".join(collected_stderr)[:8000],
        }
        try:
            await ws.send_text(json.dumps(assembled))
        except Exception:
            pass

    except subprocess.TimeoutExpired:
        await ws.send_text(json.dumps({"type": "error", "message": f"运行超时（超过 {INTERACTIVE_TIMEOUT} 秒）"}))
    except FileNotFoundError:
        await ws.send_text(json.dumps({"type": "error", "message": "服务器 Docker 环境未就绪"}))
    except Exception as exc:
        await ws.send_text(json.dumps({"type": "error", "message": f"运行异常：{str(exc)[:300]}"}))
    finally:
        DOCKER_SEMAPHORE.release()
        try:
            if proc and proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        try: os.remove(src_path)
        except OSError: pass
        try: os.rmdir(tmp_dir)
        except OSError: pass
        try:
            await ws.close()
        except Exception:
            pass
