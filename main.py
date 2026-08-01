from __future__ import annotations

import argparse
import time

from rich.console import Console

from agent import EmailAutomationAgent
from config import Settings
from logger import configure_logging


console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agentic AI Email Automation System")
    parser.add_argument("--once", action="store_true", help="Run one observe-think-act cycle.")
    parser.add_argument("--loop", action="store_true", help="Run continuously.")
    parser.add_argument("--test-mode", action="store_true", help="Use sample_emails instead of IMAP.")
    parser.add_argument("--dashboard", action="store_true", help="Start the optional FastAPI dashboard.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings.load()
    configure_logging(settings.log_file)

    if args.dashboard:
        import uvicorn

        from dashboard import app

        console.print(f"[bold green]Starting dashboard[/] http://{settings.dashboard_host}:{settings.dashboard_port}")
        uvicorn.run(app, host=settings.dashboard_host, port=settings.dashboard_port)
        return

    agent = EmailAutomationAgent(settings=settings, test_mode=args.test_mode)

    if not args.loop:
        args.once = True

    if args.once:
        summary = agent.run_once()
        console.print(summary.to_panel())
        return

    console.print("[bold green]Agent loop started.[/] Press Ctrl+C to stop.")
    try:
        while True:
            summary = agent.run_once()
            console.print(summary.to_panel())
            time.sleep(settings.loop_interval_seconds)
    except KeyboardInterrupt:
        console.print("\n[yellow]Agent stopped by user.[/]")


if __name__ == "__main__":
    main()
