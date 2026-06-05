from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text

from database import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nickname = Column(String(30), nullable=True)
    avatar = Column(String(255), nullable=True)
    grade = Column(String(50), nullable=False, default="")
    major = Column(String(100), nullable=False, default="")
    onboarding_completed = Column(Boolean, nullable=False, default=False)
    learning_goals = Column(Text, nullable=True)
    plan = Column(String(20), nullable=True, default="free")
    plan_source = Column(String(30), nullable=True, default="")
    plan_expire_at = Column(DateTime, nullable=True)
    is_admin = Column(Integer, nullable=True, default=0)
    is_active = Column(Integer, nullable=True, default=1)
    created_at = Column(DateTime, default=utc_now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), index=True, nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    attachment_type = Column(String(20), nullable=True)
    attachment_filename = Column(String(255), nullable=True)
    attachment_path = Column(String(500), nullable=True)
    extracted_text = Column(Text, nullable=True)
    material_id = Column(Integer, ForeignKey("study_materials.id"), nullable=True)
    reference_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    course = Column(String(100), nullable=True)
    subject = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now)


class StudyMaterial(Base):
    __tablename__ = "study_materials"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    subject = Column(String(100), index=True, nullable=False)
    file_type = Column(String(20), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=False, default=0)
    file_hash = Column(String(64), nullable=True)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    source_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True)
    extract_method = Column(String(20), nullable=True)
    parse_status = Column(String(20), nullable=True)
    parse_error = Column(Text, nullable=True)
    qwen_used = Column(Boolean, nullable=False, default=False)
    parsed_at = Column(DateTime, nullable=True)
    total_pages = Column(Integer, nullable=False, default=0)
    parsed_pages = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    ocr_required = Column(Integer, nullable=False, default=0)
    parse_progress = Column(Float, nullable=False, default=0)
    parse_started_at = Column(Text, nullable=True)
    parse_completed_at = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    deleted_at = Column(DateTime, nullable=True)


class MaterialChunk(Base):
    __tablename__ = "material_chunks"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("study_materials.id"), index=True, nullable=False)
    username = Column(String(50), index=True, nullable=False)
    subject = Column(String(100), index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_summary = Column(Text, nullable=False)
    keywords = Column(Text, nullable=True)
    source_filename = Column(String(255), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utc_now)


class LearningRecord(Base):
    __tablename__ = "learning_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    subject = Column(String(100), index=True, nullable=False)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), index=True, nullable=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), index=True, nullable=True)
    record_type = Column(String(30), index=True, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    references_json = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)
    review_status = Column(String(20), index=True, nullable=False, default="pending")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    reviewed_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)


class CourseProgress(Base):
    __tablename__ = "course_progress"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course = Column(String(100), index=True, nullable=False)
    knowledge_point = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="未开始")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class CodeSession(Base):
    __tablename__ = "code_sessions"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), index=True, nullable=False)
    title = Column(String(255), nullable=False, default="未命名练习")
    language = Column(String(20), nullable=False, default="Python")
    code = Column(Text, nullable=False, default="")
    challenge_id = Column(Integer, nullable=True)
    session_type = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class CodeChallenge(Base):
    __tablename__ = "code_challenges"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), nullable=True)
    language = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    difficulty = Column(String(20), nullable=False)
    knowledge_point = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    requirements = Column(Text, nullable=True)
    input_format = Column(Text, nullable=True)
    output_format = Column(Text, nullable=True)
    examples = Column(Text, nullable=True)
    starter_code = Column(Text, nullable=True)
    reference_solution = Column(Text, nullable=True)
    source = Column(String(30), nullable=True)
    target_weak_point = Column(String(255), nullable=True)
    test_cases = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class CodeAIMessage(Base):
    __tablename__ = "code_ai_messages"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    session_id = Column(Integer, index=True, nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String(20), nullable=True)
    code_snapshot = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class CodeAISavedChat(Base):
    __tablename__ = "code_ai_saved_chats"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    challenge_id = Column(Integer, index=True, nullable=False)
    session_id = Column(Integer, nullable=True)
    language = Column(String(20), nullable=True)
    user_message = Column(Text, nullable=False)
    assistant_message = Column(Text, nullable=False)
    code_snapshot = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class CodeChallengeAttempt(Base):
    __tablename__ = "code_challenge_attempts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    session_id = Column(Integer, index=True, nullable=False)
    challenge_id = Column(Integer, index=True, nullable=False)
    language = Column(String(20), nullable=True)
    code = Column(Text, nullable=False)
    status = Column(String(30), nullable=True)
    ai_feedback = Column(Text, nullable=True)
    mastered = Column(Integer, nullable=True, default=0)
    mastered_at = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class LearningTask(Base):
    __tablename__ = "learning_tasks"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False)
    source = Column(String(50), nullable=True)
    priority = Column(String(20), nullable=True)
    order_index = Column(Integer, nullable=True)
    due_date = Column(DateTime, nullable=True)
    related_session_id = Column(Integer, nullable=True)
    related_challenge_id = Column(Integer, nullable=True)
    related_material_id = Column(Integer, nullable=True)
    knowledge_point_id = Column(Integer, nullable=True)
    related_question_id = Column(Integer, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (
        Index("idx_knowledge_points_user_course_node_key", "username", "course_id", "node_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), index=True, nullable=False)
    parent_id = Column(Integer, nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=True)
    level = Column(Integer, nullable=True)
    node_key = Column(String(500), nullable=True, index=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class UserKnowledgeProgress(Base):
    __tablename__ = "user_knowledge_progress"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), index=True, nullable=False)
    knowledge_point_id = Column(Integer, index=True, nullable=False)
    mastery_score = Column(Integer, nullable=True)
    status = Column(String(30), nullable=True)
    practice_count = Column(Integer, nullable=True)
    task_count = Column(Integer, nullable=True)
    last_studied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    paper_id = Column(Integer, nullable=True, index=True)
    question_order = Column(Integer, nullable=True)
    course_id = Column(String(100), index=True, nullable=True)
    knowledge_point_id = Column(Integer, nullable=True)
    type = Column(String(30), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    options = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    difficulty = Column(String(20), nullable=True)
    source = Column(String(50), nullable=True)
    source_style = Column(String(30), nullable=True)
    imported_from = Column(String(50), nullable=True)
    original_file_name = Column(String(255), nullable=True)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class PracticePaper(Base):
    __tablename__ = "practice_papers"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), index=True, nullable=True)
    title = Column(String(255), nullable=False)
    source_file_name = Column(String(255), nullable=True)
    source_type = Column(String(50), nullable=True)
    status = Column(String(30), nullable=True)
    question_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class KnowledgeProgressEvent(Base):
    __tablename__ = "knowledge_progress_events"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), index=True, nullable=False)
    knowledge_point_id = Column(Integer, index=True, nullable=False)
    event_type = Column(String(50), nullable=False)
    delta = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=True)
    source_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    question_id = Column(Integer, index=True, nullable=False)
    course_id = Column(String(100), nullable=True)
    knowledge_point_id = Column(Integer, nullable=True)
    user_answer = Column(Text, nullable=True)
    ai_feedback = Column(Text, nullable=True)
    self_result = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=utc_now)


class MaterialKnowledgeLink(Base):
    __tablename__ = "material_knowledge_links"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), index=True, nullable=False)
    material_id = Column(Integer, index=True, nullable=False)
    knowledge_point_id = Column(Integer, index=True, nullable=False)
    source = Column(String(50), nullable=True, default="manual")
    confidence = Column(Integer, nullable=True, default=100)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class UserLearningPath(Base):
    __tablename__ = "user_learning_paths"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    subject = Column(String(100), index=True, nullable=False)
    path_type = Column(String(30), index=True, nullable=False, default="material")
    title = Column(String(255), nullable=False)
    source_material_ids = Column(Text, nullable=True)
    modules_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class AiUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    feature = Column(String(50), index=True, nullable=False)
    model = Column(String(100), nullable=True)
    estimated_tokens = Column(Integer, nullable=True, default=0)
    estimated_cost = Column(Float, nullable=True, default=0.0)
    status = Column(String(20), nullable=True, default="success")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_username = Column(String(50), index=True, nullable=False)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=True)
    target_username = Column(String(50), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class LearningReport(Base):
    __tablename__ = "learning_reports"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), nullable=True)
    course_name = Column(String(100), nullable=True)
    report_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    metrics_json = Column(Text, nullable=True)
    suggestions_json = Column(Text, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class LearningReportShare(Base):
    __tablename__ = "learning_report_shares"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    report_id = Column(Integer, index=True, nullable=False)
    share_token = Column(String(80), unique=True, nullable=False)
    title = Column(String(200), nullable=True)
    is_active = Column(Integer, nullable=True, default=1)
    view_count = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, default=utc_now)
    revoked_at = Column(DateTime, nullable=True)
    last_viewed_at = Column(DateTime, nullable=True)


class MajorClassificationCache(Base):
    __tablename__ = "major_classification_cache"

    id = Column(Integer, primary_key=True, index=True)
    raw_major_example = Column(String(200), nullable=False)
    normalized_major = Column(String(200), unique=True, nullable=False, index=True)
    recommended_plan = Column(String(50), nullable=False)
    category = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False, default=0.5)
    reason = Column(Text, nullable=True)
    suggested_courses_json = Column(Text, nullable=True)
    source = Column(String(30), nullable=False, default="rule")
    review_status = Column(String(20), nullable=True, default="active")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class RedemptionCode(Base):
    __tablename__ = "redemption_codes"

    id = Column(Integer, primary_key=True, index=True)
    code_hash = Column(String(64), unique=True, index=True, nullable=False)
    plan_code = Column(String(50), nullable=False)
    max_uses = Column(Integer, nullable=False, default=1)
    used_count = Column(Integer, nullable=False, default=0)
    used_by_user_id = Column(Integer, nullable=True)
    used_by_username = Column(String(50), nullable=True)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(String(50), nullable=True)


class PracticeImportJob(Base):
    """试卷识别异步任务"""
    __tablename__ = "practice_import_jobs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), nullable=True, default="")
    module_id = Column(String(100), nullable=True)
    knowledge_point_id = Column(Integer, nullable=True)
    filename = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True, default=0)
    status = Column(String(30), nullable=False, default="pending")
    progress_message = Column(String(500), nullable=True)
    parse_method = Column(String(50), nullable=True)
    total_pages = Column(Integer, nullable=True, default=0)
    parsed_pages = Column(Integer, nullable=True, default=0)
    page_limit_hit = Column(Boolean, nullable=True, default=False)
    text_length = Column(Integer, nullable=True, default=0)
    qwen_pages = Column(Integer, nullable=True, default=0)
    deepseek_input_length = Column(Integer, nullable=True, default=0)
    question_count = Column(Integer, nullable=True, default=0)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
