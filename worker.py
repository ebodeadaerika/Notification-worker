"""The notification worker: pops messages from Redis and delivers them."""
import json
import logging
import signal
import time

import redis

import config
from handlers import HANDLERS
from message import InvalidMessage, validate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("worker.log")],
)
log = logging.getLogger("worker")

running = True


def _stop(signum, frame):
    global running
    log.info("Shutdown requested, finishing current message...")
    running = False


def set_status(r, msg_id, status, **extra):
    r.hset(f"{config.STATUS_PREFIX}{msg_id}", mapping={"status": status, "updated_at": time.time(), **{k: str(v) for k, v in extra.items()}})


def send_with_retry(r, msg: dict) -> bool:
    """Try to deliver, retrying with exponential backoff. Returns True on success."""
    handler = HANDLERS[msg["type"]]
    last_error = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            handler(msg)
            set_status(r, msg["id"], "sent", attempts=attempt)
            log.info("SENT id=%s type=%s attempt=%d", msg["id"], msg["type"], attempt)
            return True
        except Exception as exc:  # any channel error is retryable
            last_error = exc
            log.warning("FAILED id=%s attempt=%d/%d: %s", msg["id"], attempt, config.MAX_RETRIES, exc)
            set_status(r, msg["id"], "retrying", attempts=attempt, error=exc)
            if attempt < config.MAX_RETRIES:
                time.sleep(config.BACKOFF_BASE_SECONDS ** attempt)

    msg["error"] = str(last_error)
    r.lpush(config.DEAD_LETTER_QUEUE, json.dumps(msg))
    set_status(r, msg["id"], "failed", attempts=config.MAX_RETRIES, error=last_error)
    log.error("DEAD-LETTERED id=%s after %d attempts", msg["id"], config.MAX_RETRIES)
    return False


def process_one(r, raw: str) -> None:
    try:
        msg = validate(json.loads(raw))
    except (json.JSONDecodeError, InvalidMessage) as exc:
        log.error("REJECTED invalid message: %s | raw=%s", exc, raw)
        r.lpush(config.DEAD_LETTER_QUEUE, json.dumps({"raw": raw, "error": str(exc)}))
        return

    set_status(r, msg["id"], "processing", type=msg["type"])
    send_with_retry(r, msg)


def main():
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    r = redis.from_url(
        config.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=10,
        socket_timeout=config.POLL_TIMEOUT_SECONDS + 15,  # must be longer than the BRPOP wait
        health_check_interval=30,
    )
    r.ping()
    log.info("Worker started, listening on %s", config.QUEUE_NAME)

    while running:
        try:
            item = r.brpop(config.QUEUE_NAME, timeout=config.POLL_TIMEOUT_SECONDS)
        except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError) as exc:
            log.warning("Redis connection problem (%s), retrying in 3s...", exc)
            time.sleep(3)
            continue
        if item is None:
            continue  # nothing arrived, loop again
        _, raw = item
        process_one(r, raw)

log.info("Worker stopped.")

if __name__ == "__main__":
    main()