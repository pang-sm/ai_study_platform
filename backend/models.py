from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nickname = Column(String(30), nullable=True)
    avatar = Column(String(50), nullable=True)
    grade = Column(String(50), nullable=False)
    major = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    course = Column(String(100), nullable=True)
    subject = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StudyMaterial(Base):
    __tablename__ = "study_materials"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True, nullable=False)
    subject = Column(String(100), index=True, nullable=False)
    file_type = Column(String(20), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    source_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
