#!/usr/bin/env python3
"""
Local LLM Service Performance Benchmark (Supporting Experiment 2-1)

This script measures three core metrics at the serving level for locally deployed small models
via an OpenAI-compatible interface (vLLM or Ollama), helping readers build intuition about
throughput, latency, batching, and KV Cache:

  1. throughput —— single-stream decoding throughput (tokens/s) and time to first token (TTFT)
  2. kv-cache  —— TTFT comparison between prefix cache hit vs. miss
                (corresponding to Experiment 2-1, point 5: when the system prompt is unchanged,
                 cache hit is faster; modifying the first few characters of the system prompt
                 invalidates the cache, requiring recomputation of the entire prefix)
  3. batching  —— aggregate throughput under different concurrency levels, visually demonstrating
                 the throughput improvement brought by batching

All numbers come from actual measurements on a real server; the script itself does not generate
any synthetic data.
If the server has not been started yet, use --dry-run to view the request configuration for each scenario offline.

Examples:
    # Start the server first (choose one)
    python server.py                    # vLLM (requires NVIDIA GPU)
    ollama serve && ollama pull qwen3:0.6b   # Ollama (Mac / no GPU)

    # Run all scenarios and save results
    python benchmark.py --scenario all --output results.json

    # View only KV Cache hit/miss TTFT comparison
    python benchmark.py --scenario kv-cache --backend ollama

    # Batch throughput scan
    python benchmark.py --scenario batching --concurrency 1,2,4,8
"""

import argparse
import json
import logging
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("benchmark")

#Default OpenAI-compatible addresses for each backend
BACKEND_DEFAULTS = {
    "vllm": {"base_url": "http://localhost:8000/v1", "model": "Qwen3-0.6B"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen3:0.6b"},
}

#A deterministic padding text used to lengthen the shared prefix, making the KV Cache effect more obvious
_FILLER_SENTENCE = (
    "You are a meticulous assistant that follows the operating manual precisely. "
)


def build_padded_system_prompt(target_tokens: int) -> str:
    """Construct a system prompt containing approximately target_tokens tokens (filled with repeated sentences).

    Uses a rough estimate of "4 characters ≈ 1 token" to control length; only need to ensure the prefix is long enough
    and reproducible, not an exact token count.
    """
    header = (
        "# Operating Manual\n"
        "You are a helpful local assistant deployed for the AI Agent book experiment.\n\n"
    )
    approx_chars = max(0, target_tokens * 4 - len(header))
    repeats = approx_chars // len(_FILLER_SENTENCE) + 1
    body = _FILLER_SENTENCE * repeats
    return header + body


def make_client(base_url: str, api_key: str):
    """Create an OpenAI-compatible client."""
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("Missing dependency openai, please run: pip install openai")
        sys.exit(1)
    return OpenAI(base_url=base_url, api_key=api_key)


def stream_once(
    client,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> Dict[str, float]:
    """Initiate a streaming request and return TTFT, total duration, output token count, and decoding throughput.

    - ttft: time from request start to first content chunk (seconds)
    - total: wall-clock time of the entire response (seconds)
    - output_tokens: preferably use usage.completion_tokens from the server,
      otherwise approximate by the number of content chunks received
    - decode_tps: decoding throughput = output tokens / (total time - TTFT)
    """
    start = time.perf_counter()
    ttft: Optional[float] = None
    chunk_count = 0
    usage_tokens: Optional[int] = None

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=True,
        stream_options={"include_usage": True},
    )

    for chunk in stream:
        #The last chunk may carry usage without choices
        if getattr(chunk, "usage", None) is not None:
            try:
                usage_tokens = chunk.usage.completion_tokens
            except AttributeError:
                pass
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if getattr(delta, "content", None):
            if ttft is None:
                ttft = time.perf_counter() - start
            chunk_count += 1

    total = time.perf_counter() - start
    if ttft is None:
        ttft = total
    output_tokens = usage_tokens if usage_tokens is not None else chunk_count
    decode_time = max(total - ttft, 1e-6)
    decode_tps = output_tokens / decode_time if output_tokens else 0.0

    return {
        "ttft": ttft,
        "total": total,
        "output_tokens": float(output_tokens),
        "decode_tps": decode_tps,
    }


# --------------------------------------------------------------------------- #
#Scenario implementations
# --------------------------------------------------------------------------- #
def scenario_throughput(client, model, args) -> Dict[str, Any]:
    """Single-stream throughput + TTFT: continuously send several decoding-intensive requests and aggregate statistics."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": "Write a detailed explanation of how KV Cache works in transformer inference.",
        },
    ]
    runs = []
    for i in range(args.repeats):
        r = stream_once(client, model, messages, args.max_tokens, args.temperature)
        runs.append(r)
        logger.info(
            "throughput %d/%d: TTFT=%.3fs, decode=%.1f tok/s, output=%d tok",
            i + 1, args.repeats, r["ttft"], r["decode_tps"], int(r["output_tokens"]),
        )
    return {
        "scenario": "throughput",
        "repeats": args.repeats,
        "ttft_mean_s": statistics.fmean(x["ttft"] for x in runs),
        "decode_tps_mean": statistics.fmean(x["decode_tps"] for x in runs),
        "output_tokens_mean": statistics.fmean(x["output_tokens"] for x in runs),
        "runs": runs,
    }


def scenario_kv_cache(client, model, args) -> Dict[str, Any]:
    """KV Cache hit vs. miss TTFT comparison (Experiment 2-1, point 5).

    - Hit group: system prompt unchanged byte-by-byte, same request sent repeatedly; server prefix cache hits,
      prefill can be mostly skipped → TTFT significantly lower.
    - Miss group: each time a different counter string is inserted at the beginning of the system prompt; prefix is altered,
      cache completely invalidated; server must recompute the entire prefix → TTFT significantly higher.
    The prompt lengths of the two groups are roughly the same, so the difference mainly comes from whether the prefix cache hits.
    """
    base_prompt = build_padded_system_prompt(args.prefix_tokens)
    user_msg = {"role": "user", "content": "In one short sentence, say hello."}

    #Warm-up: send one request to write the cache (this one is always cold start, not counted)
    warm_msgs = [{"role": "system", "content": base_prompt}, user_msg]
    stream_once(client, model, warm_msgs, args.max_tokens, args.temperature)

    hit_ttfts, miss_ttfts = [], []
    for i in range(args.repeats):
        #Hit: exactly the same prefix
        hit = stream_once(client, model, warm_msgs, args.max_tokens, args.temperature)
        hit_ttfts.append(hit["ttft"])

        #Miss: insert a unique prefix at the beginning to invalidate the cache
        mutated = f"[req-{i}-{time.time_ns()}] " + base_prompt
        miss_msgs = [{"role": "system", "content": mutated}, user_msg]
        miss = stream_once(client, model, miss_msgs, args.max_tokens, args.temperature)
        miss_ttfts.append(miss["ttft"])

        logger.info(
            "kv-cache %d/%d: hit TTFT=%.3fs, miss TTFT=%.3fs",
            i + 1, args.repeats, hit["ttft"], miss["ttft"],
        )

    hit_mean = statistics.fmean(hit_ttfts)
    miss_mean = statistics.fmean(miss_ttfts)
    return {
        "scenario": "kv-cache",
        "prefix_tokens_approx": args.prefix_tokens,
        "repeats": args.repeats,
        "ttft_hit_mean_s": hit_mean,
        "ttft_miss_mean_s": miss_mean,
        "speedup": (miss_mean / hit_mean) if hit_mean > 0 else None,
        "ttft_hit_s": hit_ttfts,
        "ttft_miss_s": miss_ttfts,
    }


def scenario_batching(client, model, args) -> Dict[str, Any]:
    """Batching: send concurrent requests at different concurrency levels and measure aggregate throughput.

    Continuous batching is a core optimization for local serving: higher concurrency leads to better GPU utilization,
    and system aggregate throughput (total tok/s across all requests) typically increases significantly,
    though individual request latency may increase. This scenario directly quantifies this trade-off.
    """
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain what a large language model is."},
    ]

    levels = args.concurrency
    rows = []
    for level in levels:
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=level) as pool:
            futures = [
                pool.submit(
                    stream_once, client, model, messages, args.max_tokens, args.temperature
                )
                for _ in range(level)
            ]
            results = [f.result() for f in futures]
        wall = time.perf_counter() - start
        total_tokens = sum(r["output_tokens"] for r in results)
        agg_tps = total_tokens / wall if wall > 0 else 0.0
        per_req_tps = agg_tps / level if level else 0.0
        rows.append(
            {
                "concurrency": level,
                "wall_s": wall,
                "total_output_tokens": total_tokens,
                "aggregate_tps": agg_tps,
                "per_request_tps": per_req_tps,
                "ttft_mean_s": statistics.fmean(r["ttft"] for r in results),
            }
        )
        logger.info(
            "batching concurrency=%d: aggregate throughput=%.1f tok/s, per request=%.1f tok/s, wall time=%.2fs",
            level, agg_tps, per_req_tps, wall,
        )
    return {"scenario": "batching", "levels": rows}


# --------------------------------------------------------------------------- #
#Results table
# --------------------------------------------------------------------------- #
def print_report(results: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 68)
    print("Local LLM Service Benchmark Results")
    print("=" * 68)
    for res in results:
        s = res["scenario"]
        if s == "throughput":
            print("\n[throughput] Single-stream throughput / first token latency")
            print(f"  Count           : {res['repeats']}")
            print(f"  Avg TTFT        : {res['ttft_mean_s']:.3f} s")
            print(f"  Avg decode TPS  : {res['decode_tps_mean']:.1f} tok/s")
            print(f"  Avg output len  : {res['output_tokens_mean']:.0f} tok")
        elif s == "kv-cache":
            print("\n[kv-cache] Prefix cache hit vs miss (TTFT)")
            print(f"  Prefix length(approx): {res['prefix_tokens_approx']} tok")
            print(f"  Avg hit TTFT    : {res['ttft_hit_mean_s']:.3f} s")
            print(f"  Avg miss TTFT   : {res['ttft_miss_mean_s']:.3f} s")
            if res.get("speedup"):
                print(f"  Cache speedup   : {res['speedup']:.2f}x")
        elif s == "batching":
            print("\n[batching] Impact of concurrency on aggregate throughput")
            print(f"  {'Concurrency':>4} | {'Aggregate tok/s':>10} | {'Per-request tok/s':>12} | {'Average TTFT(s)':>11} | {'Wall clock(s)':>8}")
            print(f"  {'-'*4}-+-{'-'*10}-+-{'-'*12}-+-{'-'*11}-+-{'-'*8}")
            for row in res["levels"]:
                print(
                    f"  {row['concurrency']:>4} | {row['aggregate_tps']:>10.1f} | "
                    f"{row['per_request_tps']:>12.1f} | {row['ttft_mean_s']:>11.3f} | {row['wall_s']:>8.2f}"
                )
    print("\n" + "=" * 68)


def describe_dry_run(args) -> None:
    """Print the scenario configuration to be executed offline without accessing the server."""
    print("=" * 68)
    print("DRY RUN — only print the plan, do not access the server")
    print("=" * 68)
    print(f"Backend         : {args.backend}")
    print(f"base_url     : {args.base_url}")
    print(f"Model          : {args.model}")
    print(f"Repetitions    : {args.repeats}")
    print(f"max_tokens   : {args.max_tokens}")
    print(f"temperature  : {args.temperature}")
    scenarios = ["throughput", "kv-cache", "batching"] if args.scenario == "all" else [args.scenario]
    print(f"Scenarios to run: {', '.join(scenarios)}")
    if "kv-cache" in scenarios:
        prompt = build_padded_system_prompt(args.prefix_tokens)
        print(f"  kv-cache   : prefix fill about {args.prefix_tokens} tok (actual {len(prompt)} characters)")
    if "batching" in scenarios:
        print(f"  batching   : concurrency scan {args.concurrency}")
    print("=" * 68)


def parse_concurrency(value: str) -> List[int]:
    try:
        levels = [int(x) for x in value.split(",") if x.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError("--concurrency must be a comma-separated list of positive integers, e.g., 1,2,4,8")
    if not levels or any(x <= 0 for x in levels):
        raise argparse.ArgumentTypeError("Concurrency values in --concurrency must be positive integers")
    return levels


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local LLM Service Performance Benchmark: Throughput / Latency / KV Cache / Batching (for Experiment 2-1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Scenario description:\n"
            "  throughput  Single-stream decoding throughput (tok/s) and first token latency (TTFT)\n"
            "  kv-cache    TTFT comparison between prefix cache hit vs miss\n"
            "  batching    Aggregate throughput under different concurrency levels (batching trade-off)\n"
            "  all         Run all the above scenarios sequentially\n"
        ),
    )
    parser.add_argument(
        "--scenario",
        choices=["throughput", "kv-cache", "batching", "all"],
        default="all",
        help="Benchmark scenarios to run (default: all)",
    )
    parser.add_argument(
        "--backend",
        choices=["vllm", "ollama"],
        default="vllm",
        help="Server type, used to infer default address and model name (default: vllm)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="OpenAI-compatible API endpoint, overrides backend default (e.g., http://localhost:8000/v1)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name, overrides backend default (vLLM default Qwen3-0.6B, Ollama default qwen3:0.6b)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="EMPTY",
        help="API Key, local server generally does not require a real value (default: EMPTY)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="Number of repetitions for throughput / kv-cache scenarios (default: 5)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256,
        help="Maximum number of generated tokens per request (default: 256)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Sampling temperature (default: 0.7)",
    )
    parser.add_argument(
        "--prefix-tokens",
        type=int,
        default=1024,
        help="Approximate token length of shared prefix in kv-cache scenario; longer prefix yields more obvious caching effect (default: 1024)",
    )
    parser.add_argument(
        "--concurrency",
        type=parse_concurrency,
        default=[1, 2, 4, 8],
        help="Concurrency list for batching scenario, comma-separated (default: 1,2,4,8)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write results as JSON to the specified file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan offline without accessing the server, used to verify configuration",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    #  Fill base_url / model with backend defaults
    defaults = BACKEND_DEFAULTS[args.backend]
    if args.base_url is None:
        args.base_url = defaults["base_url"]
    if args.model is None:
        args.model = defaults["model"]

    print("=" * 68)
    print("🚀 Local LLM Service Performance Benchmark (Experiment 2-1)")
    print("=" * 68)

    if args.dry_run:
        describe_dry_run(args)
        return 0

    client = make_client(args.base_url, args.api_key)
    logger.info("Connecting to server: %s (model: %s)", args.base_url, args.model)

    scenarios = (
        ["throughput", "kv-cache", "batching"]
        if args.scenario == "all"
        else [args.scenario]
    )
    dispatch = {
        "throughput": scenario_throughput,
        "kv-cache": scenario_kv_cache,
        "batching": scenario_batching,
    }

    results: List[Dict[str, Any]] = []
    try:
        for name in scenarios:
            logger.info("Starting scenario: %s", name)
            results.append(dispatch[name](client, args.model, args))
    except Exception as e:  # noqa: BLE001
        logger.error("Benchmark execution failed: %s", e)
        logger.info(
            "Please ensure the server is running: for vLLM use `python server.py`,"
            "for Ollama use `ollama serve` and have `ollama pull %s`",
            args.model,
        )
        return 1

    print_report(results)

    if args.output:
        payload = {
            "backend": args.backend,
            "base_url": args.base_url,
            "model": args.model,
            "results": results,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("Results written to: %s", args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
