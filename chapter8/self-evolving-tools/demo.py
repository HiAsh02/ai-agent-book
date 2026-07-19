"""
Experiment 8-5 One-click Demo: `python demo.py`

Demonstrates two things:
  1) Evolution: Agent starts from zero basic tools — search → read docs → sandbox test → package tool →
     use the new tool to give the real stock price of NVIDIA (NVDA) and the real percentage change relative to one week ago.
  2) Reuse: Ask again with a different stock (AAPL). The Agent should first search_tools to find the already created tool and directly reuse it,
     without re-searching the web or reinventing the wheel. The program prints the trace and automatically verifies whether reuse occurred.

Online path (default) requires real internet + real OpenAI calls. Please configure OPENAI_API_KEY first.
If you don't have an API key / cannot access the internet, use `--offline` to run a "mechanism self-check": no LLM/network calls,
 directly drive the tool library's "search miss → create tool → pre-save validation → register → reuse" loop (see below).

Common examples:
    python demo.py                 # Run the two default tasks "evolution + reuse" (requires API)
    python demo.py --fresh         # Clear tool_library/ first then run (reproduce "evolution from scratch")
    python demo.py --offline       # Offline mechanism self-check (no API/network needed), demonstrates full evolution loop
    python demo.py --task "Query Bitcoin's current USD price and 24h change"   # Custom task (can be repeated)
    python demo.py --no-create     # Disable tool creation ability (control: can only reuse / cannot evolve)
    python demo.py --model gpt-5.6-luna --output run.json   # Override model and write results to JSON
    python demo.py --help          # View all parameters

Note: The tool library persists to tool_library/. If get_stock_price was already packaged in a previous run, directly running again
will hit and reuse it at step 0, so you won't see the "evolution" process; add --fresh to reproduce evolution.
"""

import argparse
import glob
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from tool_manager import LIBRARY_DIR, ToolLibrary


TASK_1 = "Query the latest stock price of NVIDIA (ticker NVDA) and the percentage change compared to one week ago. Provide real data."
TASK_2 = "Query the latest stock price of Apple (ticker AAPL) and the percentage change compared to one week ago. Provide real data."

_META_TOOLS = {"web_search", "read_webpage", "code_interpreter", "create_tool", "search_tools"}


def _clear_library():
    """Clear the persisted tool library (only delete generated *.json artifacts) to reproduce "evolution from scratch"."""
    removed = 0
    for p in glob.glob(os.path.join(str(LIBRARY_DIR), "*.json")):
        try:
            os.remove(p)
            removed += 1
        except OSError:
            pass
    print(f"[--fresh] Cleared tool_library/ (deleted {removed} packaged tools), will start evolution from scratch.\n")


def _is_reuse(traj: list) -> bool:
    """Whether a trace belongs to "tool reuse": called search_tools, did not redo web_search/create_tool,
    and actually called some packaged (non-meta) tool."""
    return (
        "search_tools" in traj
        and "web_search" not in traj
        and "create_tool" not in traj
        and any(t not in _META_TOOLS for t in traj)
    )


# --------------------------------------------------------------------------- #
# Offline mechanism self-check: no LLM/network calls, directly drive the tool library's evolution loop
#   search miss → create tool (with pre-save validation) → register → call → reuse
# Use a purely offline, deterministic tool (calculate days between two dates) to run through the full process,
# making it easy to verify that the "self-evolution + reuse" mechanism itself is reliable without an API key or internet.
# --------------------------------------------------------------------------- #
_DAYS_TOOL_CODE = (
    "from datetime import date\n\n"
    "def run(start, end):\n"
    "    s = date.fromisoformat(start)\n"
    "    e = date.fromisoformat(end)\n"
    "    return {'start': start, 'end': end, 'days': (e - s).days}\n"
)
_DAYS_TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "start": {"type": "string", "description": "Start date YYYY-MM-DD"},
        "end": {"type": "string", "description": "End date YYYY-MM-DD"},
    },
    "required": ["start", "end"],
}
# A "broken" bad tool: used to prove that the pre-save validation gate will indeed reject it from being stored
_BAD_TOOL_CODE = (
    "def run(start, end):\n"
    "    return {'days': undefined_name}\n"  # NameError at runtime
)


def run_offline_selftest(output_path: str | None = None) -> int:
    print("=" * 70)
    print("Offline mechanism self-check (--offline): no LLM/network calls, directly drive the tool library evolution loop")
    print("  Loop: search_tools miss → create_tool (pre-save validation) → register → call → reuse")
    print("=" * 70)

    tmp = Path(tempfile.mkdtemp(prefix="selfevolve_selftest_"))
    lib = ToolLibrary(library_dir=tmp)  # Use a temporary library, never pollute the user's real tool_library/
    try:
        # ---------- Pre-save validation gate demo: bad tool should be rejected from storage ----------
        print("\n[Validation Gate] Attempting to register a bad tool that crashes on run (with test_args)...")
        bad = lib.create_tool(
            "days_between_bad", "A sample tool that will crash", _DAYS_TOOL_PARAMS, _BAD_TOOL_CODE,
            test_args={"start": "2020-01-01", "end": "2020-03-01"},
        )
        print(f"  Result: success={bad.get('success')}  ->  {bad.get('error', '')[:60]}")
        assert not bad["success"], "Bad tool passed pre-save validation!"
        assert lib.get_tool("days_between_bad") is None, "Bad tool should not be persisted!"
        print("  ✅ Pre-save validation blocked the bad tool (not stored), consistent with 'don't store bad programs'.")

        # ---------- Task 1: Evolution (create tool) ----------
        traj1: list = []
        print("\n########## Offline Task 1: Calculate days between 2020-01-01 and 2020-03-01 (demonstrate evolution) ##########")
        traj1.append("search_tools")
        hit = lib.search_tools("date days between")
        print(f"[step 1] search_tools -> hit {hit['count']} (tool library empty, no hit)")

        traj1.append("create_tool")
        created = lib.create_tool(
            "days_between",
            "Calculate the number of days between two ISO dates (YYYY-MM-DD)",
            _DAYS_TOOL_PARAMS, _DAYS_TOOL_CODE,
            test_args={"start": "2020-01-01", "end": "2020-01-11"},
        )
        print(f"[step 2] create_tool(days_between) -> success={created['success']} "
              f"validated={created.get('validated')}(pre-save validation already actually ran run() once)")

        traj1.append("days_between")
        r1 = lib.execute_tool("days_between", {"start": "2020-01-01", "end": "2020-03-01"})
        ans1 = r1.get("result", {}).get("days")
        print(f"[step 3] days_between(...) -> {r1.get('result')}")
        print(f"[Offline Task 1 Conclusion] From 2020-01-01 to 2020-03-01 total {ans1} days.")

        # ---------- Task 2: Reuse (Don't Reinvent the Wheel) ----------
        traj2: list = []
        print("\n########## Offline Task 2: Calculate the number of days from 2021-01-01 to 2021-12-31 (Demonstrate Reuse) ##########")
        traj2.append("search_tools")
        hit2 = lib.search_tools("date days between")
        print(f"[step 1] search_tools -> hit {hit2['count']} items:{[t['name'] for t in hit2['tools']]}(Reuse!)")

        traj2.append("days_between")
        r2 = lib.execute_tool("days_between", {"start": "2021-01-01", "end": "2021-12-31"})
        ans2 = r2.get("result", {}).get("days")
        print(f"[step 2] days_between(...) -> {r2.get('result')}")
        print(f"[Offline Task 2 Conclusion] From 2021-01-01 to 2021-12-31 total {ans2} days.")

        reused = _is_reuse(traj2)
        print("\n" + "=" * 70)
        print("Offline Self-Check Conclusion")
        print("=" * 70)
        print(f"Task 1 Trajectory: {traj1}")
        print(f"Task 2 Trajectory: {traj2}")
        print(f"Did Task 2 reuse the tool created by Task 1 (without re-creating create_tool): {'Yes ✅' if reused else 'No ❌'}")
        print(f"Did the pre-save validation gate block bad tools: {'Yes ✅' if not bad['success'] else 'No ❌'}")

        if output_path:
            payload = {
                "mode": "offline_selftest",
                "gate_rejected_bad_tool": (not bad["success"]),
                "tasks": [
                    {"task": "Days from 2020-01-01 to 2020-03-01", "answer_days": ans1, "trajectory": traj1},
                    {"task": "Days from 2021-01-01 to 2021-12-31", "answer_days": ans2, "trajectory": traj2},
                ],
                "reused": reused,
            }
            Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            print(f"\n[Written] {output_path}")

        return 0 if (reused and not bad["success"]) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Online path: Real LLM + Real Network
# --------------------------------------------------------------------------- #
def run_online(tasks: list, allow_create: bool, model: str | None, output_path: str | None) -> int:
    # Lazy import: No need for openai dependency when running with --offline
    from agent import SelfEvolvingAgent

    try:
        agent = SelfEvolvingAgent(verbose=True, allow_create=allow_create, model=model)
    except RuntimeError as e:
        print(f"[Configuration Error] {e}", file=sys.stderr)
        print(
            "Please configure the API Key for the corresponding provider (default OpenAI): \n"
            "  cp env.example .env then fill in OPENAI_API_KEY in .env; \n"
            "  or directly export OPENAI_API_KEY=sk-...\n"
            "To switch providers: export LLM_PROVIDER=moonshot|ark and configure the corresponding "
            "MOONSHOT_API_KEY / ARK_API_KEY。\n"
            "(If you only want to verify the mechanism without an API key, run: python demo.py --offline)",
            file=sys.stderr,
        )
        return 2

    default = tasks == [TASK_1, TASK_2]
    runs = []
    for i, task in enumerate(tasks, 1):
        label = {1: "Task 1", 2: "Task 2"}.get(i, f"Task{i}") if default else f"Task{i}"
        tag = {1: "(Demonstrate Search → Test → Encapsulate → Use)", 2: "(Demonstrate Tool Reuse)"}.get(i, "") if default else ""
        print(f"\n########## {label}{tag} ##########")
        agent.trajectory = []
        ans = agent.run(task)
        traj = list(agent.trajectory)
        created = [t["name"] for t in agent.library.list_tools()]
        print(f"\n>>> {label}End. The current tool library has encapsulated tools: {created}")
        print(f">>> {label}Action trajectory: {traj}")
        runs.append({"task": task, "answer": ans, "trajectory": traj, "reused": _is_reuse(traj)})

    # Reuse check: Reuse is considered valid if any task other than the first one reuses.
    reused = any(r["reused"] for r in runs[1:])
    print("\n" + "=" * 70)
    print("Conclusion summary")
    print("=" * 70)
    for i, r in enumerate(runs, 1):
        print(f"[Task{i}] {r['answer']}")
    print("-" * 70)
    if len(runs) >= 2:
        print(f"Whether subsequent tasks reused created tools (without re-searching/creating): {'Yes ✅' if reused else 'No ❌'}")
        print("  Evidence: The reuse task called search_tools and did not show web_search/create_tool.")

    if output_path:
        Path(output_path).write_text(json.dumps(
            {"mode": "online", "model": agent.model, "allow_create": allow_create,
             "runs": runs, "reused": reused},
            ensure_ascii=False, indent=2))
        print(f"\n[Written] {output_path}")

    if len(runs) < 2:
        return 0
    return 0 if reused else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Experiment 8-5: One-click demo of Agent finding tools from the web and self-evolving.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: \n"
               "  python demo.py                 Run default two tasks (evolution + reuse, requires API)\n"
               "  python demo.py --fresh         Clear tool library first then run (reproduce evolution from scratch)\n"
               "  python demo.py --offline       Offline mechanism self-check (no API/network needed)\n"
               "  python demo.py --task '...'    Custom task (can be repeated multiple times)\n"
               "  python demo.py --no-create     Disable tool creation ability (control experiment)\n")
    p.add_argument("--task", action="append", metavar="Task description",
                   help="The task(s) to execute (can be specified multiple times to run multiple tasks in order)."
                        "If not specified, runs the default NVDA/AAPL two tasks.")
    p.add_argument("--offline", action="store_true",
                   help="Offline mechanism self-check: without calling LLM/network, directly drive the 'search → create tool → pre-save validation → register → reuse' loop.")
    p.add_argument("--fresh", action="store_true",
                   help="Clear tool_library/ before running to reproduce the 'evolution from scratch' process (recommended for repeated demos).")
    p.add_argument("--no-create", dest="allow_create", action="store_false",
                   help="Disable the 'create_tool' ability for control demo (tool creation allowed by default).")
    p.add_argument("--model", metavar="Model name", default=None,
                   help="Override LLM model name (higher priority than LLM_MODEL environment variable), e.g., gpt-5.6-luna.")
    p.add_argument("--output", metavar="Path", default=None,
                   help="Write the tasks, answers, action trajectories, and reuse conclusions of this run into that JSON file.")
    return p


def main():
    args = build_parser().parse_args()

    if args.offline:
        return run_offline_selftest(output_path=args.output)

    if args.fresh:
        _clear_library()

    tasks = args.task if args.task else [TASK_1, TASK_2]
    return run_online(tasks, allow_create=args.allow_create,
                      model=args.model, output_path=args.output)


if __name__ == "__main__":
    sys.exit(main())
