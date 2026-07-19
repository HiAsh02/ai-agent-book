# Experiment 5-2: Enhancing Logical Reasoning with Code Generation Tools

Companion code for "Deep Understanding of AI Agents".

This experiment evaluates an Agent's ability to assist logical reasoning through **constraint solving** code: equip the same LLM with a Code Interpreter pre-installed with
`python-constraint`, and have it translate "Knights & Knaves" logic puzzles
into formalized **Constraint Satisfaction Problems (CSP)** — identify variables (whether each islander is a knight or knave), define constraints
("knights tell the truth, knaves lie"), and then invoke the solver to search for solutions satisfying all constraints.

We compare three modes using a set of 12 K&K puzzles (2~5 people, each with a unique truth-value solution):

- **Pure reasoning (pure)**: LLM uses only natural language chain-of-thought reasoning to directly give the answer;
- **Code-assisted (code)**: LLM uses the `run_python` tool to write a constraint model and invoke the solver, then answers based on the result;
- **Constraint solving (solver)**: **Offline baseline**, directly uses `python-constraint` to solve structured statements,
  requiring no API/network — it is the deterministic solver path itself, theoretically 100% correct, used to verify
  the core thesis of "translating puzzles into constraint programs and solving them" (see actual run results below).

## Core Idea: Why Code Assistance is Stronger

The key modeling rule for K&K puzzles is just one — for each resident X, add a **biconditional (equivalence) constraint**:

```
X is a knight (True)  <=>  X's statement is true
```

i.e., `X == (semantic truth value of that statement)`. Handing this to a deterministic solver to **exhaustively** search all boolean combinations is logically error-free;
while pure reasoning, on puzzles with multiple people, counting ("exactly two knights"), or self-reference ("I am the same type as B"), easily makes mistakes
when mentally propagating truth values.

## File Descriptions

| File | Purpose |
| --- | --- |
| `demo.py` | Main program: runs controlled experiments for pure reasoning / code-assisted / constraint solving, prints accuracy comparison table |
| `csp_solver.py` | Offline constraint solver: structured statement DSL + `python-constraint` solving (shared by demo's solver mode and build_puzzles validation) |
| `sandbox.py` | Minimal Code Interpreter: subprocess sandbox execution of model-generated Python (pre-installed python-constraint) |
| `puzzles.json` | 12 puzzle descriptions + structured statements + unique truth-value solutions (only descriptions are given to the LLM) |
| `build_puzzles.py` | Generate/validate puzzles: use `python-constraint` to solve and assert each puzzle has a "unique solution", can export selected puzzles or randomly generate |
| `requirements.txt` | Dependencies (openai + python-constraint) |
| `env.example` | Environment variable sample |
| `last_run.json` | Complete per-puzzle record automatically saved after each run (including model-generated code), convenient for review |

## Quick Start

```bash
pip install -r requirements.txt
```

### 1) Offline Constraint Solving Baseline (no API Key required, recommended to run first)

```bash
python demo.py --mode solver          # Use python-constraint to solve all 12 puzzles offline
python demo.py --mode solver --min-people 4   # Only run puzzles with >=4 people
```

This path is completely offline and deterministic, directly demonstrating the core thesis of "puzzle → constraint program → solving", with 100% accuracy.

### 2) LLM Controlled Experiment (requires OPENAI_API_KEY or OPENROUTER_API_KEY)

```bash
cp env.example .env        # Then edit .env to fill in OPENAI_API_KEY
# Or directly export OPENAI_API_KEY=sk-...

python demo.py             # Default both: pure reasoning vs code-assisted, all 12 puzzles
python demo.py --mode pure # Only run pure reasoning baseline
python demo.py --limit 4   # Only run first 4 puzzles (cost-saving smoke test)
python demo.py --max-people 3        # Only run puzzles with <=3 people (filter by difficulty)
python demo.py --model gpt-4o-mini   # Specify model (default gpt-4o-mini)
python demo.py --puzzles my.json --output run.json   # Change dataset/output path
```

**Universal OpenRouter fallback**: When `OPENAI_API_KEY` is not configured, as long as `OPENROUTER_API_KEY`
is set, it automatically switches to OpenRouter (`gpt-*` → `openai/*`). The default model `gpt-4o-mini` is a regular gpt id that can
directly connect to OpenAI; only when `--model` is changed to `gpt-5.x` or similar models requiring organizational real-name authentication, and
`OPENROUTER_API_KEY` is set, will it prioritize OpenRouter.

See `python demo.py --help` for complete parameters (Chinese descriptions).

### 3) Generate/Expand Puzzle Dataset

```bash
python build_puzzles.py                     # Export built-in 12 selected puzzles (default)
python build_puzzles.py --generate 20 --min-people 3 --max-people 5 --seed 7
python build_puzzles.py --generate 20 --output my.json
```

The random generator uses `python-constraint` to solve each candidate puzzle, only keeping puzzles with a "unique solution".

`sandbox.py` / `csp_solver.py` can also be run independently for self-testing:
`python sandbox.py`, `python csp_solver.py` will both use python-constraint to solve a simple puzzle.

## Actual Run Results (1): Offline Constraint Solving Baseline (`--mode solver`, no API required)

Actual output of `python demo.py --mode solver` (12 selected puzzles, completely offline, deterministic):

```
== Constraint Solving (solver, offline) ==
  [solver] kk01 (2 people) ✓   Solutions=1   Prediction={'A': 'knight', 'B': 'knave'}
  [solver] kk05 (3 people) ✓   Solutions=1   Prediction={'A': 'knave', 'B': 'knave', 'C': 'knight'}
  [solver] kk11 (5 people) ✓   Solutions=1   Prediction={'A': 'knight', 'B': 'knight', 'C': 'knave', 'D': 'knave', 'E': 'knight'}
  ... (remaining puzzles omitted)
------------------------------------------------------------
Accuracy            100.0%
============================================================
Constraint Solving   Accuracy: 100.0%  (12/12)
```

This path translates each puzzle's structured statements into `python-constraint` constraints and exhaustively solves them, achieving 12/12 correct —
it directly proves the determinism of "puzzle → constraint program → solving"; as long as the LLM correctly translates the puzzle into the same constraints,
it can achieve the same 100% result (next section). Randomly generated puzzles (`build_puzzles.py --generate`) verified by the solver
also achieve 100% solution rate and are consistent with the unique solution at generation time.

## Actual Run Results (2): LLM Controlled Experiment (gpt-4o-mini, 12 puzzles)

```
Accuracy Comparison Table
============================================================
Puzzle    People   Pure Reasoning   Code-Assisted
------------------------------------------------------------
kk01    2     ✓         ✓
kk02    2     ✓         ✓
kk03    2     ✓         ✓
kk04    3     ✓         ✓
kk05    3     ✗         ✓
kk06    3     ✗         ✓
kk07    3     ✗         ✓
kk08    4     ✗         ✓
kk09    4     ✗         ✓
kk10    4     ✓         ✓
kk11    5     ✗         ✓
kk12    5     ✓         ✓
------------------------------------------------------------
Accuracy             50.0%    100.0%
============================================================
Pure Reasoning    Accuracy:  50.0%  (6/12)
Code-Assisted     Accuracy: 100.0%  (12/12)
Improvement (Code-Assisted - Pure Reasoning): +50.0 percentage points
```

> Note: The weaker `gpt-4o-mini` was deliberately chosen here to expose the contrast — pure reasoning only got **6/12
> (50%)** correct, with errors concentrated on puzzles with 3 or more people, containing counting/self-reference (kk05~kk09, kk11), precisely the types where mental
> truth value propagation is most error-prone; while code-assisted translates each statement into a biconditional constraint, hands it to `python-constraint`
> for exhaustive solving, achieving **12/12 correct**, instantly maxing out accuracy with a net improvement of **+50 percentage points**. This is exactly what this experiment aims to
> demonstrate: outsourcing logic to a deterministic solver makes correctness no longer dependent on the model's own reasoning strength. `gpt-4o-mini`
> has some randomness, and individual puzzles may have slight fluctuations across multiple runs, but the overall pattern of "pure reasoning significantly lower than code-assisted" is stable.

> **Model and harness have a trade-off relationship**: When the model is strong enough, the harness can be thinner — the model itself
> can compute correctly; when the model is not strong enough, more work needs to be done in the harness (such as handing logic to code/solver) to guarantee
> correctness. This experiment deliberately uses the weaker `gpt-4o-mini` to make this contrast visible — if replaced with a strong reasoning model like `gpt-5.6-luna`,
> pure reasoning could also solve everything, and the code gain would converge to 0. In other words, the true value of code-assisted (and even offline
> solver) is to make correctness **deterministic and independent of model strength**: for weaker models or larger/more difficult
> puzzles, pure reasoning will lose accuracy as the number of people increases, while the path of "translating into constraint programs + exhaustive solver" always stably produces the correct solution.

### Constraint Modeling Code for One Puzzle (Model Auto-Generated, kk11, 5-person Chain + Counting)

Puzzle description: A says "B is a knight"; B says "C is a knave"; C says "D is a knight"; D says "E is a knave";
E says "Among the five of us, there are at least two knights."

```python
from constraint import Problem

p = Problem()
for name in ['A', 'B', 'C', 'D', 'E']:
    p.addVariable(name, [True, False])   # True=knight (tells truth), False=knave (lies)

# Each statement is written as a biconditional constraint: X == (truth value of that statement)
p.addConstraint(lambda a, b: a == (b == True), ['A', 'B'])          # A:"B is a knight"
p.addConstraint(lambda b, c: b == (c == False), ['B', 'C'])        # B:"C is a knave"
p.addConstraint(lambda c, d: c == (d == True), ['C', 'D'])         # C:"D is a knight"
p.addConstraint(lambda d, e: d == (e == False), ['D', 'E'])        # D:"E is a knave"
p.addConstraint(lambda a, b, c, d, e: e == ((a + b + c + d + e) >= 2),
                ['A', 'B', 'C', 'D', 'E'])                          # E:"At least two knights"

for s in p.getSolutions():
    print({k: ('knight' if v else 'knave') for k, v in s.items()})
# Output: {'A': 'knight', 'B': 'knight', 'C': 'knave', 'D': 'knave', 'E': 'knight'}
```

The solver directly exhaustively searches 2^5=32 combinations, returning the unique solution satisfying all constraints — precisely the type of puzzle where pure reasoning is most prone to errors in chain truth value propagation.

## Notes

- **Cost**: Default `gpt-4o-mini` (deliberately chosen weaker model to show contrast, see above), running all 12 puzzles in both modes has very low cost; use `MODEL`/`--model` to switch to cheaper or stronger models.- **API Key**: Read `OPENAI_API_KEY` from environment variables or `.env` (fallback to `OPENROUTER_API_KEY`); use `MODEL` to switch models.
- **Sandbox**: `sandbox.py` executes code via subprocess with a timeout, serving as a minimal sandbox for teaching; for production, replace with stronger isolation like containers/gVisor.
- **Puzzle Reliability**: `build_puzzles.py` uses `python-constraint` to solve each puzzle (built-in curated puzzles or randomly generated), asserts a unique solution before writing, ensuring unambiguous ground-truth solutions; to add custom puzzles, modify `CURATED` or use `--generate`.
