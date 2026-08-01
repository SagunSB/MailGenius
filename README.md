# Agentic AI Email Automation System

Agentic AI Email Automation System is a Python email assistant that reads emails, classifies intent, chooses safe actions, drafts replies, stores memory, and records an audit trail. It is designed to run safely in `DRY_RUN=true` by default, so you can test the workflow without sending real emails.

## Features

- IMAP email reading for Gmail, Outlook, or another compatible provider.
- SMTP reply and forwarding support with dry-run protection.
- OpenAI-powered classification and reply drafting with a local keyword fallback.
- Categories for important, spam, work, personal, and urgent emails.
- Observe-think-act agent workflow with decision and response handling.
- Local JSONL memory, optional Chroma memory backend, and SQLite audit storage.
- Safety gates for spam, risky actions, replies, forwards, rate limits, and confirmations.
- Optional FastAPI dashboard for health checks, email records, and recent actions.

## Project Structure

```text
main.py                  CLI entry point
config.py                Environment-driven settings
agent.py                 Observe-think-act workflow and decisions
email_reader.py          IMAP fetching, attachment saving, SMTP sending
email_classifier.py      Classification and reply drafting
memory.py                Memory retrieval and storage
tools.py                 Notes, notifications, calendar stubs, rate limiting
storage.py               SQLite persistence
dashboard.py             Optional FastAPI dashboard
sample_emails.py         Built-in demo emails
sample_test_emails.json  Readable sample email data
tests/                   Pytest test suite
.env.example             Local configuration template
```

## Requirements

- Python 3.10 or newer
- Gmail, Outlook, or another IMAP/SMTP email account for live mode
- Optional OpenAI API key for LLM classification and drafting

## Setup

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Create your local environment file.

```powershell
Copy-Item .env.example .env
```

On macOS or Linux:

```bash
cp .env.example .env
```

4. Edit `.env` with your values.

```env
DRY_RUN=true
REQUIRE_CONFIRMATION=true
OPENAI_API_KEY=sk-your-api-key
EMAIL_ADDRESS=your.email@gmail.com
EMAIL_PASSWORD=your-app-password
```

Keep `DRY_RUN=true` until you have tested the project and reviewed the logs. For Gmail, use an app password instead of your normal account password.

## Run In Demo Mode

Demo mode uses the built-in sample emails and does not connect to a real inbox.

```bash
python main.py --once --test-mode
```

Run continuously with sample emails:

```bash
python main.py --loop --test-mode
```

## Run With A Real Inbox

First run live inbox mode with dry-run enabled.

```bash
python main.py --once
```

For a continuous worker:

```bash
python main.py --loop
```

Only set `DRY_RUN=false` after you have reviewed the behavior. `REQUIRE_CONFIRMATION=true` keeps high-risk replies and forwards from being sent automatically.

## Dashboard

Start the dashboard:

```bash
python main.py --dashboard
```

Then open:

```text
http://127.0.0.1:8000
```

Useful endpoints:

- `GET /health`
- `GET /api/summary`
- `GET /api/actions`
- `GET /api/emails`

## Tests

```bash
pytest
```

The tests cover spam classification, safe spam handling, and a full test-mode agent cycle.

## Generated Files

The app creates local runtime files such as:

- `data/`
- `logs/`
- `test_output/`
- `.pytest_tmp/`
- `pytest-cache-files-*`

These are intentionally ignored by Git because they can contain logs, local databases, test output, and private email data.
