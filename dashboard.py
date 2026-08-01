from __future__ import annotations

import html
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from config import Settings
from storage import EmailDatabase


settings = Settings.load()
db = EmailDatabase(settings.database_path)
app = FastAPI(title="Agentic Email Automation Dashboard")


def _safe(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _truncate(value: object, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit] + ("..." if len(text) > limit else "")


def _read_recent_notes(limit: int = 8) -> list[dict]:
    notes_dir = Path("data/notes")
    if not notes_dir.exists():
        return []
    notes = sorted(notes_dir.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    output = []
    for note in notes[:limit]:
        text = note.read_text(encoding="utf-8", errors="replace")
        output.append(
            {
                "name": note.name,
                "path": str(note),
                "preview": _truncate(text, 260),
            }
        )
    return output


def _read_calendar_requests(limit: int = 6) -> list[dict]:
    path = Path("data/calendar_requests.jsonl")
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records[-limit:][::-1]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "dry_run": settings.dry_run}


@app.get("/api/summary")
def summary() -> dict:
    return db.summary()


@app.get("/api/actions")
def actions(limit: int = 50) -> list[dict]:
    return db.recent_actions(limit=limit)


@app.get("/api/emails")
def emails(limit: int = 30) -> list[dict]:
    return db.recent_emails(limit=limit)


@app.get("/api/emails/{uid}")
def email_detail(uid: str) -> dict:
    detail = db.email_detail(uid)
    if detail is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return detail


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    summary_data = db.summary()
    email_rows = db.recent_emails(limit=30)
    action_rows = db.recent_actions(limit=80)
    notes = _read_recent_notes()
    calendar_requests = _read_calendar_requests()

    latest_by_email: dict[str, list[dict]] = {}
    for action in action_rows:
        latest_by_email.setdefault(action["email_uid"], []).append(action)

    email_cards = "\n".join(_render_email_card(email_row, latest_by_email.get(email_row["uid"], [])) for email_row in email_rows)
    pending_rows = [row for row in action_rows if "pending" in row["status"] or row["action"] == "confirmation_required"]
    pending_html = "\n".join(_render_pending_item(row) for row in pending_rows[:10]) or "<div class='empty'>No pending confirmations.</div>"
    actions_html = "\n".join(_render_action_row(row) for row in action_rows[:40]) or "<tr><td colspan='5'>No actions yet.</td></tr>"
    notes_html = "\n".join(_render_note(note) for note in notes) or "<div class='empty'>No saved notes yet.</div>"
    calendar_html = "\n".join(_render_calendar_request(item) for item in calendar_requests) or "<div class='empty'>No calendar requests yet.</div>"
    category_bars = _render_bars(summary_data["categories"], "category")
    status_bars = _render_bars(summary_data["statuses"], "status")

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Email Agent Dashboard</title>
      <style>
        :root {{
          --bg: #f6f7fb;
          --panel: #ffffff;
          --ink: #18202f;
          --muted: #667085;
          --line: #dde3ee;
          --good: #167a4b;
          --warn: #b45f06;
          --bad: #b42318;
          --info: #2459a8;
          --soft-good: #e8f6ef;
          --soft-warn: #fff4df;
          --soft-bad: #ffebe8;
          --soft-info: #eaf1ff;
          --shadow: 0 8px 24px rgba(31, 41, 55, 0.08);
        }}
        * {{ box-sizing: border-box; }}
        body {{
          margin: 0;
          background: var(--bg);
          color: var(--ink);
          font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}
        header {{
          background: #172033;
          color: #ffffff;
          padding: 24px clamp(16px, 4vw, 48px);
        }}
        .topbar {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          flex-wrap: wrap;
        }}
        h1 {{ margin: 0; font-size: 28px; font-weight: 760; letter-spacing: 0; }}
        .subline {{ margin-top: 8px; color: #cbd5e1; font-size: 14px; }}
        .toolbar {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        button, a.button {{
          border: 1px solid #6f7d95;
          background: #ffffff;
          color: #172033;
          min-height: 38px;
          padding: 8px 12px;
          border-radius: 6px;
          font-weight: 700;
          cursor: pointer;
          text-decoration: none;
          display: inline-flex;
          align-items: center;
          gap: 8px;
        }}
        main {{ padding: 24px clamp(16px, 4vw, 48px) 48px; }}
        .metrics {{
          display: grid;
          grid-template-columns: repeat(5, minmax(130px, 1fr));
          gap: 14px;
          margin-bottom: 22px;
        }}
        .metric {{
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 8px;
          padding: 16px;
          box-shadow: var(--shadow);
          min-height: 98px;
        }}
        .metric .label {{ color: var(--muted); font-size: 13px; font-weight: 700; }}
        .metric .value {{ font-size: 32px; line-height: 1.1; margin-top: 10px; font-weight: 800; }}
        .layout {{
          display: grid;
          grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.8fr);
          gap: 18px;
          align-items: start;
        }}
        section {{
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 8px;
          box-shadow: var(--shadow);
          margin-bottom: 18px;
          overflow: hidden;
        }}
        section h2 {{
          margin: 0;
          padding: 16px 18px;
          font-size: 17px;
          border-bottom: 1px solid var(--line);
          background: #fbfcff;
        }}
        .email-list {{ display: grid; gap: 0; }}
        .email-card {{
          padding: 16px 18px;
          border-bottom: 1px solid var(--line);
        }}
        .email-card:last-child {{ border-bottom: 0; }}
        .email-head {{
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: start;
        }}
        .subject {{ font-weight: 800; font-size: 16px; margin-bottom: 6px; }}
        .from {{ color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }}
        .preview {{ margin-top: 10px; color: #3f4a5f; font-size: 14px; line-height: 1.45; }}
        .badges {{ display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }}
        .badge {{
          display: inline-flex;
          align-items: center;
          min-height: 24px;
          padding: 3px 8px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 800;
          border: 1px solid transparent;
          white-space: nowrap;
        }}
        .category-urgent, .status-pending_confirmation, .status-pending {{ background: var(--soft-warn); color: var(--warn); border-color: #ffd796; }}
        .category-spam, .risk-high, .status-rate_limited {{ background: var(--soft-bad); color: var(--bad); border-color: #ffc9c2; }}
        .category-work, .category-important, .status-dry_run {{ background: var(--soft-info); color: var(--info); border-color: #cddcff; }}
        .category-personal, .risk-low, .status-ok {{ background: var(--soft-good); color: var(--good); border-color: #bfe8d1; }}
        .risk-medium, .status-skipped {{ background: var(--soft-warn); color: var(--warn); border-color: #ffd796; }}
        .mini-actions {{ margin-top: 12px; display: grid; gap: 8px; }}
        .mini-action {{
          display: grid;
          grid-template-columns: 120px 110px minmax(0, 1fr);
          gap: 8px;
          font-size: 13px;
          color: #475467;
        }}
        .panel-body {{ padding: 16px 18px; }}
        .pending-item, .note, .calendar {{
          padding: 12px 0;
          border-bottom: 1px solid var(--line);
        }}
        .pending-item:first-child, .note:first-child, .calendar:first-child {{ padding-top: 0; }}
        .pending-item:last-child, .note:last-child, .calendar:last-child {{ border-bottom: 0; padding-bottom: 0; }}
        .item-title {{ font-weight: 800; margin-bottom: 4px; overflow-wrap: anywhere; }}
        .item-meta {{ color: var(--muted); font-size: 13px; margin-bottom: 6px; overflow-wrap: anywhere; }}
        .item-preview {{ color: #475467; font-size: 13px; line-height: 1.4; overflow-wrap: anywhere; }}
        .bars {{ display: grid; gap: 10px; }}
        .bar-row {{ display: grid; grid-template-columns: 110px minmax(0, 1fr) 32px; gap: 10px; align-items: center; font-size: 13px; }}
        .bar-track {{ height: 9px; background: #eef1f6; border-radius: 999px; overflow: hidden; }}
        .bar-fill {{ height: 100%; background: #3b6ea8; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
        th {{ background: #fbfcff; color: #475467; font-size: 12px; text-transform: uppercase; letter-spacing: 0; }}
        td {{ overflow-wrap: anywhere; }}
        .empty {{ color: var(--muted); font-size: 14px; }}
        @media (max-width: 980px) {{
          .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
          .layout {{ grid-template-columns: 1fr; }}
          .mini-action {{ grid-template-columns: 1fr; }}
        }}
        @media (max-width: 560px) {{
          h1 {{ font-size: 23px; }}
          .metrics {{ grid-template-columns: 1fr; }}
          .email-head {{ flex-direction: column; }}
          .badges {{ justify-content: flex-start; }}
          table {{ display: block; overflow-x: auto; white-space: nowrap; }}
        }}
      </style>
    </head>
    <body>
      <header>
        <div class="topbar">
          <div>
            <h1>Agentic Email Automation</h1>
            <div class="subline">Dry run: {_safe(settings.dry_run)} · Confirmation required: {_safe(settings.require_confirmation)} · Last action: {_safe(summary_data["last_action_at"] or "none yet")}</div>
          </div>
          <div class="toolbar">
            <button onclick="location.reload()" title="Reload dashboard data">Refresh</button>
            <a class="button" href="/api/actions" title="Open raw action JSON">Actions JSON</a>
          </div>
        </div>
      </header>

      <main>
        <div class="metrics">
          {_metric("Emails", summary_data["emails"])}
          {_metric("Actions", summary_data["actions"])}
          {_metric("Pending", summary_data["pending"])}
          {_metric("Urgent", summary_data["urgent"])}
          {_metric("Spam", summary_data["spam"])}
        </div>

        <div class="layout">
          <div>
            <section>
              <h2>Emails The Agent Handled</h2>
              <div class="email-list">{email_cards or "<div class='panel-body empty'>No emails saved yet. Run the agent first.</div>"}</div>
            </section>

            <section>
              <h2>Action Timeline</h2>
              <table>
                <thead>
                  <tr><th>Time</th><th>Email</th><th>Action</th><th>Status</th><th>Details</th></tr>
                </thead>
                <tbody>{actions_html}</tbody>
              </table>
            </section>
          </div>

          <aside>
            <section>
              <h2>Needs Your Confirmation</h2>
              <div class="panel-body">{pending_html}</div>
            </section>

            <section>
              <h2>Category Mix</h2>
              <div class="panel-body">{category_bars}</div>
            </section>

            <section>
              <h2>Action Status Mix</h2>
              <div class="panel-body">{status_bars}</div>
            </section>

            <section>
              <h2>Saved Notes</h2>
              <div class="panel-body">{notes_html}</div>
            </section>

            <section>
              <h2>Calendar Requests</h2>
              <div class="panel-body">{calendar_html}</div>
            </section>
          </aside>
        </div>
      </main>
    </body>
    </html>
    """


def _metric(label: str, value: object) -> str:
    return f"""
    <div class="metric">
      <div class="label">{_safe(label)}</div>
      <div class="value">{_safe(value)}</div>
    </div>
    """


def _render_email_card(email_row: dict, actions: list[dict]) -> str:
    action_html = "\n".join(_render_mini_action(action) for action in actions[:4])
    if not action_html:
        action_html = "<div class='empty'>No actions logged for this email.</div>"
    body_preview = _truncate(email_row.get("body"), 300)
    return f"""
    <article class="email-card">
      <div class="email-head">
        <div>
          <div class="subject">{_safe(email_row["subject"])}</div>
          <div class="from">UID {_safe(email_row["uid"])} · From {_safe(email_row["sender"])}</div>
        </div>
        <div class="badges">
          <span class="badge category-{_safe(email_row["category"])}">{_safe(email_row["category"])}</span>
          <span class="badge risk-{_safe(email_row["risk_level"])}">risk {_safe(email_row["risk_level"])}</span>
          <span class="badge">priority {_safe(email_row["priority_score"])}</span>
        </div>
      </div>
      <div class="preview">{_safe(body_preview)}</div>
      <div class="mini-actions">{action_html}</div>
    </article>
    """


def _render_mini_action(action: dict) -> str:
    return f"""
    <div class="mini-action">
      <span>{_safe(action["action"])}</span>
      <span class="badge status-{_safe(action["status"])}">{_safe(action["status"])}</span>
      <span>{_safe(_truncate(action["details"], 120))}</span>
    </div>
    """


def _render_pending_item(row: dict) -> str:
    return f"""
    <div class="pending-item">
      <div class="item-title">{_safe(row["action"])} for email {_safe(row["email_uid"])}</div>
      <div class="item-meta">{_safe(row["created_at"])} · {_safe(row["status"])}</div>
      <div class="item-preview">{_safe(_truncate(row["details"], 220))}</div>
    </div>
    """


def _render_action_row(row: dict) -> str:
    return f"""
    <tr>
      <td>{_safe(row["created_at"])}</td>
      <td>{_safe(row["email_uid"])}</td>
      <td>{_safe(row["action"])}</td>
      <td><span class="badge status-{_safe(row["status"])}">{_safe(row["status"])}</span></td>
      <td>{_safe(_truncate(row["details"], 180))}</td>
    </tr>
    """


def _render_note(note: dict) -> str:
    return f"""
    <div class="note">
      <div class="item-title">{_safe(note["name"])}</div>
      <div class="item-meta">{_safe(note["path"])}</div>
      <div class="item-preview">{_safe(note["preview"])}</div>
    </div>
    """


def _render_calendar_request(item: dict) -> str:
    return f"""
    <div class="calendar">
      <div class="item-title">{_safe(item.get("title"))}</div>
      <div class="item-meta">{_safe(item.get("suggested_start"))} · {_safe(item.get("status"))}</div>
      <div class="item-preview">Email {_safe(item.get("source_email_uid"))} · {_safe(", ".join(item.get("attendees", [])))}</div>
    </div>
    """


def _render_bars(rows: list[dict], label_key: str) -> str:
    if not rows:
        return "<div class='empty'>No data yet.</div>"
    max_count = max(row["count"] for row in rows) or 1
    bars = []
    for row in rows:
        width = int((row["count"] / max_count) * 100)
        bars.append(
            f"""
            <div class="bar-row">
              <span>{_safe(row[label_key])}</span>
              <span class="bar-track"><span class="bar-fill" style="width: {width}%"></span></span>
              <strong>{_safe(row["count"])}</strong>
            </div>
            """
        )
    return f"<div class='bars'>{''.join(bars)}</div>"
