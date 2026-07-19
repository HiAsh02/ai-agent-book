"""
replay.py — Regression Test Replay Framework

Input: Agent-generated regression test cases (structured JSON), referencing trajectory ID and interaction turns.
Process: Extract the task input from the original trajectory, feed it to the system under test (sut.run_task) for replay,
      evaluate assertions on the new trajectory produced by replay, and output pass/fail.

Structure of a test case (Agent must generate according to this DSL):
{
  "test_id": "RT-001",
  "trajectory_id": "T-1001",       # Referenced problem trajectory
  "focus_turn": 3,                 # Key interaction turn (where the problem lies)
  "description": "Eligibility check must be performed before refund",
  "assertion": {"type": "step_present", "params": {"tool": "verify_refund_eligibility"}}
}

Supported assertion types (built into replay framework, automatically evaluable):
- step_present   params.tool            A tool must appear in the trajectory (e.g., mandatory pre-check)
- tool_succeeds  params.tool            A tool must ultimately succeed, and no false success after consecutive failures
- latency_under params.tool, threshold_ms   Single latency of a tool must be below threshold
- final_status_is params.value           Final task status must equal the given value
"""

import json
import os
from typing import Dict, Any, List, Tuple

import sut

_DATA = os.path.join(os.path.dirname(__file__), "data", "trajectories.jsonl")


def load_trajectories(path: str = _DATA) -> Dict[str, Dict[str, Any]]:
    """Read the production trajectory collection, indexed by trajectory_id."""
    out = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            t = json.loads(line)
            out[t["trajectory_id"]] = t
    return out


# ---------------- Assertion Evaluator ----------------

def _tool_turns(traj: Dict[str, Any], tool: str) -> List[Dict[str, Any]]:
    return [t for t in traj["turns"] if t.get("tool") == tool]


def _eval_assertion(assertion: Dict[str, Any], traj: Dict[str, Any]) -> Tuple[bool, str]:
    a_type = assertion.get("type")
    params = assertion.get("params", {})

    if a_type == "step_present":
        tool = params.get("tool") or params.get("step")
        ok = len(_tool_turns(traj, tool)) > 0
        return ok, f"Tool {tool} {'present' if ok else 'missing'}"

    if a_type == "tool_succeeds":
        tool = params.get("tool")
        calls = _tool_turns(traj, tool)
        if not calls:
            return False, f"{tool} not called"
        n_err = sum(1 for c in calls if c.get("status") == "error")
        last_ok = calls[-1].get("status") == "success"
        # Fix criterion: final success, and no "false success after multiple failures" (>=2 failures considered not properly handled)
        ok = last_ok and n_err < 2
        return ok, f"{tool} called {len(calls)} times, failed {n_err} times, last{'success' if last_ok else 'failure'}"

    if a_type == "latency_under":
        tool = params.get("tool")
        thr = params.get("threshold_ms") or params.get("threshold")
        calls = _tool_turns(traj, tool)
        if not calls:
            return False, f"{tool} not called"
        worst = max(c.get("latency_ms", 0) for c in calls)
        ok = worst < thr
        return ok, f"{tool} max latency {worst}ms, threshold {thr}ms"

    if a_type == "final_status_is":
        want = params.get("value")
        ok = traj.get("final_status") == want
        return ok, f"final_status={traj.get('final_status')}, expected={want}"

    return False, f"Unknown assertion type: {a_type}"


def run_test_case(tc: Dict[str, Any], trajectories: Dict[str, Any],
                  fixed: bool) -> Dict[str, Any]:
    """For a single test case: take original trajectory input -> replay system under test -> evaluate assertion."""
    tid = tc.get("trajectory_id")
    src = trajectories.get(tid)
    if src is None:
        return {"test_id": tc.get("test_id"), "passed": False,
                "detail": f"Referenced trajectory {tid} does not exist"}

    replayed = sut.run_task(src["task_input"], fixed=fixed)
    passed, detail = _eval_assertion(tc.get("assertion", {}), replayed)
    return {
        "test_id": tc.get("test_id"),
        "trajectory_id": tid,
        "focus_turn": tc.get("focus_turn"),
        "passed": passed,
        "detail": detail,
        "replay_mode": "fixed" if fixed else "buggy",
    }


def run_suite(test_cases: List[Dict[str, Any]], fixed: bool,
              path: str = _DATA) -> List[Dict[str, Any]]:
    """Run the full set of test cases and return a list of results."""
    trajectories = load_trajectories(path)
    results = []
    for tc in test_cases:
        try:
            results.append(run_test_case(tc, trajectories, fixed))
        except Exception as e:  # A single case failure does not affect the entire set
            results.append({"test_id": tc.get("test_id"), "passed": False,
                            "detail": f"Test case execution exception: {e}",
                            "replay_mode": "fixed" if fixed else "buggy"})
    return results
