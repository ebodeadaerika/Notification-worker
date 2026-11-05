"""Channel handlers. Each exposes send(msg) and raises an exception on failure."""
from handlers import email_handler, push_handler, sms_handler

HANDLERS = {
    "email": email_handler.send,
    "sms": sms_handler.send,
    "push": push_handler.send,
}
