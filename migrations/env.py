"""Alembic migration environment for the zhixue-ai product backend.

Resolves the database URL from DATABASE_URL (env) or backend/database.py's default
(backend/app.db). Registers the full SQLAlchemy metadata (including the Data Plane
models) so ``target_metadata`` is authoritative for autogenerate/compare.
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure backend/ is importable (the app imports modules relative to backend/).
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Register all models on Base.metadata (including data_plane LearningEvent/Model* tables).
from database import Base, DATABASE_URL  # noqa: E402
import data_plane.models  # noqa: E402,F401  — registers Data Plane tables

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    return os.getenv("DATABASE_URL") or DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-safe ALTER support
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": _database_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
