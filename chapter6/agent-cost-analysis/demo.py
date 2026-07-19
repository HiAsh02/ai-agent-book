"""
Experiment 6-7: End-to-End Cost Analysis of Agent Tasks (Runnable Demo + CLI).

Two modes:
  1) Online (--live, default): Actually calls the model (default gpt-5.6-luna), token and cached_tokens
     are taken from the API response usage, cost is calculated by unit price. Requires OPENAI_API_KEY or OPENROUTER_API_KEY
     (falls back to OpenRouter automatically if no OpenAI key; gpt-5.x prefers OpenRouter if key is available).
  2) Offline (--offline): Does not call the model; reads a previously recorded trace (canned token
     counts), recalculates cost, cost breakdown, and A/B comparison table with configurable unit prices. No API key needed.

Both modes produce two deliverables:
  (a) Per-step and per-cost-component breakdown of a single task (which step is most expensive, input/cache/output shares).
  (b) A/B comparison table: Naive vs KV-cache only vs Compression only vs Both (full 2×2),
      quantifying total tokens / cached tokens / cache rate / cost / savings relative to baseline.

Examples:
  python demo.py                          # Online, runs default A(Naive)+B(Optimized) two groups
  python demo.py --scenario all           # Online, runs full 2×2 four groups
  python demo.py --live --save-trace out.json   # Online run and save real usage to file
  python demo.py --offline                # Offline, recalculates with built-in sample_trace.json
  python demo.py --offline --model gpt-4o # Offline, recalculates same usage with gpt-4o unit prices
  python demo.py --offline --price-input 0.20 --price-cached 0.10 --price-output 0.80
"""

import argparse
import json
import os
import sys

import config
from config import PRICING_PRESETS, Pricing


DEFAULT_TRACE = os.path.join(os.path.dirname(__file__), "sample_trace.json")
SCENARIO_KEYS = ["naive", "kv", "compress", "both"]


def _pct(saved: float, base: float) -> str:
    if base == 0:
        return "0.0%"
    return f"{saved / base * 100:.1f}%"


def build_pricing(args) -> Pricing:
    """Based on --model preset + --price-* overrides, construct the unit prices for this billing."""
    base = PRICING_PRESETS.get(args.model)
    if base is None:
        base = config.default_pricing()
    return Pricing(
        input_per_m=args.price_input if args.price_input is not None else base.input_per_m,
        cached_per_m=args.price_cached if args.price_cached is not None else base.cached_per_m,
        output_per_m=args.price_output if args.price_output is not None else base.output_per_m,
    )


def resolve_scenarios(arg: str):
    """Parse --scenario into an ordered deduplicated list of scenario keys."""
    if arg == "all":
        return list(SCENARIO_KEYS)
    if arg == "ab":
        return ["naive", "both"]
    keys, seen = [], set()
    for k in arg.split(","):
        k = k.strip()
        if k and k not in seen:
            keys.append(k)
            seen.add(k)
    return keys


# ---------------------------------------------------------------------------
#  Collect: online by running the real model, or offline by reading from a trace file
# ---------------------------------------------------------------------------
def collect_live(keys, pricing, warmup: bool):
    import agent

    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")):
        print("No OPENAI_API_KEY or OPENROUTER_API_KEY detected, please export one of them "
              "(will fall back to OpenRouter if no OpenAI key), or use --offline (offline recalculation, no key needed).",
              file=sys.stderr)
        sys.exit(1)

    #  Construct client and resolve actual model name (may be remapped to OpenRouter id).
    client, resolved = config.make_client_and_model(config.MODEL)
    if resolved != config.MODEL:
        print(f">>> Fallback to OpenRouter: model {config.MODEL} -> {resolved}")
        config.MODEL = resolved
        agent.MODEL = resolved
        try:
            agent._encoder.cache_clear()
        except Exception:
            pass
    tracers = []
    for k in keys:
        name, kv, compress = agent.SCENARIOS[k]
        #  The KV-cache group first runs a "warm-up" to write the stable prefix into OpenAI's prompt cache,
        #  so that cached_tokens are more consistently hit during actual measurement (in real systems the prefix is already hot).
        if kv and warmup:
            print(f">>> Warming up [{name}] stable prefix (writing to prompt cache)...")
            agent.run_scenario(client, kv, compress, name=name, pricing=pricing)
        print(f">>> Running [{name}] {'(online measurement)' if kv else ''}...")
        tr = agent.run_scenario(client, kv, compress, name=name, pricing=pricing)
        tracers.append((k, tr))
    return tracers


def collect_offline(keys, pricing, trace_path):
    from tracer import Tracer

    if not os.path.exists(trace_path):
        print(f"Trace file not found:{trace_path}", file=sys.stderr)
        sys.exit(1)
    with open(trace_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    by_key = {s.get("key", s.get("name")): s for s in data.get("scenarios", [])}
    print(f"Offline mode: reading {trace_path}")
    print(f"  This trace was collected from model = {data.get('model', '?')}，"
          f"Total {len(by_key)} scenarios with real recorded usage (token counts are measured, costs recalculated with current unit prices).")

    tracers = []
    for k in keys:
        sc = by_key.get(k)
        if sc is None:
            print(f"  [Skip] trace does not contain scenario '{k}' (use online mode --save-trace to record it)",
                  file=sys.stderr)
            continue
        tr = Tracer.from_records(sc["spans"], name=sc.get("name", k), pricing=pricing)
        tracers.append((k, tr))
    if not tracers:
        print("Trace contains no selected scenarios, exiting.", file=sys.stderr)
        sys.exit(1)
    return tracers


# ---------------------------------------------------------------------------
#  Deliverable (b): A/B comparison table
# ---------------------------------------------------------------------------
def print_ab_table(tracers):
    print("\n\n===== A/B Cost Comparison (Same 8-turn Customer Service Refund Task) =====")
    header = (f"{'Scheme':<26} {'Total Input Tok':>10} {'Cached Tok':>10} {'Cache Rate':>8} "
              f"{'Output Tok':>8} {'Total Cost($)':>12} {'vs baseline':>10}")
    print(header)
    print("-" * len(header))

    base_cost = tracers[0][1].total_cost()
    for _, tr in tracers:
        pin = tr.total_prompt_tokens()
        cac = tr.total_cached_tokens()
        rate = f"{(cac / pin * 100):.1f}%" if pin else "0.0%"
        cost = tr.total_cost()
        vs = "baseline" if abs(cost - base_cost) < 1e-12 else f"-{_pct(base_cost - cost, base_cost)}"
        print(f"{tr.name:<26} {pin:>10} {cac:>10} {rate:>8} "
              f"{tr.total_completion_tokens():>8} {cost:>12.6f} {vs:>10}")
    print("-" * len(header))

    # Use the first (baseline) and last (usually both optimized) for key quantification
    base_k, base = tracers[0]
    best_k, best = tracers[-1]
    if base_k != best_k:
        tok_a = base.total_prompt_tokens() + base.total_completion_tokens()
        tok_b = best.total_prompt_tokens() + best.total_completion_tokens()
        cost_a, cost_b = base.total_cost(), best.total_cost()
        print(f"\nKey comparison:{base.name}  →  {best.name}")
        print(f"  Total tokens:   A={tok_a}  →  B={tok_b}   "
              f"Reduction {tok_a - tok_b} ({_pct(tok_a - tok_b, tok_a)})")
        print(f"  Cache tokens: A={base.total_cached_tokens()}  →  "
              f"B={best.total_cached_tokens()}   (B relies on stable prefix hitting cache)")
        print(f"  Total cost:     A=${cost_a:.6f}  →  B=${cost_b:.6f}   "
              f"Reduce ${cost_a - cost_b:.6f} ({_pct(cost_a - cost_b, cost_a)})")
        if cost_b > 0:
            print(f"  Cost multiplier: A is {cost_a / cost_b:.2f} times that of B")

    print("\nConclusion: Stable long prefixes make repeated system prompts/tool definitions/history rounds billed at cache prices,")
    print("      combined with context compression to control context growth, both significantly reduce end-to-end costs.")


def dump_output(path, tracers, pricing, model):
    out = {
        "model": model,
        "pricing": {"input": pricing.input_per_m, "cached": pricing.cached_per_m,
                    "output": pricing.output_per_m},
        "scenarios": [],
    }
    import agent
    for k, tr in tracers:
        name = agent.SCENARIOS[k][0] if k in agent.SCENARIOS else tr.name
        out["scenarios"].append({
            "key": k, "name": name,
            "total_cost": tr.total_cost(),
            "component_costs": tr.component_costs(),
            "cost_distribution": tr.cost_distribution(),
            "spans": tr.to_records(),
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nResults written to {path}")


def build_parser():
    p = argparse.ArgumentParser(
        prog="demo.py",
        description="Experiment 6-7: Agent task end-to-end cost analysis — full-chain cost breakdown for a customer service refund Agent,"
                    "and compare cost differences between KV-cache / context compression levers (full 2×2 A/B).",
        epilog="Example:\n"
               "  python demo.py                       # Online, default runs A(naive)+B(optimized)\n"
               "  python demo.py --scenario all        # Online, runs full 2×2 four groups\n"
               "  python demo.py --offline             # Offline, recalculates with built-in canned trace (no key needed)\n"
               "  python demo.py --offline --model gpt-4o   # Offline recalculation with different unit price\n"
               "  python demo.py --live --save-trace out.json  # Online run and dump real usage\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true",
                      help="Online mode (default): actually calls OpenAI, requires OPENAI_API_KEY.")
    mode.add_argument("--offline", action="store_true",
                      help="Offline mode: does not call the model, reads real recorded token usage from trace file and recalculates cost at unit price.")
    p.add_argument("--trace", metavar="FILE", default=DEFAULT_TRACE,
                   help=f"Trace (canned token counts) file read by offline mode, default {os.path.basename(DEFAULT_TRACE)}。")
    p.add_argument("--save-trace", metavar="FILE", default=None,
                   help="In online mode, dump the real token usage of this run as a trace file (for later --offline recalculation).")
    p.add_argument("--scenario", metavar="NAME", default="ab",
                   help="Select A/B scenarios to run: ab(default,=naive+both) / all(2×2 four groups) / "
                        "or comma-separated subset naive,kv,compress,both.")
    p.add_argument("--model", metavar="NAME", default=config.MODEL,
                   help=f"Model name (determines default unit price preset, optional {', '.join(PRICING_PRESETS)}），"
                        f"Default {config.MODEL}。")
    p.add_argument("--price-input", type=float, default=None,
                   help="Override input unit price (per million tokens in USD).")
    p.add_argument("--price-cached", type=float, default=None,
                   help="Override cache hit input unit price (per million tokens in USD).")
    p.add_argument("--price-output", type=float, default=None,
                   help="Override output unit price (per million tokens in USD).")
    p.add_argument("--no-warmup", action="store_true",
                   help="Disable prefix warm-up for KV-cache groups in online mode (warm-up is enabled by default to stabilize cache hits).")
    p.add_argument("--output", metavar="FILE", default=None,
                   help="Write the cost breakdown result (including cost composition/distribution/step-by-step usage) to a JSON file.")
    return p


def main():
    args = build_parser().parse_args()

    # Let the agent/tracer use the selected model
    config.MODEL = args.model
    try:
        import agent
        agent.MODEL = args.model
        agent._encoder.cache_clear()
    except Exception:
        pass

    pricing = build_pricing(args)
    keys = resolve_scenarios(args.scenario)
    bad = [k for k in keys if k not in SCENARIO_KEYS]
    if bad:
        print(f"Unknown scenario {bad}, optional: {SCENARIO_KEYS} / all / ab", file=sys.stderr)
        sys.exit(2)

    print(f"Model: {args.model}")
    print(f"Unit price (per million tokens): Input ${pricing.input_per_m} / Cache input ${pricing.cached_per_m} "
          f"/ Output ${pricing.output_per_m}")

    if args.offline:
        tracers = collect_offline(keys, pricing, args.trace)
    else:
        print("Note: OpenAI prompt caching takes effect automatically (prefix >= 1024 tokens and recent hit on the same prefix),")
        print("      cached input tokens appear in usage.prompt_tokens_details.cached_tokens.")
        tracers = collect_live(keys, pricing, warmup=not args.no_warmup)
        if args.save_trace:
            dump_output(args.save_trace, tracers, pricing, args.model)

    # Deliverable (a): Per-scenario cost breakdown
    for _, tr in tracers:
        tr.print_breakdown(title=f"{tr.name}(Full-chain breakdown of a single task)")

    #  Deliverable (b): A/B comparison table
    if len(tracers) >= 2:
        print_ab_table(tracers)

    if args.output:
        dump_output(args.output, tracers, pricing, args.model)


if __name__ == "__main__":
    main()
