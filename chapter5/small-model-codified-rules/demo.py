"""
Experiment 5-3 Main Program: Small Model Matches Large Model Reliability via "Codified Rules"

Three-Arm Comparison (Core Claim):
    A. Small Model + Codified Rules (Experimental Group, Triple Guarantee)
    B. Small Model · Pure Natural Language (Control Group)
    C. Large Model · Pure Natural Language (Optional Baseline, enabled with --big-model)
Expected: Task success rate of A ≈ C, both significantly higher than B — i.e., "encoding business rules as codified guards"
enables a small model to match the reliability of a large model running bare on complex policy execution.

Metrics:
    - Task success rate: Whether the final refund result matches the codified policy ground truth.
    - Policy violation count: Over-refund (should reject but didn't) + Under-refund (should refund but didn't), both directions counted.
    - Invalid tool call count: Calls rejected by code validation / returning error/rejected for unknown bookings, etc.
    - expected_* self-report vs database ground truth inconsistency ratio (experimental group only, to verify necessity of server-side truth validation).

Common usage: see `--help`; `--selftest` requires no API Key, offline demonstration of three-layer guard codified validation logic.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()  # If .env exists, load OPENAI_API_KEY / MODEL / BIG_MODEL
except ImportError:
    pass

from airline_env import AirlineEnv, is_refundable, SERVER_NOW
from agent import MODEL
from tasks import TASKS


ALT_KEYWORDS = ["change", "credit", "credit", "keep", "alternative", "points", "voucher", "backup"]


def judge(task, env, final_text) -> dict:
    """Score rule judgments based on environment ground truth (state is truth)."""
    refunded = env.res.refund_issued > 0
    expect_refundable = task.expect_refundable

    wrongful_refund = (not expect_refundable) and refunded      # Should reject but didn't
    wrongful_refusal = expect_refundable and (not refunded)     # Should refund but didn't
    violation = wrongful_refund or wrongful_refusal
    success = not violation

    offered_alt = any(k.lower() in final_text.lower() for k in ALT_KEYWORDS)

    return {
        "task_id": task.task_id,
        "expect_refundable": expect_refundable,
        "refunded": refunded,
        "success": success,
        "wrongful_refund": wrongful_refund,
        "wrongful_refusal": wrongful_refusal,
        "invalid_tool_calls": env.invalid_tool_calls,
        "offered_alt": offered_alt if not expect_refundable else None,
        "checklist_records": env.checklist_records,
    }


# ---------------------------------------------------------------------------
# Control arms: each arm is a (mode, model) combination
# ---------------------------------------------------------------------------
def build_arms(small_model: str, big_model: str | None, mode: str) -> list[dict]:
    """Assemble the control arms to run this time based on --mode / --big-model. Default (both, no big model)
    is consistent with old behavior: control group + experimental group, both on small model."""
    arms: list[dict] = []
    if mode in ("control", "both"):
        arms.append({"key": "small_control", "mode": "control", "model": small_model,
                     "label": "Small Model · Pure Natural Language", "role": "Control Group"})
    if mode in ("codified", "both"):
        arms.append({"key": "small_codified", "mode": "codified", "model": small_model,
                     "label": "Small Model + Codified Rules", "role": "Experimental Group"})
    if big_model:  # Optional third arm: large model bare baseline (pure natural language)
        arms.append({"key": "big_control", "mode": "control", "model": big_model,
                     "label": "Large Model · Pure Natural Language", "role": "Large Model Baseline"})
    return arms


def run_arm(arm: dict, tasks, verbose: bool) -> list[dict]:
    # Lazy import run_agent: only needed when actually calling the model (--selftest does not go here)
    from agent import run_agent

    print(f"\n{'='*72}\nRunning [{arm['role']}] {arm['label']}   Model={arm['model']}\n{'='*72}")
    results = []
    for task in tasks:
        env = AirlineEnv(task.reservation)
        out = run_agent(env, task.user_message, arm["mode"], verbose=verbose, model=arm["model"])
        r = judge(task, env, out["final_text"])
        r["final_text"] = out["final_text"]
        r["transcript"] = out["transcript"]
        results.append(r)
        flag = "✅" if r["success"] else "❌"
        detail = "Over-refund" if r["wrongful_refund"] else ("Under-refund" if r["wrongful_refusal"] else "")
        print(f"  {flag} {task.task_id:<26} Should refund={str(r['expect_refundable']):<5} Actual refund={str(r['refunded']):<5} "
              f"Invalid calls={r['invalid_tool_calls']} {detail}")
    return results


def summarize(results: list[dict]) -> dict:
    n = len(results)
    succ = sum(r["success"] for r in results)
    violations = sum(r["wrongful_refund"] + r["wrongful_refusal"] for r in results)
    invalid = sum(r["invalid_tool_calls"] for r in results)
    # expected_* vs truth consistency (merged from all checklist records)
    records = [rec for r in results for rec in r["checklist_records"]]
    mism = sum(1 for rec in records if not rec["match"])
    return {
        "n": n, "success": succ, "success_rate": succ / n if n else 0.0,
        "violations": violations, "invalid": invalid,
        "checklist_total": len(records), "checklist_mismatch": mism,
    }


def print_comparison(arms: list[dict], summaries: list[dict]):
    print(f"\n{'#'*72}\n# Metric Comparison ({len(arms)} arm)\n{'#'*72}")
    col = 24
    label_w = 20
    # Header
    header = f"{'Metric':<{label_w}}" + "".join(f"{a['label']:<{col}}" for a in arms)
    print(header)
    print("-" * (label_w + col * len(arms)))
    # Task Success Rate
    rate_cells = ["{}/{} = {:.0f}%".format(s["success"], s["n"], s["success_rate"] * 100) for s in summaries]
    print(f"{'Task Success Rate':<{label_w}}" + "".join(f"{c:<{col}}" for c in rate_cells))
    print(f"{'Policy Violation Count':<{label_w}}" + "".join(f"{str(s['violations']):<{col}}" for s in summaries))
    print(f"{'Invalid Tool Call Count':<{label_w}}" + "".join(f"{str(s['invalid']):<{col}}" for s in summaries))

    # One-sentence interpretation of the core claim (when both experimental group and LLM baseline exist)
    by_role = {a["role"]: s for a, s in zip(arms, summaries)}
    if "Experimental Group" in by_role and "Large Model Baseline" in by_role:
        exp, big = by_role["Experimental Group"], by_role["Large Model Baseline"]
        print(f"\n[Core Claim] Small model + codified rules success rate {exp['success_rate']*100:.0f}% "
              f"vs LLM bare run {big['success_rate']*100:.0f}%"
              + ("(matched/exceeded)" if exp["success_rate"] >= big["success_rate"] else "(still behind)"))

    # expected_* Consistency (checklist exists only in experimental group)
    exp_summ = by_role.get("Experimental Group")
    if exp_summ and exp_summ["checklist_total"]:
        ratio = exp_summ["checklist_mismatch"] / exp_summ["checklist_total"]
        print(f"\n[Experimental Group] expected_* self-reported values vs database ground truth: total {exp_summ['checklist_total']} cancellation calls with checklist, "
              f"of which {exp_summ['checklist_mismatch']} are inconsistent with ground truth — inconsistency ratio = {ratio*100:.0f}%")
        print(" (Note: model self-awareness can be wrong; without server-side ground truth validation, these errors would directly become violations.)")


def print_interception_example(exp_results):
    """Find an example: experimental group model self-reports refundable (expected_refundable=True), but database ground truth is non-refundable, blocked by code."""
    for r in exp_results:
        for rec in r["checklist_records"]:
            if rec["expected_refundable"] is True and rec["actual_refundable"] is False:
                print(f"\n{'*'*72}\n* Codified validation interception example ({r['task_id']}）\n{'*'*72}")
                print(f"Model checklist self-report: expected_refundable=True (believes refundable)")
                print(f"Database ground truth: refundable=False, reason={rec['actual_reason']}")
                for step in r["transcript"]:
                    if step["tool"] == "cancel_reservation":
                        print(f"\nModel initiates cancellation call:{step['args']}")
                        print(f"Tool codified validation returns: status={step['result'].get('status')}，"
                              f"reason={step['result'].get('reason')}")
                        print(f"  → {step['result'].get('message')}")
                        break
                print(f"\nModel's final reply to user (intercepted, switches to explanation/alternative):\n  {r['final_text'][:400]}")
                return True
    return False


# ---------------------------------------------------------------------------
# Offline self-check: No API Key needed, directly demonstrate the third layer of the "Three-Layer Guard" — server-side codified validation
# ---------------------------------------------------------------------------
def run_selftest(tasks) -> None:
    print(f"{'='*72}\nOffline self-check (No API Key needed): Codified refund policy + in-tool ground truth validation\n"
          f"Server clock SERVER_NOW = {SERVER_NOW.isoformat()}\n{'='*72}")
    for task in tasks:
        r = task.reservation
        truth, reason = is_refundable(r, SERVER_NOW)
        print(f"\n[{task.task_id}] Cabin={r.cabin} order={r.booked_at.isoformat()} flight status={r.flight_status}")
        print(f"  policy truth value is_refundable -> refundable={truth}, reason={reason}")

        # Control group "naive tool": unconditional refund (representing a system without codified rules)
        env_naive = AirlineEnv(r)
        naive = env_naive.cancel_reservation_naive(r.reservation_id)
        print(f"  [Control group·naive tool] status={naive['status']} refund={env_naive.res.refund_issued}"
              f"  {'← Violation! Policy says non-refundable but refunded' if (not truth and env_naive.res.refund_issued > 0) else ''}")

        # Experimental group "codified tool": deliberately inject expected_refundable opposite to truth value, to see if it gets blocked
        env_cod = AirlineEnv(r)
        wrong_expected = not truth  # Simulate "model self-awareness error"
        cod = env_cod.cancel_reservation_codified(
            r.reservation_id, expected_refundable=wrong_expected, expected_reason="airline_caused")
        outcome = ("Refund executed" if cod["status"] == "ok" else f"Rejected({cod.get('reason')})")
        print(f"  [Experimental group·codified] model self-reported expected_refundable={wrong_expected} -> status={cod['status']} "
              f"[{outcome}] refund={env_cod.res.refund_issued}")
        rec = env_cod.checklist_records[-1] if env_cod.checklist_records else None
        if rec:
            print(f"      expected_* check: self-reported={rec['expected_refundable']} vs truth value={rec['actual_refundable']} "
                  f"-> {'Match' if rec['match'] else 'Mismatch (alert recorded)'}")
    print(f"\n{'='*72}\nConclusion: Regardless of what the model self-reports, the experimental group always adjudicates based on the database truth value —"
          f"Non-refundable ones are always blocked, refundable ones are allowed.\n{'='*72}")


def select_tasks(patterns: list[str] | None, quick: bool):
    tasks = TASKS
    if patterns:
        picked = [t for t in tasks if any(p.lower() in t.task_id.lower() for p in patterns)]
        if not picked:
            sys.exit(f"Error: --task {patterns} does not match any case. Available task_id: \n  "
                     + "\n  ".join(t.task_id for t in TASKS))
        return picked
    if quick:
        return tasks[:4]
    return tasks


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="demo.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Experiment 5-3: Small model, through codified business rules, matches the policy execution reliability of a large model running bare.\n"
            "Based on τ-bench airline customer service cancellation/refund scenario, conduct a three-arm controlled experiment."),
        epilog=(
            "Example: \n"
            "  python demo.py                         # Default: control group vs experimental group (both use small model), run all 8 cases\n"
            "  python demo.py --quick -v              # Run only the first 4 cases, and print each step's tool call\n"
            "  python demo.py --task R009             # Run only the case matching 'R009' (core interception example)\n"
            "  python demo.py --big-model gpt-5.6-luna  # Add third arm: large model bare baseline, verify 'small model + rules ≈ large model'\n"
            "  python demo.py --mode codified         # Run only experimental group (with codified rules)\n"
            "  python demo.py --mode control          # Run only control group (without codified rules)\n"
            "  python demo.py --small-model qwen3-4b --output result.json   # Specify the small model and save the result\n"
            "  python demo.py --selftest              # Offline demonstration of codified validation logic (no API Key required)\n"),
    )
    ap.add_argument("--mode", choices=["control", "codified", "both"], default="both",
                    help="Which group to run: control=pure natural language (without codified rules), codified=triple guarantee (with codified rules),"
                         "both=run both groups (default)")
    ap.add_argument("--task", "--tasks", dest="task", nargs="+", metavar="ID",
                    help="Only run cases whose task_id matches the given substring (multiple allowed, e.g., --task R003 R009)")
    ap.add_argument("--small-model", default=MODEL, metavar="NAME",
                    help=f"Model name for the 'small model' (default {MODEL}, can also be overridden by environment variable MODEL)")
    ap.add_argument("--big-model", default=os.environ.get("BIG_MODEL"), metavar="NAME",
                    help="Model name for the 'large model baseline' (optional; if given, run a third arm: large model bare natural language)")
    ap.add_argument("--quick", action="store_true", help="Only run the first 4 cases (save money and quick check)")
    ap.add_argument("-v", "--verbose", action="store_true", help="Print each step's tool call")
    ap.add_argument("--output", metavar="PATH", help="Write per-case results and aggregate metrics to a JSON file")
    ap.add_argument("--selftest", action="store_true",
                    help="Offline self-test: no API Key required, directly demonstrate codified refund policy and in-tool truth validation")
    return ap


def main():
    args = build_parser().parse_args()

    tasks = select_tasks(args.task, args.quick)

    #  Offline self-test: no API Key required, process first
    if args.selftest:
        run_selftest(tasks)
        return

    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")):
        sys.exit("Error: OPENAI_API_KEY (or fallback OPENROUTER_API_KEY) not set. Please copy env.example to .env and fill in, or export directly."
                 "\n(Hint: To see the codified validation logic offline, run `python demo.py --selftest`, no Key needed.)")

    arms = build_arms(args.small_model, args.big_model, args.mode)
    if not arms:
        sys.exit("Error: No runnable control arm. Please check --mode / --big-model combination.")

    print(f"Experiment 5-3: Small model improves rule execution accuracy through codified knowledge")
    print(f"Total {len(tasks)} cases (refundable {sum(t.expect_refundable for t in tasks)} / "
          f" non-refundable {sum(not t.expect_refundable for t in tasks)}），{len(arms)} control arms:"
          + "、".join(f"{a['label']}({a['model']})" for a in arms))

    arm_results = [run_arm(arm, tasks, args.verbose) for arm in arms]
    summaries = [summarize(res) for res in arm_results]

    print_comparison(arms, summaries)

    # Interception sample (take the first experimental group arm)
    for arm, res in zip(arms, arm_results):
        if arm["mode"] == "codified":
            if not print_interception_example(res):
                print("\n(No interception sample with expected=refundable/truth=non-refundable appeared in this run;"
                      "rerun or increase temperature to observe.)")
            break

    if args.output:
        payload = {
            "config": {
                "small_model": args.small_model, "big_model": args.big_model,
                "mode": args.mode, "task_ids": [t.task_id for t in tasks],
            },
            "arms": [
                {**{k: arm[k] for k in ("key", "mode", "model", "label", "role")},
                 "summary": summ, "results": res}
                for arm, summ, res in zip(arms, summaries, arm_results)
            ],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
