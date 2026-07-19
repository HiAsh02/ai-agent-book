"""Experiment 5-1: Enhancing Mathematical Problem Solving with Code Generation Tools

Controlled Experiment: On the same set of AIME-style competition math problems, compare
  - [Pure Chain-of-Thought CoT]: Reasoning only through natural language, unable to execute code;
  - [Code-Assisted]: Formalize the problem into Python (sympy symbolic computation, scipy numerical optimization,
     numpy matrices), execute in a subprocess sandbox, and return precise results.

Both modes use the same model, the same set of problems, temperature=0, and finally present an accuracy comparison table.

Run:  python demo.py                  # Run the full controlled experiment (requires API key)
       python demo.py --selfcheck      # Offline self-check: only run sandbox execution of reference solutions, no API key needed
For more usage, see  python demo.py --help"""

import os
import re
import sys
import json
import argparse

from sandbox import run_python

# ---------------------------------------------------------------------------
# Configuration: Compatible with multiple available OpenAI protocol keys (including general OpenRouter fallback)
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def map_model_to_openrouter(model: str) -> str:
    """Map the direct model name to the id on OpenRouter (non-mappable ids fall back to the current cheap flagship)."""
    if not model or "/" in model:
        return model or "openai/gpt-5.6-luna"
    m = model.lower()
    if m.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai/" + model
    if m.startswith("claude"):
        if "haiku" in m:
            return "anthropic/claude-haiku-4.5"
        if "sonnet" in m:
            return "anthropic/claude-sonnet-4.6"
        return "anthropic/claude-opus-4.8"
    if m.startswith("gemini"):
        return "google/" + model
    # kimi / doubao / other non-OpenRouter native IDs -> unified fallback
    return "openai/gpt-5.6-luna"


def resolve_llm(api_key, base_url, model):
    """General OpenRouter fallback + gpt-5.x priority routing, returns (api_key, base_url, model).

    - For gpt-5.x / gpt-5.6* and OPENROUTER_API_KEY is set, prioritize OpenRouter
      (direct OpenAI call for gpt-5.6 requires organization real-name authentication).
    - Otherwise, if a direct key exists, keep direct connection unchanged.
    - Otherwise, if OPENROUTER_API_KEY is set, switch entirely to OpenRouter.
    - If none, return as-is, letting the caller report the missing key error.
    """
    orkey = os.getenv("OPENROUTER_API_KEY")
    m = (model or "").lower()
    prefer_or = bool(orkey) and m.startswith("gpt-5")
    if prefer_or or (not api_key and orkey):
        return orkey, OPENROUTER_BASE_URL, map_model_to_openrouter(model)
    return api_key, base_url, model


def build_client_and_model(model_override=None):
    """Construct the OpenAI client and default model name based on environment variables.

    Priority: OPENAI_API_KEY > MOONSHOT_API_KEY > ARK_API_KEY, fallback to OPENROUTER_API_KEY when all are missing.
    These services all support OpenAI's chat.completions + function calling interface.
    The command-line --model has the highest priority and overrides the default model inferred from environment variables.
    """
    #  Lazy import: offline self-check (--selfcheck) does not require openai or an API key.
    from openai import OpenAI

    model = os.getenv("MODEL", "gpt-5.6-luna")
    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = None

    if os.getenv("OPENAI_API_KEY"):
        api_key = os.getenv("OPENAI_API_KEY")
    elif os.getenv("MOONSHOT_API_KEY"):
        api_key = os.getenv("MOONSHOT_API_KEY")
        base_url = base_url or "https://api.moonshot.cn/v1"
        model = os.getenv("MODEL", "kimi-k3")
    elif os.getenv("ARK_API_KEY"):
        api_key = os.getenv("ARK_API_KEY")
        base_url = base_url or "https://ark.cn-beijing.volces.com/api/v3"
        model = os.getenv("MODEL", "doubao-seed-1-6-250615")

    if model_override:
        model = model_override

    # General OpenRouter fallback: when no direct key (or default to gpt-5.x), switch to OpenRouter.
    api_key, base_url, model = resolve_llm(api_key, base_url, model)

    if not api_key:
        raise SystemExit(
            "API key not found, please set OPENAI_API_KEY (or MOONSHOT_API_KEY / ARK_API_KEY / OPENROUTER_API_KEY).\n"
            "If you only want to verify the sandbox and question bank without calling the LLM, you can run: python demo.py --selfcheck"
        )

    # Add timeout and retry: prevent individual API calls from hanging for a long time and causing the entire evaluation to freeze.
    _kw = {"api_key": api_key, "timeout": 60.0, "max_retries": 3}
    if base_url:
        _kw["base_url"] = base_url
    client = OpenAI(**_kw)
    return client, model


# ---------------------------------------------------------------------------
# Tool definition (function calling)
# ---------------------------------------------------------------------------

RUN_PYTHON_TOOL = {
    "type": "function",
    "function": {
        "name": "run_python",
        "description": (
            "Execute code in a Python sandbox with pre-installed sympy/numpy/scipy for precise mathematical calculations."
            "You must use print() to output the results you want to see. Suitable for symbolic computation, number theory enumeration,"
            "Polynomial expansion, numerical solving, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python source code to execute, output the result with print.",
                }
            },
            "required": ["code"],
        },
    },
}

FINAL_INSTRUCTION = (
    "The answer to the question is an integer. Please provide the final answer on a separate line at the end, strictly in the format: \n"
    "FINAL ANSWER: <integer>"
)

COT_SYSTEM = (
    "You are a math competition expert. Please solve the problem step by step using only natural language reasoning."
    "Do not write or call any code.\n" + FINAL_INSTRUCTION
)

CODE_SYSTEM = (
    "You are a math competition expert skilled at solving problems with programming. When encountering calculations,"
    "Please formalize the problem as Python code and call the run_python tool to execute it in the sandbox."
    "Replace mental arithmetic with precise calculation results. Tools can be called multiple times for verification.\n" + FINAL_INSTRUCTION
)


# ---------------------------------------------------------------------------
# answer extraction
# ---------------------------------------------------------------------------

def extract_answer(text: str):
    """Parse integer answer from model output. Prefer matching FINAL ANSWER, fall back to the last integer."""
    if not text:
        return None
    m = list(re.finditer(r"FINAL ANSWER:\s*(-?\d+)", text, re.IGNORECASE))
    if m:
        return int(m[-1].group(1))
    #  Degradation: grab the last \boxed{...} or trailing integer
    m = list(re.finditer(r"\\boxed\{\s*(-?\d+)\s*\}", text))
    if m:
        return int(m[-1].group(1))
    nums = re.findall(r"-?\d+", text)
    return int(nums[-1]) if nums else None


# ---------------------------------------------------------------------------
# Single problem solving
# ---------------------------------------------------------------------------

def solve(client, model, question, use_code, max_turns=8, verbose=False):
    """Solve a single problem, return (predicted integer answer, list of tool codes used, final text)."""
    system = CODE_SYSTEM if use_code else COT_SYSTEM
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
    tools = [RUN_PYTHON_TOOL] if use_code else None
    codes = []

    for _ in range(max_turns):
        # Inference models (kimi-k3 / gpt-5 / *thinking etc.) do not accept temperature=0, and require larger max_tokens to accommodate reasoning.
        _rs = ({"temperature": 1, "max_tokens": 4096}
               if any(k in (model or "").lower() for k in ("kimi-k3", "kimi-k2.", "gpt-5", "o1", "o3", "o4", "thinking", "reasoner"))
               else {"temperature": 0})
        kwargs = dict(model=model, messages=messages, **_rs)
        if tools:
            kwargs["tools"] = tools
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            #  Must add the assistant's tool_calls message back as-is
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                    code = args.get("code", "")
                except json.JSONDecodeError:
                    code = ""
                codes.append(code)
                result = run_python(code) if code else "[Error] No code provided"
                if verbose:
                    print("\n--- Model-generated code ---\n" + code)
                    print("--- Execution result ---\n" + result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            continue  # Continue to let the model reason based on tool results

        # No tool call → final answer
        return extract_answer(msg.content), codes, (msg.content or "")

    # Exceeded max rounds, force final wrap-up
    messages.append(
        {"role": "user", "content": " Please give immediately: FINAL ANSWER: <integer>"}
    )
    _rs = ({"temperature": 1, "max_tokens": 4096}
           if any(k in (model or "").lower() for k in ("kimi-k3", "kimi-k2.", "gpt-5", "o1", "o3", "o4", "thinking", "reasoner"))
           else {"temperature": 0})
    resp = client.chat.completions.create(
        model=model, messages=messages, **_rs
    )
    content = resp.choices[0].message.content or ""
    return extract_answer(content), codes, content


# ---------------------------------------------------------------------------
# Offline self-check: only use sandbox to execute reference solutions from the problem bank, no LLM calls
# ---------------------------------------------------------------------------

def run_selfcheck(problems, verbose=False):
    """ Deterministically verify the "sandbox + problem bank" pipeline, no API key required.

    For each problem, execute its reference solution (Python code) from problems.json,
    run it in a subprocess sandbox, extract the integer output, and compare with the ground truth.
    This demonstrates the core mechanism of "model writes code → sandbox executes → grade against ground truth"
    and also self-checks the ground truth itself.
    Returns the number of passed problems; exit code 0 if all pass, 1 otherwise.
    """
    print("Offline self-check: execute reference solutions in sandbox and grade against ground truth (no API key required)\n")
    print(f"{'Problem ID':<5}{'Topic':<26}{'Ground Truth':>7}{'Sandbox Output':>10}{'':>4}")
    print("-" * 56)
    ok_count = 0
    missing = 0
    for p in problems:
        sol = p.get("solution")
        if not sol:
            missing += 1
            print(f"{p['id']:<5}{p['topic']:<26}{p['answer']:>7}{'(No reference solution)':>12}")
            continue
        out = run_python(sol)
        pred = extract_answer(out)
        ok = pred == p["answer"]
        ok_count += ok
        if verbose:
            print("\n--- Reference solution ---\n" + sol)
            print("--- Sandbox output ---\n" + out)
        print(
            f"{p['id']:<5}{p['topic']:<26}{p['answer']:>7}{str(pred):>10}"
            f"{'✓' if ok else '✗':>4}"
        )
    n = len(problems)
    print("-" * 56)
    print(f"Reference solution matches ground truth:{ok_count}/{n}" + (f"（{missing} (Problem missing reference solution)" if missing else ""))
    if ok_count == n:
        print("\nAll passed: sandbox works, problem bank ground truth is self-consistent, safe to use for grading.")
        return 0
    print("\nInconsistencies found: please check the reference solution or ground truth of the above ✗ problems.")
    return 1


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="demo.py",
        description="Experiment 5-1: Accuracy comparison of code sandbox-assisted vs pure chain-of-thought (CoT) on AIME-style math problems.",
        epilog=(
            "Example:\n"
            "  python demo.py                       Run full comparison experiment (code and cot modes)\n"
            "  python demo.py --selfcheck           Offline self-check sandbox and problem bank ground truth, no API key required\n"
            "  python demo.py --mode code           Run only code-assisted mode\n"
            "  python demo.py --mode cot --limit 3  Run only pure CoT on the first 3 problems\n"
            "  python demo.py --model gpt-5.6        Switch to a stronger model\n"
            "  python demo.py --output result.json  Write per-problem results to JSON\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["both", "code", "cot"],
        default="both",
        help="Solve mode: both=run both and compare (default); code=code assistance only; cot=chain-of-thought only.",
    )
    parser.add_argument(
        "--problems",
        default="problems.json",
        metavar="Path",
        help="Path to the problems JSON (default problems.json, relative to this script directory).",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="Name",
        help="Override model name (defaults to environment variable MODEL, then falls back to vendor default, e.g., gpt-5.6-luna).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Only run the first N problems (save money for debugging, 0 means all).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="Path",
        help="Write per-problem results and summary to the specified JSON file.",
    )
    parser.add_argument(
        "--selfcheck",
        action="store_true",
        help="Offline self-check mode: only execute reference solutions in sandbox and score against ground truth, without calling any LLM (no API key needed).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print code generated by model (or reference solution) and sandbox execution results.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main flow: controlled experiment
# ---------------------------------------------------------------------------

def load_problems(path):
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isabs(path):
        path = os.path.join(here, path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    args = parse_args(argv)

    problems = load_problems(args.problems)
    if args.limit:
        problems = problems[: args.limit]

    # ---- Offline self-check: no API key needed, deterministic scoring ----
    if args.selfcheck:
        return run_selfcheck(problems, verbose=args.verbose)

    client, model = build_client_and_model(model_override=args.model)

    run_cot = args.mode in ("both", "cot")
    run_code = args.mode in ("both", "code")
    print(f"Model: {model}    Problems: {len(problems)}    Mode: {args.mode}\n")

    rows = []
    cot_correct = code_correct = 0
    for p in problems:
        q, truth = p["question"], p["answer"]
        print(f"[{p['id']:>2}] {p['topic']}  (Ground truth={truth})")

        cot_pred = code_pred = None
        cot_ok = code_ok = False
        n_calls = 0
        if run_cot:
            cot_pred, _, _ = solve(client, model, q, use_code=False, verbose=args.verbose)
            cot_ok = cot_pred == truth
            cot_correct += cot_ok
        if run_code:
            code_pred, codes, _ = solve(client, model, q, use_code=True, verbose=args.verbose)
            code_ok = code_pred == truth
            code_correct += code_ok
            n_calls = len(codes)

        parts = []
        if run_cot:
            parts.append(f"CoT    Pred={cot_pred!s:>8}  {'✓' if cot_ok else '✗'}")
        if run_code:
            parts.append(
                f"Code assist Pred={code_pred!s:>8}  {'✓' if code_ok else '✗'}"
                f"   (Tool calls {n_calls} times)"
            )
        print("     " + "   |  ".join(parts))
        rows.append(
            {
                "id": p["id"],
                "topic": p["topic"],
                "answer": truth,
                "cot_pred": cot_pred,
                "cot_ok": bool(cot_ok),
                "code_pred": code_pred,
                "code_ok": bool(code_ok),
                "tool_calls": n_calls,
            }
        )

    # ---- Summary table ----
    n = len(problems)
    print("\n" + "=" * 78)
    print("Per-problem comparison results")
    print("=" * 78)
    print(f"{'Problem ID':<5}{'Topic':<26}{'Ground Truth':>7}{'CoT prediction':>10}{'':>4}{'Code prediction':>10}{'':>4}")
    print("-" * 78)
    for r in rows:
        cp = str(r["cot_pred"]) if run_cot else "-"
        dp = str(r["code_pred"]) if run_code else "-"
        cm = ("✓" if r["cot_ok"] else "✗") if run_cot else " "
        dm = ("✓" if r["code_ok"] else "✗") if run_code else " "
        print(
            f"{r['id']:<5}{r['topic']:<26}{r['answer']:>7}{cp:>10}{cm:>4}{dp:>10}{dm:>4}"
        )
    print("-" * 78)
    summary_line = f"{'Accuracy':<5}{'':<26}{'':>7}"
    if run_cot:
        summary_line += f"{cot_correct}/{n} = {cot_correct/n:5.0%}".rjust(14)
    if run_code:
        summary_line += f"{code_correct}/{n} = {code_correct/n:5.0%}".rjust(18)
    print(summary_line)
    print("=" * 78)
    if run_cot and run_code:
        print(
            f"\nConclusion: CoT accuracy {cot_correct/n:.0%}, code assistance accuracy {code_correct/n:.0%}，"
            f"improvement {(code_correct-cot_correct)/n:+.0%}。"
        )

    # ---- Optional: write JSON results ----
    if args.output:
        summary = {
            "model": model,
            "mode": args.mode,
            "num_problems": n,
            "cot_correct": cot_correct if run_cot else None,
            "code_correct": code_correct if run_code else None,
            "rows": rows,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\nResults written to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
