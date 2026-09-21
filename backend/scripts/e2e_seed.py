"""P6.1 E2E seed — the SMALLEST dataset the product surface needs, and nothing more.

WHAT IT CREATES (one of each, as §E requires)
---------------------------------------------
    one learner                     with a known password (the harness logs in for real)
    one membership                  a real ``subscriptions`` row — the ONLY tier authority
    one course                      a ``course_learning_preferences`` entry the product reads
    one course question + a WRONG attempt
                                    which the product itself turns into a wrong-answer state,
                                    a review item and the practice history of that course
    one CS408 profile               so the exam space is reachable (facts come from the flow)
    one programming exercise + project + a ``needs_work`` progress fact
    one plan task                   the course's own task store

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not touch entitlement CODE: the learner's access comes from a real subscription row
written through the same model the product reads, so ``check_capability_permission`` decides
everything exactly as it does for a real learner. It does not invent learning facts the
product would have recorded itself, and every row it writes is stamped with the process's
``DATA_ORIGIN`` (``ACCEPTANCE`` under the harness) by the emitters — never ``LEARNER``.

Seeding is idempotent: running it twice on the same database finds the learner and stops.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DEFAULT_USERNAME = "e2e_learner"
DEFAULT_PASSWORD = "e2e-learner-pass-1"
DEFAULT_COURSE = "数据结构"
DEFAULT_MODULE = "operating_system"
DEFAULT_LANGUAGE = "Python"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def seed(db, *, username: str = DEFAULT_USERNAME, password: str = DEFAULT_PASSWORD,
         tier: str = "standard", course_id: str = DEFAULT_COURSE,
         exam_module_key: str = DEFAULT_MODULE, language: str = DEFAULT_LANGUAGE) -> dict:
    """Create (or find) the E2E learner and the minimal product state. Returns an identity."""
    from auth import hash_password
    from models import (AIGeneratedQuestion, CourseLearningPreference, ExamPrepProfile,
                        LearningTask, ProgrammingExercise, ProgrammingExerciseProgress,
                        User)
    from usage.models import Subscription

    existing = db.query(User).filter(User.username == username).first()
    if existing is not None:
        return {"username": username, "password": password, "created": False,
                "user_id": existing.id}

    now = _utcnow()
    user = User(username=username, hashed_password=hash_password(password),
                email=f"{username}@e2e.test", email_verified=True, is_active=1,
                is_admin=0, created_at=now)
    db.add(user)
    db.commit()
    db.refresh(user)

    # Membership: the REAL product state (never a bypass of the entitlement code).
    db.add(Subscription(user_id=user.id, tier=tier, status="active", start_at=now,
                        end_at=now + timedelta(days=30), source="acceptance_seed",
                        created_at=now, updated_at=now))

    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, is_started=True))

    question = AIGeneratedQuestion(
        username=username, subject_key=course_id, subject_name=course_id,
        knowledge_point_id="e2e_kp_list", knowledge_point_name="线性表",
        question_type="选择题",
        stem="顺序存储的线性表按下标访问的时间复杂度是？",
        options_json=json.dumps({"A": "O(1)", "B": "O(n)", "C": "O(log n)", "D": "O(n log n)"},
                                ensure_ascii=False),
        standard_answer="A", analysis="顺序存储按下标直接计算地址。",
        difficulty="基础", quality_status="unchecked", generation_mode="ai")
    db.add(question)

    exercise = ProgrammingExercise(
        slug="e2e-two-sum", title="两数之和", language=language, difficulty="easy",
        description="返回两个数的和。", tags_json="[]", starter_files_json="[]",
        reference_files_json="[]", public_tests_json="[]", hidden_tests_json="[]",
        official_test_files_json="[]", source_repo="e2e-seed", source_path="solution.py",
        source_commit="0" * 40, license="MIT", license_text="MIT", attribution="e2e",
        audit_report_json="{}", is_active=True, quality_status="approved")
    db.add(exercise)
    db.commit()
    db.refresh(question)
    db.refresh(exercise)

    # A needs_work programming fact — what the programming space reads to show "继续练习".
    db.add(ProgrammingExerciseProgress(
        user_id=user.id, username=username, exercise_id=exercise.id,
        personal_status="needs_work", last_submit_passed=False,
        last_submit_at=now - timedelta(days=1), last_public_passed_count=1,
        last_public_total_count=3))

    # The exam space's real user state (STEP7H4): a profile is what makes CS408 reachable.
    db.add(ExamPrepProfile(
        user_id=user.id, exam_type="postgraduate", selected_track="cs_408",
        selected_subjects_json=json.dumps(["cs_408"]), created_at=now, updated_at=now))

    db.add(LearningTask(username=username, course_id=course_id, title="复习线性表",
                        description="E2E seed task", task_type="review", status="pending",
                        source="e2e_seed", priority="normal", order_index=0,
                        created_at=now))

    db.commit()
    return {"username": username, "password": password, "created": True,
            "user_id": user.id, "course_id": course_id, "exam_module_id": exam_module_key,
            "question_id": question.id, "exercise_id": exercise.id, "tier": tier}


def record_course_wrong_answer(db, *, username: str = DEFAULT_USERNAME,
                               course_id: str = DEFAULT_COURSE) -> dict:
    """ONE wrong attempt through the PRODUCT's own practice core, so the wrong-answer state,
    the review item and the course history all exist because the product made them."""
    from core.learning_context import ServiceNamespace
    from learning.practice import service as practice_service
    from learning.practice.refs import QuestionRef, QuestionSourceType
    from learning.spaces.course_learning.context import build_course_context
    from models import AIGeneratedQuestion, User

    user = db.query(User).filter(User.username == username).one()
    question = (db.query(AIGeneratedQuestion)
                .filter(AIGeneratedQuestion.username == username).first())
    if question is None:
        raise RuntimeError("seed the learner before recording an attempt")

    context = build_course_context(user, course_id=course_id)
    session, _ = practice_service.ensure_legacy_session(
        db, user, "course_learning", source_type="e2e_acceptance",
        source_session_key=f"e2e:{course_id}", mode="e2e", context=context, started_at=None)
    ref = QuestionRef(source_type=QuestionSourceType.AI_GENERATED,
                      source_id=str(question.id),
                      service_namespace=ServiceNamespace.COURSE_LEARNING,
                      context={"course_id": course_id})
    attempt = practice_service.record_attempt(
        db, user, session, ref, answer="B", correct=False, submitted_at=_utcnow(),
        context=context,
        source=practice_service.SourceIdentity("e2e_acceptance_attempt",
                                               f"q{question.id}", "0")).attempt
    return {"attempt_id": attempt.id, "question_id": question.id}


def main() -> int:
    """CLI: seed an already-migrated database named by DATABASE_URL."""
    import os
    if not os.getenv("DATABASE_URL"):
        print("REFUSED: DATABASE_URL must be set", file=sys.stderr)
        return 2
    from database import SessionLocal, engine
    from database_schema import ensure_database_schema
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        identity = seed(db)
        identity |= record_course_wrong_answer(db)
        print(json.dumps(identity, ensure_ascii=False))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
