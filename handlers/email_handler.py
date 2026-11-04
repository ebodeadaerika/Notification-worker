"""Email channel: real SMTP, or a mock that only logs."""
import logging
import smtplib
from email.message import EmailMessage

import config

log = logging.getLogger("email")


def send(msg: dict) -> None:
    if config.EMAIL_MODE == "mock":
        log.info("[MOCK EMAIL] to=%s subject=%s", msg["to"], msg["subject"])
        return

    email = EmailMessage()
    email["From"] = config.EMAIL_FROM
    email["To"] = msg["to"]
    email["Subject"] = msg["subject"]
    email.set_content(msg["body"])

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(email)
    log.info("Email sent to %s", msg["to"])
