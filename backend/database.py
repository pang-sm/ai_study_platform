from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


PROFILE_COLUMNS = {
    "nickname": "VARCHAR(30)",
    "avatar": "VARCHAR(50)",
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_user_profile_schema():
    with engine.begin() as conn:
        existing_columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()
        }

        for column_name, column_type in PROFILE_COLUMNS.items():
            if column_name not in existing_columns:
                conn.execute(
                    text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
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
            models.ChatSession.user_id == user_id
        )
        .first()
    )

    if not conversation:
        return None

    conversation.title = title
    db.commit()
    db.refresh(conversation)
    return conversation
