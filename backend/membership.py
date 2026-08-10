"""
Membership system: plan definitions, major classification, redemption codes.

Pure logic — no FastAPI routing here. Endpoints live in main.py.
"""
import json
import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

import models
from database import get_db

logger = logging.getLogger("membership")


# Direction-bound redemption flow.  The legacy helper remains below only for
# compatibility with old database rows; new API routes use these functions.
def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _redemption_expiry(entry: models.RedemptionCode) -> datetime | None:
    return _as_utc(getattr(entry, "code_expires_at", None) or entry.expires_at)


def _redemption_plan(entry: models.RedemptionCode) -> str:
    return (getattr(entry, "target_plan", None) or entry.plan_code or "").strip().lower()


def _redemption_service(entry: models.RedemptionCode) -> str:
    return (getattr(entry, "service_key", None) or "").strip().lower()


def _validate_redemption_entry(entry: models.RedemptionCode | None, now: datetime) -> str | None:
    if not entry:
        return "兑换码不存在"
    if entry.status in {"revoked", "disabled"}:
        return "兑换码已撤销"
    if entry.status in {"exhausted", "used"} or entry.used_count >= entry.max_uses:
        return "兑换码已用完"
    expires_at = _redemption_expiry(entry)
    if expires_at and expires_at <= now:
        entry.status = "expired"
        return "兑换码已过期"
    if not _redemption_service(entry) or not _redemption_plan(entry):
        return "兑换码未配置有效服务方向"
    if not get_service_plan(_redemption_service(entry), _redemption_plan(entry)):
        return "兑换码套餐无效"
    duration = getattr(entry, "membership_duration_days", None)
    if not duration or duration <= 0:
        return "兑换码会员时长无效"
    return None


def _current_service_membership(db: Session, user_id: int, service_key: str):
    return db.query(models.UserServiceMembership).filter(
        models.UserServiceMembership.user_id == user_id,
        models.UserServiceMembership.service_key == service_key,
    ).first()


def _preview_payload(entry: models.RedemptionCode, user: models.User, db: Session, now: datetime) -> dict:
    service_key = _redemption_service(entry)
    target_plan = _redemption_plan(entry)
    membership = _current_service_membership(db, user.id, service_key)
    current_plan = "free"
    current_expires_at = None
    if membership and membership.is_enabled and membership.status == "active":
        current_plan = membership.plan or "free"
        current_expires_at = _as_utc(membership.expires_at)
        if current_expires_at and current_expires_at <= now:
            current_plan = "free"
            current_expires_at = None
    if service_plan_rank(service_key, target_plan) < service_plan_rank(service_key, current_plan):
        raise ValueError("兑换码套餐低于当前套餐，不能降级")
    base_time = max(now, current_expires_at or now)
    projected_expiry = base_time + timedelta(days=int(entry.membership_duration_days))
    plan = get_service_plan(service_key, target_plan)
    code_expires_at = _redemption_expiry(entry)
    return {
        "service_key": service_key,
        "target_plan": target_plan,
        "target_plan_name": plan["name"],
        "membership_duration_days": int(entry.membership_duration_days),
        "code_expires_at": code_expires_at.isoformat() if code_expires_at else None,
        "current_plan": current_plan,
        "current_expires_at": current_expires_at.isoformat() if current_expires_at else None,
        "projected_expires_at": projected_expiry.isoformat(),
        "remaining_redemptions": max(0, int(entry.max_uses or 0) - int(entry.used_count or 0)),
    }


def preview_redemption_code(user: models.User, code_input: str, db: Session) -> dict:
    entry = db.query(models.RedemptionCode).filter(
        models.RedemptionCode.code_hash == hash_code(code_input)
    ).first()
    error = _validate_redemption_entry(entry, datetime.now(timezone.utc))
    if error:
        if entry and error == "兑换码已过期":
            db.commit()
        return {"success": False, "message": error}
    try:
        return {"success": True, "preview": _preview_payload(entry, user, db, datetime.now(timezone.utc))}
    except ValueError as exc:
        return {"success": False, "message": str(exc)}


def redeem_membership_code(user: models.User, code_input: str, db: Session) -> dict:
    """Atomically redeem one direction-bound code for the authenticated user."""
    now = datetime.now(timezone.utc)
    entry = db.query(models.RedemptionCode).filter(
        models.RedemptionCode.code_hash == hash_code(code_input)
    ).first()
    error = _validate_redemption_entry(entry, now)
    if error:
        db.rollback()
        return {"success": False, "message": error}
    try:
        if db.query(models.RedemptionCodeUsage).filter(
            models.RedemptionCodeUsage.code_id == entry.id,
            models.RedemptionCodeUsage.user_id == user.id,
        ).first():
            db.rollback()
            return {"success": False, "message": "同一用户不能重复兑换此码"}

        payload = _preview_payload(entry, user, db, now)
        updated = db.query(models.RedemptionCode).filter(
            models.RedemptionCode.id == entry.id,
            models.RedemptionCode.status == "active",
            models.RedemptionCode.used_count < models.RedemptionCode.max_uses,
        ).update({models.RedemptionCode.used_count: models.RedemptionCode.used_count + 1}, synchronize_session=False)
        if updated != 1:
            db.rollback()
            return {"success": False, "message": "兑换码已用完"}

        membership = _current_service_membership(db, user.id, payload["service_key"])
        expires_at = datetime.fromisoformat(payload["projected_expires_at"])
        if not membership:
            db.add(models.UserServiceMembership(
                user_id=user.id,
                service_key=payload["service_key"],
                is_enabled=True,
                plan=payload["target_plan"],
                status="active",
                activated_at=now,
                expires_at=expires_at,
            ))
        else:
            membership.is_enabled = True
            membership.plan = payload["target_plan"]
            membership.status = "active"
            membership.activated_at = membership.activated_at or now
            membership.expires_at = expires_at
            membership.updated_at = now

        db.add(models.RedemptionCodeUsage(
            code_id=entry.id,
            user_id=user.id,
            username=user.username,
            redeemed_at=now,
        ))
        db.flush()
        db.refresh(entry)
        entry.status = "exhausted" if entry.used_count >= entry.max_uses else "active"
        if entry.max_uses == 1:
            entry.used_by_user_id = user.id
            entry.used_by_username = user.username
            entry.used_at = now
        db.commit()
        return {"success": True, "message": "兑换成功", "redemption": payload}
    except Exception:
        db.rollback()
        logger.exception("Membership redemption failed")
        return {"success": False, "message": "兑换失败，请稍后重试"}


def redeem_code(username: str, code_input: str, db: Session) -> dict:
    """Backward-compatible wrapper; new routes use the authenticated user."""
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return {"success": False, "message": "用户不存在"}
    return redeem_membership_code(user, code_input, db)

# ── Plan Definitions ────────────────────────────────────────

PLAN_DEFINITIONS = {
    "free": {
        "name": "免费用户",
        "price_cents": 0,
        "visible": True,
        "daily_ai_limit": 5,
        "daily_upload_limit": 1,
        "daily_code_limit": 3,
        "requires_ads": True,
        "description": "基础功能可用，部分功能需观看广告解锁",
    },
    "python_basic": {
        "name": "Python 入门套餐",
        "price_cents": 1000,
        "visible": True,
        "daily_ai_limit": 50,
        "daily_upload_limit": 5,
        "daily_code_limit": 20,
        "allowed_languages": ["python"],
        "description": "适合经管类、文学类、法学类、教育类、外语类等只需要 Python / 数据分析入门的学生",
        "perks": "开放 Python 学习和基础编程功能",
    },
    "engineering_plus": {
        "name": "工科进阶套餐",
        "price_cents": 2000,
        "visible": True,
        "daily_ai_limit": 100,
        "daily_upload_limit": 15,
        "daily_code_limit": 60,
        "allowed_languages": ["python", "c", "cpp"],
        "description": "适合自动化、机械、电子、电气、土木、材料、化工、能源等强工科学生",
        "perks": "开放大部分功能",
    },
    "cs_pro": {
        "name": "计算机全功能套餐",
        "price_cents": 3000,
        "visible": True,
        "daily_ai_limit": 200,
        "daily_upload_limit": 50,
        "daily_code_limit": 150,
        "allowed_languages": ["python", "c", "cpp", "java", "javascript"],
        "description": "适合软件工程、计算机、人工智能、数据科学、网络安全等计算机相关专业",
        "perks": "开放所有主要学习功能",
    },
    "gift_pro": {
        "name": "礼品卡权益",
        "price_cents": 0,
        "visible": False,
        "daily_ai_limit": 500,
        "daily_upload_limit": 100,
        "daily_code_limit": 300,
        "description": "开放全部功能，享受高额额度",
        "perks": "通过兑换码激活的会员权益",
    },
    "developer": {
        "name": "开发者账号",
        "price_cents": 0,
        "visible": False,
        "daily_ai_limit": 999999,
        "daily_upload_limit": 999999,
        "daily_code_limit": 999999,
        "description": "开发者账号，已开放所有功能，无需开通会员",
    },
}

VALID_PLANS = set(PLAN_DEFINITIONS.keys())

# Direction-specific commercial catalog.  This is the only source of truth
# for the V1 mock checkout flow; legacy plan definitions above remain for the
# existing global entitlement/redeem API.
SERVICE_PLAN_CATALOG = {
    "exam_11408": {
        "free": {"name": "免费模式", "rank": 0, "price_cents": 0, "duration_days": None, "quota": {
            "ai_chat_daily_limit": 50, "ai_question_daily_limit": 5, "material_upload_limit_mb": 100,
            "learning_plan": False, "mistake_review": False, "learning_report": False,
        }},
        "monthly_sprint": {"name": "月度冲刺包", "rank": 1, "price_cents": 2900, "duration_days": 30, "quota": {
            "ai_chat_daily_limit": 300, "ai_question_daily_limit": 30, "material_upload_limit_mb": 500,
            "learning_plan": True, "mistake_review": True, "learning_report": True,
        }},
        "quarterly_boost": {"name": "季度强化包", "rank": 2, "price_cents": 7900, "duration_days": 90, "quota": {
            "ai_chat_daily_limit": 500, "ai_question_daily_limit": 50, "material_upload_limit_mb": 1024,
            "learning_plan": True, "mistake_review": True, "learning_report": True,
        }},
        "full_exam": {"name": "全程考包", "rank": 3, "price_cents": 14900, "duration_days": 365, "quota": {
            "ai_chat_daily_limit": 1000, "ai_question_daily_limit": 100, "material_upload_limit_mb": 2048,
            "learning_plan": True, "mistake_review": True, "learning_report": True,
        }},
    },
    "course_learning": {
        "free": {"name": "免费模式", "rank": 0, "price_cents": 0, "duration_days": None, "quota": {
            "ai_chat_daily_limit": 50, "ai_question_daily_limit": 5, "material_upload_limit_mb": 100,
            "learning_plan": False, "mistake_review": False, "learning_report": False,
        }},
        "monthly": {"name": "月度学习包", "rank": 1, "price_cents": 2900, "duration_days": 30, "quota": {
            "ai_chat_daily_limit": 300, "ai_question_daily_limit": 30, "material_upload_limit_mb": 500,
            "learning_plan": True, "mistake_review": True, "learning_report": True,
        }},
        "quarterly": {"name": "季度学习包", "rank": 2, "price_cents": 7900, "duration_days": 90, "quota": {
            "ai_chat_daily_limit": 500, "ai_question_daily_limit": 50, "material_upload_limit_mb": 1024,
            "learning_plan": True, "mistake_review": True, "learning_report": True,
        }},
        "full": {"name": "全程学习包", "rank": 3, "price_cents": 14900, "duration_days": 365, "quota": {
            "ai_chat_daily_limit": 1000, "ai_question_daily_limit": 100, "material_upload_limit_mb": 2048,
            "learning_plan": True, "mistake_review": True, "learning_report": True,
        }},
    },
    "programming": {
        "free": {"name": "免费模式", "rank": 0, "price_cents": 0, "duration_days": None, "quota": {
            "ai_chat_daily_limit": 50, "ai_question_daily_limit": 5, "material_upload_limit_mb": 0,
            "problem_records": False, "file_library": False,
        }},
        "monthly": {"name": "编程练习月卡", "rank": 1, "price_cents": 900, "duration_days": 30, "quota": {
            "ai_chat_daily_limit": 300, "ai_question_daily_limit": 30, "material_upload_limit_mb": 1024,
            "problem_records": True, "file_library": True,
        }},
        "quarterly": {"name": "编程进阶训练包", "rank": 2, "price_cents": 1900, "duration_days": 90, "quota": {
            "ai_chat_daily_limit": 300, "ai_question_daily_limit": 30, "material_upload_limit_mb": 1024,
            "problem_records": True, "file_library": True,
        }},
        "full": {"name": "实验与算法强化包", "rank": 3, "price_cents": 5900, "duration_days": 365, "quota": {
            "ai_chat_daily_limit": 999999, "ai_question_daily_limit": 100, "material_upload_limit_mb": 2048,
            "problem_records": True, "file_library": True,
        }},
    },
}

SERVICE_KEY_ALIASES = {
    "course": "course_learning",
    "course_learning": "course_learning",
    "exam": "exam_11408",
    "exam_408": "exam_11408",
    "exam_11408": "exam_11408",
    "programming": "programming",
}


def canonical_service_key(service_key: str | None) -> str:
    return SERVICE_KEY_ALIASES.get((service_key or "").strip().lower(), "")


def get_service_plan_catalog(service_key: str | None) -> dict:
    canonical = canonical_service_key(service_key)
    if canonical not in SERVICE_PLAN_CATALOG:
        raise ValueError(f"Unsupported service key: {service_key}")
    return SERVICE_PLAN_CATALOG[canonical]


def get_service_plan(service_key: str | None, plan_code: str | None) -> dict | None:
    return get_service_plan_catalog(service_key).get((plan_code or "free").strip().lower())


def service_plan_rank(service_key: str | None, plan_code: str | None) -> int:
    plan = get_service_plan(service_key, plan_code)
    return int(plan["rank"]) if plan else -1


def serialize_service_plan(service_key: str, plan_code: str, definition: dict) -> dict:
    return {
        "service_key": canonical_service_key(service_key),
        "plan_code": plan_code,
        "name": definition["name"],
        "rank": definition["rank"],
        "price_cents": definition["price_cents"],
        "price_yuan": definition["price_cents"] / 100,
        "duration_days": definition["duration_days"],
        "quota": dict(definition.get("quota") or {}),
    }

# ── Admin / Developer detection ──────────────────────────────

def _parse_env_usernames(var_name: str) -> set:
    raw = os.getenv(var_name, "")
    if not raw.strip():
        return set()
    return {u.strip().lower() for u in raw.split(",") if u.strip()}

ADMIN_USERNAMES = _parse_env_usernames("ADMIN_USERNAMES")
DEVELOPER_USERNAMES = _parse_env_usernames("DEVELOPER_USERNAMES")


def is_developer_account(username: str) -> bool:
    return username.lower() in DEVELOPER_USERNAMES


def is_admin_account(username: str) -> bool:
    return username.lower() in ADMIN_USERNAMES


# ── Effective Plan ───────────────────────────────────────────

def get_effective_plan(user: models.User, db: Optional[Session] = None) -> dict:
    """
    Returns the effective plan after considering:
    1. Developer users override to 'developer'
    2. Admin users via DB is_admin flag
    3. Plan expiry check
    """
    username = user.username

    if is_developer_account(username):
        plan_code = "developer"
    elif bool(user.is_admin):
        plan_code = "developer"
    else:
        plan_code = (user.plan or "free").strip().lower()
        if plan_code not in VALID_PLANS:
            plan_code = "free"

    # Expiry check for time-limited plans
    if plan_code in ("python_basic", "engineering_plus", "cs_pro", "gift_pro"):
        if user.plan_expire_at:
            expire = user.plan_expire_at
            if expire.tzinfo is None:
                expire = expire.replace(tzinfo=timezone.utc)
            if expire < datetime.now(timezone.utc):
                plan_code = "free"

    plan_def = PLAN_DEFINITIONS.get(plan_code, PLAN_DEFINITIONS["free"])
    return {
        "plan_code": plan_code,
        "plan_name": plan_def["name"],
        "is_developer": is_developer_account(username) or bool(user.is_admin),
        "role": "admin" if bool(user.is_admin) else "developer" if is_developer_account(username) else "user",
        "plan_source": user.plan_source or "",
        "plan_expires_at": user.plan_expire_at.isoformat() if user.plan_expire_at else None,
    }


def get_plan_limits_v2(plan_code: str) -> dict:
    defn = PLAN_DEFINITIONS.get(plan_code, PLAN_DEFINITIONS["free"])
    return {
        "daily_ai_limit": defn["daily_ai_limit"],
        "daily_upload_limit": defn["daily_upload_limit"],
        "daily_code_limit": defn["daily_code_limit"],
    }


def check_user_entitlement(user: models.User, action_type: str, db: Session) -> dict:
    """Check if a user has access to a particular action type. Non-blocking helper."""
    effective = get_effective_plan(user, db)
    limits = get_plan_limits_v2(effective["plan_code"])
    return {
        "allowed": True,
        "plan_code": effective["plan_code"],
        "plan_name": effective["plan_name"],
        "limits": limits,
    }


# ── Major Normalization ──────────────────────────────────────

# Synonyms map: user input -> canonical major name
MAJOR_SYNONYMS = {
    "软工": "软件工程",
    "计科": "计算机科学与技术",
    "计算机": "计算机科学与技术",
    "ai": "人工智能",
    "人工智能": "人工智能",
    "大数据": "数据科学与大数据技术",
    "数据科学": "数据科学与大数据技术",
    "软件开发": "软件工程",
    "网安": "网络安全",
    "信安": "信息安全",
    "物联网": "物联网工程",
    "数媒": "数字媒体技术",
    "智科": "智能科学与技术",
    "自动化": "自动化",
    "机械": "机械工程",
    "电信": "电子信息工程",
    "通信": "通信工程",
    "电气": "电气工程及其自动化",
    "土木": "土木工程",
    "材料": "材料科学与工程",
    "化工": "化学工程与工艺",
    "能源": "能源与动力工程",
    "车辆": "车辆工程",
    "测控": "测控技术与仪器",
    "机器人": "机器人工程",
    "智能制造": "智能制造工程",
    "工商管理": "工商管理",
    "会计": "会计学",
    "金融": "金融学",
    "经济": "经济学",
    "市场营销": "市场营销",
    "财务管理": "财务管理",
    "汉语言": "汉语言文学",
    "中文": "汉语言文学",
    "法学": "法学",
    "教育": "教育学",
    "英语": "英语",
    "新闻": "新闻传播学",
    "广告": "广告学",
    "新媒体": "网络与新媒体",
    "网新": "网络与新媒体",
}


def normalize_major(major: str) -> str:
    """Normalize a major string input to a canonical form."""
    if not major or not major.strip():
        return ""
    text = major.strip()

    # Remove common noise words
    for noise in ["专业", "学院", "方向", "系", "（", "）", "(", ")"]:
        text = text.replace(noise, "")

    # Lowercase for matching
    text_lower = text.lower().strip()
    text_clean = text.strip()

    # Direct synonym lookup (case-insensitive)
    check = text_lower
    if check in MAJOR_SYNONYMS:
        return MAJOR_SYNONYMS[check]

    # Try original case
    if text_clean in MAJOR_SYNONYMS:
        return MAJOR_SYNONYMS[text_clean]

    return text_clean


# ── Rule-Based Classification ────────────────────────────────

COMPUTER_MAJORS = {
    "软件工程", "计算机科学与技术", "人工智能", "数据科学与大数据技术",
    "网络安全", "信息安全", "物联网工程", "数字媒体技术", "智能科学与技术",
}

ENGINEERING_MAJORS = {
    "自动化", "机械工程", "机械设计制造及其自动化", "电子信息工程",
    "通信工程", "电气工程及其自动化", "土木工程", "材料科学与工程",
    "化学工程与工艺", "能源与动力工程", "车辆工程", "测控技术与仪器",
    "机器人工程", "智能制造工程",
}

LIBERAL_ARTS_MAJORS = {
    "工商管理", "会计学", "金融学", "经济学", "市场营销", "财务管理",
    "汉语言文学", "法学", "教育学", "英语", "新闻传播学", "广告学",
    "网络与新媒体",
}

# Keywords for fuzzy matching
COMPUTER_KEYWORDS = [
    "计算机", "软件", "数据", "人工智能", "智能科学", "网络安全",
    "信息安全", "物联网", "数字媒体", "大数据", "区块链",
]

ENGINEERING_KEYWORDS = [
    "机械", "自动化", "电气", "电子", "通信", "材料", "能源",
    "车辆", "控制", "制造", "建造", "土木", "测控", "机器人",
    "航空", "航天",
]

LIBERAL_ARTS_KEYWORDS = [
    "管理", "经济", "金融", "会计", "财务", "文学", "法学",
    "教育", "外语", "英语", "新闻", "传媒", "广告", "艺术", "设计",
]

COURSE_SUGGESTIONS = {
    "cs_pro": ["程序设计", "数据结构", "数据库", "操作系统", "计算机网络", "算法设计"],
    "engineering_plus": ["Python程序设计", "工程数学", "C语言编程", "数据结构基础", "建模与仿真"],
    "python_basic": ["Python数据分析", "办公自动化", "Python基础编程", "数据可视化"],
    "free": [],
    "gift_pro": [],
    "developer": [],
}


def _keyword_match(major: str) -> Optional[str]:
    """Try keyword-based fuzzy matching."""
    for kw in COMPUTER_KEYWORDS:
        if kw in major:
            return "cs_pro"
    for kw in ENGINEERING_KEYWORDS:
        if kw in major:
            return "engineering_plus"
    for kw in LIBERAL_ARTS_KEYWORDS:
        if kw in major:
            return "python_basic"
    return None


# ── Recommendation Engine ────────────────────────────────────

def _build_recommendation(plan_code: str, category: str, confidence: float,
                          reason: str, source: str, normalized_major: str) -> dict:
    courses = COURSE_SUGGESTIONS.get(plan_code, [])
    return {
        "recommended_plan": plan_code,
        "category": category,
        "confidence": confidence,
        "reason": reason,
        "suggested_courses": courses,
        "source": source,
        "normalized_major": normalized_major,
        "needs_manual_choice": confidence < 0.65,
    }


def recommend_plan_by_major(major: str, grade: str, db: Session,
                            ai_client=None) -> dict:
    """
    Multi-layer major classification → plan recommendation.

    Layers:
      1. Normalize the major name
      2. Exact rule match
      3. Keyword fuzzy match
      4. Cache lookup
      5. AI fallback classification
      6. Total fallback -> free
    """
    normalized = normalize_major(major)

    # ── Layer 1: Exact match ──
    if normalized in COMPUTER_MAJORS:
        return _build_recommendation("cs_pro", "computer", 0.98,
                                     f"你的专业「{normalized}」属于计算机相关专业，全面学习编程与算法非常重要",
                                     "rule", normalized)

    if normalized in ENGINEERING_MAJORS:
        return _build_recommendation("engineering_plus", "engineering", 0.95,
                                     f"你的专业「{normalized}」属于强工科专业，编程和建模能力是核心竞争力",
                                     "rule", normalized)

    if normalized in LIBERAL_ARTS_MAJORS:
        return _build_recommendation("python_basic", "liberal_arts", 0.92,
                                     f"你的专业「{normalized}」更侧重数据分析与办公自动化，Python 入门套餐最适合你",
                                     "rule", normalized)

    # ── Layer 2: Keyword fuzzy match ──
    kw_result = _keyword_match(normalized)
    if kw_result:
        cat_map = {"cs_pro": "computer", "engineering_plus": "engineering", "python_basic": "liberal_arts"}
        return _build_recommendation(kw_result, cat_map.get(kw_result, "unknown"), 0.75,
                                     f"你的专业与{PLAN_DEFINITIONS[kw_result]['name']}的匹配度较高",
                                     "keyword", normalized)

    # ── Layer 3: Cache lookup ──
    cache_entry = db.query(models.MajorClassificationCache).filter(
        models.MajorClassificationCache.normalized_major == normalized
    ).first()

    if cache_entry and cache_entry.review_status == "active":
        courses = []
        if cache_entry.suggested_courses_json:
            try:
                courses = json.loads(cache_entry.suggested_courses_json)
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            "recommended_plan": cache_entry.recommended_plan,
            "category": cache_entry.category,
            "confidence": cache_entry.confidence,
            "reason": cache_entry.reason or "",
            "suggested_courses": courses,
            "source": "cache",
            "normalized_major": normalized,
            "needs_manual_choice": cache_entry.confidence < 0.65,
        }

    # ── Layer 4: AI fallback ──
    if ai_client:
        try:
            ai_result = _ai_classify_major(normalized, grade, ai_client)
            if ai_result:
                _write_classification_cache(db, normalized, major, ai_result)
                return {
                    **ai_result,
                    "source": "ai",
                    "normalized_major": normalized,
                    "needs_manual_choice": ai_result.get("confidence", 0.5) < 0.65,
                }
        except Exception:
            logger.warning(f"AI classification failed for major: {normalized}", exc_info=True)

    # ── Layer 5: Fallback ──
    fallback = _build_recommendation("free", "unknown", 0.3,
                                     "暂时无法准确识别你的专业方向，可先使用免费版或手动选择学习方向",
                                     "fallback", normalized)
    fallback["needs_manual_choice"] = True
    return fallback


# ── AI Classification ────────────────────────────────────────

MAJOR_CLASSIFICATION_PROMPT = """你是一个高校专业分类助手。请根据中国高校常见培养方案，判断以下专业更偏向哪一类别。

用户专业：{major}
用户年级：{grade}

你只能从以下三个选项中选择一个：
- python_basic：该专业主要需要 Python 数据分析、办公自动化、基础编程能力（经管、文学、法学、教育、外语等）
- engineering_plus：该专业主要需要工科综合学习能力，包括编程、建模、仿真（机械、电气、土木、材料、化工、自动化等）
- cs_pro：该专业是计算机相关专业，需要全面学习编程、算法、系统设计（软件工程、计算机科学、人工智能、网络安全、数据科学等）

请严格返回以下 JSON 格式，不要返回其他内容：
{{
  "recommended_plan": "python_basic | engineering_plus | cs_pro",
  "category": "computer | engineering | liberal_arts",
  "confidence": 0.0 ~ 1.0,
  "reason": "推荐理由，50字以内",
  "suggested_courses": ["课程1", "课程2", "课程3"]
}}"""


def _ai_classify_major(normalized_major: str, grade: str, ai_client) -> Optional[dict]:
    """Use AI to classify an unknown major. Returns dict or None on failure."""
    prompt = MAJOR_CLASSIFICATION_PROMPT.format(
        major=normalized_major,
        grade=grade or "未知",
    )

    response = ai_client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=500,
    )

    content = response.choices[0].message.content.strip()

    # Try to extract JSON from the response
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        content = json_match.group(0)

    result = json.loads(content)

    plan = (result.get("recommended_plan") or "").strip().lower()
    if plan not in ("python_basic", "engineering_plus", "cs_pro"):
        return None

    courses = result.get("suggested_courses", [])
    if isinstance(courses, str):
        courses = [c.strip() for c in courses.split(",") if c.strip()]

    return {
        "recommended_plan": plan,
        "category": result.get("category", "unknown"),
        "confidence": min(max(float(result.get("confidence", 0.5)), 0.0), 1.0),
        "reason": str(result.get("reason", ""))[:200],
        "suggested_courses": courses[:6],
    }


# ── Classification Cache ─────────────────────────────────────

def _write_classification_cache(db: Session, normalized_major: str,
                                raw_example: str, result: dict):
    try:
        existing = db.query(models.MajorClassificationCache).filter(
            models.MajorClassificationCache.normalized_major == normalized_major
        ).first()
        if existing:
            existing.recommended_plan = result["recommended_plan"]
            existing.category = result.get("category", "unknown")
            existing.confidence = result.get("confidence", 0.5)
            existing.reason = result.get("reason", "")
            existing.suggested_courses_json = json.dumps(result.get("suggested_courses", []), ensure_ascii=False)
            existing.source = "ai"
            existing.raw_major_example = raw_example
            existing.updated_at = datetime.now(timezone.utc)
        else:
            entry = models.MajorClassificationCache(
                raw_major_example=raw_example,
                normalized_major=normalized_major,
                recommended_plan=result["recommended_plan"],
                category=result.get("category", "unknown"),
                confidence=result.get("confidence", 0.5),
                reason=result.get("reason", ""),
                suggested_courses_json=json.dumps(result.get("suggested_courses", []), ensure_ascii=False),
                source="ai",
            )
            db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning(f"Failed to write classification cache for {normalized_major}", exc_info=True)


# ── Redemption Codes ─────────────────────────────────────────

def hash_code(code: str) -> str:
    """Normalize and hash a redemption code."""
    normalized = code.strip().upper().replace(" ", "").replace("-", "")
    return hashlib.sha256(f"redemption:{normalized}".encode()).hexdigest()


def preload_redemption_codes(db: Session):
    """Seed test redemption codes from GIFT_REDEEM_CODES env var on startup."""
    raw = os.getenv("GIFT_REDEEM_CODES", "")
    if not raw.strip():
        return

    codes = [c.strip() for c in raw.split(",") if c.strip()]
    for code in codes:
        code_hash = hash_code(code)
        existing = db.query(models.RedemptionCode).filter(
            models.RedemptionCode.code_hash == code_hash
        ).first()
        if not existing:
            entry = models.RedemptionCode(
                code_hash=code_hash,
                plan_code="gift_pro",
                max_uses=1,
                status="active",
                created_by="env",
            )
            db.add(entry)
    db.commit()
    logger.info(f"Preloaded {len(codes)} redemption codes from env")


def _legacy_redeem_code(username: str, code_input: str, db: Session) -> dict:
    """Attempt to redeem a code. Returns result dict."""
    code_hash = hash_code(code_input)

    code_entry = db.query(models.RedemptionCode).filter(
        models.RedemptionCode.code_hash == code_hash
    ).first()

    if not code_entry:
        return {"success": False, "message": "兑换码不存在"}

    if code_entry.status == "used" or code_entry.used_count >= code_entry.max_uses:
        return {"success": False, "message": "兑换码已被使用"}

    if code_entry.status == "disabled":
        return {"success": False, "message": "兑换码已失效"}

    if code_entry.status == "expired":
        return {"success": False, "message": "兑换码已过期"}

    if code_entry.expires_at:
        expire = code_entry.expires_at
        if expire.tzinfo is None:
            expire = expire.replace(tzinfo=timezone.utc)
        if expire < datetime.now(timezone.utc):
            code_entry.status = "expired"
            db.commit()
            return {"success": False, "message": "兑换码已过期"}

    # Find the user
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return {"success": False, "message": "用户不存在"}

    # Apply the plan
    plan_code = code_entry.plan_code
    user.plan = plan_code
    user.plan_source = "redeem"
    # Gift cards: 365 days validity
    from datetime import timedelta
    user.plan_expire_at = datetime.now(timezone.utc) + timedelta(days=365)

    # Mark code as used
    code_entry.used_count += 1
    code_entry.used_by_username = username
    code_entry.used_by_user_id = user.id
    code_entry.used_at = datetime.now(timezone.utc)
    if code_entry.used_count >= code_entry.max_uses:
        code_entry.status = "used"

    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "plan_code": plan_code,
        "message": "兑换成功，礼品卡权益已激活",
    }
