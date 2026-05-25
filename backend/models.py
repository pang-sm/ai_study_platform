from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

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
