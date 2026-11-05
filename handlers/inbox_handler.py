"""In-app inbox channel: stores the notification in the user's inbox list in Redis.

The web dashboard reads this list and shows it to the signed-in user.
"""
import json
import logging
import time

import config

log = logging.getLogger("inbox")


def send(msg: dict, r) -> None:
    key = f"{config.INBOX_PREFIX}{msg['user']}"
    entry = {
        "id": msg["id"],
        "title": msg["title"],
        "body": msg["body"],
        "from": msg.get("from", "system"),
        "time": time.time(),
    }
    r.lpush(key, json.dumps(entry))
    r.ltrim(key, 0, config.INBOX_MAX - 1)  # keep only the newest messages
    log.info("Inbox notification stored for %s", msg["user"])
