from pathlib import Path
import shutil
import sqlite3
import sys
from datetime import datetime


DB_PATH = Path(__file__).resolve().parents[1] / "app.db"
PROFILE_COLUMNS = ("nickname", "grade", "major", "avatar")


def main():
    if not DB_PATH.exists():
        print(f"数据库文件不存在，已停止：{DB_PATH}")
        return 1

    backup_path = DB_PATH.with_suffix(
        DB_PATH.suffix + f".bak-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute("PRAGMA table_info(users)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        if "nickname" not in existing_columns:
            conn.execute("ALTER TABLE users ADD COLUMN nickname VARCHAR(30)")

        if "avatar" not in existing_columns:
            conn.execute("ALTER TABLE users ADD COLUMN avatar VARCHAR(50)")

        set_clause = ", ".join(f"{column} = ''" for column in PROFILE_COLUMNS)
        conn.execute(f"UPDATE users SET {set_clause}")
        conn.commit()
    finally:
        conn.close()

    print(f"已备份数据库：{backup_path}")
    print("已清空用户个人资料字段：nickname, grade, major, avatar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
