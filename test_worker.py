import json
import sys
from pathlib import Path

import fakeredis
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import worker  # noqa: E402
from message import InvalidMessage, validate  # noqa: E402


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)  # no real waiting in tests


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


def test_validate_accepts_good_email_and_adds_id():
    msg = validate({"type": "email", "to": "a@b.c", "subject": "s", "body": "b"})
    assert "id" in msg


def test_validate_rejects_unknown_type():
    with pytest.raises(InvalidMessage):
        validate({"type": "fax", "to": "x", "body": "y"})


def test_validate_rejects_missing_fields():
    with pytest.raises(InvalidMessage):
        validate({"type": "sms", "to": "123"})


def test_successful_sms_marks_sent(r):
    worker.process_one(r, json.dumps({"id": "1", "type": "sms", "to": "123", "body": "hi"}))
    assert r.hget("notification:1", "status") == "sent"
    assert r.llen(config.DEAD_LETTER_QUEUE) == 0


def test_failing_message_retries_then_dead_letters(r):
    raw = json.dumps({"id": "2", "type": "sms", "to": "123", "body": "x", "simulate_failure": True})
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
