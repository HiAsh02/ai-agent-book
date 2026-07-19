# Experiment 5-3: Small Model Improves Rule Execution Accuracy Through Codified Knowledge

Companion to Chapter 5 (Experiment 5-3) of "Deep Understanding of AI Agents". Based on the τ-bench airline customer service scenario, this is a
**controlled experiment** that verifies whether a small model (default `gpt-5.6-luna`) can **match the reliability of a large model running bare** when executing complex business policies by using **codified business rules** (as CODE guards) — achieving greater accuracy and consistency than pure natural language rules.

## One-Sentence Conclusion

For the same small model and the same set of tasks, simply moving "business rules from the prompt into code/tools" improved
**task success rate from 88% to 100%, and policy violations dropped from 1 to 0** — and we can observe that the in-tool code
validation intercepted the model's erroneous cognition in real time. Core claim: **Codifying business rules as guards allows a small model to
match a large model running bare in complex policy execution** (run with `--big-model` to add the large model baseline arm for on-site verification, see below).

## Experiment Design

A simplified airline customer service environment: a simulated "database ground truth" (flights/bookings/cabins/booking time/flight status), and a
**codified refund policy** (`airline_env.is_refundable`) as the sole authoritative criterion.

Refund policy (natural language + code from the same source):
- Basic economy tickets (`basic_economy`) are **non-refundable** by default;
- Exception 1: Full refund within **24 hours of booking**;
- Exception 2: Full refund if the flight is **cancelled by the airline** or **delayed ≥ 3 hours** (significant delay);
- Flexible tickets / business class are fully refundable;
- When non-refundable, explain the policy and **proactively offer alternatives** (retain ticket for rebooking, travel credits).

### Comparison Arms

By default, run two arms (same small model, only difference is "whether rules are codified"); add `--big-model` to add a third arm
**large model bare baseline**, forming the three-way comparison described in the book:

| Arm | Model | Codified Rules | Role |
|---|---|---|---|
| A `codified` | Small model | ✅ Triple safeguards | Experimental group |
| B `control` | Small model | ❌ Pure natural language | Control group |
| C `control` | **Large model** | ❌ Pure natural language | Large model baseline (`--big-model`, optional) |

Expected relationship **A ≈ C > B**: Small model + codified guards (A) matches large model bare (C), and both significantly outperform
small model bare (B).

### The Only Difference Between Control / Experimental Groups (Three-Layer Guard Comparison)

| | Control Group `control` | Experimental Group `codified` |
|---|---|---|
| ① System prompt (first layer guard) | Natural language policy | Natural language policy (same) |
| ② Tool description (second layer guard · checklist) | Minimal, no checklist parameters | Lists full policy, and guides model to **check item by item before calling** via optional `expected_refundable` / `expected_reason` parameters |
| ③ Inside tool (third layer guard · gatekeeper) | Naive execution: cancels and **unconditionally refunds** when called | Code-based validation against **database ground truth**: all policy facts checked against DB, time taken from server clock, model's self-reported parameters not trusted; policy-violating calls are **rejected** |

Both groups share the read-only tool `get_reservation` (returns ground truth, `hours_since_booking` calculated by server clock,
eliminating model calculation errors). The difference is cleanly isolated as "whether there is a third safeguard: in-tool code validation".
The three layers together constitute the "triple safeguards" described in the book: the first two layers reduce errors, the third ensures errors don't become irreversible losses.

### Evaluation Tasks (8 total, 4 refundable / 4 non-refundable)

Includes normal tasks and boundary-violation tasks, covering: flexible tickets, 24h boundary (5h / 26h), airline cancellation, business class,
user falsely claiming flexible ticket, minor delay (not significant delay), airline schedule change (neither cancellation nor ≥3h delay).
See `tasks.py`.

### Metrics and Criteria (Rule-Based, Deterministic, Reproducible, Zero Extra Cost)

"State is ground truth": After a single run, directly check whether `refund_issued` occurred in the environment, and compare against the codified policy
ground truth:
- **Task success rate**: Whether the refund result matches the policy ground truth;
- **Number of policy violations**: `Over-refund (should have refused but didn't)` + `Under-refund (should have refunded but didn't)`, counted in both directions;
- **Number of invalid tool calls**: Calls rejected by code validation / unknown bookings returning error/rejected;
- **`expected_*` self-reported value vs database ground truth inconsistency rate** (experimental group only): Quantifies "model self-cognition can be wrong", thus verifying the necessity of server-side ground truth validation.

## Running

```bash
pip install -r requirements.txt
cp env.example .env   # Fill in OPENAI_API_KEY (or use environment variables directly)
# General fallback: if OPENAI_API_KEY is not configured, setting OPENROUTER_API_KEY will automatically switch to OpenRouter
# (small model gpt-5.6-luna belongs to gpt-5.x, code will automatically prefer OpenRouter: openai/gpt-5.6-luna; large model baseline similarly)

# Offline self-test (no API Key needed): directly view the validation logic of the codified guard
python demo.py --selftest

# Default: run all 8 cases, control group vs experimental group (both using small model)
python demo.py

# Three-way comparison: add large model baseline arm to verify "small model + rules ≈ large model bare"
python demo.py --big-model gpt-5.6-luna
```

### Command Line Arguments (`python demo.py --help` for full Chinese help)

| Argument | Description |
|---|---|
| `--mode {control,codified,both}` | Which group to run: without/with codified rules, or both (default `both`) |
| `--task ID [ID ...]` | Only run cases where `task_id` matches the substring, e.g., `--task R009` to directly target the core interception example |
| `--small-model NAME` | Small model name (default `gpt-5.6-luna`, or use environment variable `MODEL`) |
| `--big-model NAME` | Large model baseline name (optional; if given, adds a third arm, or use environment variable `BIG_MODEL`) |
| `--quick` | Only run the first 4 cases (save money and time) |
| `-v, --verbose` | Print each tool call step |
| `--output PATH` | Write per-case results and summary metrics to JSON |
| `--selftest` | Offline demonstration of codified validation logic (no API Key needed) |

`--selftest` prints the policy ground truth for all cases, and compares "naive tool (unconditional refund, violates when non-refundable)"
with "codified tool (always adjudicates by database ground truth, intercepts all non-refundable cases)". It's the fastest way to understand the third layer guard.

## Actual Run Results (`gpt-5.6-luna`, reasoning model temperature=1)

```
Metric                  Control Group               Experimental Group
--------------------------------------------------------------------
Task success rate       7/8 = 88%                   8/8 = 100%
Policy violations       1                           0
Invalid tool calls      0                           1        (= 1 violation intercepted by code)

[Experimental group] expected_* self-reported vs database ground truth:
  Of 5 cancellation calls with checklist, 1 was inconsistent with ground truth — inconsistency rate = 20%
```

> **Regarding the large model baseline arm (C)**: The table above shows the actual two-arm run from this repository (same small model `gpt-5.6-luna`).
> The third arm "large model bare" is **run on demand** — add `--big-model <your large model>` to get column C's
> success rate on the spot and fill it into the comparison table, verifying **A (small model + rules) ≈ C (large model bare) > B (small model bare)**.
> Specific numbers for C are not pre-filled here to avoid mismatch with your actual large model/timing.

> **Which numbers are stable and which fluctuate**: The core conclusion — "task success rate 88%→100%, policy violations 1→0,
> and the control group's only violation consistently falls on the trap case `R009`" — is stably reproducible every run; secondary metrics
> (experimental group invalid tool calls 0~1, `expected_*` inconsistency rate 0%~20%, and whether R009 in the experimental group
> is "self-identified as non-refundable by the model at the parameter stage" or "intercepted by the code guard after initiating cancellation") depend on
> the reasoning model's choices each time, and will fluctuate slightly, which is normal — both paths stably lead to the correct non-refundable result.

> **Model ↔ scaffolding trade-off, but the scaffolding here has "two layers of value".** This experiment was tested on both strong and weak models:
> The weaker model `gpt-4o-mini` achieved 6/8 in the control group and 8/8 in the experimental group, with codified rules widening the gap by **+2 questions**; switching to the stronger `gpt-5.6-luna`,
> the control group itself rose to 7/8, narrowing the gap to **+1 question**. It can be seen that the **accuracy** benefit indeed diminishes as the model gets stronger — consistent with the pattern of `code-for-logic`,
> `code-for-math`. However, codified rules also provide a **second layer of value that does not disappear as the model gets stronger**: **determinism and ground truth fallback**.
> Even a strong model can still "fail to refuse when it should" on policy traps like `R009`, while "always check the database, don't trust the model's self-report" can stably intercept and maintain 0 violations.
> In other words: the part that model capability can compensate for (accuracy) will be gradually flattened by stronger models, but the part that only scaffolding can guarantee (determinism, auditability, safety fallback)
> will not — **this is the key to determining "which scaffolding can be thinned as models upgrade, and which must be retained"**.

The control group's only violation consistently occurs on the trap case `R009`, where **model cognition does not match ground truth**, forming a clear causal chain:

| case | Policy ground truth | Model cognition | Control group result | Experimental group result |
|---|---|---|---|---|
| R009 (basic ticket · airline schedule change, not one of the two exceptions) | Non-refundable | Mistakenly considered "airline schedule change = airline cause = refundable" (`expected_refundable=True`) | ❌ Over-refund | ✅ Code validation intercepts (or self-identifies at parameter stage), switches to explanation + alternative proposal |

`gpt-5.6-luna`, as a relatively strong small model, can already answer correctly on routine judgments like the 24h boundary (e.g., R003 booking 5h),
but when faced with policy details like "airline unilateral schedule change ≠ airline cancellation/significant delay", it still tends to be **overly generous, failing to refuse when it should**; server-side
ground truth validation (all policy facts checked against the database, model's self-reported parameters not trusted) is designed to catch exactly this type of cognitive error.

### Codified Validation Interception Example (R009)

```
Model checklist self-report: expected_refundable=True, expected_reason=airline_caused (believes "airline schedule change = airline cause = refundable")
Database ground truth        : refundable=False, reason=non_refundable_basic_economy
Model initiates cancellation call: {'reservation_id':'R009','expected_refundable':True,'expected_reason':'airline_caused'}
Tool codified validation returns: status=rejected, reason=policy_violation
  → "Validated against database ground truth: this reservation is non-refundable (basic economy ticket, booked over 24 hours ago, and no airline cause).
     The system has intercepted the refund operation. Do not promise a refund. Instead, explain the policy to the passenger and proactively offer alternatives (such as retaining the ticket for rebooking, applying for travel credits)."

Model's final response to user (autonomously pivots after interception):
  "…According to the refund policy, basic economy tickets are only refundable within 24 hours of booking, or if the flight is cancelled or significantly delayed (≥3 hours).
   The current conditions do not meet the refund criteria, so a full refund cannot be processed for R009. You may choose to retain the ticket and apply for rebooking to another available flight,
   or inquire about the possibility of applying for travel credits…"
```

The same case in the **control group**: the naive tool directly executed the refund — `gpt-5.6-luna` treated "airline unilateral schedule change"
as a refund reason. This shows: relying on model natural language reasoning to execute complex policies is unreliable; by **codifying** rules into the tool,
even if the model makes a wrong judgment, the ground truth fallback can intercept it, and smoothly transition to explaining and proposing alternatives to the user.

## Two Key Observed Phenomena (Corresponding to Experiment Objectives)

1. **"Parameters as checklist"**: In the experimental group, when the model **prepares the `expected_*` parameters**, it is guided by the
   itemized policy in the tool description. Most violation boundaries (R006 26h, R008 minor delay, R005 user falsely claiming) are
   **self-identified as non-refundable** by the model at the parameter stage, directly explaining to the user and proposing alternatives, without ever reaching the refund step.
2. **Necessity of server-side ground truth validation**: `gpt-5.6-luna`'s self-cognition is already quite accurate, but it still makes mistakes on traps like R009 —
   in this run, the `expected_*` self-reported values had a **20% (1/5)** inconsistency with ground truth (fluctuating between 0%~20% across different runs); if the model's self-report/self-judgment were trusted as in the control group,
   this cognitive error would directly become a violation (R009 over-refund). To deterministically reproduce the "guard interception" in a keyless environment, run `python demo.py --selftest` (injects self-reported values opposite to ground truth for each case, demonstrating that all are intercepted).

## File Descriptions

- `airline_env.py`: Simulated database, codified refund policy `is_refundable`, tool implementations for both groups (naive / codified validation).
- `tasks.py`: 8 evaluation tasks and their policy ground truths.- `agent.py`: OpenAI tool-call loop, system prompts and tool schemas for both arms ( `run_agent` supports a `model` parameter, allowing the LLM baseline arm to reuse the control group logic).
- `demo.py`: Assembles comparison arms, runs evaluations, scores by rule-based criteria, prints an N-arm metric comparison table + inconsistency ratio + intercepted examples; includes CLI ( `--mode/--task/--small-model/--big-model/--output/--selftest` ) and offline self-test.
- `requirements.txt` / `env.example`.

## Notes

- Only `OPENAI_API_KEY` is required (default small model is `gpt-5.6-luna`, can be overridden with `MODEL` / `--small-model`; the LLM baseline uses `BIG_MODEL` / `--big-model`). Cost is very low (8 cases per arm, about a few dozen calls).
- To understand the code guard without an API key, simply run `python demo.py --selftest`.
- Reasoning models ( `gpt-5.6-luna` and other gpt-5/o series) do not accept `temperature=0`; the code will automatically use `temperature=1` instead. As a result, secondary metrics (number of invalid tool calls, `expected_*` inconsistency ratio) may fluctuate slightly, and occasional path differences for individual cases are normal. However, the conclusion that "the experimental group ≥ the control group, and the experimental group has 8/8 zero violations" remains stable.
- The server clock is fixed at `2026-07-17 12:00` ( `airline_env.SERVER_NOW` ), and all time judgments are based on it.
