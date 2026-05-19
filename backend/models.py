from sqlalchemy import Column, Integer, String, DateTime
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