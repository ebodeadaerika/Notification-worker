"""Producer: puts test notifications into the queue.

Usage:
    python producer.py demo            # one email, one sms, one push
    python producer.py fail            # a message that always fails (shows retries + dead-letter)
    python producer.py invalid         # a malformed message (shows validation)
    python producer.py status <id>     # check a notification's status
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
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"

    if cmd == "demo":
        enqueue({"type": "email", "to": "student@example.com", "subject": "Welcome", "body": "Hello from the worker!"})
        enqueue({"type": "sms", "to": "+237600000000", "body": "Your code is 123456"})
        enqueue({"type": "push", "to": "device-token-abc", "title": "New message", "body": "You have a notification"})
    elif cmd == "fail":
        enqueue({"type": "sms", "to": "+237600000000", "body": "this will fail", "simulate_failure": True})
    elif cmd == "invalid":
        enqueue({"type": "telegram", "to": "someone", "body": "unsupported channel"})
    elif cmd == "status" and len(sys.argv) > 2:
        print(r.hgetall(f"{config.STATUS_PREFIX}{sys.argv[2]}"))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
