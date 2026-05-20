from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # 登录账号
    username = Column(String(50), unique=True, index=True, nullable=False)

    # 加密后的密码，不存明文密码
    hashed_password = Column(String(255), nullable=False)

    # 用户学习信息
    grade = Column(String(50), nullable=False)          # 年级，例如：大一、大二
    major = Column(String(100), nullable=False)         # 专业，例如：软件工程

    created_at = Column(DateTime, default=datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 这条消息属于哪个历史对话
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), index=True, nullable=False)

    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    # 左侧历史列表显示的标题，一般用用户第一次提问
    title = Column(String(255), nullable=False)

    # 保存当时选择的课程，例如 Python、Java、数据库
    course = Column(String(100), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)