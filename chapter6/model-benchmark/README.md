# Multi-Dimensional Model Performance Benchmark (Code for Experiment 6-8)

A horizontal benchmark for multiple OpenAI-compatible LLM API providers. Run a single command to produce a multi-dimensional comparison table of
**TTFT / End-to-End Latency / Throughput / Std Dev / p50 / p95 / p99 / Success Rate**,
providing empirical data for model selection. Also supports **concurrency stress testing** (stepwise pressure increase to find rate limits, observing how metrics change with concurrency)
and **offline self-check** (`--mock` synthetic data, no key/network required to verify metric aggregation).

Corresponds to Chapter 6, **Experiment 6-8: Multi-Dimensional Model Performance Benchmark** in *Understanding AI Agents*.

## Purpose

The full version of Experiment 6-8 in the book requires "probing every hour for a week, 8K/32K/128K context, 100+ requests, MTTR/rate-limit thresholds/comprehensive cost", etc. This companion code focuses on the **most core, low-cost, locally reproducible** part: using **streaming interfaces** to precisely measure time-to-first-token,
measuring latency percentiles and throughput under **concurrency**, and characterizing availability with **success rate** —
allowing readers to obtain a real multi-provider comparison table in minutes for pennies,
and understand that "model selection is a multi-dimensional trade-off, not just looking at a leaderboard."

## Metric Definitions

| Metric | Meaning | How It's Measured |
| --- | --- | --- |
| Success Rate (Availability) | Successful requests / Total requests | Any exception (timeout/rate-limit/network error/empty response) for a single request counts as failure, without aborting the entire table |
| TTFT | Time to first token | Streaming read, record the arrival time of the first "content" chunk − request send time |
| End-to-End Latency | Total time from request send to response end | Last chunk time − request send time |
| Throughput (tokens/s) | Output speed during generation phase | Output tokens / (End-to-End − TTFT), stripping out first-token wait, reflecting pure decoding speed |
| p50 / p95 / p99 | Median / 95th / 99th percentile of latency | Linear interpolation after sorting multiple successful requests for the same (provider, model); high p95/p99 indicates heavy tail and unstable experience |
| Std Dev (std) | Dispersion of latency | Sample standard deviation; the book emphasizes "high latency variance means unstable user experience" |
| Aggregate Throughput / RPS | Total throughput of the batch | During concurrency stress testing: total output tokens of all successful requests / total wall-clock time of the batch (RPS = successful requests / wall-clock time); as concurrency increases, it first rises then plateaus, hitting the server-side limit at the plateau point |

> Output token count preferentially uses the server-returned precise `usage.completion_tokens`;
> if the service does not return usage, it is approximated by counting streaming chunks (slightly overestimated, noted in code comments).

## Running

```bash
cd chapter6/model-benchmark
pip install -r requirements.txt

# Configure keys: only fill in the ones you have; providers without keys are automatically skipped
cp env.example .env        # Then edit .env
# Or directly export OPENAI_API_KEY=... MOONSHOT_API_KEY=... ARK_API_KEY=...

python demo.py             # Run a single command to produce the comparison table
```

Common parameters:

```bash
python demo.py --list                          # Only list providers to be tested
python demo.py --num-requests 20 --concurrency 5   # Increase sample size and concurrency
python demo.py --serial                        # Send serially (concurrency=1, measure baseline latency without contention)
python demo.py --max-tokens 256                # Generate longer responses for more thorough throughput measurement
```

Default parameters (`N=10/provider, concurrency=3, max_tokens=64`) cost about a few cents for a full run.
To approach the book's statistical requirement of "≥100 requests per configuration", set `--num-requests` to 100
(note that cost and rate limits will increase accordingly).

### Specify Any OpenAI-Compatible Endpoint (Test New Models/Providers Without Changing Code)

The book requires "testing the same model against different API providers (e.g., DeepSeek official vs SiliconFlow)".
Use `--base-url / --model / --api-key-env` to directly specify a single endpoint without modifying `DEFAULT_PROVIDERS`:

```bash
python demo.py --base-url https://api.deepseek.com --model deepseek-chat \
               --api-key-env DEEPSEEK_API_KEY --name "DeepSeek Official/deepseek-chat"
# Change base_url, keep the same model, to compare "same model, different providers"
```

### Concurrency Stress Testing: Stepwise Pressure Increase to Find Rate Limits

Experiment 6-8 in the book requires "finding rate limits by gradually increasing concurrency, recording RPM/TPM limits."
`--concurrency-sweep` applies stepwise pressure to the same model, producing a table of metrics as concurrency changes
(p50/p95/p99/std/success rate/RPS/aggregate throughput):

```bash
python demo.py --model gpt-5.6-luna --concurrency-sweep 1,2,4,8,16 --num-requests 100
```

As concurrency increases, single-request latency tail (p95/p99/std) typically worsens, availability may decrease due to rate limiting,
while **aggregate throughput (tokens/s) and RPS first rise then plateau** — the plateau point is the server's actual throughput limit.

### Select Metrics to Display / Export Results

```bash
python demo.py --metrics ttft,throughput      # Main table shows only TTFT and throughput (success rate always shown)
python demo.py --output result.json           # Write full results (including p50/p95/p99/std) to JSON
```

### Offline Self-Check (`--mock`, No Key/Network Required)

Run the entire metric aggregation pipeline with **synthetic data**, convenient for verifying p50/p95/p99/std/availability/aggregate throughput calculations without an API key or network. **All output numbers are pseudo-random synthetic, marked with `[SYNTHETIC]`, not real benchmarks. Never use for model selection.**

```bash
python demo.py --mock                                   # Synthetic horizontal comparison table
python demo.py --mock --concurrency-sweep 1,2,4,8,16     # Synthetic concurrency stress test table
```

Output of a single synthetic concurrency stress test (`--mock --concurrency-sweep 1,2,4,8,16 --num-requests 100`,
**numbers are synthetic, for trend demonstration only**):

```
Concurrency | Success Rate      | TTFT_p50 | TTFT_p95 | End-to-End p50 | End-to-End p95 | End-to-End p99 | End-to-End std | RPS  | Aggregate Throughput
-----+----------------+----------+----------+-----------+-----------+-----------+-----------+------+----------
1    | 99/100 (99%)   | 301ms    | 514ms    | 0.73s     | 1.04s     | 1.16s     | 0.13s     | 1.3  | 49.8 t/s
2    | 100/100 (100%) | 335ms    | 570ms    | 0.79s     | 1.07s     | 1.19s     | 0.15s     | 2.5  | 94.4 t/s
4    | 98/100 (98%)   | 381ms    | 617ms    | 0.83s     | 1.11s     | 1.19s     | 0.16s     | 4.7  | 180.0 t/s
8    | 92/100 (92%)   | 523ms    | 932ms    | 0.96s     | 1.53s     | 1.67s     | 0.25s     | 8.0  | 305.3 t/s
16   | 97/100 (97%)   | 878ms    | 1487ms   | 1.30s     | 1.97s     | 2.37s     | 0.35s     | 11.9 | 441.0 t/s
```

As concurrency increases: End-to-End p95/p99 and std rise (worse tail), aggregate throughput continues to grow (not yet plateaued).
On a real endpoint, this curve will plateau at some concurrency level accompanied by a drop in availability — that is the rate limit point.

## Default Tested Providers

`DEFAULT_PROVIDERS` in the code only runs providers with **valid keys** (OpenAI one key tests multiple models):

| Display Name | Model | base_url | Key Environment Variable |
| --- | --- | --- | --- |
| OpenAI/gpt-5.6-luna | gpt-5.6-luna | (Official default, can fallback to OpenRouter) | OPENAI_API_KEY |
| Moonshot/moonshot-v1-8k | moonshot-v1-8k | https://api.moonshot.cn/v1 | MOONSHOT_API_KEY |
| Doubao/doubao-1.5-pro-32k | doubao-1-5-pro-32k-250115 | https://ark.cn-beijing.volces.com/api/v3 | ARK_API_KEY |

> **OpenRouter Fallback**: The `OpenAI/*` entries (native OpenAI entries with empty base_url) will automatically fall back to **OpenRouter** (`OPENROUTER_API_KEY`, model name mapped to `openai/*`) when `OPENAI_API_KEY` is not set. Direct connection to `gpt-5.x` via OpenAI requires organizational real-name authentication, so as long as `OPENROUTER_API_KEY` is set, OpenRouter is preferred. Entries with dedicated `base_url` (Kimi/Doubao) do not participate in the fallback.

**The provider list is configurable**: Append `ProviderConfig(...)` to `DEFAULT_PROVIDERS` in `benchmark.py` to extend. All providers use the same OpenAI-compatible protocol, differing only in `base_url` and `model` — this is precisely why "same model, different providers" (e.g., DeepSeek official vs SiliconFlow as mentioned in the book) can be compared.

## Real Run Results (Example)

Below is the output of a real run (`python demo.py --num-requests 10 --concurrency 3`,
test machine on mainland China network, `2026-07`). **Numbers are real measurements, not fabricated**;
results may vary with different networks/time periods. Please rely on your own runs.

```
Provider/Model            | Success Rate  | TTFT Avg | TTFT_p95 | End-to-End Avg | End-to-End p95 | Throughput | Output Tok
--------------------------+--------------+----------+----------+------------+-----------+-----------+--------
OpenAI/gpt-5.6-luna       | 10/10 (100%) | 1360ms   | 2334ms   | 1.73s      | 2.54s     | 174.9 t/s | 26
Moonshot/moonshot-v1-8k   | 10/10 (100%) | 530ms    | 671ms    | 0.89s      | 1.07s     | 92.1 t/s  | 32
Doubao/doubao-1.5-pro-32k | 10/10 (100%) | 1097ms   | 1409ms   | 2.32s      | 2.91s     | 36.2 t/s  | 44
```

## Conclusions (Based on the Run Above)

- **Availability**: All three providers achieved 10/10 (100%) success this time. Availability differences often only emerge with larger samples, higher concurrency, or longer time windows — precisely why the book emphasizes "probing every hour for a week." The code is designed so that a single point of failure is "recorded as a drop in availability, without aborting the entire table," facilitating long-term sampling.
- **Time to First Token (TTFT)**: On this test machine within mainland China's network, Kimi's TTFT (~530ms) was significantly lower than cross-border access to OpenAI/gpt-5.6-luna (~1.36s); Doubao's TTFT (~1.1s) was slightly lower than OpenAI but had longer end-to-end latency. **TTFT is highly dependent on network location** — running the same code in a US data center would drastically reduce OpenAI's TTFT.
- **Throughput**: This run: gpt-5.6-luna (175 t/s) > Kimi (92 t/s) > Doubao (36 t/s). Throughput determines wait time for long responses and is an independent dimension from TTFT.
- **Stability (p95)**: Look at the gap between p95 and the average. For gpt-5.6-luna accessed cross-border, TTFT p95 (2.33s) / average (1.36s)The spread is larger, and the long tail is heavier; Kimi's p95 is closest to the mean, making it the most stable this time.
- **Selection Insights**: No single provider is "universally optimal"—latency, throughput, availability, and price involve **multi-dimensional trade-offs**.
  For real-time interactive scenarios targeting domestic users, localized services with low TTFT offer a better experience;
  batch processing/long-text generation places more emphasis on throughput and unit price. **Be sure to test in your own deployment network environment**,
  and do not directly copy numbers from third-party monitoring platforms (e.g., Artificial Analysis).

## File Description

| File | Description |
| --- | --- |
| `benchmark.py` | Core: provider configuration, single streaming measurement, concurrency scheduling, metric aggregation (including p99/std/aggregate throughput), concurrency sweep `sweep_concurrency`, synthetic data `synthetic_summary` |
| `demo.py` | Command-line entry: parse arguments, run tests (including concurrency stress test / `--mock` offline self-check), print comparison table, export JSON |
| `requirements.txt` | Dependencies (openai SDK + optional python-dotenv) |
| `env.example` | Key configuration template |

## Notes

- **Cost Control**: Default `max_tokens=64`, `N=10`, the full run cost is very low. Be mindful of billing before increasing parameters.
- **Rate Limiting**: Setting concurrency or N very high may trigger provider RPM/TPM rate limits, which will then be recorded as failures
  contributing to decreased availability—this itself is a way to "measure rate limit thresholds in practice" (part of Experiment 6-8 in the book).
- **TTFT is Highly Network-Dependent**: Services accessed across borders will have significantly higher TTFT; conclusions must be interpreted in the context of the deployment location.
- **OpenRouter Fallback**: When `OPENAI_API_KEY` is not set, `OpenAI/*` entries are automatically routed through OpenRouter
  (requires `OPENROUTER_API_KEY`, `gpt-*` mapped to `openai/*`); `gpt-5.x` will prioritize OpenRouter as long as `OPENROUTER_API_KEY` is set
  (direct connection requires real-name authentication). For other providers (DEEPSEEK / SILICONFLOW, etc.), if you wish to enable them,
  add the configuration in `DEFAULT_PROVIDERS` and set the corresponding environment variables.
