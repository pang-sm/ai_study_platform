from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from subjects import DEFAULT_SUBJECT, get_subject_migration_pairs

DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

PROFILE_COLUMNS = {
    "nickname": "VARCHAR(30)",
    "avatar": "VARCHAR(255)",
    "grade": "VARCHAR(50) NOT NULL DEFAULT ''",
    "major": "VARCHAR(100) NOT NULL DEFAULT ''",
    "onboarding_completed": "BOOLEAN NOT NULL DEFAULT 0",
    "learning_goals": "TEXT",
    "plan": "VARCHAR(20) DEFAULT 'free'",
    "plan_source": "VARCHAR(30) DEFAULT ''",
    "plan_expire_at": "DATETIME",
    "is_admin": "INTEGER DEFAULT 0",
    "admin_role": "VARCHAR(30) DEFAULT 'none'",
    "admin_real_name": "TEXT",
    "school": "VARCHAR(100) DEFAULT ''",
    "learning_direction": "VARCHAR(100) DEFAULT ''",
    "default_course_id": "VARCHAR(100) DEFAULT ''",
    "learning_stage": "VARCHAR(50) DEFAULT ''",
    "daily_study_minutes": "INTEGER DEFAULT 0",
    "ai_answer_style": "VARCHAR(50) DEFAULT ''",
    "answer_detail_level": "VARCHAR(50) DEFAULT ''",
    "material_reference_preference": "VARCHAR(50) DEFAULT ''",
    "focus_courses": "TEXT DEFAULT ''",
    "email": "VARCHAR(255)",
    "email_verified": "BOOLEAN NOT NULL DEFAULT 0",
    "phone": "VARCHAR(30)",
    "phone_verified": "BOOLEAN NOT NULL DEFAULT 0",
    "onboarding_detail": "TEXT",
    "is_active": "INTEGER DEFAULT 1",
    "is_banned": "INTEGER DEFAULT 0",
    "banned_reason": "TEXT",
    "banned_at": "TEXT",
    "is_deleted": "INTEGER DEFAULT 0",
    "deleted_at": "TEXT",
}

CHAT_SESSION_COLUMNS = {
    "course": "VARCHAR(100)",
    "subject": "VARCHAR(100)",
    "exam_subject": "VARCHAR(64)",
}

CHAT_MESSAGE_COLUMNS = {
    "attachment_type": "VARCHAR(20)",
    "attachment_filename": "VARCHAR(255)",
    "attachment_path": "VARCHAR(500)",
    "extracted_text": "TEXT",
    "material_id": "INTEGER",
    "reference_payload": "TEXT",
    "parent_message_id": "INTEGER",
    "root_message_id": "INTEGER",
    "branch_id": "VARCHAR(64)",
    "version_index": "INTEGER NOT NULL DEFAULT 0",
}

STUDY_MATERIAL_COLUMNS = {
    "mime_type": "VARCHAR(255)",
    "file_size": "INTEGER DEFAULT 0",
    "file_hash": "TEXT",
    "file_path": "TEXT",
    "source_message_id": "INTEGER",
    "source_type": "VARCHAR(50) NOT NULL DEFAULT 'user_upload'",
    "visibility": "VARCHAR(50) NOT NULL DEFAULT 'private'",
    "copyright_status": "VARCHAR(50) NOT NULL DEFAULT 'user_responsibility'",
    "allow_download": "BOOLEAN NOT NULL DEFAULT 1",
    "allow_public_rag": "BOOLEAN NOT NULL DEFAULT 0",
    "allow_private_rag": "BOOLEAN NOT NULL DEFAULT 1",
    "allow_generate_knowledge": "BOOLEAN NOT NULL DEFAULT 1",
    "is_default_reference": "BOOLEAN NOT NULL DEFAULT 0",
    "extract_method": "VARCHAR(20)",
    "parse_status": "VARCHAR(20)",
    "parse_error": "TEXT",
    "qwen_used": "BOOLEAN NOT NULL DEFAULT 0",
    "parsed_at": "DATETIME",
    "total_pages": "INTEGER DEFAULT 0",
    "parsed_pages": "INTEGER DEFAULT 0",
    "ocr_page_limit": "INTEGER DEFAULT 0",
    "chunk_count": "INTEGER DEFAULT 0",
    "ocr_required": "INTEGER DEFAULT 0",
    "parse_progress": "REAL DEFAULT 0",
    "parse_started_at": "TEXT",
    "parse_completed_at": "TEXT",
    "is_deleted": "BOOLEAN NOT NULL DEFAULT 0",
    "updated_at": "DATETIME",
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

COURSE_PROGRESS_COLUMNS = {
    "username": "VARCHAR(50)",
    "course": "VARCHAR(100)",
    "knowledge_point": "VARCHAR(255)",
    "status": "VARCHAR(20) NOT NULL DEFAULT '未开始'",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

COURSE_LEARNING_PREFERENCES_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100) NOT NULL",
    "mastery_level": "VARCHAR(50) NOT NULL DEFAULT ''",
    "learning_goal": "VARCHAR(50) NOT NULL DEFAULT ''",
    "is_started": "BOOLEAN NOT NULL DEFAULT 0",
    "started_at": "DATETIME",
    "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
}

CODE_AI_MESSAGES_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "session_id": "INTEGER NOT NULL",
    "role": "VARCHAR(20) NOT NULL",
    "content": "TEXT NOT NULL",
    "language": "VARCHAR(20)",
    "code_snapshot": "TEXT",
    "created_at": "DATETIME",
}

CODE_CHALLENGES_COLUMNS = {
    "source": "VARCHAR(30)",
    "target_weak_point": "VARCHAR(255)",
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100)",
    "language": "VARCHAR(20) NOT NULL",
    "title": "VARCHAR(255) NOT NULL",
    "difficulty": "VARCHAR(20) NOT NULL",
    "knowledge_point": "VARCHAR(255)",
    "description": "TEXT NOT NULL",
    "requirements": "TEXT",
    "input_format": "TEXT",
    "output_format": "TEXT",
    "examples": "TEXT",
    "starter_code": "TEXT",
    "reference_solution": "TEXT",
    "test_cases": "TEXT",
    "created_at": "DATETIME",
}

CODE_SESSIONS_COLUMNS = {
    "username": "VARCHAR(50)",
    "course_id": "VARCHAR(100)",
    "title": "VARCHAR(255) NOT NULL DEFAULT '未命名练习'",
    "language": "VARCHAR(20) NOT NULL DEFAULT 'Python'",
    "code": "TEXT NOT NULL DEFAULT ''",
    "challenge_id": "INTEGER",
    "session_type": "VARCHAR(20)",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}

PAST_PAPER_WRONG_QUESTIONS_COLUMNS = {
    "mastered": "BOOLEAN NOT NULL DEFAULT 0",
    "reviewed_at": "DATETIME",
}

EXAM_FAVORITE_QUESTIONS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "subject_key": "VARCHAR(50) NOT NULL",
    "subject_name": "VARCHAR(50)",
    "source": "VARCHAR(50) NOT NULL DEFAULT 'past_paper'",
    "source_question_id": "VARCHAR(100) NOT NULL",
    "year": "INTEGER",
    "number": "INTEGER",
    "question_type": "VARCHAR(30)",
    "stem": "TEXT",
    "options_json": "TEXT",
    "standard_answer": "TEXT",
    "knowledge_point_id": "VARCHAR(100)",
    "knowledge_point_name": "VARCHAR(255)",
    "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
}

LEARNING_TASKS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100)",
    "title": "VARCHAR(255) NOT NULL",
    "description": "TEXT",
    "task_type": "VARCHAR(50) NOT NULL",
    "status": "VARCHAR(30) NOT NULL",
    "source": "VARCHAR(50)",
    "priority": "VARCHAR(20)",
    "order_index": "INTEGER DEFAULT 0",
    "due_date": "DATETIME",
    "related_session_id": "INTEGER",
    "related_challenge_id": "INTEGER",
    "related_material_id": "INTEGER",
    "knowledge_point_id": "INTEGER",
    "knowledge_point_text": "TEXT",
    "related_question_id": "INTEGER",
    "metadata": "TEXT",
    "completed_at": "DATETIME",
    "created_at": "DATETIME NOT NULL",
    "updated_at": "DATETIME NOT NULL",
}

KNOWLEDGE_POINTS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100) NOT NULL",
    "parent_id": "INTEGER",
    "title": "VARCHAR(255) NOT NULL",
    "description": "TEXT",
    "order_index": "INTEGER",
    "level": "INTEGER",
    "node_key": "VARCHAR(500)",
    "created_at": "DATETIME NOT NULL",
    "updated_at": "DATETIME NOT NULL",
}

QUESTIONS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "paper_id": "INTEGER",
    "question_order": "INTEGER",
    "course_id": "VARCHAR(100)",
    "knowledge_point_id": "INTEGER",
    "type": "VARCHAR(30) NOT NULL",
    "title": "VARCHAR(255) NOT NULL",
    "content": "TEXT NOT NULL",
    "options": "TEXT",
    "answer": "TEXT",
    "explanation": "TEXT",
    "difficulty": "VARCHAR(20)",
    "source": "VARCHAR(50)",
    "source_style": "VARCHAR(30)",
    "imported_from": "VARCHAR(50)",
    "original_file_name": "VARCHAR(255)",
    "raw_text": "TEXT",
    "created_at": "DATETIME NOT NULL",
    "updated_at": "DATETIME NOT NULL",
}

PRACTICE_PAPERS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100)",
    "title": "VARCHAR(255) NOT NULL",
    "source_file_name": "VARCHAR(255)",
    "source_type": "VARCHAR(50)",
    "status": "VARCHAR(30)",
    "question_count": "INTEGER",
    "created_at": "DATETIME NOT NULL",
    "updated_at": "DATETIME NOT NULL",
}

QUESTION_ATTEMPTS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "question_id": "INTEGER NOT NULL",
    "course_id": "VARCHAR(100)",
    "knowledge_point_id": "INTEGER",
    "user_answer": "TEXT",
    "ai_feedback": "TEXT",
    "self_result": "VARCHAR(30)",
    "created_at": "DATETIME NOT NULL",
}

AI_USAGE_LOGS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "feature": "VARCHAR(50) NOT NULL",
    "model": "VARCHAR(100)",
    "estimated_tokens": "INTEGER DEFAULT 0",
    "estimated_cost": "REAL DEFAULT 0",
    "status": "VARCHAR(20) DEFAULT 'success'",
    "error_message": "TEXT",
    "created_at": "DATETIME NOT NULL",
}

ADMIN_AUDIT_LOGS_COLUMNS = {
    "admin_username": "VARCHAR(50) NOT NULL",
    "action": "VARCHAR(100) NOT NULL",
    "target_type": "VARCHAR(50)",
    "target_id": "VARCHAR(100)",
    "target_username": "VARCHAR(50)",
    "result": "VARCHAR(20) DEFAULT 'success'",
    "detail": "TEXT",
    "details": "TEXT",
    "ip": "VARCHAR(100)",
    "created_at": "DATETIME NOT NULL",
}

LEARNING_REPORTS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100)",
    "course_name": "VARCHAR(100)",
    "report_type": "VARCHAR(50) NOT NULL",
    "title": "VARCHAR(200) NOT NULL",
    "summary": "TEXT",
    "content": "TEXT NOT NULL",
    "metrics_json": "TEXT",
    "suggestions_json": "TEXT",
    "start_date": "DATETIME",
    "end_date": "DATETIME",
    "created_at": "DATETIME NOT NULL",
}

LEARNING_REPORT_SHARES_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "report_id": "INTEGER NOT NULL",
    "share_token": "VARCHAR(80) NOT NULL",
    "title": "VARCHAR(200)",
    "is_active": "INTEGER DEFAULT 1",
    "view_count": "INTEGER DEFAULT 0",
    "created_at": "DATETIME NOT NULL",
    "revoked_at": "DATETIME",
    "last_viewed_at": "DATETIME",
}

CODE_AI_SAVED_CHATS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "challenge_id": "INTEGER NOT NULL",
    "session_id": "INTEGER",
    "language": "VARCHAR(20)",
    "user_message": "TEXT NOT NULL",
    "assistant_message": "TEXT NOT NULL",
    "code_snapshot": "TEXT",
    "created_at": "DATETIME NOT NULL",
}

CODE_CHALLENGE_ATTEMPTS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "session_id": "INTEGER NOT NULL",
    "challenge_id": "INTEGER NOT NULL",
    "language": "VARCHAR(20)",
    "code": "TEXT NOT NULL",
    "status": "VARCHAR(30)",
    "ai_feedback": "TEXT",
    "mastered": "INTEGER DEFAULT 0",
    "mastered_at": "TEXT",
    "note": "TEXT",
    "created_at": "DATETIME NOT NULL",
}

MATERIAL_KNOWLEDGE_LINKS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100) NOT NULL",
    "material_id": "INTEGER NOT NULL",
    "knowledge_point_id": "INTEGER NOT NULL",
    "source": "VARCHAR(50) DEFAULT 'manual'",
    "confidence": "INTEGER DEFAULT 100",
    "reason": "TEXT",
    "created_at": "DATETIME NOT NULL",
}

KNOWLEDGE_PROGRESS_EVENTS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100) NOT NULL",
    "knowledge_point_id": "INTEGER NOT NULL",
    "event_type": "VARCHAR(50) NOT NULL",
    "delta": "INTEGER NOT NULL",
    "reason": "TEXT",
    "source_type": "VARCHAR(50)",
    "source_id": "INTEGER",
    "created_at": "DATETIME NOT NULL",
}

USER_KNOWLEDGE_PROGRESS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100) NOT NULL",
    "knowledge_point_id": "INTEGER NOT NULL",
    "knowledge_point_code": "VARCHAR(100)",
    "knowledge_point_title": "VARCHAR(255)",
    "mastery_score": "INTEGER",
    "status": "VARCHAR(30)",
    "practice_count": "INTEGER",
    "task_count": "INTEGER",
    "last_studied_at": "DATETIME",
    "learned_at": "DATETIME",
    "review_due_at": "DATETIME",
    "review_interval_days": "INTEGER",
    "created_at": "DATETIME NOT NULL",
    "updated_at": "DATETIME NOT NULL",
}

USER_KNOWLEDGE_REVIEW_SETTINGS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100) NOT NULL",
    "review_interval_days": "INTEGER NOT NULL DEFAULT 7",
    "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
}

USER_LEARNING_PATHS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "subject": "VARCHAR(100) NOT NULL",
    "path_type": "VARCHAR(30) NOT NULL DEFAULT 'material'",
    "title": "VARCHAR(255) NOT NULL",
    "source_material_ids": "TEXT",
    "modules_json": "TEXT NOT NULL",
    "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
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


def ensure_admin_roles_schema(conn):
    ensure_columns(conn, "users", {"admin_role": "VARCHAR(30) DEFAULT 'none'"})
    conn.execute(
        text(
            """
            UPDATE users
            SET admin_role = 'none'
            WHERE COALESCE(is_admin, 0) = 0
              AND (admin_role IS NULL OR admin_role = '')
            """
        )
    )
    admin_users = conn.execute(
        text(
            """
            SELECT id, username, COALESCE(admin_role, '') AS admin_role
            FROM users
            WHERE COALESCE(is_admin, 0) = 1
            ORDER BY CASE WHEN username = 'admin' THEN 0 ELSE 1 END, id ASC
            """
        )
    ).fetchall()
    if not admin_users:
        return

    super_admin_count = conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM users
            WHERE COALESCE(is_admin, 0) = 1 AND admin_role = 'super_admin'
            """
        )
    ).scalar() or 0
    if super_admin_count <= 0:
        first_admin_id = admin_users[0][0]
        conn.execute(
            text("UPDATE users SET admin_role = 'super_admin' WHERE id = :user_id"),
            {"user_id": first_admin_id},
        )

    conn.execute(
        text(
            """
            UPDATE users
            SET admin_role = 'operator'
            WHERE COALESCE(is_admin, 0) = 1
              AND (admin_role IS NULL OR admin_role = '' OR admin_role = 'none')
              AND id NOT IN (
                  SELECT id FROM users
                  WHERE COALESCE(is_admin, 0) = 1 AND admin_role = 'super_admin'
              )
            """
        )
    )


def ensure_study_material_schema(conn):
    ensure_columns(conn, "study_materials", STUDY_MATERIAL_COLUMNS)
    backfill_study_material_permissions(conn)
    seed_default_reference_materials(conn)


DEFAULT_REFERENCE_MATERIALS = [
    {
        "username": "system",
        "subject": "11408 数据结构",
        "file_type": "reference",
        "original_filename": "2027 数据结构考研复习指导",
        "mime_type": "application/x-reference-metadata",
        "file_path": "reference_metadata://2027-data-structure",
        "summary": (
            "目录级参考索引：用于定位数据结构复习章节、知识点和题型，不包含第三方资料正文，"
            "不提供原文下载。覆盖绪论、线性表、栈和队列、串、数组和广义表、树与二叉树、图、查找、排序等复习模块。"
        ),
        "extracted_text": (
            "数据结构目录级索引：绪论；线性表；栈、队列和数组；串与模式匹配；树与二叉树；图；查找；排序。"
            "本记录仅用于学习路径、章节定位、知识点索引和题型位置提示，不包含第三方书籍正文。"
        ),
    }
]


def backfill_study_material_permissions(conn):
    conn.execute(
        text(
            """
            UPDATE study_materials
            SET
              source_type = COALESCE(NULLIF(source_type, ''), 'user_upload'),
              visibility = COALESCE(NULLIF(visibility, ''), 'private'),
              copyright_status = COALESCE(NULLIF(copyright_status, ''), 'user_responsibility'),
              allow_download = COALESCE(allow_download, 1),
              allow_public_rag = COALESCE(allow_public_rag, 0),
              allow_private_rag = COALESCE(allow_private_rag, 1),
              allow_generate_knowledge = COALESCE(allow_generate_knowledge, 1),
              is_default_reference = COALESCE(is_default_reference, 0)
            """
        )
    )


def seed_default_reference_materials(conn):
    for item in DEFAULT_REFERENCE_MATERIALS:
        existing = conn.execute(
            text(
                """
                SELECT id
                FROM study_materials
                WHERE subject = :subject
                  AND original_filename = :original_filename
                  AND source_type = 'reference_metadata'
                  AND COALESCE(is_default_reference, 0) = 1
                  AND COALESCE(is_deleted, 0) = 0
                LIMIT 1
                """
            ),
            item,
        ).first()
        if existing:
            conn.execute(
                text(
                    """
                    UPDATE study_materials
                    SET
                      username = 'system',
                      file_type = :file_type,
                      mime_type = :mime_type,
                      file_size = 0,
                      file_path = :file_path,
                      extracted_text = :extracted_text,
                      summary = :summary,
                      source_type = 'reference_metadata',
                      visibility = 'system_public_metadata',
                      copyright_status = 'restricted_reference_only',
                      allow_download = 0,
                      allow_public_rag = 0,
                      allow_private_rag = 0,
                      allow_generate_knowledge = 1,
                      is_default_reference = 1,
                      extract_method = 'metadata',
                      parse_status = 'success',
                      parse_error = NULL,
                      qwen_used = 0,
                      total_pages = 0,
                      parsed_pages = 0,
                      chunk_count = 0,
                      ocr_required = 0,
                      parse_progress = 100,
                      updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                    """
                ),
                {**item, "id": existing[0]},
            )
            continue

        conn.execute(
            text(
                """
                INSERT INTO study_materials (
                    username, subject, file_type, original_filename, mime_type,
                    file_size, file_hash, file_path, extracted_text, summary,
                    source_message_id, source_type, visibility, copyright_status,
                    allow_download, allow_public_rag, allow_private_rag,
                    allow_generate_knowledge, is_default_reference, extract_method,
                    parse_status, parse_error, qwen_used, parsed_at, total_pages,
                    parsed_pages, chunk_count, ocr_required, parse_progress,
                    parse_started_at, parse_completed_at, is_deleted, created_at, updated_at
                ) VALUES (
                    :username, :subject, :file_type, :original_filename, :mime_type,
                    0, NULL, :file_path, :extracted_text, :summary,
                    NULL, 'reference_metadata', 'system_public_metadata', 'restricted_reference_only',
                    0, 0, 0,
                    1, 1, 'metadata',
                    'success', NULL, 0, CURRENT_TIMESTAMP, 0,
                    0, 0, 0, 100,
                    NULL, CURRENT_TIMESTAMP, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            item,
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


def ensure_course_progress_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS course_progress (
                id INTEGER PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                course VARCHAR(100) NOT NULL,
                knowledge_point VARCHAR(255) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT '未开始',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "course_progress", COURSE_PROGRESS_COLUMNS)


def ensure_course_learning_preferences_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS course_learning_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100) NOT NULL,
                mastery_level VARCHAR(50) NOT NULL DEFAULT '',
                learning_goal VARCHAR(50) NOT NULL DEFAULT '',
                is_started BOOLEAN NOT NULL DEFAULT 0,
                started_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "course_learning_preferences", COURSE_LEARNING_PREFERENCES_COLUMNS)
    conn.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_course_learning_preferences_user_course
            ON course_learning_preferences (username, course_id)
            """
        )
    )


def ensure_code_sessions_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS code_sessions (
                id INTEGER PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL DEFAULT '未命名练习',
                language VARCHAR(20) NOT NULL DEFAULT 'Python',
                code TEXT NOT NULL DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "code_sessions", CODE_SESSIONS_COLUMNS)


def ensure_code_ai_messages_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS code_ai_messages (
                id INTEGER PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                session_id INTEGER NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                language VARCHAR(20),
                code_snapshot TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "code_ai_messages", CODE_AI_MESSAGES_COLUMNS)


def ensure_code_challenges_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS code_challenges (
                id INTEGER PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100),
                language VARCHAR(20) NOT NULL,
                title VARCHAR(255) NOT NULL,
                difficulty VARCHAR(20) NOT NULL,
                knowledge_point VARCHAR(255),
                description TEXT NOT NULL,
                requirements TEXT,
                input_format TEXT,
                output_format TEXT,
                examples TEXT,
                starter_code TEXT,
                reference_solution TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "code_challenges", CODE_CHALLENGES_COLUMNS)


def ensure_code_ai_saved_chats_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS code_ai_saved_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                challenge_id INTEGER NOT NULL,
                session_id INTEGER,
                language VARCHAR(20),
                user_message TEXT NOT NULL,
                assistant_message TEXT NOT NULL,
                code_snapshot TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "code_ai_saved_chats", CODE_AI_SAVED_CHATS_COLUMNS)


def ensure_code_challenge_attempts_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS code_challenge_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                session_id INTEGER NOT NULL,
                challenge_id INTEGER NOT NULL,
                language VARCHAR(20),
                code TEXT NOT NULL,
                status VARCHAR(30),
                ai_feedback TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "code_challenge_attempts", CODE_CHALLENGE_ATTEMPTS_COLUMNS)


SYSTEM_ANNOUNCEMENTS_COLUMNS = {
    "title": "TEXT NOT NULL",
    "content": "TEXT NOT NULL",
    "type": "VARCHAR(20) DEFAULT 'info'",
    "is_active": "INTEGER DEFAULT 1",
    "target": "VARCHAR(20) DEFAULT 'all'",
    "created_by": "VARCHAR(50)",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
    "withdrawn_at": "DATETIME",
}

SYSTEM_SETTINGS_COLUMNS = {
    "value": "TEXT",
    "description": "TEXT",
    "updated_by": "VARCHAR(50)",
    "updated_at": "DATETIME",
}


def ensure_system_announcements_schema(conn):
    conn.execute(text("""CREATE TABLE IF NOT EXISTS system_announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, content TEXT NOT NULL,
        type VARCHAR(20) DEFAULT 'info', is_active INTEGER DEFAULT 1,
        target VARCHAR(20) DEFAULT 'all', created_by VARCHAR(50),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        withdrawn_at DATETIME)"""))
    ensure_columns(conn, "system_announcements", SYSTEM_ANNOUNCEMENTS_COLUMNS)


def ensure_system_settings_schema(conn):
    conn.execute(text("""CREATE TABLE IF NOT EXISTS system_settings (
        key VARCHAR(100) PRIMARY KEY, value TEXT,
        description TEXT, updated_by VARCHAR(50),
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"""))
    ensure_columns(conn, "system_settings", SYSTEM_SETTINGS_COLUMNS)
    # Initialize default settings if not present
    defaults = {
        "feature_ai_chat_enabled": ("true", "AI 问答是否启用"),
        "feature_material_upload_enabled": ("true", "资料上传是否启用"),
        "feature_code_studio_enabled": ("true", "编程助手是否启用"),
        "feature_practice_center_enabled": ("true", "练习中心是否启用"),
        "feature_report_share_enabled": ("true", "报告分享是否启用"),
        "limit_free_daily_ai_calls": ("5", "免费版每日AI调用次数"),
        "limit_pro_daily_ai_calls": ("30", "专业版每日AI调用次数"),
        "limit_admin_daily_ai_calls": ("-1", "管理员每日AI调用次数(-1无限制)"),
    }
    for k, (v, desc) in defaults.items():
        existing = conn.execute(text("SELECT 1 FROM system_settings WHERE key=:k"), {"k": k}).fetchone()
        if not existing:
            conn.execute(text("INSERT INTO system_settings(key,value,description) VALUES(:k,:v,:d)"), {"k": k, "v": v, "d": desc})


def ensure_learning_tasks_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS learning_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100),
                title VARCHAR(255) NOT NULL,
                description TEXT,
                task_type VARCHAR(50) NOT NULL,
                status VARCHAR(30) NOT NULL,
                source VARCHAR(50),
                priority VARCHAR(20),
                due_date DATETIME,
                related_session_id INTEGER,
                related_challenge_id INTEGER,
                related_material_id INTEGER,
                completed_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "learning_tasks", LEARNING_TASKS_COLUMNS)


def ensure_questions_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                paper_id INTEGER,
                question_order INTEGER,
                course_id VARCHAR(100),
                knowledge_point_id INTEGER,
                type VARCHAR(30) NOT NULL,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                options TEXT,
                answer TEXT,
                explanation TEXT,
                difficulty VARCHAR(20),
                source VARCHAR(50),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "questions", QUESTIONS_COLUMNS)


def ensure_practice_papers_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS practice_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100),
                title VARCHAR(255) NOT NULL,
                source_file_name VARCHAR(255),
                source_type VARCHAR(50),
                status VARCHAR(30),
                question_count INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "practice_papers", PRACTICE_PAPERS_COLUMNS)


PRACTICE_IMPORT_JOBS_COLUMNS = {
    "username": "VARCHAR(50) NOT NULL",
    "course_id": "VARCHAR(100) DEFAULT ''",
    "module_id": "VARCHAR(100)",
    "knowledge_point_id": "INTEGER",
    "filename": "VARCHAR(255)",
    "file_path": "VARCHAR(500)",
    "file_size": "INTEGER DEFAULT 0",
    "status": "VARCHAR(30) NOT NULL DEFAULT 'pending'",
    "progress_message": "VARCHAR(500)",
    "parse_method": "VARCHAR(50)",
    "total_pages": "INTEGER DEFAULT 0",
    "parsed_pages": "INTEGER DEFAULT 0",
    "page_limit_hit": "BOOLEAN DEFAULT 0",
    "text_length": "INTEGER DEFAULT 0",
    "qwen_pages": "INTEGER DEFAULT 0",
    "deepseek_input_length": "INTEGER DEFAULT 0",
    "question_count": "INTEGER DEFAULT 0",
    "result_json": "TEXT",
    "error_message": "TEXT",
    "updated_at": "DATETIME",
    "started_at": "DATETIME",
    "finished_at": "DATETIME",
}


def ensure_practice_import_jobs_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS practice_import_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "practice_import_jobs", PRACTICE_IMPORT_JOBS_COLUMNS)


def ensure_question_attempts_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS question_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                question_id INTEGER NOT NULL,
                course_id VARCHAR(100),
                knowledge_point_id INTEGER,
                user_answer TEXT,
                ai_feedback TEXT,
                self_result VARCHAR(30),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "question_attempts", QUESTION_ATTEMPTS_COLUMNS)


def ensure_past_paper_wrong_questions_schema(conn):
    ensure_columns(conn, "past_paper_wrong_questions", PAST_PAPER_WRONG_QUESTIONS_COLUMNS)


def ensure_exam_favorite_questions_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS exam_favorite_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                subject_key VARCHAR(50) NOT NULL,
                subject_name VARCHAR(50),
                source VARCHAR(50) NOT NULL DEFAULT 'past_paper',
                source_question_id VARCHAR(100) NOT NULL,
                year INTEGER,
                number INTEGER,
                question_type VARCHAR(30),
                stem TEXT,
                options_json TEXT,
                standard_answer TEXT,
                knowledge_point_id VARCHAR(100),
                knowledge_point_name VARCHAR(255),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "exam_favorite_questions", EXAM_FAVORITE_QUESTIONS_COLUMNS)


def ensure_knowledge_points_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS knowledge_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100) NOT NULL,
                parent_id INTEGER,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                order_index INTEGER,
                level INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "knowledge_points", KNOWLEDGE_POINTS_COLUMNS)
    conn.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_points_user_course_node_key
            ON knowledge_points (username, course_id, node_key)
            """
        )
    )


def ensure_user_knowledge_progress_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_knowledge_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100) NOT NULL,
                knowledge_point_id INTEGER NOT NULL,
                mastery_score INTEGER,
                status VARCHAR(30),
                practice_count INTEGER,
                task_count INTEGER,
                last_studied_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "user_knowledge_progress", USER_KNOWLEDGE_PROGRESS_COLUMNS)
    conn.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_user_knowledge_progress_user_course_code
            ON user_knowledge_progress (username, course_id, knowledge_point_code)
            """
        )
    )


def ensure_user_knowledge_review_settings_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_knowledge_review_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100) NOT NULL,
                review_interval_days INTEGER NOT NULL DEFAULT 7,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "user_knowledge_review_settings", USER_KNOWLEDGE_REVIEW_SETTINGS_COLUMNS)
    conn.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_knowledge_review_settings_user_course
            ON user_knowledge_review_settings (username, course_id)
            """
        )
    )


def ensure_user_learning_paths_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_learning_paths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                subject VARCHAR(100) NOT NULL,
                path_type VARCHAR(30) NOT NULL DEFAULT 'material',
                title VARCHAR(255) NOT NULL,
                source_material_ids TEXT,
                modules_json TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "user_learning_paths", USER_LEARNING_PATHS_COLUMNS)


def ensure_ai_usage_logs_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS ai_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                feature VARCHAR(50) NOT NULL,
                model VARCHAR(100),
                estimated_tokens INTEGER DEFAULT 0,
                estimated_cost REAL DEFAULT 0,
                status VARCHAR(20) DEFAULT 'success',
                error_message TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "ai_usage_logs", AI_USAGE_LOGS_COLUMNS)


def ensure_admin_audit_logs_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS admin_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_username VARCHAR(50) NOT NULL,
                action VARCHAR(100) NOT NULL,
                target_type VARCHAR(50),
                target_username VARCHAR(50),
                detail TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "admin_audit_logs", ADMIN_AUDIT_LOGS_COLUMNS)


def ensure_user_learning_tracks_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_learning_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                track_type VARCHAR(30) NOT NULL,
                plan VARCHAR(30) DEFAULT 'free',
                package_type VARCHAR(30),
                permissions_json TEXT,
                quota_json TEXT,
                onboarding_detail_json TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                status VARCHAR(20) DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, track_type)
            )
            """
        )
    )
    # Ensure columns for migrations from older versions
    USER_LEARNING_TRACK_COLUMNS = {
        "plan": "VARCHAR(30) DEFAULT 'free'",
        "package_type": "VARCHAR(30)",
        "permissions_json": "TEXT",
        "quota_json": "TEXT",
        "onboarding_detail_json": "TEXT",
        "is_active": "BOOLEAN NOT NULL DEFAULT 1",
        "status": "VARCHAR(20) DEFAULT 'active'",
        "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    }
    ensure_columns(conn, "user_learning_tracks", USER_LEARNING_TRACK_COLUMNS)


def ensure_verification_codes_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS verification_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                target VARCHAR(255) NOT NULL,
                purpose VARCHAR(30) NOT NULL,
                code_hash VARCHAR(255) NOT NULL,
                expires_at DATETIME NOT NULL,
                used BOOLEAN NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def ensure_learning_reports_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS learning_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100),
                course_name VARCHAR(100),
                report_type VARCHAR(50) NOT NULL,
                title VARCHAR(200) NOT NULL,
                summary TEXT,
                content TEXT NOT NULL,
                metrics_json TEXT,
                suggestions_json TEXT,
                start_date DATETIME,
                end_date DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "learning_reports", LEARNING_REPORTS_COLUMNS)


def ensure_learning_report_shares_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS learning_report_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                report_id INTEGER NOT NULL,
                share_token VARCHAR(80) NOT NULL,
                title VARCHAR(200),
                is_active INTEGER DEFAULT 1,
                view_count INTEGER DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                revoked_at DATETIME,
                last_viewed_at DATETIME
            )
            """
        )
    )
    ensure_columns(conn, "learning_report_shares", LEARNING_REPORT_SHARES_COLUMNS)


def ensure_material_knowledge_links_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS material_knowledge_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100) NOT NULL,
                material_id INTEGER NOT NULL,
                knowledge_point_id INTEGER NOT NULL,
                source VARCHAR(50) DEFAULT 'manual',
                confidence INTEGER DEFAULT 100,
                reason TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "material_knowledge_links", MATERIAL_KNOWLEDGE_LINKS_COLUMNS)


def ensure_knowledge_progress_events_schema(conn):
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS knowledge_progress_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) NOT NULL,
                course_id VARCHAR(100) NOT NULL,
                knowledge_point_id INTEGER NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                delta INTEGER NOT NULL,
                reason TEXT,
                source_type VARCHAR(50),
                source_id INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    ensure_columns(conn, "knowledge_progress_events", KNOWLEDGE_PROGRESS_EVENTS_COLUMNS)


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


def column_exists(conn, table_name: str, column_name: str) -> bool:
    return column_name in get_existing_columns(conn, table_name)


def update_subject_aliases(conn, table_name: str, column_name: str):
    if not column_exists(conn, table_name, column_name):
        return

    for old_value, new_value in get_subject_migration_pairs():
        conn.execute(
            text(f"UPDATE {table_name} SET {column_name} = :new_value WHERE {column_name} = :old_value"),
            {"old_value": old_value, "new_value": new_value},
        )


def fill_blank_subject_column(conn, table_name: str, column_name: str):
    if not column_exists(conn, table_name, column_name):
        return

    conn.execute(
        text(
            f"""
            UPDATE {table_name}
            SET {column_name} = :default_subject
            WHERE {column_name} IS NULL OR TRIM({column_name}) = ''
            """
        ),
        {"default_subject": DEFAULT_SUBJECT},
    )


def normalize_existing_subjects(conn):
    update_subject_aliases(conn, "chat_sessions", "subject")
    update_subject_aliases(conn, "chat_sessions", "course")
    update_subject_aliases(conn, "study_materials", "subject")
    update_subject_aliases(conn, "material_chunks", "subject")
    update_subject_aliases(conn, "learning_records", "subject")
    update_subject_aliases(conn, "chat_messages", "subject")
    update_subject_aliases(conn, "course_progress", "course")
    update_subject_aliases(conn, "course_learning_preferences", "course_id")

    chat_session_columns = get_existing_columns(conn, "chat_sessions")
    if "subject" in chat_session_columns and "course" in chat_session_columns:
        conn.execute(
            text(
                """
                UPDATE chat_sessions
                SET subject = COALESCE(NULLIF(subject, ''), NULLIF(course, ''), :default_subject)
                WHERE subject IS NULL OR TRIM(subject) = ''
                """
            ),
            {"default_subject": DEFAULT_SUBJECT},
        )
        conn.execute(
            text(
                """
                UPDATE chat_sessions
                SET course = COALESCE(NULLIF(course, ''), NULLIF(subject, ''), :default_subject)
                WHERE course IS NULL OR TRIM(course) = ''
                """
            ),
            {"default_subject": DEFAULT_SUBJECT},
        )
    else:
        fill_blank_subject_column(conn, "chat_sessions", "subject")
        fill_blank_subject_column(conn, "chat_sessions", "course")

    fill_blank_subject_column(conn, "study_materials", "subject")
    fill_blank_subject_column(conn, "material_chunks", "subject")
    fill_blank_subject_column(conn, "learning_records", "subject")
    fill_blank_subject_column(conn, "chat_messages", "subject")
    fill_blank_subject_column(conn, "course_progress", "course")
    fill_blank_subject_column(conn, "course_learning_preferences", "course_id")


def init_user_profile_schema():
    with engine.begin() as conn:
        ensure_columns(conn, "users", PROFILE_COLUMNS)
        ensure_admin_roles_schema(conn)
        ensure_columns(conn, "chat_sessions", CHAT_SESSION_COLUMNS)
        ensure_columns(conn, "chat_messages", CHAT_MESSAGE_COLUMNS)
        ensure_study_material_schema(conn)
        ensure_material_chunks_schema(conn)
        ensure_learning_records_schema(conn)
        ensure_course_progress_schema(conn)
        ensure_course_learning_preferences_schema(conn)
        ensure_code_sessions_schema(conn)
        ensure_code_ai_messages_schema(conn)
        ensure_code_challenges_schema(conn)
        ensure_code_challenge_attempts_schema(conn)
        ensure_code_ai_saved_chats_schema(conn)
        ensure_learning_tasks_schema(conn)
        ensure_practice_papers_schema(conn)
        ensure_questions_schema(conn)
        ensure_question_attempts_schema(conn)
        ensure_past_paper_wrong_questions_schema(conn)
        ensure_exam_favorite_questions_schema(conn)
        ensure_practice_import_jobs_schema(conn)
        ensure_knowledge_points_schema(conn)
        ensure_user_knowledge_progress_schema(conn)
        ensure_user_knowledge_review_settings_schema(conn)
        ensure_user_learning_paths_schema(conn)
        ensure_knowledge_progress_events_schema(conn)
        ensure_material_knowledge_links_schema(conn)
        ensure_ai_usage_logs_schema(conn)
        ensure_admin_audit_logs_schema(conn)
        ensure_verification_codes_schema(conn)
        ensure_user_learning_tracks_schema(conn)
        ensure_learning_reports_schema(conn)
        ensure_learning_report_shares_schema(conn)
        ensure_system_announcements_schema(conn)
        ensure_system_settings_schema(conn)
        ensure_material_chunks_fts(conn)
        normalize_existing_subjects(conn)

        user_columns = get_existing_columns(conn, "users")
        if "onboarding_completed" in user_columns:
            conn.execute(
                text(
                    """
                    UPDATE users
                    SET onboarding_completed = 1
                    WHERE COALESCE(onboarding_completed, 0) = 0
                      AND (
                        COALESCE(is_admin, 0) = 1
                        OR COALESCE(NULLIF(TRIM(nickname), ''), NULLIF(TRIM(grade), ''), NULLIF(TRIM(major), ''),
                                    NULLIF(TRIM(learning_direction), ''), NULLIF(TRIM(default_course_id), ''),
                                    NULLIF(TRIM(learning_goals), '')) IS NOT NULL
                        OR EXISTS (
                            SELECT 1 FROM study_materials
                            WHERE study_materials.username = users.username
                            LIMIT 1
                        )
                        OR EXISTS (
                            SELECT 1 FROM learning_records
                            WHERE learning_records.user_id = users.id
                            LIMIT 1
                        )
                        OR EXISTS (
                            SELECT 1 FROM chat_sessions
                            WHERE chat_sessions.user_id = users.id
                            LIMIT 1
                        )
                      )
                    """
                )
            )

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

        if "qwen_used" in study_material_columns:
            conn.execute(
                text(
                    """
                    UPDATE study_materials
                    SET qwen_used = 0
                    WHERE qwen_used IS NULL
                    """
                )
            )

        if "file_size" in study_material_columns:
            conn.execute(
                text(
                    """
                    UPDATE study_materials
                    SET file_size = 0
                    WHERE file_size IS NULL
                    """
                )
            )

        if "updated_at" in study_material_columns:
            conn.execute(
                text(
                    """
                    UPDATE study_materials
                    SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
                    WHERE updated_at IS NULL
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

        course_progress_columns = get_existing_columns(conn, "course_progress")
        if "status" in course_progress_columns:
            conn.execute(
                text(
                    """
                    UPDATE course_progress
                    SET status = '未开始'
                    WHERE status IS NULL OR TRIM(status) = ''
                    """
                )
            )

        if "updated_at" in course_progress_columns:
            conn.execute(
                text(
                    """
                    UPDATE course_progress
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
