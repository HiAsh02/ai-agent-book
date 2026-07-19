"""
Experiment 8-3: Automatic Optimization of System Prompts (Automated System Prompt Learning Based on Human Feedback)

Run the complete pipeline with one command:
  1. Evaluate with the [initial prompt] → expose the over-transfer issue of "transfer to human for policy disputes";
  2. Coding Agent reads the prompt file, locates the transfer rules, generates precise edits and [actually rewrites the file] → shows diff;
  3. Re-evaluate with the [automatically optimized prompt];
  4. Compare with the [manually tuned prompt];
  5. Print a comparison table of accuracy for the "holdout task set / boundary case set" before and after optimization, plus the manual version.

    python demo.py            # Full run: 10 test cases × 3 prompts
    python demo.py --quick    # Quick demo: only 2 cases per group, saves time and money
    python demo.py --help     # View all command-line arguments (Chinese description)
"""

import argparse
import json
import os
import shutil
import sys

from evaluate import evaluate_prompt
from coding_agent import optimize_prompt
from config import get_provider, get_model
from airline_env import CASES

GROUPS = ("holdout", "boundary")

HERE = os.path.dirname(os.path.abspath(__file__))
INITIAL_PROMPT = os.path.join(HERE, "prompts", "system_prompt.txt")
MANUAL_PROMPT = os.path.join(HERE, "prompts", "system_prompt_manual.txt")
WORKING_PROMPT = os.path.join(HERE, "runtime", "system_prompt_working.txt")

# Human expert feedback: This is the signal driving "automatic system prompt learning"
HUMAN_FEEDBACK = (
    "Evaluation reveals that the Agent has an [over-transfer] issue: whenever encountering a policy dispute (e.g., passenger requests a refund beyond policy,"
    "requests a free service, or requests a fee waiver), it directly transfers to a human agent without attempting to explain the policy to the passenger.\n"
    "The correct approach is: handle such disputes by patiently and empathetically explaining the policy, and provide compliant alternatives,"
    "rather than immediately transferring. The only two situations that truly require transfer to a human agent are when the passenger explicitly requests a human agent,"
    "or when there is an urgent safety / personal health risk."
)


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _pct(cn):
    c, n = cn
    return f"{c}/{n} ({100 * c / n:.0f}%)" if n else "-"


def print_table(rows):
    """rows: list of (label, holdout_tuple, boundary_tuple)"""
    print("\n" + "=" * 74)
    print("Accuracy comparison (holdout task set = existing correct behaviors must not regress; boundary case set = over-transfer should improve)")
    print("=" * 74)
    header = f"{'System prompt version':<26}{'Holdout task set':<20}{'Boundary case set':<20}"
    print(header)
    print("-" * 74)
    for label, holdout, boundary in rows:
        print(f"{label:<24}{_pct(holdout):<22}{_pct(boundary):<22}")
    print("=" * 74)


def _select_cases(limit_per_group=None, groups=GROUPS):
    """Filter test cases by group, and take at most limit_per_group per group (None means no limit)."""
    picked, counts = [], {}
    for c in CASES:
        g = c["group"]
        if g not in groups:
            continue
        if limit_per_group and counts.get(g, 0) >= limit_per_group:
            continue
        picked.append(c)
        counts[g] = counts.get(g, 0) + 1
    return picked


def main(cases=None, rounds=3, output=None):
    if cases is None:
        cases = CASES
    print("#" * 74)
    print("# Experiment 8-3: Automatic Optimization of System Prompts Based on Human Feedback (Airline Customer Service Scenario)")
    print(f"# LLM Provider: {get_provider()}   Model: {get_model()}")
    print(f"# Number of test cases: {len(cases)}(holdout set + boundary set)   Coding Agent optimization rounds limit: {rounds}")
    print("#" * 74)

    # ---- Preparation: Copy the initial prompt to a working copy for this run (Coding Agent will rewrite it) ----
    os.makedirs(os.path.dirname(WORKING_PROMPT), exist_ok=True)
    shutil.copyfile(INITIAL_PROMPT, WORKING_PROMPT)

    # ---- Step 1: Evaluate the initial prompt ----
    print("\n【Step 1】Evaluate with the initial system prompt (observe over-transfer)")
    before = evaluate_prompt(_read(INITIAL_PROMPT), label="Initial prompt", cases=cases)
    print(
        f"\n  Initial results: holdout set {_pct(before['holdout'])}，"
        f"boundary set {_pct(before['boundary'])}"
    )
    over_transfer = [
        r for r in before["results"]
        if r["group"] == "boundary" and not r["should_transfer"] and r["transferred"]
    ]
    print(f"  Number of test cases in boundary set with [over-transfer]: {len(over_transfer)} / "
          f"{len([r for r in before['results'] if r['group'] == 'boundary'])}")
    for r in over_transfer:
        print(f"    - {r['id']}: policy dispute but directly transferred to human, reason: '{r['transfer_reason']}』")

    # ---- Step 2: Coding Agent automatically rewrites the prompt file ----
    print("\n【Step 2】Coding Agent reads and rewrites the system prompt file...")
    opt = optimize_prompt(WORKING_PROMPT, HUMAN_FEEDBACK, max_rounds=rounds, verbose=True)
    print(f"\n  Coding Agent change description:{opt['rationale']}")
    print("\n  ---------- System prompt file diff (actually written to disk) ----------")
    print(opt["diff"] if opt["diff"].strip() else "  (no changes)")
    print("  --------------------------------------------------------")

    # ---- Step 3: Evaluate the auto-optimized prompt ----
    print("\n【Step 3】Re-evaluate with the auto-optimized system prompt")
    after = evaluate_prompt(opt["after"], label="Auto-optimized prompt", cases=cases)

    # ---- Step 4: Compare with the manually tuned version ----
    print("\n【Step 4】Control group: manually tuned system prompt")
    manual = evaluate_prompt(_read(MANUAL_PROMPT), label="Manually tuned prompt (control)", cases=cases)

    # ---- Step 5: Comparison table ----
    print_table([
        ("Initial prompt (before optimization)", before["holdout"], before["boundary"]),
        ("Auto-optimized prompt", after["holdout"], after["boundary"]),
        ("Manually tuned version (control)", manual["holdout"], manual["boundary"]),
    ])

    # ---- Conclusion ----
    b_before_c, b_before_n = before["boundary"]
    b_after_c, _ = after["boundary"]
    h_before_c, _ = before["holdout"]
    h_after_c, _ = after["holdout"]
    print("\n【Conclusion】")
    print(f"  · Boundary case set accuracy:{b_before_c}/{b_before_n} → {b_after_c}/{b_before_n} "
          f"（{'Improved ✓' if b_after_c > b_before_c else 'Not improved'}）")
    print(f"  · Holdout task set accuracy:{h_before_c} → {h_after_c} "
          f"（{'Not degraded ✓' if h_after_c >= h_before_c else 'Degraded ✗'}）")
    print(f"\n  Optimized working copy written to:{WORKING_PROMPT}")

    # ---- Optional: Write comparison results to JSON for reproducibility and secondary analysis ----
    if output:
        summary = {
            "provider": get_provider(),
            "model": get_model(),
            "rounds": rounds,
            "num_cases": len(cases),
            "rationale": opt["rationale"],
            "diff": opt["diff"],
            "rows": [
                {"label": "Initial prompt (before optimization)", "holdout": list(before["holdout"]),
                 "boundary": list(before["boundary"])},
                {"label": "Auto-optimized prompt", "holdout": list(after["holdout"]),
                 "boundary": list(after["boundary"])},
                {"label": "Manually tuned version (control)", "holdout": list(manual["holdout"]),
                 "boundary": list(manual["boundary"])},
            ],
        }
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"  Comparison results written to:{output}")


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="demo.py",
        description="Experiment 8-3: Demonstration of automatic system prompt optimization based on human feedback (airline customer service scenario).",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python demo.py                     # Full run: 10 cases × 3 prompts\n"
            "  python demo.py --quick             # Only 2 cases per group, saving time and cost\n"
            "  python demo.py --group boundary    # Evaluate only the boundary case set\n"
            "  python demo.py --rounds 5 --model gpt-5.6-luna\n"
            "  python demo.py --output output/run.json  # Write comparison results as JSON\n"
            "  python demo.py --dry-run           # Offline: print configuration and case count only, no API calls"
        ),
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick demo mode: only 2 cases per group, reducing API calls and time.",
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Maximum number of cases to evaluate per group (overrides --quick).",
    )
    parser.add_argument(
        "--group", choices=("holdout", "boundary", "both"), default="both",
        help="Select the task set to evaluate: holdout / boundary / both (default: run both).",
    )
    parser.add_argument(
        "--rounds", type=int, default=3, metavar="N",
        help="Maximum retry rounds for Coding Agent to automatically rewrite prompts (default 3).",
    )
    parser.add_argument(
        "--model", default=None, metavar="NAME",
        help="Override LLM model name (equivalent to setting environment variable LLM_MODEL, e.g., gpt-5.6-luna).",
    )
    parser.add_argument(
        "--provider", choices=("openai", "moonshot", "ark"), default=None,
        help="Override LLM provider (equivalent to setting environment variable LLM_PROVIDER, default openai).",
    )
    parser.add_argument(
        "--output", default=None, metavar="PATH",
        help="Write comparison results (before/after optimization + manual reference) to a specified JSON file (e.g., output/run.json).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Offline self-check: only print parsed configuration and selected test case count, without calling any LLM API.",
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()

    #  Command-line overrides take precedence over environment variables: get_provider()/get_model() read environment variables at call time
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    if args.model:
        os.environ["LLM_MODEL"] = args.model

    limit = args.limit if args.limit is not None else (2 if args.quick else None)
    groups = GROUPS if args.group == "both" else (args.group,)
    cases = _select_cases(limit, groups=groups)

    if args.dry_run:
        #  Offline mode: no network requests triggered, only for verifying parameter parsing and test case selection
        print("[dry-run] Parsed runtime configuration (no API calls):")
        print(f"  LLM provider : {get_provider()}")
        print(f"  LLM model    : {get_model()}")
        print(f"  Optimization rounds : {args.rounds}")
        print(f"  Task set     : {args.group}")
        print(f"  Selected test cases : {len(cases)}  -> {[c['id'] for c in cases]}")
        print(f"  Output file  : {args.output or '(no file written)'}")
        sys.exit(0)

    try:
        main(cases=cases, rounds=args.rounds, output=args.output)
    except RuntimeError as e:
        #  For example, if API Key is not set: provide a clear human-readable error instead of a raw traceback
        print(f"\n[Error] {e}", file=sys.stderr)
        sys.exit(1)
