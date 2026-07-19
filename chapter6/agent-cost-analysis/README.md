# Experiment 6-7: End-to-End Cost Analysis of Agent Tasks

Companion to Chapter 6 of *Deep Understanding of AI Agents* — "Experiment 6-7 ★: End-to-End Cost Analysis of Agent Tasks".

Perform a **full-chain cost breakdown** of a typical multi-turn Agent task (customer service refund). Use a **self-built lightweight tracing/observability system** to record input/output/cache tokens, latency, and cost for each LLM call. Aggregate by step to identify "which step is the most expensive", break down **cost composition** into "uncached input / cached input / output shares and how many tokens were injected by tool returns", and provide **per-step cost distribution (p50/p95/p99)**. Then run a complete **2×2 A/B comparison** to quantify the real cost differences from **KV-cache reuse** and **context compression**, both individually and combined.

- Default model: **`gpt-5.6-luna`** (current cheap flagship), called via the OpenAI Python SDK. Prefers `OPENAI_API_KEY`; if not set, **automatically falls back to `OPENROUTER_API_KEY`** (via OpenRouter compatible endpoint, `gpt-*` mapped to `openai/*`). Since `gpt-5.x` direct connection to OpenAI requires organizational real-name authentication, OpenRouter is preferred whenever `OPENROUTER_API_KEY` is present.
- KV-cache savings are **real**: leveraging OpenAI's automatic prompt caching (prefix ≥ 1024 tokens and hitting a recent identical prefix results in `usage.prompt_tokens_details.cached_tokens > 0`, these input tokens are billed at 50% of the cache price).
- Provides **offline mode**: no model calls; reads token usage from a previously recorded real run (`sample_trace.json`, canned token counts), and **recalculates** costs/cost composition/A/B comparison tables using configurable unit prices — no API key needed to reproduce all tables, and can be easily converted to other model pricing.

## Files

| File | Description |
|------|-------------|
| `config.py` | Model and pricing: `Pricing` unit price object + common OpenAI model price presets, token→cost conversion |
| `tracer.py` | Self-built lightweight tracing: wraps each LLM call to record tokens/cache/latency/cost; cost composition breakdown, per-step cost distribution, per-step breakdown table; supports offline recalculation from recorded usage (`from_records`) |
| `agent.py` | Multi-turn customer service refund Agent task; `run_scenario(kv_cache, compress)` orthogonally combines two switches into 2×2 scenarios, and uses tiktoken to estimate "tool return injected" tokens |
| `demo.py` | Command-line entry point (argparse): run real model online / recalculate offline; select A/B scenarios, model pricing, output file |
| `sample_trace.json` | Per-step token usage for four scenarios recorded from one real run (input for offline mode, costs recalculated at current unit prices) |
| `requirements.txt` / `env.example` | Dependencies and environment variable example |

## Running

```bash
pip install -r requirements.txt

# Online (real model calls, requires key): default runs A(naive)+B(optimized) two groups
export OPENAI_API_KEY=sk-...           # or export OPENROUTER_API_KEY=sk-or-... (auto fallback)
python demo.py

# Offline (no key needed): recalculate all tables using built-in canned trace
python demo.py --offline --scenario all
```

Online mode makes real OpenAI calls; `--scenario all` does about several dozen chat completions, taking one to two minutes.

### Command-line Arguments (`python demo.py --help`)

| Argument | Description |
|----------|-------------|
| `--live` / `--offline` | Online real calls (default) / offline recalculation from trace file (no key needed) |
| `--scenario NAME` | `ab`(default=naive+both) / `all`(2×2 four groups) / comma-separated subset `naive,kv,compress,both` |
| `--trace FILE` | Canned trace file for offline reading, default `sample_trace.json` |
| `--save-trace FILE` | When running online, save real token usage to disk for later `--offline` recalculation |
| `--model NAME` | Model name (determines default price preset: `gpt-4o-mini`/`gpt-4o`/`gpt-4.1-mini`/`gpt-4.1`) |
| `--price-input/-cached/-output` | Override three unit prices (USD per million tokens) |
| `--no-warmup` | Disable prefix warmup for KV-cache groups (default warms up to stabilize cache hits) |
| `--output FILE` | Write cost breakdown results (including cost composition/distribution/per-step usage) as JSON |

> **Running `python demo.py` with no argument changes behaves identically to before**: runs A(naive) and B(optimized) groups online and prints breakdown + A/B comparison table.

## A/B Four Strategies (Full 2×2)

The same 8-turn customer service refund task (query order → query logistics → check refund policy → query knowledge base → risk control → issue refund → send notification → close ticket). All four groups perform **the same logical work**, differing only in context construction — therefore cost differences come purely from the two orthogonal switches: "KV-cache friendly" and "context compression":

| Scenario | KV-cache | Compression | Context Construction |
|----------|:--:|:--:|------|
| `naive` A naive | ✗ | ✗ | Insert random session header before system each turn (breaks prefix) + keep all historical tool returns verbatim |
| `kv` cache only | ✓ | ✗ | Stable long prefix (system byte-identical each turn) + no compression on history |
| `compress` compression only | ✗ | ✓ | Unstable prefix + only last 2 turns keep full tool returns, earlier ones compressed into one-sentence summary |
| `both` B optimized | ✓ | ✓ | Stable long prefix + context compression (both levers combined) |

> To focus on the two "input-side" levers, all four groups use `temperature=0` and limit output length (`max_tokens=160`), making output token cost approximately equal across groups as a fixed term, avoiding random fluctuations in model generation length from interfering with comparison.
>
> The tool environment is "controlled" (tool return content is preset, in a real system it would come from order/logistics/knowledge base backends), but **every LLM call, every token usage, and every cent of cost is actually sent to OpenAI**, ensuring reproducibility.

## Real Run Output (gpt-4o-mini)

Below is the output from one real run (`python demo.py --scenario all`). `sample_trace.json` was saved from this run for `--offline` reproduction.

### (a) Single Task Cost Breakdown: By Step + By Cost Composition + Distribution

```
===== Cost Breakdown: A naive (no cache/no compression) (single task full-chain breakdown) =====
Step       Tool/Action                  Input tok    Cache tok    Tool tok    Output tok    Latency(s)        Cost($)
---------------------------------------------------------------------------------------
turn-1   query_order              1113        0      276      104     3.15     0.000229
turn-2   query_logistics          1807        0      829       99     2.09     0.000330
turn-3   check_refund_policy      2154        0     1046      139     2.69     0.000406
turn-4   query_knowledge_base     2564        0     1287      160     2.92     0.000481
turn-5   query_user_history       2863        0     1389      136     2.69     0.000511
turn-6   issue_refund             3123        0     1490      160     3.07     0.000564
turn-7   send_notification        3408        0     1579      160     3.09     0.000607
turn-8   close_ticket             3668        0     1648      160     2.50     0.000646
---------------------------------------------------------------------------------------
Total                               20700        0     9544     1118    22.20     0.003776

Most expensive step → turn-8 / close_ticket: $0.000646 (17.1% of total cost)
Cost composition:
  Uncached input     20700 tok  $0.003105  (82.2%)
  Cached input           0 tok  $0.000000  (0.0%)
  Output            1118 tok  $0.000671  (17.8%)
  Of which "tool return injection" cumulative input 9544 tok (same tool returns billed repeatedly in subsequent turns)
Per-step cost distribution(n=8): mean $0.000472  p50 $0.000481  p95 $0.000646  p99 $0.000646

===== Cost Breakdown: B optimized (KV cache+compression) (single task full-chain breakdown) =====
Step       Tool/Action                  Input tok    Cache tok    Tool tok    Output tok    Latency(s)        Cost($)
---------------------------------------------------------------------------------------
turn-1   query_order              1056     1024      276      139     2.41     0.000165
turn-2   query_logistics          1781        0      829      112     2.18     0.000334
turn-3   check_refund_policy      2143     1024     1046      151     2.56     0.000335
turn-4   query_knowledge_base     2310        0     1052      160     3.03     0.000442
turn-5   query_user_history       2060     1024      635      160     2.48     0.000328
turn-6   issue_refund             2143     1024      551      160     2.71     0.000341
turn-7   send_notification        2188     1024      430      160     2.79     0.000347
turn-8   close_ticket             2354     1024      429      122     2.38     0.000349
---------------------------------------------------------------------------------------
Total                               16035     6144     5248     1164    20.54     0.002643

Most expensive step → turn-4 / query_knowledge_base: $0.000442 (16.7% of total cost)
Cost composition:
  Uncached input      9891 tok  $0.001484  (56.1%)
  Cached input        6144 tok  $0.000461  (17.4%)
  Output            1164 tok  $0.000698  (26.4%)
  Of which "tool return injection" cumulative input 5248 tok (same tool returns billed repeatedly in subsequent turns)Per-step cost distribution (n=8): mean $0.000330  p50 $0.000335  p95 $0.000442  p99 $0.000442
```

As shown: Naive group A's input tokens increase from 1113 to 3668 across rounds (context accumulation effect, with the last step being the most expensive), and "tool return injection" cumulatively consumes 9544 input tokens. Optimized group B's input tokens are suppressed by the compression strategy (last round at 2354 instead of 3668, cumulative tool injection reduced to 5248), and most rounds consistently hit the 1024 cache token, with cached input cutting the overall cost by half.

### (b) Full 2×2 A/B Comparison

```
===== A/B Cost Comparison (Same 8-Round Customer Refund Task) =====
Scheme                           Total Input Tokens  Cached Tokens  Cache Rate  Output Tokens  Total Cost ($)  vs Baseline
------------------------------------------------------------------------------------------
A Naive (No Cache / No Compression)           20700              0      0.0%         1118        0.003776        Baseline
KV Only Cache (Stable Prefix / No Compression) 20386          13568     66.6%         1112        0.002707       -28.3%
Compression Only (Unstable Prefix / Summary)   16177              0      0.0%         1147        0.003115       -17.5%
B Optimized (KV Cache + Compression)          16035           6144     38.3%         1164        0.002643       -30.0%
------------------------------------------------------------------------------------------

Key comparison: A Naive (No Cache / No Compression) → B Optimized (KV Cache + Compression)
  Total tokens:   A=21818  →  B=17199   Reduction of 4619 (21.2%)
  Cached tokens:  A=0  →  B=6144   (B hits cache due to stable prefix)
  Total cost:     A=$0.003776  →  B=$0.002643   Reduction of $0.001133 (30.0%)
  Cost ratio:     A is 1.43 times B
```

Conclusion (reading the individual and combined contributions of the two levers):
- **KV-cache only**: Without changing context length, it relies solely on a stable prefix to bill repeated system prompts, tool definitions, and historical rounds at the cached price. The cache rate reaches 66.6%, reducing end-to-end cost by **28.3%**—in this example, it is the single most effective lever.
- **Compression only**: Compressing old-round tool returns into summaries reduces total input tokens from 20,700 to 16,177 (approx. −22%), lowering end-to-end cost by **17.5%**; however, because the prefix is unstable, the cache rate is 0.
- **Both combined (B Optimized)**: Achieves the fewest input tokens while still hitting the cache, resulting in an end-to-end cost reduction of **30.0%** (A is 1.43 times B). Looking solely at input-side costs, the reduction falls within the empirical range of "KV Cache can reduce input token costs by 30%-60%" mentioned in the book.

> Note that KV and compression do not simply add up: compression shortens the history, so the number of "historical rounds" that can be cached also decreases. Hence, B's cached tokens (6,144) are fewer than those of "KV only" (13,568). This is precisely the value of evaluation—when combining two optimizations, the synergistic effect must be measured empirically, rather than simply summing their individual benefits.

## Offline Recalculation (No API Key Required)

`sample_trace.json` stores the **per-step token usage (measured values)** from the real run above; offline mode performs only the pure offline math of "recalculating costs at unit prices," thus requiring no key to reproduce all tables. It can also convert to other model pricing with a single command:

```bash
python demo.py --offline --scenario all                 # Recalculate using gpt-4o-mini unit prices
python demo.py --offline --scenario all --model gpt-4o  # Same token usage, recalculate with gpt-4o unit prices
python demo.py --offline --price-input 0.20 --price-cached 0.10 --price-output 0.80
```

After switching to `gpt-4o` unit prices, the total costs for the four groups scale proportionally (conclusions and proportions remain unchanged, A=$0.062930 → B=$0.044047, still −30.0%)—this demonstrates that **the relative benefit of cost optimization is determined by token structure and is independent of absolute unit prices**.

## Notes

- Specific numbers will fluctuate slightly with each online run: OpenAI's prompt cache is **best-effort** (cached in blocks of approximately 128 tokens, expires in about 5–10 minutes, and occasionally misses), so some rounds may show `cached_tokens=0` (e.g., turn-2/turn-4 in group B above). Before formal measurement, `demo.py` runs a "warm-up" for the KV-cache group to write the stable prefix into the cache, making hits more consistent; `--no-warmup` can disable this.
- Prices are defined in `config.py` (`PRICING_PRESETS`), defaulting to gpt-4o-mini's public unit prices (input $0.15 / cached $0.075 / output $0.60 per million tokens). **To change models**: use `--model` (e.g., `--model gpt-4o`) or `--price-*` to directly override unit prices; cache hits require a stable prefix ≥ 1024 tokens, and switching to a more powerful model does not affect this mechanism.
- "Tool return injection" tokens are estimated offline using tiktoken with the current model's encoder (counting how many tokens the tool return text occupies in each round's input). This is used to answer the amplification factor mentioned in the book: "a single tool return can occupy 2000-5000 tokens and is repeatedly billed in every subsequent round."
- Credentials: `OPENAI_API_KEY` is preferred; if not set, it automatically falls back to `OPENROUTER_API_KEY` (via OpenRouter, with `gpt-*` mapped to `openai/*`). Direct connection to `gpt-5.x` requires organizational real-name authentication, so `OPENROUTER_API_KEY` is prioritized when available. Offline recalculation (`--offline`) requires no key.
