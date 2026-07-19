"""
demo.py — One command to generate multi-provider performance comparison table / concurrency stress test table.

Usage:
    python demo.py                      # Use default parameters, horizontal comparison across multiple providers
    python demo.py --num-requests 20 --concurrency 5
    python demo.py --serial             # Send serially (concurrency=1)
    python demo.py --list               # Only list providers to be tested

    # Specify any OpenAI-compatible endpoint (test new models/providers without modifying code):
    python demo.py --base-url https://api.deepseek.com --model deepseek-chat \
                   --api-key-env DEEPSEEK_API_KEY

    # Concurrency stress test: gradually increase concurrency for the same model to find rate limits and observe latency tail changes with concurrency:
    python demo.py --model gpt-5.6-luna --concurrency-sweep 1,2,4,8

    # Offline self-check (no key/network needed): use synthetic data to verify metric aggregation math
    python demo.py --mock
    python demo.py --mock --concurrency-sweep 1,2,4,8,16

By default, only providers with valid keys are tested (OpenAI / Kimi / Doubao).
Providers without corresponding environment variables set are automatically skipped.
"""

from __future__ import annotations

import argparse
import json
import os

#  If python-dotenv is installed and a .env file exists, it is automatically loaded (optional, not mandatory)
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001
    pass

from benchmark import (
    DEFAULT_PROVIDERS,
    ProviderConfig,
    ProviderSummary,
    run_benchmark,
    sweep_concurrency,
    synthetic_summary,
)


#  Short prompt: control cost while ensuring stable output for throughput measurement.
DEFAULT_PROMPT = "Explain in one sentence what a large language model is."

#  Optional metric families for the main comparison table (success rate always displayed). Use --metrics to select a subset with commas.
METRIC_KEYS = ["ttft", "e2e", "throughput", "tokens"]


def _fmt(v, unit: str = "", scale: float = 1.0, digits: int = 1) -> str:
    """Format possibly None numeric values into aligned strings."""
    if v is None:
        return "  N/A"
    return f"{v * scale:.{digits}f}{unit}"


def _render_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a table aligned by Chinese character width."""
    def width(text: str) -> int:
        return sum(2 if ord(c) > 127 else 1 for c in text)

    cols = len(headers)
    col_w = [width(headers[i]) for i in range(cols)]
    for row in rows:
        for i in range(cols):
            col_w[i] = max(col_w[i], width(row[i]))

    def pad(text: str, w: int) -> str:
        return text + " " * (w - width(text))

    sep = "-+-".join("-" * col_w[i] for i in range(cols))
    print()
    print(" | ".join(pad(headers[i], col_w[i]) for i in range(cols)))
    print(sep)
    for row in rows:
        print(" | ".join(pad(row[i], col_w[i]) for i in range(cols)))
    print()


def _print_errors(summaries: list[ProviderSummary]) -> None:
    """Print failure details for locating availability issues."""
    if not any(s.errors for s in summaries):
        return
    print("Failed request details (reasons for availability degradation):")
    for s in summaries:
        if s.errors:
            for e in s.errors[:3]:
                print(f"  - {s.provider}: {e}")
            if len(s.errors) > 3:
                print(f"    ... and another {len(s.errors) - 3} similar errors")
    print()


def print_table(summaries: list[ProviderSummary], metrics: list[str]) -> None:
    """Print horizontal comparison table across multiple providers (success rate + selected metric families)."""
    headers = ["Provider/Model", "Success Rate"]
    for m in metrics:
        if m == "ttft":
            headers += ["Avg TTFT", "TTFT_p95"]
        elif m == "e2e":
            headers += ["Avg End-to-End", "p95 End-to-End"]
        elif m == "throughput":
            headers += ["Throughput"]
        elif m == "tokens":
            headers += ["Output Tokens"]

    rows: list[list[str]] = []
    for s in summaries:
        row = [
            s.provider,
            f"{s.success}/{s.total} ({s.availability * 100:.0f}%)",
        ]
        for m in metrics:
            if m == "ttft":
                row += [_fmt(s.stat("ttft", "mean"), "ms", 1000, 0),
                        _fmt(s.stat("ttft", "p95"), "ms", 1000, 0)]
            elif m == "e2e":
                row += [_fmt(s.stat("latency", "mean"), "s", 1, 2),
                        _fmt(s.stat("latency", "p95"), "s", 1, 2)]
            elif m == "throughput":
                row += [_fmt(s.stat("throughput", "mean"), " t/s", 1, 1)]
            elif m == "tokens":
                row += [_fmt(s.stat("completion_tokens", "mean"), "", 1, 0)]
        rows.append(row)

    _render_table(headers, rows)
    _print_errors(summaries)


def print_sweep_table(summaries: list[ProviderSummary]) -> None:
    """
    Print concurrency stress test table: each row is a concurrency level, showing latency tail (p50/p95/p99/std),
    availability, and aggregate throughput (RPS / tokens·s⁻¹) as concurrency changes.
    """
    headers = [
        "Concurrency", "Success Rate", "TTFT_p50", "TTFT_p95",
        "p50 End-to-End", "p95 End-to-End", "p99 End-to-End", "Std End-to-End",
        "RPS", "Aggregate Throughput",
    ]
    rows: list[list[str]] = []
    for s in summaries:
        rows.append([
            str(s.concurrency),
            f"{s.success}/{s.total} ({s.availability * 100:.0f}%)",
            _fmt(s.stat("ttft", "p50"), "ms", 1000, 0),
            _fmt(s.stat("ttft", "p95"), "ms", 1000, 0),
            _fmt(s.stat("latency", "p50"), "s", 1, 2),
            _fmt(s.stat("latency", "p95"), "s", 1, 2),
            _fmt(s.stat("latency", "p99"), "s", 1, 2),
            _fmt(s.stat("latency", "std"), "s", 1, 2),
            _fmt(s.rps, "", 1, 1),
            _fmt(s.agg_throughput, " t/s", 1, 1),
        ])
    _render_table(headers, rows)
    _print_errors(summaries)


def summary_to_dict(s: ProviderSummary) -> dict:
    """Serialize a summary into a JSON-serializable structure (for --output)."""
    def stats(attr: str) -> dict:
        return {
            k: s.stat(attr, k)
            for k in ("mean", "std", "p50", "p95", "p99")
        }

    return {
        "provider": s.provider,
        "model": s.model,
        "concurrency": s.concurrency,
        "total": s.total,
        "success": s.success,
        "availability": s.availability,
        "wall_time_s": s.wall_time,
        "rps": s.rps,
        "agg_throughput_tps": s.agg_throughput,
        "ttft_s": stats("ttft"),
        "latency_s": stats("latency"),
        "throughput_tps": stats("throughput"),
        "completion_tokens_mean": s.stat("completion_tokens", "mean"),
        "errors": s.errors[:20],
    }


def write_output(path: str, meta: dict, summaries: list[ProviderSummary]) -> None:
    payload = {"meta": meta, "results": [summary_to_dict(s) for s in summaries]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Results written to:{path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-dimensional model performance benchmark (Experiment 6-8): TTFT / End-to-End / Throughput / p50·p95·p99·std / Availability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--num-requests", type=int, default=10,
                        help="Number of requests per concurrency level (default 10, cost control; book standard ≥100)")
    parser.add_argument("--concurrency", type=int, default=3,
                        help="Concurrency per level (default 3; mutually exclusive with --concurrency-sweep)")
    parser.add_argument("--serial", action="store_true",
                        help="Send serially (equivalent to --concurrency 1, baseline latency without contention)")
    parser.add_argument("--concurrency-sweep", type=str, default=None, metavar="1,2,4,8",
                        help="Concurrency stress test: comma-separated list of concurrency levels, progressively increasing load on the same model to find the throttling point")
    parser.add_argument("--max-tokens", type=int, default=64,
                        help="Maximum number of tokens generated per request (default 64, controls cost)")
    parser.add_argument("--timeout", type=float, default=60.0,
                        help="Single request timeout (seconds); timeout counts as availability degradation")
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT,
                        help="Short test prompt")
    parser.add_argument("--metrics", type=str, default="all",
                        help="Metric families displayed in the main comparison table, comma-separated, optional "
                             "ttft/e2e/throughput/tokens or all (default all; success rate always shown)")
    parser.add_argument("--output", type=str, default=None, metavar="FILE.json",
                        help="Write full results (including p50/p95/p99/std) to a JSON file")
    parser.add_argument("--list", action="store_true",
                        help="List the providers to be tested and exit")

    # Specify any single OpenAI-compatible endpoint (test new providers/models without modifying code)
    grp = parser.add_argument_group("Custom endpoint (if specified, only this one is tested, ignoring the default provider list)")
    grp.add_argument("--base-url", type=str, default=None,
                     help="base_url of the OpenAI-compatible endpoint (leave empty for official OpenAI)")
    grp.add_argument("--model", type=str, default=None,
                     help="Model name to test (e.g., gpt-5.6-luna / deepseek-chat)")
    grp.add_argument("--api-key-env", type=str, default="OPENAI_API_KEY",
                     help="Environment variable name for the API key (default OPENAI_API_KEY)")
    grp.add_argument("--name", type=str, default=None,
                     help="Display name of this endpoint in the table (defaults to model name)")

    parser.add_argument("--mock", action="store_true",
                        help="Offline self-check: run metric aggregation with synthetic data,"
                             "no network requests or keys needed (numbers are synthetic, not real benchmarks)")
    return parser.parse_args()


def resolve_metrics(raw: str) -> list[str]:
    if raw.strip().lower() == "all":
        return list(METRIC_KEYS)
    chosen = [m.strip() for m in raw.split(",") if m.strip()]
    bad = [m for m in chosen if m not in METRIC_KEYS]
    if bad:
        raise SystemExit(f"Unknown metric:{', '.join(bad)}; optional:{', '.join(METRIC_KEYS)} or all")
    return chosen


def build_providers(args: argparse.Namespace) -> tuple[list[ProviderConfig], list[ProviderConfig]]:
    """
    Returns (available, skipped).
    If --base-url or --model is specified, constructs a single custom provider (overrides default list).
    """
    if args.base_url or args.model:
        if not args.model:
            raise SystemExit("Must provide --model when using a custom endpoint")
        cfg = ProviderConfig(
            name=args.name or f"custom/{args.model}",
            model=args.model,
            api_key_env=args.api_key_env,
            base_url=args.base_url,
        )
        available = [cfg] if cfg.is_available() else []
        skipped = [] if cfg.is_available() else [cfg]
        return available, skipped

    available = [p for p in DEFAULT_PROVIDERS if p.is_available()]
    skipped = [p for p in DEFAULT_PROVIDERS if not p.is_available()]
    return available, skipped


def run_mock(args: argparse.Namespace, metrics: list[str]) -> None:
    """Demonstrate metric aggregation with synthetic data, no key/network required."""
    print("=" * 72)
    print("Multi-dimensional model performance benchmark (experimental 6-8) — synthetic data self-check mode [SYNTHETIC]")
    print("=" * 72)
    print("⚠️  All numbers below are synthetically generated (pseudo-random), only for verifying metric aggregation math,")
    print("    do not represent any real model/provider/network performance, and must not be used for selection.")
    print("-" * 72)

    name = args.name or (args.model and f"custom/{args.model}") or "mock/demo-model"
    model = args.model or "demo-model"

    if args.concurrency_sweep:
        levels = parse_sweep_levels(args.concurrency_sweep)
        print(f"Concurrency stress test (synthetic):{name}  level={levels}  N={args.num_requests}/level")
        summaries = [
            synthetic_summary(name, model, args.num_requests, c, fail_rate=0.02, seed=42)
            for c in levels
        ]
        print_sweep_table(summaries)
        print("Interpretation: as concurrency increases → end-to-end p95/p99 and std increase (long tail worsens),")
        print("      availability decreases due to throttling, aggregate throughput first rises then plateaus (hits server-side limit).")
    else:
        concurrency = 1 if args.serial else args.concurrency
        print(f"Single-concurrency comparison (synthetic): concurrency={concurrency}  N={args.num_requests}/provider")
        # Create three "providers" with different parameters to show horizontal differences
        summaries = [
            synthetic_summary("mockA/fast-low-ttft", "fast", args.num_requests,
                              concurrency, base_ttft=0.20, base_gen_throughput=110, seed=1),
            synthetic_summary("mockB/balanced", "balanced", args.num_requests,
                              concurrency, base_ttft=0.35, base_gen_throughput=85, seed=2),
            synthetic_summary("mockC/high-throughput", "hi-tp", args.num_requests,
                              concurrency, base_ttft=0.55, base_gen_throughput=140,
                              fail_rate=0.05, seed=3),
        ]
        print_table(summaries, metrics)

    if args.output:
        write_output(args.output, {"mode": "mock-synthetic", "note": "Numbers are synthetic, not real benchmarks"},
                     summaries)


def parse_sweep_levels(raw: str) -> list[int]:
    try:
        levels = [int(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        raise SystemExit(f"--concurrency-sweep must be a comma-separated list of integers, e.g., 1,2,4,8; received:{raw!r}")
    levels = [c for c in levels if c >= 1]
    if not levels:
        raise SystemExit("--concurrency-sweep requires at least one concurrency level ≥ 1")
    return levels


def main() -> None:
    args = parse_args()
    metrics = resolve_metrics(args.metrics)

    if args.mock:
        run_mock(args, metrics)
        return

    available, skipped = build_providers(args)

    print("=" * 72)
    print("Multi-dimensional model performance benchmark (experiments 6-8)")
    print("=" * 72)
    if skipped:
        for p in skipped:
            print(f"[Skip] {p.name} —— environment variable not set {p.api_key_env}")
    if not available:
        print("No available providers: set the corresponding API key environment variables,")
        print("or use --mock to verify metric aggregation offline without keys.")
        return

    print(f"Providers under test:{', '.join(p.name for p in available)}")

    # ---- Concurrency stress test mode ----
    if args.concurrency_sweep:
        levels = parse_sweep_levels(args.concurrency_sweep)
        print(f"Mode: concurrency stress test (stepwise pressurization to find rate limit)   concurrency={levels}")
        print(f"Parameters: N={args.num_requests}/run, max_tokens={args.max_tokens}, "
              f"timeout={args.timeout}s")
        print(f"Prompt：{args.prompt!r}")
        if args.list:
            return
        all_summaries: list[ProviderSummary] = []
        for cfg in available:
            print("-" * 72)
            print(f"Stress test {cfg.name}:")
            summaries = sweep_concurrency(
                cfg, args.prompt, args.num_requests, levels,
                args.max_tokens, args.timeout,
            )
            print_sweep_table(summaries)
            all_summaries.extend(summaries)
        if args.output:
            write_output(args.output,
                         {"mode": "concurrency-sweep", "levels": levels}, all_summaries)
        return

    # ---- Single-concurrency horizontal comparison mode (default, keep original behavior) ----
    concurrency = 1 if args.serial else args.concurrency
    print(f"Parameters: N={args.num_requests}/provider, concurrency={concurrency}, "
          f"max_tokens={args.max_tokens}, timeout={args.timeout}s")
    print(f"Prompt：{args.prompt!r}")

    if args.list:
        return

    print("-" * 72)
    summaries = run_benchmark(
        providers=available,
        prompt=args.prompt,
        num_requests=args.num_requests,
        concurrency=concurrency,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )

    print_table(summaries, metrics)

    print("Metric description:")
    print("  Success rate = successful requests / total requests (availability dimension)")
    print("  TTFT    = time to first token (measured via streaming), lower is smoother")
    print("  End-to-end = total time from request to response completion")
    print("  Throughput = output tokens / generation phase time (tokens/s)")
    print("  p95     = 95th percentile latency, reflects long-tail/stability (high variance means unstable experience)")
    print("  Hint    = add --concurrency-sweep 1,2,4,8 to run concurrency stress test and see how metrics change with concurrency")

    if args.output:
        write_output(args.output,
                     {"mode": "single", "concurrency": concurrency}, summaries)


if __name__ == "__main__":
    main()
