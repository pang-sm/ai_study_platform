"""SECURITY_S1A — upload storage containment.

The pre-fix sink built its directory from the *username* (``UPLOAD_ROOT / username``) with no
character validation, so a username containing ``..`` or a separator could place uploaded
bytes outside the upload root. These tests hold three separate contracts:

* the containment helper refuses structure, absolute forms and symlinked escapes;
* the file writer keys storage by the numeric user id, so no request-supplied string reaches
  the path at all — asserted on the filesystem, not on a status code;
* the normal product still works: Chinese usernames and filenames, and pre-existing uploads
  that live in the old username-keyed layout, must keep working.
"""
import secrets as pysecrets
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import database
import main
import models
from auth import hash_password
from conftest import register_and_login
from core.storage_paths import (
    StoragePathError,
    is_contained,
    safe_join_under_root,
    validate_segment,
)

UPLOAD_ROOT = main.UPLOAD_ROOT

# Usernames that must never become a path component. Chosen to be meaningful on both POSIX
# and Windows so the same matrix runs on the dev host and in CI.
HOSTILE_USERNAMES = [
    "../s1a_escape",
    "../../s1a_escape",
    "..\\s1a_escape",
    "..\\..\\s1a_escape",
    "nested/../../s1a_escape",
    "....//s1a_escape",
]

# Slash-like Unicode is NOT a path separator on either platform, so these values are ordinary
# names. They are asserted to stay contained rather than to be refused — a rejection here
# would be a product regression for Chinese usernames.
UNICODE_NAME_LIKE = ["\uff0fs1a_escape", "\u2215s1a_escape", "\u2044s1a_escape"]


def _insert_legacy_user(username: str) -> int:
    """Create a user row with an arbitrary username, bypassing registration validation.

    Registration now refuses these names, so this models an account that already existed
    before the fix — the only way the historical sink could have been reached.
    """
    db = database.SessionLocal()
    try:
        user = models.User(
            username=username,
            hashed_password=hash_password("secret123"),
            nickname="", avatar="", grade="", major="",
            onboarding_completed=False, learning_goals=None,
            email=f"s1a_{pysecrets.token_hex(6)}@example.test", email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def _legacy_target(username: str) -> Path:
    """Where the pre-fix code would have written: the username used as a path component."""
    return (UPLOAD_ROOT / username).resolve()


# ── the containment helper ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("segment", [
    "..", "../escape", "..\\escape", "nested/../escape", "a/b", "a\\b",
    "/absolute/path", "\\absolute\\path", "C:\\absolute\\path", "C:drive-relative",
    "", "   ", "\x00name", "a\x00b",
])
def test_structurally_unsafe_segments_are_refused(tmp_path, segment):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(StoragePathError):
        safe_join_under_root(root, segment)


@pytest.mark.parametrize("segment", ["..name", "中文目录", *UNICODE_NAME_LIKE])
def test_harmless_segments_are_accepted_and_stay_inside(tmp_path, segment):
    root = tmp_path / "root"
    root.mkdir()
    target = safe_join_under_root(root, segment, "file.txt")
    assert is_contained(root, target)
    assert target.parent.resolve().parent == root.resolve()


@pytest.mark.parametrize("segment", ["...", "name..", "name. "])
def test_trailing_dot_names_never_escape_even_when_the_platform_normalizes_them(tmp_path, segment):
    """Windows strips trailing dots and spaces, so `...` normalizes toward the parent.

    The contract is containment, not a particular verdict: the value is either refused
    outright or it stays inside the root. Either outcome is safe, and the test tolerates both
    so it means the same thing on POSIX (where the name is literal).
    """
    root = tmp_path / "root"
    root.mkdir()
    try:
        target = safe_join_under_root(root, segment, "file.txt")
    except StoragePathError:
        return  # refused — the safe outcome
    assert is_contained(root, target)


def test_containment_is_ancestry_not_text_prefix(tmp_path):
    """`/root2` starts with `/root` without living inside it — prefix matching would pass it."""
    root = tmp_path / "uploads"
    root.mkdir()
    sibling = tmp_path / "uploads2"
    sibling.mkdir()

    assert is_contained(root, root / "file.txt") is True
    assert is_contained(root, root) is True
    assert is_contained(root, sibling / "file.txt") is False
    assert is_contained(root, root / ".." / "uploads2" / "file.txt") is False


def test_symlinked_parent_that_escapes_the_root_is_refused(tmp_path):
    """resolve() follows the link, so a symlinked directory pointing outside is caught."""
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this host does not permit creating symlinks")

    with pytest.raises(StoragePathError):
        safe_join_under_root(root, "link", "file.txt")


def test_segment_validator_rejects_the_dot_and_empty_forms_directly():
    for bad in ("", " ", "..", ".", "/", "\\", "a/b", "C:x"):
        with pytest.raises(StoragePathError):
            validate_segment(bad)
    assert validate_segment("正常名字") == "正常名字"


# ── the writer: storage identity is the user id ────────────────────────────────────

@pytest.mark.parametrize("username", HOSTILE_USERNAMES + UNICODE_NAME_LIKE)
def test_hostile_username_cannot_place_bytes_outside_the_upload_root(username):
    """The original exploit, driven through the writer itself."""
    user_id = _insert_legacy_user(username)
    escape = _legacy_target(username)
    assert not escape.exists(), "precondition: nothing outside the root yet"

    db = database.SessionLocal()
    try:
        stored = main.save_uploaded_file(db.get(models.User, user_id), "notes.txt", b"S1A_BODY")
    finally:
        db.close()

    written = (main.BASE_DIR / stored).resolve()
    assert written.is_file(), "the upload must actually have been written"
    assert is_contained(UPLOAD_ROOT, written), f"escaped the upload root: {written}"
    assert str(user_id) in written.parts, "storage must be keyed by the internal user id"
    assert not escape.exists(), f"the pre-fix escape target exists: {escape}"


def test_writer_refuses_a_user_without_an_internal_id():
    class _Unsaved:
        id = None
        username = "whatever"

    with pytest.raises(Exception):
        main.save_uploaded_file(_Unsaved(), "a.txt", b"x")


def test_chinese_username_and_filename_still_work():
    user_id = _insert_legacy_user("学习者甲")
    db = database.SessionLocal()
    try:
        user = db.get(models.User, user_id)
        stored = main.save_uploaded_file(user, "数据结构笔记.txt", "正文".encode())
    finally:
        db.close()

    written = (main.BASE_DIR / stored).resolve()
    assert written.is_file()
    assert is_contained(UPLOAD_ROOT, written)
    assert "学习者甲" not in written.parts, "the username must not appear as a path component"


# ── the legacy route: no escape, whatever it returns ───────────────────────────────

def test_chat_upload_never_writes_outside_the_upload_root(client: TestClient):
    """Asserted on the filesystem, not on a status code.

    ``/chat/upload`` currently raises before the write (``handle_material_upload`` references
    an undefined name), so the historical traversal was latent rather than live. This test
    keeps its meaning either way: repairing that route must not re-open the escape.
    """
    hostile = "../s1a_route_escape"
    _insert_legacy_user(hostile)
    login = client.post("/login", json={"username": hostile, "password": "secret123"})
    assert login.status_code == 200, login.text

    escape = _legacy_target(hostile)
    assert not escape.exists()

    # The route raises today; the assertion of interest is what reached the filesystem.
    forgiving = TestClient(client.app, raise_server_exceptions=False)
    try:
        forgiving.post(
            "/chat/upload",
            data={"message": "hi"},
            files={"file": ("a.txt", b"hello world", "text/plain")},
        )
    finally:
        forgiving.close()

    assert not escape.exists(), f"the route wrote outside the upload root: {escape}"


# ── registration validation (defense in depth) ─────────────────────────────────────

def _register(client: TestClient, username: str) -> "object":
    email = f"s1a_reg_{pysecrets.token_hex(6)}@example.test"
    codes: list[str] = []

    def capture(_recipient: str, code: str) -> bool:
        codes.append(code)
        return True

    from unittest.mock import patch

    with patch.object(main, "_send_email_code", side_effect=capture):
        client.post("/auth/register/send-code", json={"email": email})
        client.post("/auth/register/verify-code", json={"email": email, "code": codes[-1]})
    return client.post("/register", json={"username": username, "password": "secret123", "email": email})


@pytest.mark.parametrize("username", [
    "../escape", "..\\escape", "a/b", "a\\b", "a\x00b", "", "   ", "x" * 51,
])
def test_registration_refuses_unsafe_usernames(client: TestClient, username):
    assert _register(client, username).status_code == 400


def test_registration_still_accepts_chinese_and_ordinary_usernames(client: TestClient):
    assert _register(client, "学习者乙").status_code == 200
    assert _register(client, "s1a-ordinary_user.1").status_code == 200


# ── the live route and legacy compatibility ────────────────────────────────────────

def test_live_upload_stores_contained_and_keeps_the_display_name(client: TestClient):
    register_and_login(client, "s1a-cn-upload")
    response = client.post(
        "/personal-materials/upload",
        files={"file": ("数据结构笔记.txt", "正文内容".encode(), "text/plain")},
    )
    assert response.status_code == 200, response.text

    db = database.SessionLocal()
    try:
        material = db.get(models.StudyMaterial, response.json()["id"])
        assert material is not None
        assert material.original_filename == "数据结构笔记.txt"
        stored = (main.BASE_DIR / material.file_path).resolve()
        assert stored.is_file()
        assert is_contained(UPLOAD_ROOT, stored)
    finally:
        db.close()


def test_pre_existing_username_keyed_upload_is_still_readable():
    """Compatibility: files written before the fix keep resolving, by their stored path.

    The read gate never rebuilds a path from a request value — it resolves the path recorded
    in the database — so changing the write layout does not orphan existing uploads.
    """
    legacy_dir = UPLOAD_ROOT / "s1a_legacy_user"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_file = legacy_dir / "old_upload.txt"
    legacy_file.write_text("legacy body", encoding="utf-8")
    relative = legacy_file.relative_to(main.BASE_DIR).as_posix()

    resolved = main.resolve_stored_file_path(relative)
    assert resolved.resolve() == legacy_file.resolve()
    assert is_contained(UPLOAD_ROOT, resolved)


def test_read_gate_refuses_a_path_outside_the_upload_root():
    """The same gate must keep rejecting an escaping stored path (fail closed)."""
    with pytest.raises(Exception):
        main.resolve_stored_file_path("../outside.txt")


def test_cross_user_cannot_download_preview_or_delete(client: TestClient):
    register_and_login(client, "s1a-owner")
    uploaded = client.post(
        "/personal-materials/upload",
        files={"file": ("private.txt", b"S1A_PRIVATE_BODY", "text/plain")},
    )
    material_id = uploaded.json()["id"]

    other = TestClient(client.app)
    try:
        register_and_login(other, "s1a-other")
        assert other.get(f"/materials/{material_id}/download").status_code == 404
        assert other.get(f"/materials/{material_id}/preview").status_code == 404
        assert other.delete(f"/personal-materials/{material_id}").status_code == 404
        assert other.delete(f"/library/materials/{material_id}").status_code == 404
    finally:
        other.close()

    # The owner still has it.
    assert client.get(f"/materials/{material_id}/download").status_code == 200
