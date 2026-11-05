"""Channel handlers. Each exposes send(msg, r) and raises an exception on failure."""
from handlers import email_handler, inbox_handler, push_handler, sms_handler

HANDLERS = {
    "inbox": inbox_handler.send,
    "email": email_handler.send,
    "sms": sms_handler.send,
    "push": push_handler.send,
}
