# Experiment 5-1: Boosting Math Problem-Solving with Code Generation Tools

Companion experiment for "Deep Understanding of AI Agents" (★★). Validates a conclusion: when an Agent is equipped with a
Python sandbox capable of executing code, its accuracy on competitive math problems is **significantly higher** than with pure Chain-of-Thought (CoT).

## Purpose

Large models frequently make errors when "mentally calculating" large numbers, enumerations, and factorizations—not because they lack the method, but because they miscalculate.
This experiment runs the same model (default `gpt-5.6-luna`) on the same set of problems in two modes for a direct comparison:

- **Pure CoT**: Reasoning step-by-step using only natural language, with code writing prohibited;
- **Code-Assisted**: Formalizing the problem into Python (sympy symbolic computation, numpy matrices, scipy numerical solving),
  invoking the `run_python` tool via function calling to execute in a **subprocess sandbox**, using precise results to replace mental calculation.

## Principle

```
Problem ──► Model
            │  Pure CoT: Direct natural language reasoning ─────────────► Final Answer (prone to errors)
            │
            └─ Code-Assisted: Generate Python code
                         │  function calling
                         ▼
                   run_python tool (subprocess sandbox, pre-installed sympy/numpy/scipy, timeout protection)
                         │  returns stdout
                         ▼
                  Model continues reasoning based on precise results ──────────► Final Answer (more accurate)
```

- The tool is exposed via OpenAI **function calling**: the model autonomously decides when and what code to write.
- The sandbox is `run_python()` in `sandbox.py`: writes code to a temporary file, executes it in a subprocess,
  with a 20-second timeout; crashes/infinite loops do not affect the main process. `sympy / numpy / scipy` are pre-imported.
- Problems are in `problems.json`: 11 AIME-style competition problems, **answers are all integers, verified offline via brute-force enumeration**,
  covering number theory, modular arithmetic, Diophantine equations, generating functions, prime factorization, lattice point counting, etc. Each problem also includes a
  `solution` reference solution code for offline self-checking (see below).

## Offline Self-Check (No API Key Required)

Want to verify that the "sandbox + problem set ground truth" pipeline works, but don't have an API key handy? Run:

```bash
pip install -r requirements.txt
python demo.py --selfcheck        # Executes the reference solution for each problem in the sandbox, scores against ground truth
```

It executes the reference solution attached in `problems.json` for each problem, runs it in the subprocess sandbox, extracts the integer output
and compares it against the ground truth—this both demonstrates the core mechanism of "write code → sandbox execution → score against ground truth" and self-checks the
problem set's ground truth itself. Exit code is 0 when all pass. Actual output (11/11 all passed):

```
Problem  Topic                           Ground Truth  Sandbox Output
--------------------------------------------------------
1    number theory (inclusion-exclusion)    925       925   ✓
2    modular exponentiation        216       216   ✓
...
11   lattice points               1245      1245   ✓
--------------------------------------------------------
Reference solutions matched ground truth: 11/11
```

## Running the Controlled Experiment (API Key Required)

```bash
cp env.example .env   # Or directly export OPENAI_API_KEY=...
export OPENAI_API_KEY=sk-...      # Also supports MOONSHOT_API_KEY / ARK_API_KEY

python demo.py                    # Run the full controlled experiment (code and cot modes)
python demo.py --verbose          # Additionally print the model-generated code and execution results
python demo.py --limit 3          # Only run the first 3 problems (saves money for debugging)
python demo.py --mode code        # Only run code-assisted mode
python demo.py --mode cot         # Only run pure chain-of-thought mode
python demo.py --model gpt-5.6-luna   # Override the model name (equivalent to setting the MODEL environment variable)
python demo.py --output result.json   # Write per-problem results and summary to JSON
python demo.py --problems mine.json   # Use a custom problem set
```

See `python demo.py --help` for all parameters. Common flags:

| Parameter | Description |
| --- | --- |
| `--mode {both,code,cot}` | Solving mode, default `both` (runs both and compares) |
| `--selfcheck` | Offline self-check, only runs sandbox reference solutions, no API key needed |
| `--model name` | Override the model name (higher priority than the `MODEL` environment variable) |
| `--problems path` | Path to the problem set JSON, default `problems.json` |
| `--limit N` | Only run the first N problems |
| `--output path` | Write per-problem results to a JSON file |
| `--verbose` | Print generated code and sandbox execution results |

Available environment variables: `OPENAI_API_KEY` (or `MOONSHOT_API_KEY` / `ARK_API_KEY`),
`OPENAI_BASE_URL` (to switch compatible endpoints), `MODEL` (default `gpt-5.6-luna`).

**Universal OpenRouter fallback**: When no direct API key is configured, as long as `OPENROUTER_API_KEY`
is set, it will automatically route through OpenRouter (model names are auto-mapped: `gpt-*` → `openai/*`, others → `openai/gpt-5.6-luna`).
Additionally, the default model `gpt-5.6-luna` belongs to the gpt-5.x series; calling it directly via OpenAI requires organizational identity verification.
Therefore, as long as `OPENROUTER_API_KEY` is set, it will prioritize OpenRouter (route `openai/gpt-5.6-luna`).

## Expected Output Example / Conclusion

An excerpt from an actual run with `gpt-5.6-luna` (11 problems, reasoning model default `temperature=1`):

```
Problem  Topic                           Ground Truth  CoT Prediction  Code Prediction
------------------------------------------------------------------------------
2    modular exponentiation        216       216   ✓       216   ✓
6    sum of two squares            330       306   ✗       330   ✓
7    prime factorization           661       661   ✓       661   ✓
10   factorials and modular arithmetic    313       313   ✓       313   ✓
11   lattice points               1245      1245   ✓      1245   ✓
------------------------------------------------------------------------------
Accuracy                                  10/11 =   91%     11/11 =  100%
```

| Mode | Accuracy (this actual measurement) |
| --- | --- |
| Pure CoT | 10 / 11 (≈ 91%) |
| Code-Assisted | 11 / 11 (100%) |

**The accuracy of the code-assisted mode is consistently not lower than pure CoT.** The pure CoT of strong reasoning models like `gpt-5.6-luna` is already quite accurate,
but it can still stumble on problems requiring extensive enumeration / error-prone boundary conditions—the only miss this time was problem 6, "Sum of Two Squares Counting"
(e.g., counting representations for x²+y²<400; CoT miscalculated the boundary, giving 306 instead of 330). Code-assisted mode delegates such enumeration to
sympy/numpy for precise execution, filling this gap and achieving a perfect score.

> **Stronger models narrow the gap, but the direction remains unchanged.** With a weaker small model, pure CoT will make more errors on
> problems requiring large number operations / extensive enumeration (large number modulo, 100! accumulation modulo, lattice point counting, perfect square determination, etc.),
> and the lead of code-assisted mode will be significantly larger; however, code-assisted mode is not absolutely infallible: weak models may occasionally write enumeration code
> that is "correct in concept but wrong in detail," in which case a buggy piece of code is precisely executed. Regardless of model strength, the conclusion that "code-assisted is not lower than, and is usually significantly higher than,
> pure CoT" holds stably.

> **This is another example of the "model ↔ harness seesaw."** This experiment has been run on both strong and weak models:
> The weaker model `gpt-4o-mini` achieved 6/11 with pure CoT and 8/11 with code-assisted, with the code harness widening the gap by **+2 problems**; switching to the strong reasoning model
> `gpt-5.6-luna`, pure CoT itself rose to 10/11, code-assisted to 11/11, narrowing the gap to **+1 problem** (only the most difficult enumeration problem, "Sum of Two Squares Counting," needed code as a safety net).
> The stronger the model, the less code can compensate for it; if the model were strong enough to solve everything with pure thought, the gain from code-assisted would converge to 0, as seen in the companion experiment `code-for-logic`.
> **How thick the harness should be depends on the capability boundary of the model you are using**—this is a prerequisite often overlooked when evaluating an Agent technology.

## How to Adapt / Extend

- **Change Model / Provider**: Set the `MODEL` environment variable to switch models (e.g., `MODEL=gpt-5.6-luna`, `MODEL=claude-opus-4.8`);
  to change providers, set `MOONSHOT_API_KEY` (automatically switches to Kimi) or `ARK_API_KEY` (automatically switches to Doubao),
  or use `OPENAI_BASE_URL` to point to any endpoint compatible with the OpenAI protocol. Stronger models can compensate for occasional buggy code.
- **Change Problem Set**: Edit `problems.json`, providing `question` / `answer` (integer) / `topic` for each problem,
  and include a `solution` (Python reference solution that prints the answer). When adding new problems, it is recommended to **first use
  `python demo.py --selfcheck` to have the reference solution produce the ground truth in the sandbox**, just like the existing problems, to avoid errors in the answer itself.
- **Change Sandbox Capabilities**: The `PREAMBLE` in `sandbox.py` pre-imports sympy/numpy/scipy; to support more libraries,
  add the import here and update `requirements.txt` accordingly.

## Limitations

- The sandbox is a teaching-grade implementation (subprocess + timeout + temporary directory), **not a security isolation boundary**; production environments should use
  containers / gVisor / network-less strong isolation sandboxes.
- Accuracy depends on model quality: small models may still produce buggy code (see above); code-assisted reduces but does not eliminate errors.
- Answer extraction parses according to `FINAL ANSWER: <integer>`, only supporting integer-type answers; non-integer / multi-value answers require modifying
  `extract_answer` and the scoring logic.

## Files

| File | Description |
| --- | --- |
| `demo.py` | Main program: controlled experiment + function calling loop + results table + offline self-check (`--selfcheck`) |
| `sandbox.py` | Subprocess Python sandbox (`run_python`, timeout protection, pre-installed math libraries) |
| `problems.json` | 11 competition problems (problem statements + verified integer ground truths + topics + reference solutions `solution`) |
| `requirements.txt` | Dependencies |
| `env.example` | Environment variable example |
