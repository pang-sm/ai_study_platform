from fastapi.testclient import TestClient

from conftest import register_and_login


def test_protected_api_requires_server_session(client: TestClient):
    response = client.get("/membership/summary", params={"username": "someone"})
    assert response.status_code == 401


def test_login_cookie_and_me(client: TestClient):
    user = register_and_login(client, "auth-owner")
    response = client.post("/me", json={"username": "auth-owner"})
    assert response.status_code == 200
    assert response.json()["user"]["username"] == user["username"]


def test_wrong_password_and_invalid_session(client: TestClient):
    register = client.post("/register", json={"username": "wrong-password", "password": "secret123"})
    assert register.status_code == 200
    client.cookies.clear()
    wrong = client.post("/login", json={"username": "wrong-password", "password": "bad-password"})
    assert wrong.status_code == 400

    client.cookies.set("ai_session", "not-a-real-session")
    invalid = client.post("/me", json={})
    assert invalid.status_code == 401


def test_users_cannot_switch_identity_with_username(client):
    register_and_login(client, "owner-a")
    other = TestClient(client.app)
    try:
        register_and_login(other, "owner-b")
        denied = client.get("/membership/summary", params={"username": "owner-b"})
        assert denied.status_code == 403
        denied_me = client.post("/me", json={"username": "owner-b"})
        assert denied_me.status_code == 403
    finally:
        other.close()


def test_user_scoped_api_families_reject_cross_user_identity(client: TestClient):
    register_and_login(client, "scope-a")
    other = TestClient(client.app)
    try:
        register_and_login(other, "scope-b")
        a_params = {"username": "scope-a"}

        for path, params in (
            ("/membership/plans", a_params),
            ("/membership/recommendation", a_params),
            ("/course-learning/status", a_params),
            ("/course-progress", {**a_params, "course": "data_structure"}),
            ("/course-dashboard", {**a_params, "course": "data_structure"}),
            ("/course-preferences", {**a_params, "course_id": "data_structure"}),
            ("/programming/home", a_params),
            ("/programming/file-library", a_params),
            ("/programming/exercises", a_params),
            ("/code/progress", a_params),
            ("/code/sessions", a_params),
        ):
            response = other.get(path, params=params)
            assert response.status_code == 403, (path, response.status_code, response.text)

        execute = other.post(
            "/code/execute",
            json={"username": "scope-a", "language": "python", "code": "print(1)"},
        )
        assert execute.status_code == 403

        redeem = other.post(
            "/membership/redeem?username=scope-a",
            json={"code": "not-a-real-code"},
        )
        assert redeem.status_code == 403
    finally:
        other.close()


def test_programming_project_isolated_between_users(client):
    register_and_login(client, "programming-a")
    created = client.post("/code/projects", json={
        "username": "programming-a",
        "name": "A project",
        "language": "Python",
        "course_id": "programming",
    })
    assert created.status_code == 200, created.text
    project_id = created.json()["project"]["id"]

    other = TestClient(client.app)
    try:
        register_and_login(other, "programming-b")
        response = other.get(f"/code/projects/{project_id}", params={"username": "programming-b"})
        assert response.status_code == 404
        changed = other.put(f"/code/projects/{project_id}", json={"username": "programming-b", "name": "hijack"})
        assert changed.status_code == 404
    finally:
        other.close()
