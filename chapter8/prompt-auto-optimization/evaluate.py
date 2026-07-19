"""
Evaluator: Given a system prompt, run the Agent on a set of test cases and determine whether each case is "correctly handled".

Judgment rules (combining deterministic rules + LLM-as-judge):
- The test case is labeled with should_transfer (whether the correct behavior should transfer to a human agent).
- If should_transfer=True: correct ⇔ the Agent indeed transferred.
- If should_transfer=False: correct ⇔ the Agent did not transfer, and the LLM judge confirms that it properly handled the request according to the rubric
                             (i.e., it actually explained the policy / processed the business, rather than being perfunctory or irrelevant).
  The reason for adding an LLM judge for "no transfer" cases is to prevent the Agent from passing by "not transferring but also not handling properly".
"""

import json
from config import get_client, get_model, TEMPERATURE
from airline_env import run_agent


def _judge_handled(user_message: str, rubric: str, agent_reply: str) -> bool:
    """LLM-as-judge: When the Agent does not transfer, whether it properly handled the request according to the rubric."""
    client = get_client()
    model = get_model()
    prompt = f"""You are a strict customer service quality inspector. Determine whether the customer service Agent's response properly handled the passenger's request.

【Passenger Request】
{user_message}

【Qualification Standard (Rubric)】
{rubric}

【Agent's Response】
{agent_reply}

Please output only one JSON: {{"handled": true or false, "reason": "brief reason"}}
where handled=true means the Agent's response substantially meets the qualification standard."""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
        response_format={"type": "json_object"},
    )
    try:
        verdict = json.loads(resp.choices[0].message.content)
        return bool(verdict.get("handled", False))
    except (json.JSONDecodeError, TypeError):
        return False


def evaluate_case(system_prompt: str, case: dict, verbose: bool = False) -> dict:
    """Evaluate a single test case, return a result dict."""
    result = run_agent(system_prompt, case["user"])
    transferred = result["transferred"]
    should_transfer = case["should_transfer"]

    if should_transfer:
        correct = transferred
        note = "Should transfer:" + ("Transferred ✓" if transferred else "Not transferred ✗")
    else:
        if transferred:
            correct = False
            note = "Should not transfer: but transferred ✗ (over-transfer)"
        else:
            handled = _judge_handled(case["user"], case["rubric"], result["final_text"])
            correct = handled
            note = "Should not transfer: not transferred and properly handled ✓" if handled else "Should not transfer: not transferred but improperly handled ✗"

    out = {
        "id": case["id"],
        "group": case["group"],
        "correct": correct,
        "transferred": transferred,
        "should_transfer": should_transfer,
        "note": note,
        "final_text": result["final_text"],
        "transfer_reason": result["transfer_reason"],
        "tool_calls": result["tool_calls"],
    }
    if verbose:
        icon = "✓" if correct else "✗"
        print(f"  [{icon}] {case['id']:<16} {note}")
        if transferred:
            print(f"        Transfer reason: {result['transfer_reason']}")
        else:
            preview = (result["final_text"] or "").replace("\n", " ")[:80]
            print(f"        Response: {preview}...")
    return out


def evaluate_prompt(system_prompt: str, label: str = "", verbose: bool = True, cases=None) -> dict:
    """Evaluate a prompt on all test cases, return grouped accuracy and details.

    When cases is None, evaluate all test cases; you can also pass a subset of cases (e.g., --quick mode) to control cost.
    """
    from airline_env import CASES

    if cases is None:
        cases = CASES

    if verbose and label:
        print(f"\n>>> Evaluation [{label}]")
    results = []
    for case in cases:
        results.append(evaluate_case(system_prompt, case, verbose=verbose))

    def _acc(group):
        rows = [r for r in results if r["group"] == group]
        n = len(rows)
        c = sum(1 for r in rows if r["correct"])
        return c, n

    holdout_c, holdout_n = _acc("holdout")
    boundary_c, boundary_n = _acc("boundary")
    return {
        "label": label,
        "holdout": (holdout_c, holdout_n),
        "boundary": (boundary_c, boundary_n),
        "results": results,
    }
