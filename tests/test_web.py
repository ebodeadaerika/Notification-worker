import json
import sys
from pathlib import Path

import fakeredis
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import worker  # noqa: E402
from app import create_app  # noqa: E402


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def client(r):
    app = create_app(redis_client=r)
    app.config["TESTING"] = True
    return app.test_client()


def post(client, url, **data):
    # Like a browser: the form carries the CSRF token the server put in the session.
    # (The session is reset on login/logout, and the next page load issues a new token.)
    with client.session_transaction() as s:
        token = s.setdefault("csrf", "test-token")
    return client.post(url, data={"csrf": token, **data})


def signup(client, name="Ada", email="ada@example.com", password="password123"):
    return post(client, "/register", name=name, email=email, password=password)


def run_worker_once(r):
    _, raw = r.brpop(config.QUEUE_NAME)
    worker.process_one(r, raw)


def test_dashboard_requires_login(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]
    assert client.get("/api/inbox").status_code == 302


def test_post_without_csrf_token_is_rejected(client):
    assert client.post("/login", data={"email": "a@b.c", "password": "x"}).status_code == 400


def test_signup_logs_in_and_shows_dashboard(client):
    assert signup(client).status_code == 302
    page = client.get("/dashboard")
    assert page.status_code == 200 and b"Hello, Ada" in page.data


def test_password_is_stored_hashed(client, r):
    signup(client)
    stored = r.hget("user:ada@example.com", "password_hash")
    assert stored and "password123" not in stored


def test_duplicate_email_rejected(client):
    signup(client)
    assert signup(client).status_code == 400


def test_weak_password_rejected(client):
    assert signup(client, password="short").status_code == 400


def test_login_wrong_password_then_correct(client):
    signup(client)
    post(client, "/logout")
    assert post(client, "/login", email="ada@example.com", password="nope").status_code == 401
    assert post(client, "/login", email="ada@example.com", password="password123").status_code == 302


def test_account_locks_after_repeated_failures(client):
    signup(client)
    post(client, "/logout")
    for _ in range(config.MAX_LOGIN_ATTEMPTS):
        post(client, "/login", email="ada@example.com", password="bad")
    # even the right password is refused while locked
    assert post(client, "/login", email="ada@example.com", password="password123").status_code == 401


def test_full_flow_send_to_self_appears_in_inbox(client, r):
    signup(client)
    post(client, "/send", to="ada@example.com", title="Hello", body="World")
    run_worker_once(r)
    items = client.get("/api/inbox").get_json()
    assert [(i["title"], i["body"], i["from"]) for i in items] == [("Hello", "World", "ada@example.com")]


def test_cannot_send_to_someone_without_account(client, r):
    signup(client)
    post(client, "/send", to="ghost@example.com", title="Hi", body="x")
    assert r.llen(config.QUEUE_NAME) == 0  # never even queued


def test_worker_refuses_unregistered_recipient_even_if_queued_directly(r):
    r.lpush(config.QUEUE_NAME, json.dumps({"type": "inbox", "user": "ghost@example.com", "title": "t", "body": "b"}))
    run_worker_once(r)
    assert r.llen(config.DEAD_LETTER_QUEUE) == 1


def test_users_only_see_their_own_inbox(client, r):
    signup(client, name="Ada", email="ada@example.com")
    post(client, "/logout")
    signup(client, name="Bob", email="bob@example.com")
    post(client, "/send", to="ada@example.com", title="For Ada", body="private")
    run_worker_once(r)
    assert client.get("/api/inbox").get_json() == []  # Bob sees nothing
    post(client, "/logout")
    post(client, "/login", email="ada@example.com", password="password123")
    assert [i["title"] for i in client.get("/api/inbox").get_json()] == ["For Ada"]


def test_html_in_message_is_escaped(client, r):
    signup(client)
    post(client, "/send", to="ada@example.com", title="<script>alert(1)</script>", body="b")
    run_worker_once(r)
    page = client.get("/dashboard").data
    assert b"<script>alert(1)</script>" not in page
    assert b"&lt;script&gt;" in page
