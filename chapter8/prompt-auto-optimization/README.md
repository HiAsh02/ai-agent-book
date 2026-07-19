# Experiment 8-3: Automatic Optimization of System Prompts (★★)

> Companion code for "Deep Understanding of AI Agents" · Chapter 8
>
> **Automated system prompt learning based on human feedback**: Have a Coding Agent read the system prompt file, identify problematic rules, generate precise modifications, and **actually rewrite the prompt file** to fix the Agent's "excessive transfer" behavior. The scenario is a tau-bench style airline customer service.

## 1. Purpose and Problem

In the initial airline customer service Agent, the manual transfer rules were written vaguely — "transfer only when the request cannot be handled within your scope of action," with emphasis on "customer satisfaction first; transfer to human agent when encountering dissatisfaction; do not argue policies with passengers."

Evaluation revealed that the Agent **over-transfers** — whenever encountering policy disputes (requesting refunds beyond policy, demanding free services, requesting fee waivers), it immediately transfers to a human agent instead of attempting to explain the policy to passengers.

Human expert feedback: Such disputes should be **handled by patiently explaining the policy**, rather than simply transferring. The only two situations that truly require human transfer are: **passenger explicitly requests human agent** and **emergency safety/health risk**.

This experiment demonstrates an automated closed loop: **Human feedback → Coding Agent rewrites system prompt → Re-evaluation and verification**.

## 2. Method and Flow

```
Initial prompt ──Evaluation──► Exposes "excessive transfer" problem
                                  │
               Human feedback ───┤
                                  ▼
                   Coding Agent (reads file → locates rules → generates precise search/replace edits → rewrites file)
                                  │  Displays actual diff
                                  ▼
             Automatically optimized prompt ──Evaluation──► Boundary set accuracy ↑ and holdout set does not degrade
                                  │
               Control: manually tuned prompt ──Evaluation──►
```

Two groups of evaluation cases (5 each, cost-controlled with reproducible conclusions):

- **Holdout task set**: Normal requests. 3 should be handled by the Agent itself (rebooking / baggage allowance / seat selection), 2 should be transferred (passenger explicitly requests human / emergency safety). Used to verify that optimization **does not break existing correct behavior**.
- **Boundary case set**: 5 policy disputes (non-refundable ticket refund request / request to waive change fee / small delay compensation claim / request for free upgrade / excess free baggage). Correct behavior is **explain policy, do not transfer**. Used to verify that excessive transfer is fixed.

Criteria (`evaluate.py`): Combination of deterministic rules + LLM-as-judge —
- Cases that should transfer: correct ⇔ `transfer_to_human` was actually called;
- Cases that should not transfer: correct ⇔ no transfer, and LLM judge confirms it properly explained the policy / handled the business according to the rubric.

The Coding Agent (`coding_agent.py`) does not rewrite the entire document, but produces a set of precise `(old_str → new_str)` edits like a real programming Agent, which are applied one by one via exact string replacement; if a match fails, the error is fed back to the model for retry, ensuring modifications are auditable and can produce a diff.

## 3. File Structure

| File | Description |
| --- | --- |
| `demo.py` | Single command to run the complete flow (evaluation → rewrite → re-evaluation → comparison → comparison table) |
| `airline_env.py` | Simplified airline customer service simulation environment: tools (including `transfer_to_human`), Agent loop, 10 test cases |
| `coding_agent.py` | Coding Agent: reads and **rewrites** the system prompt file, outputs diff |
| `evaluate.py` | Evaluator: rules + LLM-as-judge to determine if each case was handled correctly |
| `config.py` | LLM client configuration (default OpenAI `gpt-5.6-luna`, switchable to Moonshot / Volcengine Ark; falls back to OpenRouter when key is missing) |
| `prompts/system_prompt.txt` | Initial system prompt (contains rules that induce excessive transfer) |
| `prompts/system_prompt_manual.txt` | Control group: manually tuned system prompt |
| `runtime/system_prompt_working.txt` | Runtime working copy rewritten by the Coding Agent (reset on each run) |

## 4. Running

```bash
pip install -r requirements.txt
cp env.example .env      # Fill in OPENAI_API_KEY (or just set OPENROUTER_API_KEY for fallback)
python demo.py           # Full run: 10 cases × 3 prompts
python demo.py --quick   # Quick demo: only 2 cases per group, saves time and cost (recommended to run this first)
python demo.py --help    # View all command-line arguments (Chinese descriptions)
python demo.py --dry-run # Offline self-check: only print configuration and selected cases, no API calls
```

Command-line arguments (full Chinese descriptions visible with `python demo.py --help`):

| Argument | Effect | Default |
| --- | --- | --- |
| `--quick` | Only 2 cases per group, saves time and cost | Off |
| `--limit N` | Maximum N cases per group to evaluate (overrides `--quick`) | Unlimited |
| `--group {holdout,boundary,both}` | Select task set for evaluation | `both` |
| `--rounds N` | Maximum retry rounds for Coding Agent's automatic prompt rewriting | `3` |
| `--model NAME` | Override LLM model name (equivalent to `LLM_MODEL`) | See `config.py` |
| `--provider {openai,moonshot,ark}` | Override LLM provider (equivalent to `LLM_PROVIDER`) | `openai` |
| `--output PATH` | Write comparison results (before/after optimization + manual control) as JSON | Not written |
| `--dry-run` | Offline: only print parsed configuration and case count, no API calls | Off |

Default model `gpt-5.6-luna` (reads `OPENAI_API_KEY`; if missing but `OPENROUTER_API_KEY` is present, automatically switches to OpenRouter and maps to `openai/gpt-5.6-luna`), temperature 0 (reproducible results). Full run processes 10 cases × 3 prompts, approximately dozens of API calls, taking several minutes; `--quick` (or `--limit N` specifying cases per group) significantly reduces time for rapid closed-loop verification. Command-line arguments take precedence over environment variables: `--model` / `--provider` override `LLM_MODEL` / `LLM_PROVIDER` in `.env`. Adding `--output output/run.json` writes the comparison table as JSON (`output/` is already ignored by `.gitignore`), facilitating reproduction and secondary analysis. If the corresponding API Key is not set, the program prints a clear Chinese error message and exits, rather than throwing a stack trace.

The optimized working copy is written to `runtime/system_prompt_working.txt` (automatically reset on each run, a generated artifact ignored by `.gitignore`).

## 5. Real Run Results

The table below shows results from one real run (`gpt-5.6-luna`, full 10 cases):

```
Accuracy Comparison (Holdout set = existing correct behavior must not degrade; Boundary set = excessive transfer should improve)
==========================================================================
System Prompt Version               Holdout Set             Boundary Set
--------------------------------------------------------------------------
Initial prompt (before optimization)   5/5 (100%)            0/5 (0%)
Automatically optimized prompt         5/5 (100%)            1/5 (20%)
Manually tuned version (control)       5/5 (100%)            2/5 (40%)
==========================================================================

【Conclusion】
  · Boundary set accuracy: 0/5 → 1/5 (improvement ✓)
  · Holdout set accuracy: 5 → 5 (no degradation ✓)
```

- **Boundary set**: Before optimization, all 5 cases were "transferred away" (excessive transfer 5/5); after optimization, **transfers completely disappeared (boundary set transfer count 5 → 0)**, fixing the excessive transfer problem; accuracy increased from 0/5 to 1/5 — B5 (excess free baggage) was judged acceptable for proactively explaining weight-based pricing policy; B1/B2/B3/B4 no longer transferred, but the model tended to first ask passengers for order numbers without fully explaining the policy, which was judged as "improper handling" by the strict evaluator — a genuine boundary performance.
- **Holdout set**: 5/5 both before and after optimization, existing correct behavior (including H4/H5 "cases that should transfer still transfer") **did not degrade**.
- The automatically optimized result is close to the **manually tuned control group** (automatic boundary 1/5, manual 2/5, holdout both 5/5); the manual version explained one more case correctly on B2 (request to waive change fee), with the difference within the evaluator's ±1 case fluctuation range.

> Note: Specific numbers may fluctuate by ±1 case depending on model version and sampling, but the conclusion that "boundary set excessive transfer is fixed, holdout set does not degrade, and automatic optimization approaches manual tuning" is stable and reproducible. The table above is from one real run of `gpt-5.6-luna` (since this model only supports default temperature, this run used `LLM_TEMPERATURE=1`).

The Coding Agent's actual rewrite of `system_prompt.txt` (diff excerpt) is printed in [Step 2] of `python demo.py`, with the core change being tightening rules 3 and 4 for transfer to "only transfer when passenger explicitly requests human / emergency safety," and adding a negative rule "never transfer due to policy disputes or passenger dissatisfaction; first explain the policy then offer alternatives."

### Supplement: Model ↔ Scaffolding Trade-off (Two Real Runs with Strong vs Weak Models)

A natural question: **If the model is stronger, is this "automatic prompt rewriting" scaffolding less necessary?** To explore this, we ran the identical closed loop (10 cases × 3 prompts × max 3 rewrite rounds) on a weaker model `gpt-4o-mini` (OpenAI direct connection, `LLM_TEMPERATURE=0`) and compared it with the `gpt-5.6-luna` run above. The boundary set (excessive transfer should improve) **before optimization → after automatic optimization** changes:

| Model | Holdout Set | Boundary Set Before → After Auto Optimization | Auto Optimization Gain | Manually Tuned (Control) |
| --- | --- | --- | --- | --- |
| `gpt-4o-mini` (weaker) | 5/5 → 5/5 (no degradation) | **1/5 → 3/5** | **+2 cases** | 3/5 |
| `gpt-5.6-luna` (stronger) | 5/5 → 5/5 (no degradation) | **0/5 → 1/5** | **+1 case** | 2/5 |

- **Directionally**, the weaker `gpt-4o-mini` gained more from this automatic optimization scaffolding (boundary set +2 cases, 1/5→3/5), outperforming `gpt-5.6-luna`'s +1 (0/5→1/5); after optimization, `gpt-4o-mini` matched its manually tuned version (both 3/5). This aligns with the intuition that "weaker models rely more on scaffolding, while stronger models have higher tolerance for the same baseline prompt."
- **However, two honest caveats are needed to avoid over-interpretation**: (1) The gain difference between the two is only 1 case, falling within the ±1 case evaluator fluctuation band repeatedly stated in this experiment; (2) The sampling conditions differ between the two runs — the weaker model used `temperature=0` (deterministic), while the stronger model used `temperature=1` (with sampling noise) due to only supporting default temperature. Therefore, this is a **directional, non-conclusive** comparison: one can say "the weaker model benefits no less than the stronger model from the scaffolding," but it would be inappropriate to assert based on this 1-case difference that the stronger model "does not need" automatic optimization. The truly robust conclusion remains the one shared by both models — **boundary set excessive transfer is fixed, holdout set does not degrade, and automatic optimization approaches manual tuning**.

## 6. How to Adapt / Extend and Limitations

- **Change model / provider**: `LLM_PROVIDER` can switch between `openai` / `moonshot` / `ark` (all compatible with OpenAI interface), `LLM_MODEL` overrides the model name, `LLM_TEMPERATURE` adjusts sampling temperature (default 0, see `config.py` / `env.example`).
- **Change task / input**: The evaluation case set is in `airline_env.py`'s `CASES` (divided into `holdout` / `boundary` groups); the human feedback driving optimization is `HUMAN_FEEDBACK` at the top of `demo.py`; the initial and manual control prompts are under `prompts/` — modify these to apply the closed loop to your own scenario.- **Limitation**: The environment is a simplified simulation for educational purposes, with tools returning fixed mock data; the focus is on the closed loop of "human-feedback-driven automatic prompt optimization" rather than a full reproduction of tau-bench. The specific accuracy may vary by ±1 test case depending on the model version and sampling.
