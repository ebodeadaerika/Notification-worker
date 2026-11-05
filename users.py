"""Accounts: sign up, log in. Users live in Redis as hashes (user:<email>)."""
import re
import time

from werkzeug.security import check_password_hash, generate_password_hash

import config

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HASH_METHOD = "pbkdf2:sha256"
# Used to make "unknown user" take as long as "wrong password".
_DUMMY_HASH = generate_password_hash("dummy-password", method=HASH_METHOD)


class UserError(Exception):
    """A problem the user can be told about (bad input, wrong login...)."""


def normalize(email: str) -> str:
    return (email or "").strip().lower()


def key(email: str) -> str:
    return f"{config.USER_PREFIX}{normalize(email)}"


def exists(r, email: str) -> bool:
    return bool(r.exists(key(email)))


def create_user(r, name: str, email: str, password: str) -> str:
    name = (name or "").strip()
    email = normalize(email)
    if not 1 <= len(name) <= 60:
        raise UserError("Please enter your name (max 60 characters).")
    if not EMAIL_RE.match(email) or len(email) > 120:
        raise UserError("Please enter a valid email address.")
    if len(password or "") < 8:
        raise UserError("Password must be at least 8 characters.")
    if len(password) > 200:
        raise UserError("Password is too long.")

    # hsetnx is atomic: only one request can create this account.
    if not r.hsetnx(key(email), "email", email):
        raise UserError("An account with this email already exists.")
    r.hset(key(email), mapping={
        "name": name,
        "password_hash": generate_password_hash(password, method=HASH_METHOD),
        "created_at": str(time.time()),
    })
    return email


def authenticate(r, email: str, password: str) -> dict:
    email = normalize(email)
    fail_key = f"{config.LOGIN_FAIL_PREFIX}{email}"

    attempts = int(r.get(fail_key) or 0)
    if attempts >= config.MAX_LOGIN_ATTEMPTS:
        raise UserError("Too many failed attempts. Try again in 15 minutes.")

    user = r.hgetall(key(email))
    stored = user.get("password_hash") if user else None
    ok = check_password_hash(stored or _DUMMY_HASH, password or "")
    if not (user and stored and ok):
        r.incr(fail_key)
        r.expire(fail_key, config.LOGIN_LOCK_SECONDS)
        raise UserError("Wrong email or password.")  # same message for both cases

    r.delete(fail_key)
    return {"email": email, "name": user.get("name", email)}
