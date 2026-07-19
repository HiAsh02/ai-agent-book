"""
Memobase User Profile + Event Memory Demo

Corresponding to the introduction of Memobase in Chapter 3 "Memory Framework Case" of "Deep Understanding of AI Agent":
Memobase (open source project memodb-io/memobase) organizes user memory into two parts:
  * User Profile: Stable user attributes organized in a two-level "topic—subtopic" structure
    (e.g., basic_info→name, interest→game preference, work→position), extracted from conversations;
  * Event Memory: Records user experiences chronologically,
    used to answer time-related questions like "When did we last discuss the budget?"
Engineering-wise, Memobase uses "buffer batch processing": conversations are first inserted into a buffer for accumulation,
and only when flushed does it trigger a single LLM memory extraction; the query side (profile/event/context)
only reads the processed results, ensuring low latency.

This script uses the real memobase Python SDK to demonstrate this pipeline:
    insert (write conversation buffer) → flush (trigger extraction) → profile / event / context (retrieval)

Prerequisites: Memobase requires a running server + an LLM for memory extraction.
  * Self-hosted: see https://github.com/memodb-io/memobase (start with docker compose,
    default server address http://localhost:8019, default token is secret);
  * Cloud service: apply for project_url and api_key at https://www.memobase.io.
Without a server, use --dry-run to view sample conversations and the operations to be performed (no network, no fake results).
"""

import argparse
import json
import os
import sys
from pathlib import Path

#  Example multi-turn conversation: content deliberately covers three profile topics to observe the two-level structure of Profile
SAMPLE_CONVERSATION = [
    {"role": "user", "content": "Hello, my name is Li Ming, I am 28 years old and live in Shanghai."},
    {"role": "assistant", "content": "Hello Li Ming, nice to meet you! How can I help you?"},
    {"role": "user", "content": "I work as a backend engineer at a game company, mainly using Go."},
    {"role": "assistant", "content": "Backend engineer is cool, Go is very common in high-concurrency services."},
    {"role": "user", "content": "I usually like playing open-world games like The Legend of Zelda and Elden Ring."},
    {"role": "assistant", "content": "The sense of exploration in open-world games is indeed great."},
    {"role": "user", "content": "By the way, last week we set the budget for the new project at 500,000."},
    {"role": "assistant", "content": "Okay, I remember the new project budget is 500,000."},
]

#  Expected extracted profile topics (only for --dry-run structure explanation, not actual results)
EXPECTED_TOPICS = {
    "basic_info": ["Name", "Age", "City"],
    "work": ["Position", "Company", "Tech Stack"],
    "interest": ["Game Preference"],
}

DEFAULT_PROJECT_URL = os.getenv("MEMOBASE_PROJECT_URL", "http://localhost:8019")
DEFAULT_API_KEY = os.getenv("MEMOBASE_API_KEY", "secret")


def load_conversation(input_path: str | None) -> list[dict]:
    """Read conversations from the JSON file specified by --input, or use built-in example conversations if not specified.

    File format: [{"role": "user"|"assistant", "content": "..."}, ...]
    """
    if not input_path:
        return SAMPLE_CONVERSATION
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(
        isinstance(m, dict) and "role" in m and "content" in m for m in data
    ):
        raise ValueError("The conversation file should be a JSON in the form [{'role':..., 'content':...}, ...]")
    return data


def print_conversation(conversation: list[dict]) -> None:
    print("\n💬 Conversation content:")
    for m in conversation:
        who = "👤 User" if m["role"] == "user" else "🤖 Assistant"
        print(f"  {who}: {m['content']}")


def build_client(args):
    """Construct and connect to the Memobase client (online). Provide actionable hints on failure."""
    try:
        from memobase import MemoBaseClient
    except ImportError:
        print("❌ memobase SDK not installed, please run: pip install -r requirements.txt")
        sys.exit(1)

    client = MemoBaseClient(project_url=args.project_url, api_key=args.api_key)
    try:
        reachable = client.ping()
    except Exception as exc:  #  Connection refused, timeout, DNS failure, etc.
        reachable = False
        print(f"❌ Error connecting to Memobase server:{exc}")
    if not reachable:
        print("❌ Unable to connect to Memobase server:", args.project_url)
        print("   Please confirm the service is running (self-hosted see docker compose of memodb-io/memobase),")
        print("   or use --project-url / --api-key to specify cloud service address and key.")
        print("   To only view examples and flow (offline), add --dry-run.")
        sys.exit(1)
    return client


def render_profiles(profiles) -> list[dict]:
    """Organize the UserProfile list returned by the SDK into a topic → subtopic → content structure."""
    rows = []
    for p in profiles:
        rows.append({"topic": p.topic, "sub_topic": p.sub_topic, "content": p.content})
    return rows


def render_events(events) -> list[dict]:
    """Organize the UserEventData list returned by the SDK into a readable timeline."""
    rows = []
    for e in events:
        tip = None
        tags = None
        if e.event_data is not None:
            tip = e.event_data.event_tip
            if e.event_data.event_tags:
                tags = {t.tag: t.value for t in e.event_data.event_tags}
        rows.append(
            {
                "created_at": str(e.created_at),
                "event_tip": tip,
                "event_tags": tags,
            }
        )
    return rows


def op_insert(user, conversation) -> None:
    from memobase import ChatBlob

    print_conversation(conversation)
    bid = user.insert(ChatBlob(messages=conversation))
    print(f"\n✅ Written to conversation buffer (blob id: {bid}）")
    print("   Note: Writing only enters the buffer; memory is not yet extracted; execute flush to trigger extraction.")


def op_flush(user) -> None:
    print("\n🧠 Flushing buffer, triggering memory extraction (done by server-side LLM, may take a few seconds)...")
    ok = user.flush(sync=True)
    print("✅ Memory extraction complete" if ok else "⚠️ flush returned False, please check server logs")


def op_profile(user) -> list[dict]:
    profiles = render_profiles(user.profile())
    print("\n📇 User Profile (topic → subtopic → content):")
    if not profiles:
        print("   (No profile yet. Insert conversations and flush to extract first.)")
    for r in profiles:
        print(f"  • [{r['topic']}] {r['sub_topic']}: {r['content']}")
    return profiles


def op_event(user) -> list[dict]:
    events = render_events(user.event())
    print("\n🗓️  Event Memory (timeline):")
    if not events:
        print("   (No events yet.)")
    for r in events:
        print(f"  • {r['created_at']}  {r['event_tip'] or ''}")
        if r["event_tags"]:
            print(f"       Tags: {r['event_tags']}")
    return events


def op_context(user) -> str:
    ctx = user.context()
    print("\n🧩 Assembled memory context (can be directly spliced into LLM prompt):")
    print(ctx if ctx else "   (Empty)")
    return ctx


def run_demo(user, conversation, output_path):
    """End-to-end demo: Build profile from conversations, then recall profile/events/context."""
    print("=" * 64)
    print("Memobase User Profile + Event Memory End-to-End Demo")
    print("=" * 64)
    op_insert(user, conversation)
    op_flush(user)
    profiles = op_profile(user)
    events = op_event(user)
    ctx = op_context(user)
    result = {"profiles": profiles, "events": events, "context": ctx}
    if output_path:
        Path(output_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n💾 Results written to:{output_path}")
    return result


def run_dry_run(conversation):
    """Offline mode: No network, show example conversations, buffer batch processing flow, and expected profile structure."""
    print("=" * 64)
    print("Memobase Demo (--dry-run offline preview, no server connection, no fake results)")
    print("=" * 64)
    print_conversation(conversation)
    print("\n🔀 Operations to be executed (buffer batch pipeline):")
    print("  1) insert  — Write the above conversations to user buffer (no extraction triggered)")
    print("  2) flush   — Trigger a single LLM memory extraction (amortize call cost)")
    print("  3) profile — Read extracted structured user profile")
    print("  4) event   — Read event memory organized by timeline")
    print("  5) context — Read assembled memory context")
    print("\n🧬 Expected profile structure to be extracted (topic → subtopic, illustrative, not actual results):")
    for topic, subs in EXPECTED_TOPICS.items():
        print(f"  • {topic}: {', '.join(subs)}")
    print("\n▶️  After connecting to a real server, remove --dry-run to execute the full pipeline.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Memobase User Profile + Event Memory Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example: \n"
            "  python profile_demo.py                      # End-to-end demo (built-in example conversation)\n"
            "  python profile_demo.py --dry-run            # Preview flow offline, do not connect to server\n"
            "  python profile_demo.py --op profile         # Only recall extracted user profile\n"
            "  python profile_demo.py --op event           # Only view event memory timeline\n"
            "  python profile_demo.py --input chat.json --output result.json\n"
        ),
    )
    parser.add_argument(
        "--op",
        choices=["demo", "insert", "flush", "profile", "event", "context", "reset"],
        default="demo",
        help="Memory operations: demo=end-to-end demo (default); insert=write conversation buffer; "
        "flush=trigger extraction; profile=recall profile; event=event memory; "
        "context=memory context; reset=delete user and reset",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Conversation input file (JSON: [{'role','content'}, ...]), uses built-in example conversation if omitted",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default="demo_user_liming",
        help="User ID (default demo_user_liming)",
    )
    parser.add_argument(
        "--project-url",
        type=str,
        default=DEFAULT_PROJECT_URL,
        help=f"Memobase service URL (default {DEFAULT_PROJECT_URL}, can use environment variable MEMOBASE_PROJECT_URL)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=DEFAULT_API_KEY,
        help="Memobase access key (default from environment variable MEMOBASE_API_KEY, default for self-hosted is secret)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM used for memory extraction (for reference only: Memobase configures the extraction model on the server side, "
        "the client does not specify it directly; to change, modify the server .env)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write profile/event/context results to specified JSON file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Offline preview: only show example conversation and operation flow, do not connect to server or fake results",
    )
    return parser


def main():
    args = build_parser().parse_args()
    try:
        conversation = load_conversation(args.input)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"❌ Failed to read conversation file ({args.input}）：{exc}")
        sys.exit(1)

    if args.dry_run:
        run_dry_run(conversation)
        return

    if args.model:
        print(f"ℹ️  --model={args.model}: Memobase's extraction model is configured on the server side, this is for reference only.")

    client = build_client(args)
    user = client.get_or_create_user(args.user_id)

    if args.op == "demo":
        run_demo(user, conversation, args.output)
        return

    result = None
    if args.op == "insert":
        op_insert(user, conversation)
    elif args.op == "flush":
        op_flush(user)
    elif args.op == "profile":
        result = {"profiles": op_profile(user)}
    elif args.op == "event":
        result = {"events": op_event(user)}
    elif args.op == "context":
        result = {"context": op_context(user)}
    elif args.op == "reset":
        client.delete_user(args.user_id)
        print(f"🧹 User {args.user_id} deleted, profile and events cleared.")

    if result and args.output:
        Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n💾 Results written to:{args.output}")


if __name__ == "__main__":
    main()
