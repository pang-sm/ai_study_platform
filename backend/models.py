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
    onboarding_detail = Column(Text, nullable=True)
    plan = Column(String(20), nullable=True, default="free")
    plan_source = Column(String(30), nullable=True, default="")
    plan_expire_at = Column(DateTime, nullable=True)
    is_admin = Column(Integer, nullable=True, default=0)
    admin_role = Column(String(30), nullable=True, default="none")
    admin_real_name = Column("admin_real_name", Text, nullable=True)
    school = Column(String(100), nullable=True, default="")
    learning_direction = Column(String(100), nullable=True, default="")
    default_course_id = Column(String(100), nullable=True, default="")
    learning_stage = Column(String(50), nullable=True, default="")
    daily_study_minutes = Column(Integer, nullable=True, default=0)
    ai_answer_style = Column(String(50), nullable=True, default="")
    answer_detail_level = Column(String(50), nullable=True, default="")
    material_reference_preference = Column(String(50), nullable=True, default="")
    focus_courses = Column(Text, nullable=True, default="")
    email = Column(String(255), nullable=True, default=None)
    email_verified = Column(Boolean, nullable=False, default=False)
    phone = Column(String(30), nullable=True, default=None)
    phone_verified = Column(Boolean, nullable=False, default=False)
    is_active = Column(Integer, nullable=True, default=1)
    is_banned = Column(Integer, nullable=True, default=0)
    banned_reason = Column(Text, nullable=True)
    banned_at = Column(Text, nullable=True)
    is_deleted = Column(Integer, nullable=True, default=0)
    deleted_at = Column(Text, nullable=True)
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
    parent_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True)
    root_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True)
    branch_id = Column(String(64), nullable=True)
    version_index = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utc_now)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    course = Column(String(100), nullable=True)
    subject = Column(String(100), nullable=True)
    exam_subject = Column(String(64), nullable=True)
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
    source_type = Column(String(50), nullable=False, default="user_upload")
    visibility = Column(String(50), nullable=False, default="private")
    copyright_status = Column(String(50), nullable=False, default="user_responsibility")
    allow_download = Column(Boolean, nullable=False, default=True)
    allow_public_rag = Column(Boolean, nullable=False, default=False)
    allow_private_rag = Column(Boolean, nullable=False, default=True)
    allow_generate_knowledge = Column(Boolean, nullable=False, default=True)
    is_default_reference = Column(Boolean, nullable=False, default=False)
    extract_method = Column(String(20), nullable=True)
    parse_status = Column(String(20), nullable=True)
    parse_error = Column(Text, nullable=True)
    qwen_used = Column(Boolean, nullable=False, default=False)
    parsed_at = Column(DateTime, nullable=True)
    total_pages = Column(Integer, nullable=False, default=0)
    parsed_pages = Column(Integer, nullable=False, default=0)
    ocr_page_limit = Column(Integer, nullable=False, default=0)
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


class CourseLearningPreference(Base):
    __tablename__ = "course_learning_preferences"
    __table_args__ = (
        Index("idx_course_learning_preferences_user_course", "username", "course_id", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), index=True, nullable=False)
    mastery_level = Column(String(50), nullable=False, default="")
    learning_goal = Column(String(50), nullable=False, default="")
    is_started = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime, nullable=True)
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
    knowledge_point_text = Column(String, nullable=True)
    related_question_id = Column(Integer, nullable=True)
    task_metadata = Column("metadata", Text, nullable=True)
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
    knowledge_point_code = Column(String(100), index=True, nullable=True)
    knowledge_point_title = Column(String(255), nullable=True)
    mastery_score = Column(Integer, nullable=True)
    status = Column(String(30), nullable=True)
    practice_count = Column(Integer, nullable=True)
    task_count = Column(Integer, nullable=True)
    last_studied_at = Column(DateTime, nullable=True)
    learned_at = Column(DateTime, nullable=True)
    review_due_at = Column(DateTime, nullable=True)
    review_interval_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class UserKnowledgeReviewSetting(Base):
    __tablename__ = "user_knowledge_review_settings"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    course_id = Column(String(100), index=True, nullable=False)
    review_interval_days = Column(Integer, nullable=False, default=7)
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
    target_id = Column(String(100), nullable=True)
    target_username = Column(String(50), nullable=True)
    result = Column(String(20), nullable=True, default="success")
    detail = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    ip = Column(String(100), nullable=True)
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


class SystemAnnouncement(Base):
    __tablename__ = "system_announcements"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    type = Column(String(20), nullable=True, default="info")
    is_active = Column(Integer, nullable=True, default=1)
    target = Column(String(20), nullable=True, default="all")
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    withdrawn_at = Column(DateTime, nullable=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_by = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class UserLearningTrack(Base):
    __tablename__ = "user_learning_tracks"
    __table_args__ = (
        Index("idx_user_learning_tracks_user_track", "user_id", "track_type", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    track_type = Column(String(30), nullable=False)
    plan = Column(String(30), nullable=True, default="free")
    package_type = Column(String(30), nullable=True)
    permissions_json = Column(Text, nullable=True)
    quota_json = Column(Text, nullable=True)
    onboarding_detail_json = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=True, default="active")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class VerificationCode(Base):
    __tablename__ = "verification_codes"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    target = Column(String(255), nullable=False)
    purpose = Column(String(30), nullable=False)
    code_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utc_now)


class PastPaperWrongQuestion(Base):
    __tablename__ = "past_paper_wrong_questions"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    subject_key = Column(String(50), index=True, nullable=False)
    source = Column(String(50), index=True, nullable=False, default="past_paper")
    year = Column(Integer, nullable=False)
    attempt_id = Column(Integer, nullable=True, default=0)
    question_id = Column(String(100), nullable=False)
    question_number = Column(Integer, nullable=False, default=0)
    question_type = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)
    options = Column(Text, nullable=True)
    standard_answer = Column(Text, nullable=True)
    user_answer = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    wrong_reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active")
    mastered = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class ExamFavoriteQuestion(Base):
    __tablename__ = "exam_favorite_questions"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    subject_key = Column(String(50), index=True, nullable=False)
    subject_name = Column(String(50), nullable=True)
    source = Column(String(50), index=True, nullable=False, default="past_paper")
    source_question_id = Column(String(100), nullable=False)
    year = Column(Integer, nullable=True)
    number = Column(Integer, nullable=True)
    question_type = Column(String(30), nullable=True)
    stem = Column(Text, nullable=True)
    options_json = Column(Text, nullable=True)
    standard_answer = Column(Text, nullable=True)
    knowledge_point_id = Column(String(100), nullable=True)
    knowledge_point_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now)


class AIGeneratedQuestion(Base):
    __tablename__ = "ai_generated_questions"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    subject_key = Column(String(50), index=True, nullable=False)
    subject_name = Column(String(50), nullable=True)
    knowledge_point_id = Column(String(100), nullable=True)
    knowledge_point_name = Column(String(255), nullable=True)
    knowledge_point_path = Column(Text, nullable=True)
    question_type = Column(String(30), nullable=False)
    stem = Column(Text, nullable=False)
    options_json = Column(Text, nullable=True)
    standard_answer = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)
    difficulty = Column(String(30), nullable=True)
    requirement = Column(Text, nullable=True)
    generation_prompt = Column(Text, nullable=True)
    raw_ai_response = Column(Text, nullable=True)
    generation_mode = Column(String(30), nullable=True, default="deepseek")
    quality_status = Column(String(20), nullable=True, default="unchecked")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class AIQuestionAttempt(Base):
    __tablename__ = "ai_question_attempts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    mode = Column(String(20), nullable=False, default="11408")
    subject_key = Column(String(50), nullable=False)
    subject_name = Column(String(50), nullable=False)
    knowledge_point_id = Column(String(100), nullable=True)
    knowledge_point_name = Column(String(255), nullable=True)
    knowledge_point_path = Column(Text, nullable=True)
    question_ids_json = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="in_progress")
    total_questions = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=True)
    accuracy = Column(Float, nullable=True)
    answers_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    started_at = Column(DateTime, default=utc_now)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


# ── v2 Unified Models ──

class ExamQuestionBank(Base):
    __tablename__ = "exam_question_bank"
    id = Column(Integer, primary_key=True, index=True)
    subject_key = Column(String(50), index=True, nullable=False)
    subject_name = Column(String(50), nullable=True)
    source_type = Column(String(30), index=True, nullable=False, default="chapter")
    visibility = Column(String(20), nullable=False, default="public")
    owner_username = Column(String(50), nullable=True)
    knowledge_point_id = Column(String(100), nullable=True)
    knowledge_point_name = Column(String(255), nullable=True)
    knowledge_point_path = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    question_number = Column(Integer, nullable=True)
    question_type = Column(String(30), nullable=False, default="choice")
    stem = Column(Text, nullable=False)
    options_json = Column(Text, nullable=True)
    standard_answer = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)
    difficulty = Column(String(30), nullable=True)
    source_ref = Column(Text, nullable=True)
    generation_mode = Column(String(30), nullable=True)
    quality_status = Column(String(20), nullable=True, default="unchecked")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class ExamPracticeAttempt(Base):
    __tablename__ = "exam_practice_attempts"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    subject_key = Column(String(50), nullable=False)
    practice_type = Column(String(30), nullable=False, default="chapter")
    source_type = Column(String(30), nullable=True)
    status = Column(String(20), nullable=False, default="in_progress")
    title = Column(String(255), nullable=True)
    knowledge_point_id = Column(String(100), nullable=True)
    knowledge_point_name = Column(String(255), nullable=True)
    knowledge_point_path = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    question_ids_json = Column(Text, nullable=True)
    answers_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    total_questions = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=True)
    wrong_count = Column(Integer, nullable=True)
    accuracy = Column(Float, nullable=True)
    started_at = Column(DateTime, default=utc_now)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class ExamWrongQuestion(Base):
    __tablename__ = "exam_wrong_questions"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    subject_key = Column(String(50), index=True, nullable=False)
    question_bank_id = Column(Integer, nullable=True)
    practice_attempt_id = Column(Integer, nullable=True)
    source_type = Column(String(30), nullable=True)
    practice_type = Column(String(30), nullable=True)
    knowledge_point_id = Column(String(100), nullable=True)
    knowledge_point_name = Column(String(255), nullable=True)
    knowledge_point_path = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    question_number = Column(Integer, nullable=True)
    question_type = Column(String(30), nullable=True)
    stem_snapshot = Column(Text, nullable=True)
    options_snapshot_json = Column(Text, nullable=True)
    standard_answer_snapshot = Column(Text, nullable=True)
    analysis_snapshot = Column(Text, nullable=True)
    user_answer = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    wrong_reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active")
    mastered = Column(Boolean, nullable=False, default=False)
    review_count = Column(Integer, nullable=False, default=0)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class ExamFavoriteQuestionV2(Base):
    __tablename__ = "exam_favorite_questions_v2"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    subject_key = Column(String(50), index=True, nullable=False)
    question_bank_id = Column(Integer, nullable=True)
    source_type = Column(String(30), nullable=True)
    knowledge_point_id = Column(String(100), nullable=True)
    knowledge_point_name = Column(String(255), nullable=True)
    knowledge_point_path = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    question_number = Column(Integer, nullable=True)
    question_type = Column(String(30), nullable=True)
    stem_snapshot = Column(Text, nullable=True)
    options_snapshot_json = Column(Text, nullable=True)
    standard_answer_snapshot = Column(Text, nullable=True)
    analysis_snapshot = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class PastPaperAttempt(Base):
    __tablename__ = "past_paper_attempts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    mode = Column(String(20), nullable=False, default="11408")
    subject_key = Column(String(50), nullable=False)
    subject_name = Column(String(50), nullable=False)
    year = Column(Integer, nullable=False)
    attempt_no = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="in_progress")
    total_questions = Column(Integer, nullable=False, default=0)
    choice_correct = Column(Integer, nullable=True)
    big_avg_score = Column(Float, nullable=True)
    total_score = Column(Integer, nullable=True)
    max_score = Column(Integer, nullable=True)
    wrong_count = Column(Integer, nullable=True)
    answers_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    started_at = Column(DateTime, default=utc_now)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
