# Notification Worker (Inbox / Email / SMS / Push) + Web App

A background service that reads notification requests from a Redis queue and delivers them through the right channel, with retries, a dead-letter queue, validation, logging and per-notification status tracking.

## Architecture

```
producer.py ──LPUSH──▶ Redis list "notifications:queue" ──BRPOP──▶ worker.py
                                                                      │
                                              validate ─ invalid ─▶ "notifications:failed" (dead-letter)
                                                  │
                                       route by "type"
                                    ┌─────────┼─────────┐
                                 email      sms       push        (handlers/)
                                    └─────────┼─────────┘
                              success ─▶ status "sent"
                              failure ─▶ retry with exponential backoff
                                         still failing ─▶ dead-letter + status "failed"
```

Status for each notification is stored in a Redis hash `notification:<id>` (queued → processing → sent / retrying / failed).

## Web app (accounts + live inbox)

Users sign up and log in; only registered users can receive notifications.

```
Browser ─▶ app.py (Flask: sign up / log in / send form) ─▶ Redis queue ─▶ worker.py ─▶ inbox:<email> ─▶ dashboard (refreshes every 10s)
```

- Accounts are stored in Redis (`user:<email>`), passwords hashed with PBKDF2 (never stored in plain text).
- **Two layers enforce "signed-in clients only"**: the web app refuses recipients without an account, and the worker re-checks every message and rejects unknown recipients to the dead-letter queue.
- A user can only read their own inbox (the API reads the inbox of the logged-in user from the session, never from the URL).
- Security basics: CSRF token on every POST, login lockout after 5 failures, session cookie `HttpOnly` + `SameSite=Lax`, messages escaped in HTML, Content-Security-Policy header.

Run (two terminals, venv active in both):
```bash
python worker.py      # terminal 1
python app.py         # terminal 2, then open http://127.0.0.1:5000
```
Each message also carries `"user"`: the account that should receive it.

## Message format

```json
{"type": "inbox", "user": "ada@example.com", "title": "Hi", "body": "Shown on the dashboard"}
{"id": "optional", "type": "email", "user": "ada@example.com", "to": "ada@example.com", "subject": "Hello", "body": "Welcome!"}
{"type": "sms",  "user": "ada@example.com", "to": "+237600000000", "body": "Your code is 123456"}
{"type": "push", "user": "ada@example.com", "to": "device-token", "title": "Hi", "body": "New message"}
```

## Setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then edit .env with your Upstash URL/token
```

## Run

Terminal 1 (the worker):
```bash
python worker.py
```

Terminal 2 (send test messages):
```bash
python producer.py demo you@example.com   # inbox + email + sms + push (you@... must be signed up)
python producer.py fail you@example.com   # shows retries then dead-letter
python producer.py unregistered           # shows rejection of a recipient with no account
python producer.py invalid                # shows validation rejection
python producer.py status <id>
```

## Tests

```bash
pytest -v
```

## Design choices

- **Redis list + BRPOP**: simple, reliable FIFO queue; the worker blocks instead of busy-polling.
- **Handlers share one signature** (`send(msg)`), so adding a channel = one new file + one line in `handlers/__init__.py`.
- **Invalid messages skip retries** (retrying can't fix a bad message); **delivery errors are retried** with exponential backoff.
- **Dead-letter queue** keeps failed messages for inspection instead of losing them.
- **SMS and push are simulated**; email can be real via SMTP (`EMAIL_MODE=smtp`).

## Possible improvements

Real Twilio/Firebase handlers, templates, priority queues, Docker Compose.
