"""Producer: puts test notifications into the queue (command-line version).

Usage:
    python producer.py demo <user_email>     # inbox + email + sms + push for a registered user
    python producer.py fail <user_email>     # always fails (shows retries + dead-letter)
    python producer.py unregistered          # recipient has no account (shows rejection)
    python producer.py invalid               # malformed message (shows validation)
    python producer.py status <id>           # check a notification's status
"""
import json
import sys
import uuid

import redis

import config

r = redis.from_url(config.REDIS_URL, decode_responses=True)


def enqueue(msg: dict) -> str:
    msg.setdefault("id", str(uuid.uuid4()))
    r.lpush(config.QUEUE_NAME, json.dumps(msg))
    r.hset(f"{config.STATUS_PREFIX}{msg['id']}", mapping={"status": "queued", "type": msg.get("type", "?")})
    print(f"queued {msg.get('type')} id={msg['id']}")
    return msg["id"]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    user = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "demo" and user:
        enqueue({"type": "inbox", "user": user, "title": "Welcome", "body": "Your inbox notification works!", "from": "producer"})
        enqueue({"type": "email", "user": user, "to": user, "subject": "Welcome", "body": "Hello from the worker!"})
        enqueue({"type": "sms", "user": user, "to": "+237600000000", "body": "Your code is 123456"})
        enqueue({"type": "push", "user": user, "to": "device-token-abc", "title": "New message", "body": "You have a notification"})
    elif cmd == "fail" and user:
        enqueue({"type": "sms", "user": user, "to": "+237600000000", "body": "this will fail", "simulate_failure": True})
    elif cmd == "unregistered":
        enqueue({"type": "inbox", "user": "nobody@example.com", "title": "Hi", "body": "No account for this address"})
    elif cmd == "invalid":
        enqueue({"type": "telegram", "to": "someone", "body": "unsupported channel"})
    elif cmd == "status" and user:
        print(r.hgetall(f"{config.STATUS_PREFIX}{user}"))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
