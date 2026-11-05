"""Web front end: sign up / log in, a live inbox, and a form to send notifications.

Run:  python app.py      then open http://127.0.0.1:5000
The worker (python worker.py) must be running in another terminal to deliver messages.
"""
import json
import secrets
import uuid
from functools import wraps

import redis
from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)

import config
import users
from message import InvalidMessage, validate

TITLE_MAX = 100
BODY_MAX = 1000


def create_app(redis_client=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.SECRET_KEY or secrets.token_hex(32),  # random if .env has none
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if not config.SECRET_KEY:
        print("WARNING: SECRET_KEY is not set in .env, logins reset every time the app restarts.")

    r = redis_client or redis.from_url(
        config.REDIS_URL, decode_responses=True,
        socket_connect_timeout=10, socket_timeout=15,
    )

    # ---------- security helpers ----------
    def csrf_token() -> str:
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            sent = request.form.get("csrf", "") or request.headers.get("X-CSRF-Token", "")
            expected = session.get("csrf", "")
            if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
                abort(400)

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = "default-src 'self'"
        return resp

    def login_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not session.get("user"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapper

    def read_inbox(email: str) -> list:
        raw = r.lrange(f"{config.INBOX_PREFIX}{email}", 0, config.INBOX_MAX - 1)
        return [json.loads(item) for item in raw]

    # ---------- pages ----------
    @app.get("/")
    def index():
        return redirect(url_for("dashboard" if session.get("user") else "login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            try:
                email = users.create_user(
                    r, request.form.get("name"), request.form.get("email"), request.form.get("password"))
            except users.UserError as exc:
                flash(str(exc), "error")
                return render_template("register.html"), 400
            session.clear()  # fresh session after sign-up
            session["user"], session["name"] = email, request.form.get("name", "").strip()
            return redirect(url_for("dashboard"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            try:
                user = users.authenticate(r, request.form.get("email"), request.form.get("password"))
            except users.UserError as exc:
                flash(str(exc), "error")
                return render_template("login.html"), 401
            session.clear()  # avoids session fixation
            session["user"], session["name"] = user["email"], user["name"]
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html", name=session["name"], email=session["user"],
                               inbox=read_inbox(session["user"]),
                               title_max=TITLE_MAX, body_max=BODY_MAX)

    @app.get("/api/inbox")
    @login_required
    def api_inbox():
        resp = jsonify(read_inbox(session["user"]))  # a user can only ever read their own inbox
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.post("/send")
    @login_required
    def send():
        to = users.normalize(request.form.get("to"))
        title = (request.form.get("title") or "").strip()
        body = (request.form.get("body") or "").strip()

        if not title or not body or len(title) > TITLE_MAX or len(body) > BODY_MAX:
            flash(f"Title (max {TITLE_MAX}) and message (max {BODY_MAX}) are required.", "error")
        elif not users.exists(r, to):
            flash("That person has no account, so they can't receive notifications.", "error")
        else:
            msg = {"id": str(uuid.uuid4()), "type": "inbox", "user": to,
                   "title": title, "body": body, "from": session["user"]}
            try:
                validate(msg)
            except InvalidMessage as exc:
                flash(str(exc), "error")
            else:
                r.lpush(config.QUEUE_NAME, json.dumps(msg))
                r.hset(f"{config.STATUS_PREFIX}{msg['id']}", mapping={"status": "queued", "type": "inbox"})
                flash(f"Notification queued for {to}.", "ok")
        return redirect(url_for("dashboard"))

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
