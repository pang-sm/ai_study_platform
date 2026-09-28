"""Revoke every live auth session — SECURITY_S0.5 post-incident containment.

The SECURITY_S0 window let any authenticated learner run code on the production host, which
put ``app.db`` — and therefore ``auth_sessions.token_hash`` — within reach of a read
primitive. The raw session tokens are never persisted (only a SHA-256 hash is), so a stolen
hash is not directly replayable. But "a read primitive existed and the endpoint logged
nothing, so we cannot prove it was unused" is exactly the case where the conservative move
beats reasoning about hash strength under uncertainty.

Scope is deliberately one column: ``auth_sessions.revoked_at``. Users, passwords,
memberships, learning records and every other table are untouched. Idempotent — a second
run revokes nothing.

    DATABASE_URL=sqlite:////var/lib/ai_study_platform/app.db \
        python scripts/deploy/revoke_all_sessions.py

Exit codes:
    0  no session remains live
    1  sessions are still live after the update (the run did not achieve its goal)
    2  the script could not run (no DATABASE_URL)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))


def main() -> int:
    if not os.environ.get("DATABASE_URL"):
        print("[revoke] DATABASE_URL is required (never assume the default database)")
        return 2

    import models  # noqa: E402  (import after DATABASE_URL is in place)
    from database import SessionLocal  # noqa: E402

    db = SessionLocal()
    try:
        live = db.query(models.AuthSession).filter(models.AuthSession.revoked_at.is_(None))
        before = live.count()
        # Matches the application's own logout path: timezone-aware UTC into the same column.
        live.update({"revoked_at": datetime.now(timezone.utc)}, synchronize_session=False)
        db.commit()
        after = (
            db.query(models.AuthSession)
            .filter(models.AuthSession.revoked_at.is_(None))
            .count()
        )
    finally:
        db.close()

    print(f"[revoke] ACTIVE_SESSION_COUNT_BEFORE={before}")
    print(f"[revoke] ACTIVE_SESSION_COUNT_AFTER={after}")
    if after:
        print("[revoke] ERROR: live sessions remain")
        return 1
    print("[revoke] all sessions revoked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
