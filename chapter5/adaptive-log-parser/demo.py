"""
demo.py —— Adaptive Log Parsing System: Self-Healing Closed-Loop Demo

Demonstrates the complete self-healing process (full automation):
  Initial system only recognizes basic JSON logs →
  Encounters an unseen new format → Parsing [fails] and is detected →
  Failed sample + error are sent to Agent → Agent [generates parsing code] →
  [Automatic testing] (data structure assertions) → Upon passing, [hot-load registration + persistence] →
  System [correctly parses] the new format.

Run:
  python demo.py            # Full demo (two new formats, two Agent calls, requires API Key)
  python demo.py --offline  # Offline demo: uses pre-built parsers to run full mechanism, no API Key needed
  python demo.py --quick    # Quick mode: only demonstrates 1 new format, saves one API call
  python demo.py --help     # View all parameters

See build_arg_parser() at the bottom of the file for command-line arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import textwrap
from typing import List, Tuple

from engine import LogParserEngine, ParseError, builtin_json_parser
from agent import CodeGenAgent, OfflineCodeGenAgent
from tester import run_tests

HERE = os.path.dirname(os.path.abspath(__file__))
PARSERS_DIR = os.path.join(HERE, "parsers")

MAX_ATTEMPTS = 3  #Maximum number of iterative repairs for agent generation → testing


# ---------------------------------------------------------------------------
#  Three progressive log formats for demonstration
# ---------------------------------------------------------------------------
# Format 1: Basic JSON line — supported from the initial system
JSON_LOGS = [
    '{"timestamp": "2026-07-17T10:22:31Z", "level": "INFO", "message": "Agent started task planning"}',
    '{"timestamp": "2026-07-17T10:22:33Z", "level": "DEBUG", "message": "Loaded 12 tools into context"}',
]

# Format 2: Custom vertical bar separated format — Agent has not seen
#   Timestamp|Level|Module|step=N|Message
PIPE_LOGS = [
    "2026-07-17T10:23:01Z|INFO|agent.planner|step=3|Generated plan with 5 actions",
    "2026-07-17T10:23:04Z|WARNING|agent.executor|step=4|Tool call retried once",
    "2026-07-17T10:23:07Z|ERROR|agent.executor|step=5|Tool web_search returned empty result",
]
PIPE_REQUIRED = ["timestamp", "level", "module", "step", "message"]

# Format 3: Nested bracket format — Agent hasn't seen it either
#   [time] (level) <tool=name> {k=v k=v} :: message
BRACKET_LOGS = [
    "[2026-07-17 10:24:55] (ERROR) <tool=web_search> {latency_ms=812 status=timeout} :: upstream request failed",
    "[2026-07-17 10:25:01] (INFO) <tool=code_run> {latency_ms=134 status=ok} :: executed snippet successfully",
    "[2026-07-17 10:25:09] (WARN) <tool=file_read> {latency_ms=45 status=partial} :: file truncated at 1MB",
]
BRACKET_REQUIRED = ["timestamp", "level", "tool", "message"]


# ---------------------------------------------------------------------------
# Gadget
# ---------------------------------------------------------------------------
def hr(title: str = "") -> None:
    print("\n" + "=" * 78)
    if title:
        print(title)
        print("=" * 78)


def try_parse_all(
    engine: LogParserEngine, logs: List[str]
) -> Tuple[bool, List[dict]]:
    """Attempt to parse a batch of logs, print the results; return (whether all succeeded, list of successfully parsed structured records)."""
    all_ok = True
    records: List[dict] = []
    for line in logs:
        try:
            result = engine.parse_line(line)
            records.append(result)
            print(f"  ✅ [{result['_parser']}] {result}")
        except ParseError:
            all_ok = False
            print(f"  ❌ Parsing failed: {line}")
    return all_ok, records


def read_log_file(path: str) -> List[str]:
    """Read logs from an external log file (one per line, ignoring empty lines)."""
    with open(path, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def write_output(path: str, records: List[dict]) -> None:
    """Write the parsed structured records as JSONL (one JSON per line)."""
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Self-healing loop: detect failure → generate → test → hot update
# ---------------------------------------------------------------------------
def self_heal(
    engine: LogParserEngine,
    agent: "CodeGenAgent | OfflineCodeGenAgent",
    parser_name: str,
    samples: List[str],
    required_keys: List[str],
) -> bool:
    """Run the complete self-healing loop for a new format, return True on successful registration."""
    # (a) Trigger reason: Take a sample for the system to parse and confirm that it indeed failed
    failing_line = samples[0]
    try:
        engine.parse_line(failing_line)
        print("  (This format can already be parsed, no self-healing required)")
        return True
    except ParseError as exc:
        error_report = str(exc)
        print(f"  🔎 Detected a new format that cannot be parsed, triggering self-healing. Error: {error_report}")

    target_path = os.path.join(PARSERS_DIR, f"{parser_name}.py")
    feedback = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n  ---  Part {attempt}/{MAX_ATTEMPTS} 次：Agent generates parsing code ---")
        code = agent.generate_parser_code(
            samples=samples,
            required_keys=required_keys,
            error_report=error_report,
            feedback=feedback,
        )
        print(textwrap.indent(code, "    | "))

        # Write to candidate file (parsers/), then hot reload
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(code)

        #  Parse function generated by hot reloading
        try:
            fn = LogParserEngine.load_parser_from_file(target_path)
        except Exception as exc:
            feedback = f"Code cannot be imported/executed:{type(exc).__name__}: {exc}"
            print(f"  ⚠️ Hot reload failed: {feedback}")
            continue

        # (b) Automated testing: data structure assertions
        print("  🧪 Automated test (data structure assertion):")
        test = run_tests(fn, samples, required_keys)
        print(textwrap.indent(test["report"], "    "))

        if test["passed"]:
            # (c) Registered into the engine via hot update, the file has been persisted to parsers/
            engine.register(parser_name, fn)
            print(f"  ✅ Auto test passed, hot-updated registered parser '{parser_name}' and persist to parsers/{parser_name}.py")
            return True

        feedback = "Automated test failed, details as follows:\n" + test["report"]
        print("  ↻ Test failed, feed the failure report back to the Agent for retry.")

    #  All attempts failed: delete invalid file
    if os.path.exists(target_path):
        os.remove(target_path)
    print(f"  ❌ {MAX_ATTEMPTS}  Still failing after attempts, abandon this format.")
    return False


# ---------------------------------------------------------------------------
#  Main flow
# ---------------------------------------------------------------------------
def main(args: argparse.Namespace) -> None:
    hr("Adaptive Log Parsing System — Self-Healing Closed-Loop Demo (Experiment 5-7)")
    print("The initial system only has one built-in parser: JSON line parser.")
    if args.quick:
        print("  (--quick fast mode: only demo 1 new format, save one Agent/API call)")
    if args.offline:
        print("  (--offline offline mode: use preset parsers instead of OpenAI, no API Key needed, mechanism is identical)")

    os.makedirs(PARSERS_DIR, exist_ok=True)  #  Ensure the persistence directory exists (may only have .gitkeep when freshly cloned)

    engine = LogParserEngine()
    engine.register("builtin_json", builtin_json_parser)
    print(f"  Currently registered parsers:{engine.parser_names}")

    #  When model=None, fall back to MODEL environment variable / default gpt-5.6-luna; offline mode does not touch API
    agent = OfflineCodeGenAgent(args.model) if args.offline else CodeGenAgent(model=args.model)
    print(f"  Code generation Agent uses model:{agent.model}")

    #  Step 0: Basic JSON format, the system can parse it natively
    hr("Step 0: Parse basic JSON logs (natively supported by the system)")
    try_parse_all(engine, JSON_LOGS)

    #  Step 1: Custom pipe-separated format (Agent hasn't seen it)
    hr("Step 1: Encounter new format A — custom pipe-separated format")
    print("  Raw log sample:")
    for l in PIPE_LOGS:
        print(f"  {l}")
    print("\n(a) Let the system parse first, expect [failure]:")
    try_parse_all(engine, PIPE_LOGS)
    print("\nTrigger self-healing closed loop:")
    ok1 = self_heal(engine, agent, "pipe_parser", PIPE_LOGS, PIPE_REQUIRED)
    if ok1:
        print("\n(c) After hot update, re-parse the same logs, expect [success]:")
        try_parse_all(engine, PIPE_LOGS)

    #  Step 2: Nested bracket format (Agent hasn't seen it either) — skipped in quick mode to save one API call
    ok2 = None
    if args.quick:
        hr("Step 2: (--quick mode skipped demo of new format B)")
    else:
        hr("Step 2: Encounter new format B — nested bracket format")
        print("  Raw log sample:")
        for l in BRACKET_LOGS:
            print(f"  {l}")
        print("\n(a) Let the system parse first, expect [failure]:")
        try_parse_all(engine, BRACKET_LOGS)
        print("\nTrigger self-healing closed loop:")
        ok2 = self_heal(engine, agent, "bracket_parser", BRACKET_LOGS, BRACKET_REQUIRED)
        if ok2:
            print("\n(c) After hot update, re-parse the same logs, expect [success]:")
            try_parse_all(engine, BRACKET_LOGS)

    #  Step 3: Verify persistence reuse — new engine directly loads parsers/, no need to ask Agent again
    hr("Step 3: Verify persistence reuse (restart system, directly load learned parsers)")
    engine2 = LogParserEngine()
    engine2.register("builtin_json", builtin_json_parser)
    loaded = engine2.load_persisted(PARSERS_DIR)
    print(f"  New engine hot-loaded from parsers/:{loaded}")
    if args.log_file:
        print(f"  Parse external log files with the learned parsing system (no more Agent calls):{args.log_file}")
        mixed = read_log_file(args.log_file)
    else:
        print("  Directly parse the previous new format (no more Agent calls):")
        mixed = [JSON_LOGS[0], PIPE_LOGS[0]]
        if not args.quick:
            mixed.append(BRACKET_LOGS[0])  #  Quick mode did not generate bracket_parser, so it is not included in the mixed sample
    all_ok, records = try_parse_all(engine2, mixed)

    if args.output:
        write_output(args.output, records)
        print(f"  Has {len(records)}  Write structured parsing results to (JSONL):{args.output}")

    hr("Demo ends")
    print(f"New format A (pipe-separated) self-healing results:{'Success' if ok1 else 'Failure'}")
    if ok2 is None:
        print("New format B (nested parentheses): --quick mode skipped")
    else:
        print(f"New format B (nested parentheses) self-healing results:{'Success' if ok2 else 'Failure'}")
    print(f"Persistent reuse (mixed format fully parsed):{'Success' if all_ok else 'Failure'}")
    print(f"Learned and persisted parser directory:{PARSERS_DIR}")


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser (provides --help / --quick / --model)."""
    parser = argparse.ArgumentParser(
        description="Adaptive log parsing system: self-healing closed-loop demo (detect failure → Agent generates parsing code → "
        "Auto-test → hot-load registration → persistent reuse). Default uses OpenAI, requires OPENAI_API_KEY;"
        "Add --offline to use canned parsers to demonstrate the same mechanism, no API Key needed.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Offline mode: use canned parser code instead of calling OpenAI, no API Key needed,"
        "Deterministically demonstrate the entire mechanism of \"failure detection → generation → test → hot-reload → persistence\".",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: only demo 1 new format (pipe-separated), skip nested parentheses format, saving one Agent/API call.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the model used for code generation; default reads environment variable MODEL, then falls back to gpt-5.6-luna."
        "(Under --offline this option is for display only, does not affect canned parsers.)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="External log file path (one log per line). When given, step 3 uses the learned parsing system to parse"
        "that file instead of the built-in mixed samples; used to verify the learned parser can be reused on real log streams.",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write the structured results from step 3 to this file as JSONL (one JSON per line).",
    )
    return parser


if __name__ == "__main__":
    main(build_arg_parser().parse_args())
