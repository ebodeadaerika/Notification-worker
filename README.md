# Notification Worker (Email / SMS / Push)

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

## Message format

```json
{"id": "optional", "type": "email", "to": "user@example.com", "subject": "Hello", "body": "Welcome!"}
{"type": "sms",  "to": "+237600000000", "body": "Your code is 123456"}
{"type": "push", "to": "device-token", "title": "Hi", "body": "New message"}
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
python producer.py demo       # email + sms + push
python producer.py fail       # shows retries then dead-letter
python producer.py invalid    # shows validation rejection
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
