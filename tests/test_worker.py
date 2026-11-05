import json
import sys
from pathlib import Path

import fakeredis
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import users  # noqa: E402
import worker  # noqa: E402
from message import InvalidMessage, validate  # noqa: E402

USER = "ada@example.com"


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)  # no real waiting in tests


@pytest.fixture
def r():
    conn = fakeredis.FakeRedis(decode_responses=True)
    users.create_user(conn, "Ada", USER, "password123")  # a registered user
    return conn


def test_validate_accepts_good_email_and_adds_id():
    msg = validate({"type": "email", "user": USER, "to": "a@b.c", "subject": "s", "body": "b"})
    assert "id" in msg


def test_validate_rejects_unknown_type():
    with pytest.raises(InvalidMessage):
        validate({"type": "fax", "user": USER, "to": "x", "body": "y"})


def test_validate_rejects_missing_fields():
    with pytest.raises(InvalidMessage):
        validate({"type": "sms", "user": USER, "to": "123"})


def test_validate_requires_a_user():
    with pytest.raises(InvalidMessage):
        validate({"type": "inbox", "title": "t", "body": "b"})


def test_successful_sms_marks_sent(r):
    worker.process_one(r, json.dumps({"id": "1", "type": "sms", "user": USER, "to": "123", "body": "hi"}))
    assert r.hget("notification:1", "status") == "sent"
    assert r.llen(config.DEAD_LETTER_QUEUE) == 0


def test_inbox_message_lands_in_users_inbox(r):
    worker.process_one(r, json.dumps({"id": "3", "type": "inbox", "user": USER, "title": "Hi", "body": "there"}))
    items = [json.loads(i) for i in r.lrange(f"{config.INBOX_PREFIX}{USER}", 0, -1)]
    assert [i["title"] for i in items] == ["Hi"]


def test_unregistered_recipient_is_rejected(r):
    worker.process_one(r, json.dumps({"id": "4", "type": "inbox", "user": "ghost@example.com", "title": "x", "body": "y"}))
    assert r.hget("notification:4", "status") == "failed"
    assert r.llen(config.DEAD_LETTER_QUEUE) == 1
    assert r.llen(f"{config.INBOX_PREFIX}ghost@example.com") == 0


def test_failing_message_retries_then_dead_letters(r):
    raw = json.dumps({"id": "2", "type": "sms", "user": USER, "to": "123", "body": "x", "simulate_failure": True})
    worker.process_one(r, raw)
    assert r.hget("notification:2", "status") == "failed"
    assert r.hget("notification:2", "attempts") == str(config.MAX_RETRIES)
    assert r.llen(config.DEAD_LETTER_QUEUE) == 1


def test_invalid_message_goes_straight_to_dead_letter(r):
    worker.process_one(r, json.dumps({"type": "fax"}))
    assert r.llen(config.DEAD_LETTER_QUEUE) == 1


def test_garbage_json_goes_to_dead_letter(r):
    worker.process_one(r, "not json at all")
    assert r.llen(config.DEAD_LETTER_QUEUE) == 1
