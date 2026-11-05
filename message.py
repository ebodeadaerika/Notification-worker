"""Message format and validation."""
import uuid

import config

VALID_TYPES = {"inbox", "email", "sms", "push"}

# Fields every message of a given type must contain.
REQUIRED_FIELDS = {
    "inbox": ["title", "body"],
    "email": ["to", "subject", "body"],
    "sms": ["to", "body"],
    "push": ["to", "title", "body"],  # "to" = device token or user id
}


class InvalidMessage(Exception):
    """Raised when a message is malformed. Retrying will never fix it."""


def validate(msg: dict) -> dict:
    if not isinstance(msg, dict):
        raise InvalidMessage("message must be a JSON object")

    msg_type = msg.get("type")
    if msg_type not in VALID_TYPES:
        raise InvalidMessage(f"unknown type {msg_type!r}, expected one of {sorted(VALID_TYPES)}")

    required = list(REQUIRED_FIELDS[msg_type])
    if config.REQUIRE_REGISTERED_USER:
        required.append("user")  # the account that should receive this notification
    missing = [f for f in required if not msg.get(f)]
    if missing:
        raise InvalidMessage(f"missing fields for {msg_type}: {missing}")

    if msg.get("user"):
        msg["user"] = str(msg["user"]).strip().lower()

    msg.setdefault("id", str(uuid.uuid4()))
    return msg
