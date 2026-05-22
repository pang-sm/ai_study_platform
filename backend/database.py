from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

PROFILE_COLUMNS = {
    "nickname": "VARCHAR(30)",
    "avatar": "VARCHAR(50)",
}

CHAT_SESSION_COLUMNS = {
    "subject": "VARCHAR(100)",
}

CHAT_MESSAGE_COLUMNS = {
    "attachment_type": "VARCHAR(20)",
    "attachment_filename": "VARCHAR(255)",
    "attachment_path": "VARCHAR(500)",
    "extracted_text": "TEXT",
    "material_id": "INTEGER",
}

STUDY_MATERIAL_COLUMNS = {
    "source_message_id": "INTEGER",
    "is_deleted": "BOOLEAN NOT NULL DEFAULT 0",
    "deleted_at": "DATETIME",
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_existing_columns(conn, table_name: str):
    return {
        row[1]
        for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    }


def ensure_columns(conn, table_name: str, columns: dict[str, str]):
    existing_columns = get_existing_columns(conn, table_name)
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            conn.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            )


def init_user_profile_schema():
    with engine.begin() as conn:
        ensure_columns(conn, "users", PROFILE_COLUMNS)
        ensure_columns(conn, "chat_sessions", CHAT_SESSION_COLUMNS)
        ensure_columns(conn, "chat_messages", CHAT_MESSAGE_COLUMNS)
        ensure_columns(conn, "study_materials", STUDY_MATERIAL_COLUMNS)

        chat_session_columns = get_existing_columns(conn, "chat_sessions")
        if "subject" in chat_session_columns and "course" in chat_session_columns:
            conn.execute(
                text(
                    """
                    UPDATE chat_sessions
                    SET subject = COALESCE(NULLIF(subject, ''), course)
                    WHERE course IS NOT NULL AND TRIM(course) != ''
                    """
                )
            )

        study_material_columns = get_existing_columns(conn, "study_materials")
        if "is_deleted" in study_material_columns:
            conn.execute(
                text(
                    """
                    UPDATE study_materials
                    SET is_deleted = 0
                    WHERE is_deleted IS NULL
                    """
                )
            )


def clear_user_profile_fields(db):
    import models

    db.query(models.User).update(
        {
            models.User.grade: "",
            models.User.major: "",
            models.User.nickname: "",
            models.User.avatar: "",
        },
        synchronize_session=False,
    )
    db.commit()


def update_conversation_title(db, user_id: int, conversation_id: int, title: str):
    import models

    conversation = (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.id == conversation_id,
            models.ChatSession.user_id == user_id,
        )
        .first()
    )

    if not conversation:
        return None

    conversation.title = title
    db.commit()
    db.refresh(conversation)
    return conversation
