"""
Experiment 8-6 One-click demo: python demo.py

Process:
1) Print dataset overview and a few task examples that "do not imply tool names".
2) Use strong reference Agent to run four-layer validation on 2-3 tasks (including real LLM-as-a-Judge scoring).
3) Use weak reference Agent as a control to show the discriminative power of the four layers.
4) Reuse layer comparison: strong directly retrieves registered tools for a second similar task; weak repeats search and creation.
5) Finally print a "per-task × per-layer" result table, horizontally comparing each task's scores across the four layers.

Usage:
    python demo.py                       # Default: strong runs 3 tasks + weak control runs 1 task
    python demo.py --quick               # Quick demo: strong/weak each run only 1 task, saves time and cost
    python demo.py --tasks task-01,task-07   # Specify task IDs to evaluate (comma-separated)
    python demo.py --all --offline       # Run all 20 tasks offline without API key on deterministic layers (L1/L2/L4)
    python demo.py --layers L1,L2,L4     # Run only specified layers (excluding L3 means no network required)
    python demo.py --output results.json # Write full scoring results as JSON

Full parameters see python demo.py --help.
"""

import argparse
import json
import os
import sys
import unicodedata

from agent import STRONG, WEAK, SelfEvolutionAgent, ToolRegistry
from config import Config
from harness import ALL_LAYERS, FourLayerEvaluator

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_TASK_IDS = ["task-01", "task-17", "task-07"]  #Multimedia / Geospatial / Weather
_PROFILES = {"strong": STRONG, "weak": WEAK}


def load_dataset():
    with open(os.path.join(HERE, "dataset.json"), encoding="utf-8") as f:
        return json.load(f)


def fmt(x):
    return "N/A" if x is None else f"{x:.3f}"


def _disp_w(s: str) -> int:
    """Consider display width of CJK full-width characters for table alignment."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def _pad(s: str, width: int) -> str:
    s = str(s)
    return s + " " * max(0, width - _disp_w(s))


def print_dataset_overview(ds):
    tasks = ds["tasks"]
    print("=" * 78)
    print(f"Dataset:{ds['meta']['name']}  Total {len(tasks)} tasks, covering domains:")
    domains = [t["domain"] for t in tasks]
    print("  " + " | ".join(domains))
    print("-" * 78)
    print("Task examples (note: only state the goal, do not imply tool name / library name):")
    for t in tasks[:4]:
        print(f"  [{t['id']}] ({t['domain']}) {t['goal']}")
    print("=" * 78 + "\n")


def print_report(rep):
    L = rep["layers"]
    print(f"■ Task {rep['task_id']} ({rep['domain']}) | Profile={rep['profile']}")
    print(f"  L1 Task Correctness     : {fmt(L['L1']['score'])}  | {L['L1']['detail']}")
    print(f"  L2 Tool Discovery Effectiveness : {fmt(L['L2']['score'])}  | {L['L2']['detail']}")
    l3 = L["L3"]
    print(f"  L3 Tool Creation Quality   : {fmt(l3['score'])}  | {l3['detail']}")
    if l3.get("rubric"):
        r = l3["rubric"]
        print(f"       Rubric: Error Handling={r.get('error_handling')} Parameter Validation={r.get('input_validation')} "
              f"Documentation={r.get('documentation')} Robustness={r.get('robustness')}")
        print(f"       LLM-Judge Comments: {r.get('comment', '')}")
    print(f"  L4 Tool Reuse Capability   : {fmt(L['L4']['score'])}  | {L['L4']['detail']}")
    print(f"  >> Overall Score   : {fmt(rep['summary']['overall'])}  (Layers considered: {rep['summary']['used_layers']})")
    print()


def print_results_table(reports):
    """Print 'per-task × per-layer' result table: horizontal comparison of scores across L1-L4 and overall."""
    if not reports:
        return
    headers = ["Task", "Domain", "Profile", "L1", "L2", "L3", "L4", "Overall"]
    rows = []
    for rep in reports:
        L = rep["layers"]
        rows.append([
            rep["task_id"],
            rep["domain"],
            rep.get("profile") or "-",
            fmt(L["L1"]["score"]), fmt(L["L2"]["score"]),
            fmt(L["L3"]["score"]), fmt(L["L4"]["score"]),
            fmt(rep["summary"]["overall"]),
        ])
    widths = [max(_disp_w(headers[i]), *(_disp_w(r[i]) for r in rows)) for i in range(len(headers))]
    print("=" * 78)
    print("Per-task × per-layer result table (N/A = layer not applicable or not selected)")
    print("-" * 78)
    print("  ".join(_pad(headers[i], widths[i]) for i in range(len(headers))))
    for r in rows:
        print("  ".join(_pad(r[i], widths[i]) for i in range(len(r))))
    print("=" * 78 + "\n")


def run_profile(name, profile, tasks, evaluator, offline=False, verbose=True):
    """Run all tasks under one profile, return a list of four-layer scoring reports for each task."""
    if verbose:
        print("#" * 78)
        print(f"# Evaluate with {name} reference Agent (for each task: first run the initial task, then run a similar task to test reuse)")
        print("#" * 78 + "\n")
    registry = ToolRegistry()  # Per-profile independent registry
    agent = SelfEvolutionAgent(registry=registry, model=Config.AGENT_MODEL, offline=offline)
    reports = []
    for task in tasks:
        first = agent.run(task, profile, use_variant=False)   #  First: Discover + Create + Register (strong true-tune LLM generation tool)
        variant = agent.run(task, profile, use_variant=True)  #  Second similar task: test reuse
        rep = evaluator.evaluate(task, first, variant)
        reports.append(rep)
        if verbose:
            print_report(rep)
            #  Show trajectory difference evidence for reuse layer
            v_actions = [s["action"] for s in variant["steps"]]
            print(f"    [Reuse Probe] Action sequence for second similar task: {v_actions}")
            print()
    return reports


def parse_args():
    ap = argparse.ArgumentParser(
        description="Experiment 8-6: Design evaluation dataset for self-evolving Agent · Four-layer validation demo",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Example: \n"
            "  python demo.py                        Default: strong runs 3 tasks + weak runs 1 control\n"
            "  python demo.py --quick               strong / weak each runs only 1 task, saves time and cost\n"
            "  python demo.py --tasks task-01,task-07   Specify task IDs to evaluate\n"
            "  python demo.py --all --offline       Run all 20 tasks' deterministic layers offline without Key\n"
            "  python demo.py --layers L1,L2,L4     Run only specified layers (no L3 means no internet needed)\n"
            "  python demo.py --profile both --table Run both profiles, show only result table\n"
            "  python demo.py --output results.json Write full scoring results as JSON"
        ),
    )
    # ---- Task Selection ----
    ap.add_argument("--quick", action="store_true",
                    help="Quick demo: strong / weak each runs only 1 task, reducing API calls and time.")
    ap.add_argument("--all", action="store_true",
                    help="Evaluate all 20 tasks in the dataset (default switches to table output).")
    ap.add_argument("--tasks", metavar="IDS",
                    help="Comma-separated task IDs (e.g., task-01,task-07), defaults to built-in example tasks.")
    # ---- Layer and Profile Selection ----
    ap.add_argument("--layers", metavar="L1,L2,...",
                    help="Select which validation layers to run, comma-separated (default runs all four layers).\n"
                         "Only L3 requires LLM calls via internet; removing L3 allows fully offline operation.")
    ap.add_argument("--profile", choices=["strong", "weak", "both"],
                    help="Reference Agent profile under test: strong / weak / both.\n"
                         "Default retains default behavior (strong runs all selected tasks + weak runs only the first).")
    ap.add_argument("--offline", action="store_true",
                    help="Offline mode: no LLM calls (strong uses offline tool templates),\n"
                         "and automatically skips L3. Used for demonstrating L1/L2/L4 deterministic layers without API Key.")
    # ---- Model / Provider ----
    ap.add_argument("--provider", choices=["openai", "moonshot", "ark"],
                    help="Override PROVIDER (default reads environment variable, defaults to openai).")
    ap.add_argument("--agent-model", metavar="MODEL",
                    help="Override the model used by the Agent under test for tool creation (default reads AGENT_MODEL).")
    ap.add_argument("--judge-model", metavar="MODEL",
                    help="Override the model used by L3 LLM-as-a-Judge (default reads JUDGE_MODEL).")
    # ---- Output ----
    ap.add_argument("--table", action="store_true",
                    help="Print only 'per-task × per-layer' result table, not detailed per-task layer reports.")
    ap.add_argument("--output", metavar="PATH",
                    help="Write the complete scoring result (including details of each layer) to a JSON file.")
    return ap.parse_args()


def resolve_layers(args):
    """Determine which layers to actually run based on --layers / --offline."""
    if args.layers:
        want = [x.strip().upper() for x in args.layers.split(",") if x.strip()]
        bad = [x for x in want if x not in ALL_LAYERS]
        if bad:
            print(f"[Error] Unknown layer: {bad}, optional: {list(ALL_LAYERS)}")
            sys.exit(1)
        layers = tuple(x for x in ALL_LAYERS if x in want)  # Normalize to L1..L4 order
    elif args.offline:
        layers = ("L1", "L2", "L4")  # Offline mode: skip L3 which requires network by default
    else:
        layers = ALL_LAYERS
    if args.offline and "L3" in layers:
        print("[Hint] Offline mode cannot run L3 (requires an online LLM judge); L3 has been automatically removed from the current layer set.\n")
        layers = tuple(x for x in layers if x != "L3")
    return layers


def main():
    args = parse_args()

    # Apply command-line overrides for vendor/model (higher priority than environment variables)
    if args.provider:
        Config.PROVIDER = args.provider
    if args.agent_model:
        Config.AGENT_MODEL = args.agent_model
    if args.judge_model:
        Config.JUDGE_MODEL = args.judge_model

    layers = resolve_layers(args)

    # Non-offline mode: the strong agent profiling tool will actually call the LLM, and L3 also requires network, so a usable client is needed.
    if not args.offline:
        try:
            Config.get_client()
        except Exception as e:
            print(f"[Configuration Error] {e}")
            print("Hint: If you only want to demonstrate deterministic layers, use `python demo.py --offline` (no API Key required).")
            sys.exit(1)

    mode = "offline" if args.offline else "online"
    print(f"Run mode={mode}  PROVIDER={Config.PROVIDER}  "
          f"AGENT_MODEL={Config.resolve_default_model()}  JUDGE_MODEL={Config.JUDGE_MODEL}")
    print(f"Verification layers for this run:{list(layers)}\n")

    ds = load_dataset()
    print_dataset_overview(ds)

    by_id = {t["id"]: t for t in ds["tasks"]}
    # Task selection: --tasks specified > --all all > --quick pick 1 > default 3 sample tasks
    if args.tasks:
        want = [i.strip() for i in args.tasks.split(",") if i.strip()]
        missing = [i for i in want if i not in by_id]
        if missing:
            print(f"[Error] These task IDs do not exist in the dataset: {missing}")
            sys.exit(1)
        task_ids = want
    elif args.all:
        task_ids = [t["id"] for t in ds["tasks"]]
    elif args.quick:
        task_ids = DEMO_TASK_IDS[:1]
    else:
        task_ids = DEMO_TASK_IDS
    tasks = [by_id[i] for i in task_ids]
    evaluator = FourLayerEvaluator(judge_model=Config.JUDGE_MODEL, layers=layers)

    # When there are many tasks (--all), only the result table is output by default to avoid flooding with per-task detailed reports.
    verbose = not (args.table or (args.all and not args.tasks))

    all_reports = []
    if args.profile in (None, "strong", "both"):
        # Strong: good discovery + high-quality tools (offline templates / online LLM calls) + reuse
        strong_tasks = tasks
        all_reports += run_profile("STRONG", STRONG, strong_tasks, evaluator,
                                   offline=args.offline, verbose=verbose)
    if args.profile in ("weak", "both"):
        weak_tasks = tasks
        all_reports += run_profile("WEAK", WEAK, weak_tasks, evaluator,
                                   offline=args.offline, verbose=verbose)
    elif args.profile is None:
        # Default behavior: weak only runs the first task, highlighting the four-layer differentiation.
        all_reports += run_profile("WEAK", WEAK, tasks[:1], evaluator,
                                   offline=args.offline, verbose=verbose)

    print_results_table(all_reports)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"layers": list(layers), "reports": all_reports}, f,
                      ensure_ascii=False, indent=2)
        print(f"[Written] Complete scoring result -> {args.output}\n")

    print("=" * 78)
    print("Conclusion: The four-layer verification yields different scores for 'strong' and 'weak' agents under test;")
    print(" L2 judges discovery effectiveness based on search keywords/database selection, L3 uses LLM-as-a-Judge to score tool code according to a rubric,")
    print(" L4 distinguishes 'reuse' from 'repeated search' via action sequences in a second similar task.")
    print("=" * 78)


if __name__ == "__main__":
    main()
