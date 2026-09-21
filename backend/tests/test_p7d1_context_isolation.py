"""P7-D.1 — the course space and the programming space may not write into each other.

The reproduced defect: `POST /programming/onboarding` stored the chosen LANGUAGE in
`users.default_course_id`, and the course space reads that column as a course source. Setting up
`C++` therefore made a course called `C++` appear in the course space. The same endpoint also
stamped `learning_direction` and `users.onboarding_detail` with programming state that no
programming reader consults.

These tests pin the boundary from both directions: programming may not move the course context,
and the course onboarding read contract may not describe a different course set from the one the
course space shows.
"""
import json

from fastapi.testclient import TestClient

from conftest import register_and_login
from database import SessionLocal
import models


# ------------------------------------------------------------------ helpers


def _user(username: str) -> models.User:
    db = SessionLocal()
    try:
        return db.query(models.User).filter(models.User.username == username).one()
    finally:
        db.close()


def _track(username: str, track_type: str) -> models.UserLearningTrack | None:
    db = SessionLocal()
    try:
        return (
            db.query(models.UserLearningTrack)
            .join(models.User, models.User.id == models.UserLearningTrack.user_id)
            .filter(
                models.User.username == username,
                models.UserLearningTrack.track_type == track_type,
            )
            .first()
        )
    finally:
        db.close()


def _programming_onboarding(client: TestClient, languages: list[str], level: str = "基础"):
    return client.post(
        "/programming/onboarding",
        json={
            "main_language": languages[0] if languages else "",
            "selected_languages": languages,
            "level": level,
            "problems": [],
            "onboarding_completed": True,
        },
    )


def _course_onboarding(client: TestClient, courses: list[str]):
    return client.post(
        "/course-learning/onboarding",
        json={
            "major": "计算机科学与技术",
            "grade": "大三",
            "semester": "上学期",
            "selected_courses": courses,
            "material_types": [],
            "onboarding_completed": True,
        },
    )


def _course_context(client: TestClient, username: str) -> dict:
    """Everything the course space is made of, as the product reports it.

    `is_active` is deliberately NOT part of this: which direction is currently active is an
    account-level property that onboarding is allowed to move (and an existing test pins that
    behaviour), while the course CONTEXT — the declared courses, the account-level course fields,
    and the course track's stored detail — is what must not move.
    """
    user = _user(username)
    track = _track(username, "university_course")
    courses = client.get("/course-learning/courses").json()
    onboarding = client.get("/course-learning/onboarding").json()
    return {
        "default_course_id": user.default_course_id,
        "focus_courses": user.focus_courses,
        "course_track_detail": track.onboarding_detail_json if track else None,
        # The learner-visible lists, with the per-row timestamps dropped: the rows are the fact.
        "course_names": [item["course_name"] for item in courses["courses"]],
        "onboarding_selected": onboarding["selected_courses"],
    }


def _warm(client: TestClient, username: str) -> dict:
    """Read the course context twice, then return it.

    `GET /course-learning/courses` creates a preference row for a course the first time it is
    asked about, so the first read of a fresh course is not yet the steady state.
    """
    _course_context(client, username)
    return _course_context(client, username)


# ------------------------------------------------- A. programming → course


def test_programming_onboarding_does_not_change_the_current_course(client: TestClient):
    username = "p7d1-current-course"
    register_and_login(client, username)
    assert _course_onboarding(client, ["数据结构"]).status_code == 200

    before = _user(username).default_course_id
    assert before == "数据结构", "the course setup must have established a current course"

    response = _programming_onboarding(client, ["C++"])
    assert response.status_code == 200, response.text

    # Semantic: it is still the declared course. Byte-for-byte: nothing rewrote it at all.
    assert _user(username).default_course_id == before


def test_a_legitimate_course_survives_programming_onboarding(client: TestClient):
    username = "p7d1-course-survives"
    register_and_login(client, username)
    assert _course_onboarding(client, ["数据结构", "操作系统"]).status_code == 200
    before = _warm(client, username)

    assert _programming_onboarding(client, ["Python"]).status_code == 200

    assert _warm(client, username) == before


def test_the_configured_language_never_appears_as_a_course(client: TestClient):
    """One learner per language, because the language is what used to leak through."""
    for index, language in enumerate(["C++", "Python", "C", "Java"]):
        username = f"p7d1-language-only-{index}"
        register_and_login(client, username)

        # Programmed FIRST, with no course declared at all: this is the exact setup that produced
        # the phantom course.
        assert _programming_onboarding(client, [language]).status_code == 200

        courses = client.get("/course-learning/courses").json()
        assert courses["courses"] == [], f"{language} became a course"
        assert courses["total"] == 0
        assert client.get("/course-learning/onboarding").json()["selected_courses"] == []


def test_programming_onboarding_writes_only_the_programming_track(client: TestClient):
    username = "p7d1-writes-only-track"
    register_and_login(client, username)

    assert _programming_onboarding(client, ["C++"], level="进阶").status_code == 200

    # The language lives in the track's own detail — the ONE place every programming reader
    # looks.
    track = _track(username, "programming")
    assert track is not None
    detail = json.loads(track.onboarding_detail_json)
    assert detail["selected_languages"] == ["C++"]
    assert detail["main_language"] == "C++"
    assert detail["level"] == "advanced"
    assert detail["programming_onboarding_completed"] is True

    # ...and nowhere on the account row. This learner declared no course, so those fields start
    # empty — and programming setup must not be the thing that fills them.
    user_after = _user(username)
    assert not (user_after.default_course_id or ""), "the language must not be stored as a course"
    assert not (user_after.learning_direction or ""), "programming state must not fill a profile field"
    assert not (user_after.onboarding_detail or ""), "programming state must not fill a profile field"
    # The one account-level write that IS intended, and is kept.
    assert user_after.onboarding_completed is True

    # The programming space still reports the declared context, from the track.
    payload = client.get("/programming/onboarding").json()
    assert payload["selected_languages"] == ["C++"]
    assert payload["onboarding_completed"] is True


def test_programming_state_still_reads_its_own_languages(client: TestClient):
    """The fix must not have removed the only persistence programming actually needs."""
    username = "p7d1-programming-still-works"
    register_and_login(client, username)
    assert _programming_onboarding(client, ["Python", "Java"]).status_code == 200

    state = client.get("/programming/state").json()
    assert state["languages"] == ["Python", "Java"]
    assert state["current_language"] == "Python"
    assert state["onboarding_completed"] is True


# -------------------------------------------------- B. read contract unity


def test_course_onboarding_reads_the_same_courses_the_space_lists(client: TestClient):
    username = "p7d1-read-agrees"
    register_and_login(client, username)
    assert _course_onboarding(client, ["数据结构", "计算机网络"]).status_code == 200

    listing = [item["course_name"] for item in client.get("/course-learning/courses").json()["courses"]]
    onboarding = client.get("/course-learning/onboarding").json()["selected_courses"]

    assert onboarding == listing
    assert set(onboarding) == {"数据结构", "计算机网络"}


def test_a_profile_backed_course_appears_in_the_onboarding_editor(client: TestClient):
    """The reproduced read inconsistency: courses the space showed, the editor did not."""
    username = "p7d1-profile-backed"
    register_and_login(client, username)
    updated = client.put(
        "/me/profile",
        json={"focus_courses": "数据结构、操作系统"},
    )
    assert updated.status_code == 200, updated.text

    listing = [item["course_name"] for item in client.get("/course-learning/courses").json()["courses"]]
    onboarding = client.get("/course-learning/onboarding").json()

    assert set(listing) == {"数据结构", "操作系统"}
    # The editor is offered the same set the space is showing, so an empty editor over a
    # non-empty space is no longer possible.
    assert onboarding["selected_courses"] == listing


def test_a_course_goal_is_readable_under_either_stored_key(client: TestClient):
    """Two writers key the same fact differently; a reader has to accept both."""
    username = "p7d1-goal-keys"
    register_and_login(client, username)
    assert _course_onboarding(client, ["数据结构"]).status_code == 200

    # The per-course settings route stores the goal under the CANONICAL course identity.
    patched = client.patch(
        "/course-learning/courses/数据结构/settings",
        json={"primary_mode": "exam"},
    )
    assert patched.status_code == 200, patched.text

    onboarding = client.get("/course-learning/onboarding").json()
    assert onboarding["selected_courses"] == ["数据结构"]
    assert onboarding["course_goals"] == {"数据结构": "考前突击"}


def test_a_course_with_no_stored_goal_reports_the_default_the_writer_uses(client: TestClient):
    username = "p7d1-goal-default"
    register_and_login(client, username)
    assert _course_onboarding(client, ["数据结构"]).status_code == 200

    onboarding = client.get("/course-learning/onboarding").json()
    assert onboarding["course_goals"] == {"数据结构": "平日学习"}


def test_course_onboarding_update_still_persists(client: TestClient):
    username = "p7d1-course-update"
    register_and_login(client, username)
    assert _course_onboarding(client, ["数据结构"]).status_code == 200
    assert _course_onboarding(client, ["数据结构", "操作系统"]).status_code == 200

    onboarding = client.get("/course-learning/onboarding").json()
    assert onboarding["selected_courses"] == ["数据结构", "操作系统"]
    assert onboarding["major"] == "计算机科学与技术"
    assert onboarding["grade"] == "大三"

    # The account row the course flow owns is written too, and still agrees.
    user = _user(username)
    assert user.focus_courses == "数据结构、操作系统"
    assert user.default_course_id == "数据结构"


# ------------------------------------------------------- cross-user / cross-space


def test_programming_setup_does_not_touch_another_learners_course_context(client: TestClient):
    owner = "p7d1-cross-user-owner"
    other = "p7d1-cross-user-other"
    register_and_login(client, owner)
    assert _course_onboarding(client, ["数据结构"]).status_code == 200
    before = _warm(client, owner)

    register_and_login(client, other)
    assert _programming_onboarding(client, ["C++"]).status_code == 200
    assert client.get("/course-learning/courses").json()["courses"] == []

    # Back to the owner: their course context is exactly as it was.
    assert client.post("/login", json={"username": owner, "password": "secret123"}).status_code == 200
    assert _warm(client, owner) == before


def test_programming_and_course_context_are_independent_per_learner(client: TestClient):
    username = "p7d1-independent"
    register_and_login(client, username)
    assert _course_onboarding(client, ["数据结构"]).status_code == 200
    assert _programming_onboarding(client, ["Java"]).status_code == 200

    # One account, two spaces, two vocabularies, no sharing.
    assert client.get("/course-learning/onboarding").json()["selected_courses"] == ["数据结构"]
    assert client.get("/programming/onboarding").json()["selected_languages"] == ["Java"]
    assert _user(username).default_course_id == "数据结构"


# ------------------------------------------------ legacy rows written before the fix


def _force_legacy_language_as_course(username: str, language: str) -> None:
    """Write the pre-fix state directly, to model an account the old code already stamped.

    This is NOT a migration and is not applied to any real database: it reproduces, in a test,
    what `POST /programming/onboarding` used to leave behind, so the decision about those rows
    can be asserted instead of described.
    """
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).one()
        user.default_course_id = language
        db.commit()
    finally:
        db.close()


def test_a_legacy_polluted_row_is_reported_as_a_course_not_guessed_away(client: TestClient):
    """No auto-migration: an unprovable stored fact is kept and shown, not silently rewritten.

    The value could have come from the old programming write or from a learner who really typed
    it; the data alone cannot tell the two apart, so nothing here decides for them.
    """
    username = "p7d1-legacy-polluted"
    register_and_login(client, username)
    _force_legacy_language_as_course(username, "C++")

    assert [item["course_name"] for item in client.get("/course-learning/courses").json()["courses"]] == ["C++"]
    assert client.get("/course-learning/onboarding").json()["selected_courses"] == ["C++"]


def test_declaring_a_real_course_repairs_a_legacy_polluted_row(client: TestClient):
    """The repair is the product's own onboarding, not a migration.

    `POST /course-learning/onboarding` is what the setup screen calls, and it writes the declared
    courses to the course track — which is the source the course space reads FIRST. So a learner
    who declares one real course stops seeing the phantom, with no data rewrite and no guessing
    about where the old value came from.
    """
    username = "p7d1-legacy-repair"
    register_and_login(client, username)
    _force_legacy_language_as_course(username, "C++")

    assert _course_onboarding(client, ["数据结构"]).status_code == 200

    assert [item["course_name"] for item in client.get("/course-learning/courses").json()["courses"]] == ["数据结构"]
    assert client.get("/course-learning/onboarding").json()["selected_courses"] == ["数据结构"]
    assert _user(username).default_course_id == "数据结构"
