"""
demo.py — Experiment 5-8: Intelligent Diagnostic System for Production Logs (Full Demo)

Pipeline:
  Read trajectory set + architecture + PRD
    -> [LLM] Diagnosis: locate issues, structured report (priority/module/description/suggestion)
    -> [LLM] Generate regression test cases (reference trajectory ID + interaction round)
    -> Replay framework actually executes: first reproduce bug (FAIL), then verify fix (PASS)
    -> (mock) Create GitHub Issue via MCP

Run:
  cp env.example .env && fill in OPENAI_API_KEY
  python demo.py                 # Full pipeline (two real LLM calls, GitHub step defaults to mock)
  python demo.py --smoke         # Quick self-check: skip LLM, use built-in cases only for replay + GitHub mock
  python demo.py --model gpt-5.6  # Temporarily switch model
  python demo.py --create-issue  # Actually create GitHub Issue via MCP (requires GITHUB_TOKEN+GITHUB_REPO)
  python demo.py -h              # View all parameters

Change provider/model: set OPENAI_BASE_URL + OPENAI_MODEL (see README『How to adapt/extend』).
"""

import argparse
import json
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from diagnoser import Diagnoser
import replay
import github_mcp

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DEFAULT_OUTPUT = os.path.join(HERE, "output", "github_issues.json")

#Built-in samples for --smoke self-check: consistent with LLM's stable output on this dataset,
# so that the end-to-end pipeline of replay framework + GitHub mock can be verified without network or API Key.
_CANNED_PROBLEMS = [
    {"title": "Refund eligibility check not performed", "priority": "P0", "module": "order_service",
     "description": "Missing mandatory verify_refund_eligibility check before refund.", "prd_ref": "R1",
     "trajectory_ids": ["T-1001", "T-1002"], "focus_turns": [3]},
    {"title": "Payment retry mechanism not correctly implemented", "priority": "P0", "module": "payment_service",
     "description": "process_refund repeatedly fails, no backoff, and falsely reports success.", "prd_ref": "R2",
     "trajectory_ids": ["T-1002"], "focus_turns": [7]},
    {"title": "Inventory query latency not degraded", "priority": "P1", "module": "inventory_service",
     "description": "check_stock latency 8300ms timeout without degradation.", "prd_ref": "R3",
     "trajectory_ids": ["T-1003"], "focus_turns": [3]},
]
_CANNED_TEST_CASES = [
    {"test_id": "RT-001", "trajectory_id": "T-1001", "focus_turn": 3,
     "description": "Must perform eligibility check before refund",
     "assertion": {"type": "step_present", "params": {"tool": "verify_refund_eligibility"}}},
    {"test_id": "RT-002", "trajectory_id": "T-1002", "focus_turn": 7,
     "description": "process_refund should eventually succeed without 'false success after multiple failures'",
     "assertion": {"type": "tool_succeeds", "params": {"tool": "process_refund"}}},
    {"test_id": "RT-003", "trajectory_id": "T-1003", "focus_turn": 3,
     "description": "check_stock latency should be below 5000ms",
     "assertion": {"type": "latency_under", "params": {"tool": "check_stock", "threshold_ms": 5000}}},
]


def _read(data_dir, name):
    with open(os.path.join(data_dir, name), "r", encoding="utf-8") as f:
        return f.read()


def _traj_path(data_dir):
    return os.path.join(data_dir, "trajectories.jsonl")


def _hr(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _replay_and_issues(problems, test_cases, do_github=True,
                       traj_path=None, out_path=DEFAULT_OUTPUT, create_issue=False):
    """Step 3/4: Replay the system under test with the same input and assert, then generate GitHub Issue (default mock).

    Replay once each for fixed=False / fixed=True, demonstrating the same regression test case's
    'failure (reproduce bug)' and 'pass (verify fix)'. Returns (reproduced count, verified count).
    """
    traj_path = traj_path or replay._DATA
    _hr("Step 3｜Replay framework actually executes test cases")
    print("(A) Replay on 'unfixed' system — expect bug reproduction (FAIL)")
    buggy = replay.run_suite(test_cases, fixed=False, path=traj_path)
    for r in buggy:
        flag = "PASS" if r["passed"] else "FAIL"
        print(f"    [{flag}] {r['test_id']}  ({r.get('trajectory_id')})  {r['detail']}")

    print("\n(B) Replay on 'fixed' system — expect fix verification (PASS)")
    fixed = replay.run_suite(test_cases, fixed=True, path=traj_path)
    for r in fixed:
        flag = "PASS" if r["passed"] else "FAIL"
        print(f"    [{flag}] {r['test_id']}  ({r.get('trajectory_id')})  {r['detail']}")

    reproduced = sum(1 for r in buggy if not r["passed"])
    verified = sum(1 for r in fixed if r["passed"])
    print(f"\n  Summary: reproduced bug {reproduced}/{len(buggy)} cases; after fix, passed {verified}/{len(fixed)} cases.")

    if do_github:
        token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPO")
        if create_issue and token and repo:
            _hr(f"Step 4｜Create Issue on GitHub {repo} via MCP")
            github_mcp.create_issues(problems, test_cases, mock=False,
                                     out_path=out_path, repo=repo, token=token)
        else:
            if create_issue:
                print("\n[Tip] --create-issue requires GITHUB_TOKEN and GITHUB_REPO(owner/repo),"
                      " currently missing, falling back to mock.")
            _hr("Step 4｜Create GitHub Issue via MCP (mock, no network)")
            github_mcp.create_issues(problems, test_cases, mock=True, out_path=out_path)
    return reproduced, verified


def run_smoke(data_dir=DATA, out_path=DEFAULT_OUTPUT):
    """Quick self-check: no LLM calls, use built-in samples only for end-to-end pipeline of replay framework + GitHub mock.

    Exit code: 0 if pipeline fully green (all reproduced + all verified), otherwise 3.
    """
    _hr("Self-check mode (--smoke): skip LLM, use built-in diagnosis results to verify replay + GitHub mock pipeline")
    reproduced, verified = _replay_and_issues(
        _CANNED_PROBLEMS, _CANNED_TEST_CASES,
        traj_path=_traj_path(data_dir), out_path=out_path)
    n = len(_CANNED_TEST_CASES)
    ok = reproduced == n and verified == n
    print(f"\nSelf-check result:{'OK' if ok else 'FAILED'} (reproduced {reproduced}/{n}, verified {verified}/{n}）")
    return 0 if ok else 3


def run_full(model=None, do_github=True, data_dir=DATA,
             out_path=DEFAULT_OUTPUT, create_issue=False):
    """Full pipeline: real OpenAI calls for diagnosis and regression test generation, then replay execution."""
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")):
        print("Error: OPENAI_API_KEY (or fallback OPENROUTER_API_KEY) not set. Please cp env.example .env and fill in."
              "(Or use python demo.py --smoke for API-free self-check).")
        sys.exit(1)

    # ---------- 0. Read Input ----------
    architecture = _read(data_dir, "architecture.md")
    prd = _read(data_dir, "PRD.md")
    trajectories = list(replay.load_trajectories(_traj_path(data_dir)).values())
    _hr(f"Step 0 | Read Input:{len(trajectories)} production traces + architecture docs + PRD")
    for t in trajectories:
        print(f"  - {t['trajectory_id']}: {t['task']}（{len(t['turns'])} rounds)")

    agent = Diagnoser(model=model) if model else Diagnoser()
    print(f"  Model used:{agent.model}")

    # ---------- 1. Diagnosis: Locate Issues ----------
    _hr("Step 1 | Agent Diagnosis (real OpenAI call): Locate issues and generate structured report")
    problems = agent.diagnose(architecture, prd, trajectories)
    if not problems:
        print("No issues diagnosed (anomaly).")
        sys.exit(2)
    for i, p in enumerate(problems, 1):
        print(f"\n[Issue {i}] {p.get('title', '')}")
        print(f" Priority : {p.get('priority')}    Module: {p.get('module')}    PRD: {p.get('prd_ref')}")
        print(f"  Trace   : {p.get('trajectory_ids')}  Key Round: {p.get('focus_turns')}")
        print(f"  Description   : {p.get('description')}")
        print(f"  Suggestion   : {p.get('suggestion')}")

    # ---------- 2. Generate Regression Test Cases ----------
    _hr("Step 2 | Agent generates regression test cases (real OpenAI call): Reference trace ID + interaction round")
    test_cases = agent.gen_test_cases(problems)
    for tc in test_cases:
        print(f"  {tc.get('test_id')}  Trace={tc.get('trajectory_id')} "
              f"Round={tc.get('focus_turn')}  Assertion={json.dumps(tc.get('assertion'), ensure_ascii=False)}")
        print(f"      Description: {tc.get('description')}")

    # ---------- 3/4. Replay Execution + GitHub Issue (default mock) ----------
    _replay_and_issues(problems, test_cases, do_github=do_github,
                       traj_path=_traj_path(data_dir), out_path=out_path,
                       create_issue=create_issue)

    _hr("Done | Full pipeline: read traces -> diagnosis report -> regression test cases -> (mock) GitHub Issue")


def main():
    parser = argparse.ArgumentParser(
        description="Experiment 5-8: Intelligent Diagnosis System for Production Logs (read traces -> diagnosis -> regression tests -> GitHub Issue)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: \n"
               "  python demo.py                     Full pipeline (requires OPENAI_API_KEY)\n"
               "  python demo.py --smoke             API-free quick self-check (replay + GitHub mock only)\n"
               "  python demo.py --model gpt-5.6      Temporarily switch model\n"
               "  python demo.py --data-dir ./mine   Replace with your own trajectory/architecture/PRD directory\n"
               "  python demo.py --create-issue      Actually create an Issue via MCP (requires GITHUB_TOKEN+GITHUB_REPO)\n"
               "Change provider: set OPENAI_BASE_URL + OPENAI_MODEL environment variables.")
    parser.add_argument("--smoke", action="store_true",
                        help="Quick self-check: skip LLM, use built-in samples to only run replay framework + GitHub mock (no API Key needed)")
    parser.add_argument("--model", default=None,
                        help="Temporarily override model (equivalent to setting OPENAI_MODEL; default gpt-5.6-luna)")
    parser.add_argument("--data-dir", default=DATA, metavar="DIR",
                        help="Input directory: trajectory logs trajectories.jsonl + architecture.md + PRD.md (default data/)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, metavar="FILE",
                        help="GitHub Issue (mock) output path (default output/github_issues.json)")
    parser.add_argument("--create-issue", action="store_true",
                        help="Create Issue in real repository via MCP (requires GITHUB_TOKEN and GITHUB_REPO; default mock without network)")
    parser.add_argument("--no-github", action="store_true",
                        help="Skip step 4 (neither mock nor create GitHub Issue)")
    args = parser.parse_args()

    if args.smoke:
        sys.exit(run_smoke(data_dir=args.data_dir, out_path=args.output))
    run_full(model=args.model, do_github=not args.no_github,
             data_dir=args.data_dir, out_path=args.output,
             create_issue=args.create_issue)


if __name__ == "__main__":
    main()
