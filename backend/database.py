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
    "reference_payload": "TEXT",
}

STUDY_MATERIAL_COLUMNS = {
    "source_message_id": "INTEGER",
    "is_deleted": "BOOLEAN NOT NULL DEFAULT 0",
    "deleted_at": "DATETIME",
}

MATERIAL_CHUNK_COLUMNS = {
    "material_id": "INTEGER",
    "username": "VARCHAR(50)",
    "subject": "VARCHAR(100)",
    "chunk_index": "INTEGER",
    "chunk_text": "TEXT",
    "chunk_summary": "TEXT",
    "keywords": "TEXT",
    "source_filename": "VARCHAR(255)",
    "is_deleted": "BOOLEAN NOT NULL DEFAULT 0",
    "created_at": "DATETIME",
}

LEARNING_RECORD_COLUMNS = {
    "user_id": "INTEGER",
    "subject": "VARCHAR(100)",
    "session_id": "INTEGER",
    "message_id": "INTEGER",
    "record_type": "VARCHAR(30)",
    "question": "TEXT",
    "answer": "TEXT",
    "references_json": "TEXT",
    "note": "TEXT",
    "tags": "TEXT",
    "review_status": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
    "reviewed_at": "DATETIME",
    "is_deleted": "BOOLEAN NOT NULL DEFAULT 0",
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


def ensure_material_chunks_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS material_chunks (
                id INTEGER PRIMARY KEY,
                material_id INTEGER NOT NULL,
                username VARCHAR(50) NOT NULL,
                subject VARCHAR(100) NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                chunk_summary TEXT NOT NULL,
                keywords TEXT,
                source_filename VARCHAR(255) NOT NULL,
                is_deleted BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "material_chunks", MATERIAL_CHUNK_COLUMNS)


def ensure_learning_records_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS learning_records (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                subject VARCHAR(100) NOT NULL,
                session_id INTEGER,
                message_id INTEGER,
                record_type VARCHAR(30) NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                references_json TEXT,
                note TEXT,
                tags TEXT,
                review_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reviewed_at DATETIME,
                is_deleted BOOLEAN NOT NULL DEFAULT 0
            )
            """
        )
    )
    ensure_columns(conn, "learning_records", LEARNING_RECORD_COLUMNS)


def ensure_material_chunks_fts(conn):
    fts_enabled = True
    try:
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS material_chunks_fts
                USING fts5(
                    chunk_text,
                    chunk_summary,
                    keywords,
                    source_filename,
                    chunk_id UNINDEXED,
                    material_id UNINDEXED,
                    username UNINDEXED,
                    subject UNINDEXED
                )
                """
            )
        )
    except Exception:
        fts_enabled = False

    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS app_runtime_flags (
                key VARCHAR(100) PRIMARY KEY,
                value VARCHAR(50) NOT NULL
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO app_runtime_flags(key, value)
            VALUES ('material_chunks_fts_enabled', :value)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """
        ),
        {"value": "1" if fts_enabled else "0"},
    )


def init_user_profile_schema():
    with engine.begin() as conn:
        ensure_columns(conn, "users", PROFILE_COLUMNS)
        ensure_columns(conn, "chat_sessions", CHAT_SESSION_COLUMNS)
        ensure_columns(conn, "chat_messages", CHAT_MESSAGE_COLUMNS)
        ensure_columns(conn, "study_materials", STUDY_MATERIAL_COLUMNS)
        ensure_material_chunks_schema(conn)
        ensure_learning_records_schema(conn)
        ensure_material_chunks_fts(conn)

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

        material_chunk_columns = get_existing_columns(conn, "material_chunks")
        if "is_deleted" in material_chunk_columns:
            conn.execute(
                text(
                    """
                    UPDATE material_chunks
                    SET is_deleted = 0
                    WHERE is_deleted IS NULL
                    """
                )
            )

        learning_record_columns = get_existing_columns(conn, "learning_records")
        if "is_deleted" in learning_record_columns:
            conn.execute(
                text(
                    """
                    UPDATE learning_records
                    SET is_deleted = 0
                    WHERE is_deleted IS NULL
                    """
                )
            )

        if "review_status" in learning_record_columns:
            conn.execute(
                text(
                    """
                    UPDATE learning_records
                    SET review_status = 'pending'
                    WHERE review_status IS NULL OR TRIM(review_status) = ''
                    """
                )
            )

        if "updated_at" in learning_record_columns:
            conn.execute(
                text(
                    """
                    UPDATE learning_records
                    SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
                    WHERE updated_at IS NULL
                    """
                )
            )


def is_material_chunks_fts_enabled():
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS app_runtime_flags (
                    key VARCHAR(100) PRIMARY KEY,
                    value VARCHAR(50) NOT NULL
                )
                """
            )
        )
        row = conn.execute(
            text(
                """
                SELECT value
                FROM app_runtime_flags
                WHERE key = 'material_chunks_fts_enabled'
                """
            )
        ).fetchone()
        return bool(row and row[0] == "1")


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
