"""SMS channel (simulated).

To go real later, call a provider such as Twilio here and raise an
exception if the provider rejects the request.
"""
import logging

log = logging.getLogger("sms")


def send(msg: dict) -> None:
    if msg.get("simulate_failure"):  # handy for demoing retries
        raise RuntimeError("simulated SMS provider failure")
    log.info("[MOCK SMS] to=%s body=%s", msg["to"], msg["body"])
