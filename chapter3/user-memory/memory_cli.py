#!/usr/bin/env python3
"""
User Memory Offline CLI Tool (memory_cli)

This is an **offline** memory operations CLI that directly operates on the persistent storage of memory_manager,
without requiring any LLM API, to demonstrate the complete lifecycle of the user memory system:
extraction (manual writing) → storage → update → deduplication/versioned conflict resolution → cross-session recall.

Division of labor with main.py:
  * main.py — complete conversation/background memory processing/evaluation pipeline, requires LLM API.
  * memory_cli.py — single memory CRUD and consolidation logic, fully local and runnable,
    convenient for verifying storage, deduplication, and conflict resolution behavior without an API Key.

Subcommands:
  add          Write a memory (simulate extracting a fact from a session)
  query        Retrieve memories by keyword (cross-session recall)
  update       Update an existing memory by ID
  consolidate  Perform deduplication and versioned conflict resolution on memories (no API needed)
  show         Print all current memories of a user
  demo         Run a multi-session offline example showing memory reuse in subsequent sessions
  extract      Automatically extract memories from a conversation (requires LLM API)

Examples:
  python memory_cli.py demo
  python memory_cli.py add --user alice --session s1 \
      --content "likes window seat" --tags seat_preference
  python memory_cli.py query --user alice --query seat
  python memory_cli.py consolidate --user alice
"""

import argparse
import sys

from config import Config, MemoryMode
from memory_manager import create_memory_manager


#Memory mode string -> enum, shared by all subcommands
MODE_MAP = {
    "notes": MemoryMode.NOTES,
    "enhanced_notes": MemoryMode.ENHANCED_NOTES,
    "json_cards": MemoryMode.JSON_CARDS,
    "advanced_json_cards": MemoryMode.ADVANCED_JSON_CARDS,
}


def _apply_store_path(store_path):
    """If --store-path is specified, redirect the memory storage directory (does not affect default data)."""
    if store_path:
        Config.MEMORY_STORAGE_DIR = store_path
    Config.create_directories()


def _build_manager(args):
    """Construct the corresponding memory manager from command line arguments (set storage directory first, then instantiate)."""
    _apply_store_path(getattr(args, "store_path", None))
    mode = MODE_MAP[args.memory_mode] if getattr(args, "memory_mode", None) else Config.MEMORY_MODE
    manager = create_memory_manager(args.user, mode)
    manager.verbose = True
    return manager, mode


def cmd_add(args):
    """Write a memory. Only notes / enhanced_notes modes support free text writing."""
    manager, mode = _build_manager(args)
    if mode not in (MemoryMode.NOTES, MemoryMode.ENHANCED_NOTES):
        print("❌ add subcommand only supports notes / enhanced_notes modes (for JSON cards, use main.py's conversation flow to generate)")
        return 1
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    note_id = manager.add_memory(args.content, args.session, tags=tags)
    print(f"✅ Memory written, ID={note_id}")
    return 0


def cmd_query(args):
    """Retrieve memories by keyword — used to demonstrate recalling user information in subsequent sessions."""
    manager, _ = _build_manager(args)
    results = manager.search_memories(args.query)
    if not results:
        print(f"🔍 No memories found related to \"{args.query}\"")
        return 0
    print(f"🔍 Found {len(results)} memories related to \"{args.query}\":")
    for item in results:
        if hasattr(item, "content"):  # MemoryNote
            tags = f" [tags: {', '.join(item.tags)}]" if item.tags else ""
            print(f"  - ({item.note_id[:8]}) {item.content}{tags}")
        else:  # (memory_path, data) tuple from JSON managers
            path, data = item
            print(f"  - {path}: {data}")
    return 0


def cmd_update(args):
    """Update an existing memory by ID (simulate user providing updated information)."""
    manager, _ = _build_manager(args)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    ok = manager.update_memory(args.id, args.content, args.session, tags=tags)
    print("✅ Update successful" if ok else "⚠️  No memory found with the given ID, update failed")
    return 0 if ok else 1


def cmd_consolidate(args):
    """Deduplication + versioned conflict resolution (fully offline, no API needed)."""
    manager, _ = _build_manager(args)
    if not hasattr(manager, "consolidate_memories"):
        print("ℹ️  Consolidation for the current memory mode is automatically handled by key overwriting during writing; no explicit consolidate needed.")
        return 0
    report = manager.consolidate_memories(resolve_conflicts=not args.no_conflict)
    print("\n===== Memory Consolidation Report =====")
    print(f"Count before consolidation: {report['initial_count']}")
    print(f"Duplicates removed: {report['duplicates_removed']}")
    print(f"Conflicts resolved: {len(report['conflicts_resolved'])}")
    for c in report["conflicts_resolved"]:
        print(f"  ⚔️  Attribute \"{c['attribute']}\": kept \"{c['kept']}」，"
              f"Discarded {c['superseded']}")
    print(f"Count after consolidation: {report['final_count']}")
    return 0


def cmd_show(args):
    """Print all current memories of a user (i.e., the string injected into the model context)."""
    manager, mode = _build_manager(args)
    print(f"\n===== User {args.user}'s memories (mode: {mode.value}）=====")
    print(manager.get_context_string())
    return 0


def cmd_demo(args):
    """Multi-session offline example: write → conflict/duplicate → consolidate → subsequent session recall.

    Uses an independent user_id and temporary storage directory, never touches real user data under data/.
    """
    import tempfile

    Config.MEMORY_STORAGE_DIR = args.store_path or tempfile.mkdtemp(prefix="memcli_demo_")
    Config.create_directories()
    user_id = "demo_user"
    mgr = create_memory_manager(user_id, MemoryMode.NOTES)
    mgr.verbose = False
    #Start from a clean state to avoid stacking old data when rerunning the demo
    if hasattr(mgr, "clear_all_memories"):
        mgr.notes = []

    print("\n" + "=" * 62)
    print("  Multi-session user memory demo (offline, no API required)")
    print(f"  Storage directory: {Config.MEMORY_STORAGE_DIR}")
    print("=" * 62)

    # ---- Session 1 (earlier): First understanding of user preferences ----
    print("\n[Session 1 · 2024-03-01] User's first interaction, Agent extracted the following facts:")
    mgr.add_memory("User prefers window seat", "session_2024_03", tags=["seat_preference"])
    mgr.add_memory("User lives in Chaoyang District, Beijing", "session_2024_03", tags=["home_address"])
    mgr.add_memory("User likes Sichuan cuisine", "session_2024_03", tags=["food_preference"])
    for n in mgr.notes:
        print(f"    + {n.content}  [{n.tags[0]}]")

    # ---- Session 2 (later): User moved (conflict) and repeated seat preference (duplicate) ----
    print("\n[Session 2 · 2024-09-15] User provided updated information:")
    mgr.add_memory("User has moved to Pudong, Shanghai", "session_2024_09", tags=["home_address"])
    mgr.add_memory("User prefers window seat", "session_2024_09", tags=["seat_preference"])  #  Duplicate
    print("    + User has moved to Pudong, Shanghai  [home_address]  (conflict with Beijing address in Session 1)")
    print("    + User prefers window seat  [seat_preference]  (duplicate of Session 1)")
    print(f"\n  Total {len(mgr.notes)} memories before consolidation (including 1 duplicate, 1 conflict)")

    # ---- Memory consolidation: deduplication + versioned conflict resolution ----
    print("\n[Background consolidation] Running consolidate_memories(): deduplication + conflict resolution by update time")
    report = mgr.consolidate_memories(resolve_conflicts=True)
    print(f"    Deleted duplicates: {report['duplicates_removed']} items")
    for c in report["conflicts_resolved"]:
        print(f"    Conflict resolved: attribute \"{c['attribute']}\" kept \"{c['kept']}\", discarded {c['superseded']}")
    print(f"    Total {report['final_count']} memories after consolidation")

    # ---- Session 3 (later): Recalling user information in subsequent session ----
    print("\n[Session 3 · 2025-01-20] User asks: \"Book me a flight, do you still remember where I live?\"")
    hits = mgr.search_memories("home_address")
    recalled = hits[0].content if hits else "(No relevant memory)"
    print(f"    Agent retrieves memory (home_address) → recalls:{recalled}")
    print(f"    ✅ Agent replies: Flights recommended based on your address in Pudong, Shanghai.")
    print("       (Note: This recalls the latest address after conflict resolution, not the old address from Session 1)")

    print("\nFinal memory snapshot:")
    print(mgr.get_context_string())
    return 0


def cmd_extract(args):
    """Automatically extract memories from a conversation — requires an LLM API (online).

    Parameter parsing and validation for this subcommand can be done offline; actual extraction calls the backend memory processor,
    which requires the corresponding provider's API Key to be configured.
    """
    provider = args.provider or Config.PROVIDER
    if not Config.get_api_key(provider):
        print(f"⚠️  extract requires an LLM API: No API Key found for provider '{provider}'.")
        print("    Please configure the corresponding *_API_KEY in .env and retry (parameter parsing passed).")
        return 2

    #  Read conversation text: --conversation can be a file path or direct text
    import os
    text = args.conversation
    if text and os.path.isfile(text):
        with open(text, "r", encoding="utf-8") as f:
            text = f.read()
    if not text:
        print("❌ Please provide conversation text or file path via --conversation")
        return 1

    _apply_store_path(args.store_path)
    mode = MODE_MAP[args.memory_mode] if args.memory_mode else Config.MEMORY_MODE

    from background_memory_processor import BackgroundMemoryProcessor
    processor = BackgroundMemoryProcessor(
        user_id=args.user, provider=provider, model=args.model, memory_mode=mode, verbose=True
    )
    #  Split plain text conversation into user/assistant turns and send to processor for analysis
    lines = [ln for ln in text.splitlines() if ln.strip()]
    conversation = [{"role": "user" if i % 2 == 0 else "assistant", "content": ln}
                    for i, ln in enumerate(lines)]
    processor.analyze_conversation(conversation)
    print("\n✅ Extraction complete, current memory:")
    print(processor.memory_manager.get_context_string())
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="memory_cli.py",
        description="User memory offline CLI tool: add/query/update/organize memories, demonstrate cross-session memory storage and conflict resolution (no API required).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="Subcommands")

    def add_common(p, need_mode=True):
        p.add_argument("--user", default="default_user", help="User ID (default: default_user)")
        p.add_argument("--store-path", default=None,
                       help="Memory storage directory (default: data/memories, can specify another path to avoid affecting real data)")
        if need_mode:
            p.add_argument("--memory-mode", choices=list(MODE_MAP.keys()), default=None,
                           help="Memory storage format (default: environment variable MEMORY_MODE)")

    p_add = sub.add_parser("add", help="Write a memory (simulate a fact extracted from a conversation)")
    add_common(p_add)
    p_add.add_argument("--session", default="cli_session", help="Source session ID (default: cli_session)")
    p_add.add_argument("--content", required=True, help="Memory content text")
    p_add.add_argument("--tags", default=None, help="Tags, comma-separated; the first tag is used as the attribute key for conflict resolution")
    p_add.set_defaults(func=cmd_add)

    p_query = sub.add_parser("query", help="Search memories by keyword (cross-session recall)")
    add_common(p_query)
    p_query.add_argument("--query", required=True, help="Search keyword")
    p_query.set_defaults(func=cmd_query)

    p_update = sub.add_parser("update", help="Update an existing memory by ID")
    add_common(p_update)
    p_update.add_argument("--id", required=True, help="Memory ID to update")
    p_update.add_argument("--session", default="cli_session", help="Session ID for this update")
    p_update.add_argument("--content", required=True, help="Updated memory content")
    p_update.add_argument("--tags", default=None, help="Updated tags, comma-separated")
    p_update.set_defaults(func=cmd_update)

    p_cons = sub.add_parser("consolidate", help="Deduplication + versioned conflict resolution (fully offline)")
    add_common(p_cons)
    p_cons.add_argument("--no-conflict", action="store_true",
                        help="Only deduplicate, no conflict resolution")
    p_cons.set_defaults(func=cmd_consolidate)

    p_show = sub.add_parser("show", help="Print all current memories for a user")
    add_common(p_show)
    p_show.set_defaults(func=cmd_show)

    p_demo = sub.add_parser("demo", help="Multi-session offline example: write → conflict/duplicate → organize → subsequent session recall")
    p_demo.add_argument("--store-path", default=None,
                        help="Storage directory for demo data (default: temp directory, does not touch data/)")
    p_demo.set_defaults(func=cmd_demo)

    p_ext = sub.add_parser("extract", help="Automatically extract memories from conversations (requires LLM API)")
    add_common(p_ext)
    p_ext.add_argument("--conversation", required=True, help="Conversation text or conversation file path")
    p_ext.add_argument("--provider", default=None,
                       choices=["siliconflow", "doubao", "kimi", "moonshot", "openrouter"],
                       help="LLM provider (default: environment variable PROVIDER)")
    p_ext.add_argument("--model", default=None, help="Model name (default: provider's default model)")
    p_ext.set_defaults(func=cmd_extract)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
