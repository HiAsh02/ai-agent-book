#!/usr/bin/env python3
"""Collaboration Tools — Unified CLI Entry (Experiment 4-3)

Command-line interface for Experiment 4-3 "Collaboration Tools MCP Server" in Chapter 4 of "Deep Understanding of AI Agents".
List and invoke each collaboration tool directly, and run end-to-end demos without starting the MCP server.

Collaboration tools are divided into three categories (corresponding to the "Collaboration Tools" section in the book):
  1. Sub-agent Management: spawn_subagent / send_message_to_subagent / cancel_subagent
     (supports synchronous/asynchronous modes, and minimal / llm_generated context passing strategies)
  2. Human Collaboration (HITL): request_admin_approval / request_admin_input (with timeout and default behavior)
  3. Multi-channel Notifications: email / slack / telegram / discord

Examples:
  python main.py list                     # List all collaboration tools
  python main.py demo                      # Run offline end-to-end collaboration demo (no API Key required)
  python main.py subagent compare          # Compare two context passing strategies
  python main.py subagent spawn --task "Query order A12345 status" --strategy minimal
  python main.py hitl approve --message "Delete 1000 records?" --timeout 5 --auto-approve
  python main.py notify slack --message "Deployment complete ✅"

Notes:
  - Sub-agent execution and llm_generated context strategy require OPENAI_API_KEY;
    if not configured, it automatically falls back to deterministic offline simulation (results will be explicitly marked "LLM not invoked").
  - Actually sending notifications/emails requires configuring credentials for the corresponding channel in .env;
    if not configured, the tool will return a "not configured" message, but the command itself can still be parsed and run normally.
"""

import argparse
import asyncio
import json
import os
import sys

#Modules under src/ use bare imports (consistent with quickstart.py / subagent_comparison.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import subagent_tools as sa  # noqa: E402
import hitl_tools as hitl  # noqa: E402
import notification_tools as notify  # noqa: E402


def _print(obj) -> None:
    """Uniformly print tool results as indented JSON."""
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _parse_json_arg(value):
    """Attempt to parse as JSON; if not valid JSON, return as raw string (for direct use by sub-agents)."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


# ---------------------------------------------------------------------------
# Tool List
# ---------------------------------------------------------------------------

COLLAB_TOOLS = {
    "Sub-agent Management": [
        ("spawn_subagent", "Create sub-agent (sync/async, minimal/llm_generated context strategy)"),
        ("send_message_to_subagent", "Send subsequent message to sub-agent and get reply"),
        ("cancel_subagent", "Cancel sub-agent (async tasks will abort background coroutine)"),
        ("get_subagent_status", "Query sub-agent status and result (for async)"),
    ],
    "Human Collaboration (HITL)": [
        ("request_admin_approval", "Request admin approval before critical decisions (supports timeout and default behavior)"),
        ("request_admin_input", "Request additional input from admin"),
        ("respond_to_request", "Admin approves/rejects pending requests"),
        ("list_pending_requests", "List all pending approval requests"),
    ],
    "Multi-channel Notifications": [
        ("send_email", "Send email notification (SMTP / SendGrid)"),
        ("send_slack_message", "Send Slack message via Webhook"),
        ("send_telegram_message", "Send Telegram message"),
        ("send_discord_message", "Send Discord message via Webhook"),
    ],
}


def cmd_list(args) -> None:
    print("Collaboration Tools List (Experiment 4-3)\n" + "=" * 60)
    for category, tools in COLLAB_TOOLS.items():
        print(f"\n【{category}】")
        for name, desc in tools:
            print(f"  - {name:<28} {desc}")
    print("\nTip: `python main.py <subcommand> -h` to view parameters for each tool.")


# ---------------------------------------------------------------------------
# Sub-agent Subcommands
# ---------------------------------------------------------------------------

async def _subagent_dispatch(args) -> None:
    if args.sub_action == "spawn":
        res = await sa.spawn_subagent(
            task=args.task,
            context_strategy=args.strategy,
            mode=args.mode,
            parent_context=_parse_json_arg(args.parent_context),
            role=args.role,
            minimal_slice=_parse_json_arg(args.minimal_slice),
            business_rules=args.business_rules,
        )
        _print(res)
    elif args.sub_action == "send":
        _print(await sa.send_message_to_subagent(args.id, args.message))
    elif args.sub_action == "cancel":
        _print(await sa.cancel_subagent(args.id))
    elif args.sub_action == "status":
        _print(await sa.get_subagent_status(args.id))
    elif args.sub_action == "compare":
        await sa.run_context_strategy_comparison(task=args.task)


def cmd_subagent(args) -> None:
    asyncio.run(_subagent_dispatch(args))


# ---------------------------------------------------------------------------
# HITL Subcommands
# ---------------------------------------------------------------------------

async def _auto_responder(approve: bool, notes: str, delay: float = 1.0) -> None:
    """Simulate admin: poll pending requests and respond, used for offline HITL loop demo."""
    await asyncio.sleep(delay)
    pending = await hitl.list_pending_requests()
    for req in pending.get("requests", []):
        await hitl.respond_to_request(req["request_id"], approve, notes)


async def _hitl_dispatch(args) -> None:
    if args.hitl_action == "approve":
        coro = hitl.request_admin_approval(
            request_message=args.message,
            timeout_seconds=args.timeout,
            urgent=args.urgent,
        )
        if args.auto_approve or args.auto_reject:
            responder = _auto_responder(
                approve=not args.auto_reject,
                notes=args.notes or ("Auto-simulate approval" if not args.auto_reject else "Auto-simulate rejection"),
            )
            res, _ = await asyncio.gather(coro, responder)
        else:
            res = await coro
        _print(res)
    elif args.hitl_action == "input":
        coro = hitl.request_admin_input(prompt=args.prompt, timeout_seconds=args.timeout)
        if args.auto_answer is not None:
            responder = _auto_responder(approve=True, notes=args.auto_answer)
            res, _ = await asyncio.gather(coro, responder)
        else:
            res = await coro
        _print(res)
    elif args.hitl_action == "respond":
        _print(await hitl.respond_to_request(args.id, args.approve, args.notes))
    elif args.hitl_action == "list":
        _print(await hitl.list_pending_requests())


def cmd_hitl(args) -> None:
    asyncio.run(_hitl_dispatch(args))


# ---------------------------------------------------------------------------
# Notification Subcommands
# ---------------------------------------------------------------------------

async def _notify_dispatch(args) -> None:
    if args.channel == "email":
        _print(await notify.send_email(args.to, args.subject, args.body))
    elif args.channel == "slack":
        _print(await notify.send_slack_message(args.message, webhook_url=args.webhook))
    elif args.channel == "telegram":
        _print(await notify.send_telegram_message(args.message, chat_id=args.chat_id))
    elif args.channel == "discord":
        _print(await notify.send_discord_message(args.message, webhook_url=args.webhook))


def cmd_notify(args) -> None:
    asyncio.run(_notify_dispatch(args))


# ---------------------------------------------------------------------------
# End-to-End Demo: Customer Service Coordination Agent Handles a Refund
# ---------------------------------------------------------------------------

def _neutralize_network_creds() -> None:
    """Clear placeholder credentials in .env before demo to avoid offline demo attempting real network requests and blocking."""
    from config import config

    config.email.smtp_username = None
    config.email.smtp_password = None
    config.email.sendgrid_api_key = None
    config.im.telegram_bot_token = None
    config.im.slack_webhook_url = None
    config.im.discord_webhook_url = None
    config.hitl.webhook_url = None
    config.hitl.admin_email = None


async def _demo() -> None:
    _neutralize_network_creds()
    online = bool(os.getenv("OPENAI_API_KEY"))

    print("=" * 74)
    print("End-to-End Collaboration Demo: Customer Service Agent Handling a Refund")
    print(f"(Sub-Agent Execution Mode:{'Online LLM' if online else 'Offline Simulation (OPENAI_API_KEY not configured)'}）")
    print("=" * 74)

    print("\n[Step 1/3] Delegate sub-agent to approve refund, and compare two context passing strategies")
    print("-" * 74)
    if not online:
        print("(Note: OPENAI_API_KEY not configured, sub-agent execution and llm_generated strategy")
        print("  will return errors, only for demonstrating interface and context construction; configure Key to see real results.)")
    await sa.run_context_strategy_comparison()

    print("\n[Step 2/3] Large operation triggers HITL: Request approval from admin (with timeout and default behavior)")
    print("-" * 74)
    print("→ Scenario A: Admin approves before timeout (simulated backend response)")
    approval, _ = await asyncio.gather(
        hitl.request_admin_approval(
            request_message="Refund amount 8888 yuan, exceeds auto-approval threshold, please confirm manually.",
            timeout_seconds=10,
            urgent=True,
        ),
        _auto_responder(approve=True, notes="Verified correct, approve refund", delay=1.0),
    )
    _print(approval)

    print("\n→ Scenario B: Admin does not respond in time, triggers timeout and conservative default (not approved)")
    timeout_res = await hitl.request_admin_approval(
        request_message="Refund amount 8888 yuan, please confirm manually.",
        timeout_seconds=2,
    )
    _print(timeout_res)

    print("\n[Step 3/3] Multi-channel notification to collaborators of processing result")
    print("-" * 74)
    summary = "Refund ticket A12345: Sub-agent approved, admin confirmed, funds released."
    for channel, coro in (
        ("email", notify.send_email("admin@example.com", "Refund processing completed", summary)),
        ("slack", notify.send_slack_message(summary)),
        ("telegram", notify.send_telegram_message(summary)),
    ):
        res = await coro
        status = "Sent" if res.get("success") else f"Not sent ({res.get('error')}）"
        print(f"  [{channel:<8}] {status}：{summary}")

    print("\n" + "=" * 74)
    print("Demo ended. To actually send notifications/emails, configure corresponding channel credentials in .env;")
    print("Sub-agent's real LLM execution and llm_generated strategy require configuring OPENAI_API_KEY.")
    print("=" * 74)


def cmd_demo(args) -> None:
    asyncio.run(_demo())


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Collaboration tool command line entry (Experiment 4-3): Sub-agent management / Human collaboration / Multi-channel notification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example: \n"
            "  python main.py list\n"
            "  python main.py demo\n"
            "  python main.py subagent compare\n"
            "  python main.py subagent spawn --task 'Query order A12345 status' --strategy minimal\n"
            "  python main.py hitl approve --message 'Delete 1000 records?' --timeout 5 --auto-approve\n"
            "  python main.py notify slack --message 'Deployment complete'\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<Command>")

    sub.add_parser("list", help="List all collaboration tools").set_defaults(func=cmd_list)

    p_demo = sub.add_parser("demo", help="Run offline end-to-end collaboration demo (no API Key required)")
    p_demo.set_defaults(func=cmd_demo)

    # subagent
    p_sa = sub.add_parser("subagent", help="Sub-agent management tool")
    sa_sub = p_sa.add_subparsers(dest="sub_action", required=True, metavar="<Action>")

    p_spawn = sa_sub.add_parser("spawn", help="Create Sub-Agent")
    p_spawn.add_argument("--task", required=True, help="Delegate Subtask to Sub-Agent")
    p_spawn.add_argument("--strategy", default="minimal",
                         choices=["minimal", "llm_generated"], help="Context Passing Strategy")
    p_spawn.add_argument("--mode", default="sync", choices=["sync", "async"],
                         help="sync: wait synchronously for result; async: return task_id")
    p_spawn.add_argument("--role", default=None, help="Sub-Agent Role (for system prompt)")
    p_spawn.add_argument("--parent-context", default=None,
                         help="Main Agent Trajectory/State (JSON string)")
    p_spawn.add_argument("--minimal-slice", default=None,
                         help="Manually selected information under minimal strategy (string or JSON)")
    p_spawn.add_argument("--business-rules", default=None,
                         help="Privacy/compression rules under llm_generated strategy")

    p_send = sa_sub.add_parser("send", help="Send Follow-up Message to Sub-Agent")
    p_send.add_argument("--id", required=True, help="Sub-Agent ID")
    p_send.add_argument("--message", required=True, help="Message Content")

    p_cancel = sa_sub.add_parser("cancel", help="Cancel Sub-Agent")
    p_cancel.add_argument("--id", required=True, help="Sub-Agent ID")

    p_status = sa_sub.add_parser("status", help="Query Sub-Agent Status/Result")
    p_status.add_argument("--id", required=True, help="Sub-Agent ID")

    p_cmp = sa_sub.add_parser("compare", help="Compare minimal and llm_generated strategies")
    p_cmp.add_argument("--task", default=None, help="Common subtask for comparison")
    p_sa.set_defaults(func=cmd_subagent)

    # hitl
    p_hitl = sub.add_parser("hitl", help="Human-in-the-Loop (HITL) Tool")
    hitl_sub = p_hitl.add_subparsers(dest="hitl_action", required=True, metavar="<Action>")

    p_appr = hitl_sub.add_parser("approve", help="Request Admin Approval")
    p_appr.add_argument("--message", required=True, help="Content requiring approval")
    p_appr.add_argument("--timeout", type=int, default=None, help="Wait seconds (timeout triggers default behavior)")
    p_appr.add_argument("--urgent", action="store_true", help="Mark as Urgent")
    p_appr.add_argument("--auto-approve", action="store_true", help="Simulate admin approval in background (for offline demo)")
    p_appr.add_argument("--auto-reject", action="store_true", help="Simulate admin rejection in background (for offline demo)")
    p_appr.add_argument("--notes", default=None, help="Admin Note")

    p_inp = hitl_sub.add_parser("input", help="Request Input from Admin")
    p_inp.add_argument("--prompt", required=True, help="Question/Prompt")
    p_inp.add_argument("--timeout", type=int, default=None, help="Wait seconds")
    p_inp.add_argument("--auto-answer", default=None, help="Simulate admin response in background (for offline demo)")

    p_resp = hitl_sub.add_parser("respond", help="Admin's answer to request")
    p_resp.add_argument("--id", required=True, help="Request ID")
    grp = p_resp.add_mutually_exclusive_group(required=True)
    grp.add_argument("--approve", dest="approve", action="store_true", help="Approve")
    grp.add_argument("--reject", dest="approve", action="store_false", help="Reject")
    p_resp.add_argument("--notes", default=None, help="Notes")

    hitl_sub.add_parser("list", help="List pending requests")
    p_hitl.set_defaults(func=cmd_hitl)

    # notify
    p_notify = sub.add_parser("notify", help="Multi-channel notification tool")
    notify_sub = p_notify.add_subparsers(dest="channel", required=True, metavar="<Channel>")

    p_email = notify_sub.add_parser("email", help="Send email")
    p_email.add_argument("--to", required=True, help="Recipient")
    p_email.add_argument("--subject", required=True, help="Subject")
    p_email.add_argument("--body", required=True, help="Body")

    p_slack = notify_sub.add_parser("slack", help="Send Slack message")
    p_slack.add_argument("--message", required=True, help="Message Content")
    p_slack.add_argument("--webhook", default=None, help="Slack Webhook URL (default from .env)")

    p_tg = notify_sub.add_parser("telegram", help="Send Telegram message")
    p_tg.add_argument("--message", required=True, help="Message Content")
    p_tg.add_argument("--chat-id", default=None, help="Telegram chat ID (default from .env)")

    p_dc = notify_sub.add_parser("discord", help="Send Discord message")
    p_dc.add_argument("--message", required=True, help="Message Content")
    p_dc.add_argument("--webhook", default=None, help="Discord Webhook URL (default from .env)")
    p_notify.set_defaults(func=cmd_notify)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
