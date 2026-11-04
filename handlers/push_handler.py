"""Push channel (simulated).

To go real later, use Firebase Cloud Messaging (firebase-admin) here.
"""
import logging

log = logging.getLogger("push")


def send(msg: dict) -> None:
    if msg.get("simulate_failure"):
        raise RuntimeError("simulated push provider failure")
    log.info("[MOCK PUSH] to=%s title=%s body=%s", msg["to"], msg["title"], msg["body"])
