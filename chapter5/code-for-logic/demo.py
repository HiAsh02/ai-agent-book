#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experiment 5-2: Enhancing Logical Reasoning with Code Generation Tools

Compare the accuracy of solving "Knights & Knaves" puzzles under three modes:

  1) Pure thinking (pure)      —— LLM directly answers via natural language chain-of-thought reasoning;
  2) Code-assisted (code)    —— LLM equipped with Code Interpreter (pre-installed python-constraint),
                          formalizes the puzzle as a constraint satisfaction problem (CSP) and calls the solver to search for the answer;
  3) Constraint solving (solver)  —— [Offline, no API required] Directly solve structured statements using python-constraint as a deterministic baseline (theoretically 100% correct).

Expected conclusion: Constraint solving outsources logical reasoning to a deterministic solver, achieving 90%+ accuracy, significantly higher than pure thinking mode (which is error-prone for multi-person puzzles involving counting/self-reference).

Usage:
    # Offline constraint solving baseline (no cost, no internet, demonstrates core argument):
    python demo.py --mode solver

    # LLM controlled experiment (requires OPENAI_API_KEY):
    export OPENAI_API_KEY=sk-...
    python demo.py                       # default both: run pure thinking vs code-assisted on all puzzles
    python demo.py --mode pure           # run only pure thinking
    python demo.py --limit 4             # run only first 4 puzzles (cost-saving smoke test)
    python demo.py --max-people 3        # run only puzzles with at most 3 people (filter by difficulty)
    python demo.py --model gpt-4o-mini    # specify model (default gpt-4o-mini)
    python demo.py --puzzles my.json     # use a different puzzle dataset
"""
import argparse
import json
import os
import re
import sys

from csp_solver import solve_labeled
from sandbox import run_python

# ---- Read .env (if exists). To avoid extra dependencies, write a minimal parser manually. ----
def _load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

MODEL = os.environ.get("MODEL", "gpt-4o-mini")

# --- Generic OpenRouter fallback: automatically route through OpenRouter when no direct key is available ---
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def map_model_to_openrouter(model: str) -> str:
    """Map the direct model name to the ID on OpenRouter (non-mappable IDs fall back to the current cheap flagship)."""
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
    return "openai/gpt-5.6-luna"


def build_client_and_model():
    """Construct an OpenAI client and return (client, model).

    - With OPENAI_API_KEY: direct connection (default model gpt-4o-mini is a normal gpt id, can directly connect to OpenAI).
      Only when the model is gpt-5.x and OPENROUTER_API_KEY is also set, prioritize OpenRouter
      (direct connection to gpt-5.x requires organizational real-name authentication).
    - Without OPENAI_API_KEY but with OPENROUTER_API_KEY: switch to OpenRouter entirely.
    """
    from openai import OpenAI
    global MODEL
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    orkey = os.environ.get("OPENROUTER_API_KEY")
    prefer_or = bool(orkey) and (MODEL or "").lower().startswith("gpt-5")
    if prefer_or or (not api_key and orkey):
        api_key, base_url, MODEL = orkey, OPENROUTER_BASE_URL, map_model_to_openrouter(MODEL)
    kw = {"api_key": api_key, "timeout": 60.0, "max_retries": 3}
    if base_url:
        kw["base_url"] = base_url
    return OpenAI(**kw), MODEL


def _reasoning(model: str) -> bool:
    """Reasoning models (gpt-5 / o series / *thinking, etc.) do not accept temperature=0."""
    return any(k in (model or "").lower()
               for k in ("gpt-5", "o1", "o3", "o4", "thinking", "reasoner", "kimi-k3"))

#function calling definition for the run_python tool
TOOLS = [{
    "type": "function",
    "function": {
        "name": "run_python",
        "description": (
            "Execute Python code in a sandbox with the python-constraint library pre-installed, returning stdout/stderr."
            "Use it to model logic puzzles as constraint satisfaction problems and solve them. Remember to print the results with print()."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Complete Python code to execute"}
            },
            "required": ["code"],
        },
    },
}]

ANSWER_HINT = (
    'After reasoning, output the final answer in JSON format on a separate line at the end.'
    'The key is each resident\'s name, and the value is "knight" or "knave", for example:'
    '{"A": "knight", "B": "knave"}'
)

PURE_SYSTEM = (
    "You are an expert in logical reasoning. In the \"Knights and Knaves\" puzzle, knights always tell the truth, and knaves always lie."
    "Please rely solely on your own reasoning, analyze each resident's identity step by step, and find the unique solution that satisfies all statements.\n" + ANSWER_HINT
)

CODE_SYSTEM = (
    "You are an expert in logical reasoning, skilled at transforming puzzles into formal constraints and solving them with code."
    "In the \"Knights and Knaves\" puzzle, knights always tell the truth and knaves always lie.\n"
    "Please be sure to use the run_python tool to model the puzzle as a constraint satisfaction problem (CSP) using the python-constraint library.\n\n"
    "【Most critical modeling rule】Do not directly treat someone's statement as a factual constraint!"
    "The correct approach is to add a [biconditional (equivalence) constraint] for each resident X: \n"
    "    Boolean value of X == (X is semantically true)\n"
    "Meaning: X is a knight (True) if and only if his words are true; X is a knave (False) if and only if his words are false.\n"
    "This rule applies to every sentence, including counting statements ('there are exactly two knights') and self-referential statements ('I am of the same type as B') —"
    "must be written as `X == (truth expression of that sentence)`, never treat `(truth expression of that sentence)` alone as a hard constraint.\n\n"
    "Example (let True=Knight):\n"
    "    from constraint import Problem\n"
    "    p = Problem()\n"
    "    for name in ['A','B','C']:\n"
    "        p.addVariable(name, [True, False])\n"
    "    # A says 'exactly one of us is a knight'  ->  A == ( (A+B+C)==1 )\n"
    "    p.addConstraint(lambda a,b,c: a == ((a+b+c)==1), ['A','B','C'])\n"
    "    # B says 'C is a scoundrel'             ->  B == (not C)\n"
    "    p.addConstraint(lambda b,c: b == (not c), ['B','C'])\n"
    "    # C says 'I am the same kind of person as A'     ->  C == (C == A)\n"
    "    p.addConstraint(lambda a,c: c == (c == a), ['A','C'])\n"
    "    for s in p.getSolutions():\n"
    "        print({k:('knight' if v else 'knave') for k,v in s.items()})\n\n"
    "Steps: 1) One Boolean variable per person; 2) Write each sentence as a biconditional constraint as above;"
    "3) Call getSolutions() to enumerate all solutions and print.\n"
    "The final answer must strictly adopt the solution printed by the solver; do not override it with your own intuition."
    "If the solver output is empty, it means the constraints are incorrectly constructed (likely missing a dual condition). Please check and rerun.\n" + ANSWER_HINT
)


def parse_answer(text, names):
    """Extract the last JSON answer of the form {name: knight/knave} from the model output."""
    norm = {"knight": "knight", "knave": "knave", "knight": "knight", "knave": "knave"}
    # Find all {...} fragments and try to parse them from back to front
    for m in reversed(list(re.finditer(r"\{[^{}]*\}", text))):
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        got = {}
        for n in names:
            if n not in obj:
                break
            v = str(obj[n]).strip().lower()
            v = norm.get(v, norm.get(str(obj[n]).strip(), None))
            if v is None:
                break
            got[n] = v
        else:
            return got
    return None


def call_model(client, system, user, use_tools):
    """Run one round of dialogue (including possible multiple tool calls), return (final text, list of codes used)."""
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    codes = []
    for _ in range(8):  # At most 8 rounds to prevent infinite loops
        kwargs = (dict(model=MODEL, messages=messages, temperature=1, max_tokens=8192)
                  if _reasoning(MODEL)
                  else dict(model=MODEL, messages=messages, temperature=0))
        if use_tools:
            kwargs.update(tools=TOOLS, tool_choice="auto")
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        if use_tools and msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                try:
                    code = json.loads(tc.function.arguments).get("code", "")
                except json.JSONDecodeError:
                    code = ""
                codes.append(code)
                result = run_python(code)
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": result})
            continue
        return msg.content or "", codes
    return "", codes


def run_mode(client, puzzles, mode):
    """Run one LLM mode (pure/code), return a list of per-question records."""
    system = CODE_SYSTEM if mode == "code" else PURE_SYSTEM
    records = []
    for p in puzzles:
        text, codes = call_model(client, system, p["description"], mode == "code")
        pred = parse_answer(text, p["names"])
        correct = pred == p["solution"]
        records.append(dict(id=p["id"], num=p["num_people"], pred=pred,
                            gold=p["solution"], correct=correct,
                            codes=codes, text=text))
        mark = "✓" if correct else "✗"
        print(f"  [{mode:6}] {p['id']} ({p['num_people']}person) {mark}  "
              f"prediction={pred}")
    return records


def run_solver(puzzles):
    """Offline constraint solving mode: directly use python-constraint to solve structured statements, no LLM/API needed."""
    records = []
    for p in puzzles:
        struct = p.get("statements_struct")
        if not struct:
            sys.exit(f"Error: puzzle {p['id']} missing statements_struct field, "
                     "Please regenerate puzzles.json using the new build_puzzles.py.")
        sols = solve_labeled(p["names"], struct)
        pred = sols[0] if len(sols) == 1 else None
        correct = pred == p["solution"]
        records.append(dict(id=p["id"], num=p["num_people"], pred=pred,
                            gold=p["solution"], correct=correct,
                            codes=[], text="", num_solutions=len(sols)))
        mark = "✓" if correct else "✗"
        print(f"  [solver] {p['id']} ({p['num_people']}person) {mark}  "
              f"solution count={len(sols)}   prediction={pred}")
    return records


LABELS = {"pure": "Pure Thinking", "code": "Code-Assisted", "solver": "Constraint Solving"}


def print_table(columns, puzzles):
    """Print a multi-column accuracy comparison table. columns = [(mode, records), ...], order is column order."""
    accs = {m: sum(r["correct"] for r in recs) / len(recs) for m, recs in columns}
    header = f"{'Question No.':<8}{'Person Count':<6}" + "".join(f"{LABELS[m]:<10}" for m, _ in columns)
    print("\n" + "=" * 60)
    print("Accuracy Comparison Table")
    print("=" * 60)
    print(header)
    print("-" * 60)
    n = len(puzzles)
    for i in range(n):
        row = f"{puzzles[i]['id']:<8}{puzzles[i]['num_people']:<6}"
        for _, recs in columns:
            row += f"{('✓' if recs[i]['correct'] else '✗'):<10}"
        print(row)
    print("-" * 60)
    tail = f"{'Accuracy':<8}{'':<6}" + "".join(
        f"{accs[m]*100:>6.1f}%   " for m, _ in columns)
    print(tail)
    print("=" * 60)
    for m, recs in columns:
        n_ok = sum(r["correct"] for r in recs)
        print(f"{LABELS[m]:<6}  Accuracy: {accs[m]*100:5.1f}%  ({n_ok}/{len(recs)})")
    #  If both solver/code and pure are present, report the improvement margin
    baseline = next((m for m in ("pure",) if m in accs), None)
    best = next((m for m in ("solver", "code") if m in accs), None)
    if baseline and best and best != baseline:
        print(f"Improvement({LABELS[best]} - {LABELS[baseline]}): "
              f"{(accs[best]-accs[baseline])*100:+.1f}  percentage points")


def main():
    global MODEL
    ap = argparse.ArgumentParser(
        description="Experiment 5-2: Compare accuracy of Pure Thinking / Code-Assisted / Constraint Solving modes for solving"
                    "the \"Knights and Knaves\" logic puzzles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--mode", choices=["both", "pure", "code", "solver"],
                    default="both",
                    help="Run mode: both=pure thinking + code assistance (default); pure=pure thinking only; "
                         "code=code assistance only; solver=offline constraint solving baseline (no API needed)")
    ap.add_argument("--model", default=MODEL,
                    help=f"LLM model name (default {MODEL}; ignored in solver mode)")
    ap.add_argument("--limit", type=int, default=0,
                    help="Only run the first N problems (0=all)")
    ap.add_argument("--min-people", type=int, default=0,
                    help="Only run puzzles with residents >= this value (filter by difficulty, 0=unlimited)")
    ap.add_argument("--max-people", type=int, default=0,
                    help="Only run puzzles with residents <= this value (filter by difficulty, 0=unlimited)")
    ap.add_argument("--puzzles", default="puzzles.json",
                    help="Puzzle dataset path (default puzzles.json)")
    ap.add_argument("--output", default="last_run.json",
                    help="Output path for per-problem full records (default last_run.json)")
    args = ap.parse_args()
    MODEL = args.model

    with open(args.puzzles, encoding="utf-8") as f:
        puzzles = json.load(f)
    if args.min_people:
        puzzles = [p for p in puzzles if p["num_people"] >= args.min_people]
    if args.max_people:
        puzzles = [p for p in puzzles if p["num_people"] <= args.max_people]
    if args.limit:
        puzzles = puzzles[:args.limit]
    if not puzzles:
        sys.exit("Error: no puzzles after filtering, please relax --min-people/--max-people/--limit.")

    #Solver mode is fully offline, no API needed; other modes require OPENAI_API_KEY.
    llm_modes = {"both": ["pure", "code"], "pure": ["pure"],
                 "code": ["code"], "solver": []}[args.mode]
    results = {}

    if args.mode == "solver":
        print(f"Offline constraint solving baseline    Number of problems:{len(puzzles)}\n")
        print("== Constraint solving (solver, offline) ==")
        results["solver"] = run_solver(puzzles)
    else:
        if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")):
            sys.exit("Error: pure/code/both modes require OPENAI_API_KEY (or fallback to OPENROUTER_API_KEY)"
                     "Environment variables (can be written to .env). To only view the offline constraint solving baseline, use --mode solver.")
        client, MODEL = build_client_and_model()  #  Lazy import openai + OpenRouter fallback
        print(f"Model:{MODEL}    Number of problems:{len(puzzles)}    Mode:{args.mode}\n")
        for m in llm_modes:
            print(f"== {LABELS[m]}({m}) ==")
            results[m] = run_mode(client, puzzles, m)
            print()

    # ---- Accuracy comparison table (fixed column order: pure -> code -> solver) ----
    columns = [(m, results[m]) for m in ["pure", "code", "solver"] if m in results]
    print_table(columns, puzzles)

    # ---- Display constraint modeling code and solution for one problem ----
    code_recs = results.get("code")
    if code_recs:
        sample = next((r for r in code_recs if r["correct"] and r["codes"]), None)
        if sample:
            print("\n" + "=" * 60)
            print(f"Example:{sample['id']}  constraint modeling code (model-generated)")
            print("=" * 60)
            print(sample["codes"][0])
            print("-- Solution & Final Answer --")
            print(f"prediction={sample['pred']}  Ground truth={sample['gold']}")

    #  Save full records for review
    payload = dict(model=MODEL, mode=args.mode)
    for m, recs in results.items():
        payload[m] = recs
        payload[f"{m}_acc"] = sum(r["correct"] for r in recs) / len(recs)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nFull per-problem records saved to {args.output}")


if __name__ == "__main__":
    main()
