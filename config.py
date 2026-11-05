"""Central configuration, read from environment variables (.env file)."""
import os

from dotenv import load_dotenv

load_dotenv()

# Upstash gives you a TLS connection, so the URL must start with rediss:// (two s).
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

QUEUE_NAME = "notifications:queue"
DEAD_LETTER_QUEUE = "notifications:failed"
STATUS_PREFIX = "notification:"  # one hash per notification: notification:<id>

# --- Accounts (web app) ---
USER_PREFIX = "user:"        # one hash per account: user:<email>
INBOX_PREFIX = "inbox:"      # one list per account: inbox:<email>
INBOX_MAX = 50               # keep only the latest 50 notifications per user
LOGIN_FAIL_PREFIX = "loginfail:"
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 15 * 60

# Flask signs the login cookie with this. Set a long random value in .env.
SECRET_KEY = os.getenv("SECRET_KEY", "")

# When true, only registered (signed-up) users can receive notifications.
REQUIRE_REGISTERED_USER = os.getenv("REQUIRE_REGISTERED_USER", "true").lower() == "true"

# --- Worker ---
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BACKOFF_BASE_SECONDS = float(os.getenv("BACKOFF_BASE_SECONDS", "2"))
POLL_TIMEOUT_SECONDS = 30  # how long BRPOP waits before looping again (fewer idle commands)

# Email: "mock" just logs, "smtp" really sends.
EMAIL_MODE = os.getenv("EMAIL_MODE", "mock")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
