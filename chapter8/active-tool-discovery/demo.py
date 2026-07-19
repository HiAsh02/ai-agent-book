"""
Experiment 8-4 Demo: Active Tool Discovery vs Retrieval Prefilter vs Full Injection

For the same set of cross-domain tasks, run three "tool discovery" strategies on a tool library of 126 tools,
and output a comparable table (accuracy / injected tokens / latency) in a single run:

- full_injection: Inject all 126 tool schemas into the context at once (control group, as in the book).
- retrieval_prefilter: Perform a one-time semantic retrieval based on the initial query, injecting only top-n candidate tools.
- active_discovery: Start with a small set of basic tools plus the discover_tools meta-tool, loading tools on demand during execution.

Core argument (Chapter 8): When the tool set reaches hundreds, "stuffing all tools into the context" is expensive in tokens
and disastrous for instruction following in small models; active discovery loads tools on demand, drastically reducing tokens and improving selection accuracy.

Usage (see --help):
    python demo.py                         # Default: all tasks × three strategies (requires OPENAI_API_KEY)
    python demo.py --offline               # Offline self-check: local embeddings + mock model, no key needed
    python demo.py --tasks finance+news,crypto+news
    python demo.py --strategies full,discovery --tool-set-size 30
    python demo.py --query "Check Nvidia stock price and search related news" --offline
    python demo.py --offline --output results/offline.json
"""

import argparse
import json
import os
import sys
import time

from tools_library import TASKS, grade, select_tools, ALL_TOOLS


def _to_openrouter_model(model: str) -> str:
    """Map common model names to OpenRouter namespace (for fallback path without OPENAI_API_KEY)."""
    if not model:
        return "openai/gpt-5.6-luna"
    if "/" in model:
        return model
    if model.startswith("gpt-"):
        return "openai/" + model
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"


# Strategy registry: key -> (Chinese name, needs index?)
STRATEGIES = {
    "full": ("Full Injection", False),
    "prefilter": ("Retrieval Prefilter", True),
    "discovery": ("Active Discovery", True),
}
STRATEGY_ORDER = ["full", "prefilter", "discovery"]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="demo.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Experiment 8-4: Active Tool Discovery vs Retrieval Prefilter vs Full Injection.\n"
                    "On a tool library of 126 tools, output a comparison table of 'accuracy / injected tokens / latency' for multiple tasks in one run,\n"
                    "validating Chapter 8's argument: in scenarios with hundreds of tools, active on-demand discovery is superior to stuffing all tools into the context.",
        epilog="Examples:\n"
               "  python demo.py --offline                 # Offline self-check without API key\n"
               "  python demo.py --strategies full,discovery --tasks finance+news\n"
               "  python demo.py --query 'Check Nvidia stock price and search related news' --offline\n")
    ap.add_argument("--query", metavar="TEXT",
                    help="Temporary single task: directly provide a natural language requirement, skipping the built-in task set (scoring slots inferred automatically from keywords).")
    ap.add_argument("--tasks", metavar="IDS",
                    help="Comma-separated built-in task IDs (see tools_library.TASKS); default runs all 8 tasks."
                         "IDs with parentheses should be quoted, e.g., 'opinion(诱导)'.")
    ap.add_argument("--strategies", metavar="LIST", default="full,prefilter,discovery",
                    help="Comma-separated strategies, values: full/prefilter/discovery; default runs all three and compares.")
    ap.add_argument("--tool-set-size", type=int, default=None, metavar="N",
                    help="Truncate the tool library to N tools (always retain basic/generic/task-relevant tools)."
                         "Default uses all 126 tools—using small N can compare 'the larger the tool set, the more full injection suffers'.")
    ap.add_argument("--top-k", type=int, default=4, metavar="K",
                    help="Number of candidate tools returned by discover_tools in active discovery (default 4).")
    ap.add_argument("--prefilter-n", type=int, default=10, metavar="N",
                    help="Number of candidate tools injected at once in retrieval prefilter (default 10).")
    ap.add_argument("--model", default=os.getenv("MODEL", "gpt-5.6-luna"), metavar="NAME",
                    help="Dialogue model name (default: env var MODEL or gpt-5.6-luna); ignored in offline mode.")
    ap.add_argument("--embed-model", default=os.getenv("EMBED_MODEL", "text-embedding-3-small"),
                    metavar="NAME", help="Embedding model name (default: text-embedding-3-small); ignored in offline mode.")
    ap.add_argument("--max-steps", type=int, default=10, metavar="N",
                    help="Maximum ReAct steps for a single task (default 10).")
    ap.add_argument("--offline", action="store_true",
                    help="Offline self-check: uses local hash embeddings + scripted mock model, no API key required."
                         "Token/latency are real measurements; accuracy reflects heuristic routing only, not real model capability.")
    ap.add_argument("--output", metavar="PATH",
                    help="Write per-task, per-strategy structured results to this JSON file.")
    return ap


def _fmt_grade(g):
    tag = "✅ Correct selection" if g["precise"] else ("⚠️ Completed but wrong selection" if g["correct"] else "❌ Error")
    detail = f"{g['filled_slots']}/{g['total_slots']} Capability slot hit"
    extra = ""
    if g["missed_slots"]:
        extra += f"| Misuse: {[s[0] for s in g['missed_slots']]}"
    if g["used_generic_substitute"]:
        extra += f"| Wrong generic tool: {g['used_generic_substitute']}"
    return f"{tag}（{detail}{extra}）"


def _make_task_from_query(query: str):
    """Wrap temporary --query into a task with grading slots (slots inferred by keywords)."""
    from offline_backend import match_intents
    slots = [[tool] for tool, _ in match_intents(query)]
    return {"id": "adhoc", "prompt": query, "required_slots": slots}


def run_strategy(key, client, model, prompt, index, tools, args):
    """Execute a strategy and return (result_dict, latency_s)."""
    from agent import (run_active_discovery, run_full_injection,
                       run_retrieval_prefilter)
    t0 = time.perf_counter()
    if key == "full":
        res = run_full_injection(client, model, prompt, tools=tools, max_steps=args.max_steps)
    elif key == "prefilter":
        res = run_retrieval_prefilter(client, model, prompt, index,
                                      top_n=args.prefilter_n, tools=tools, max_steps=args.max_steps)
    else:
        res = run_active_discovery(client, model, prompt, index,
                                   top_k=args.top_k, tools=tools, max_steps=args.max_steps)
    return res, time.perf_counter() - t0


def main():
    args = build_parser().parse_args()

    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    bad = [s for s in strategies if s not in STRATEGIES]
    if bad:
        print(f"Unknown strategy: {bad}, optional: {list(STRATEGIES)}")
        sys.exit(2)
    strategies.sort(key=STRATEGY_ORDER.index)

    # ---- Task Set ----
    if args.query:
        tasks = [_make_task_from_query(args.query)]
    else:
        tasks = TASKS
        if args.tasks:
            want = set(args.tasks.split(","))
            tasks = [t for t in TASKS if t["id"] in want]
        if not tasks:
            print(f"No matching task id: {args.tasks}")
            sys.exit(2)

    tools = select_tools(args.tool_set_size, tasks)
    need_index = any(STRATEGIES[s][1] for s in strategies)

    # ---- Backend (Online OpenAI / Offline Mock) ----
    if args.offline:
        from offline_backend import LocalEmbedder, MockChatClient
        from discovery import ToolIndex
        client = MockChatClient()
        model = "mock-offline"
        embedder = LocalEmbedder()
        print("=" * 92)
        print("Offline self-check mode: local hash embedding + scripted mock model (no API key needed).")
        print("  · Token/latency are real measurements; accuracy only reflects heuristic routing, not real model capability.")
        print("  · Observation point: token gap among three strategies, and structural tool misuse of 'retrieval pre-filtering one-shot match'.")
        print("=" * 92)
    else:
        try:
            from dotenv import load_dotenv
            from openai import OpenAI
        except ImportError:
            print("Missing openai / python-dotenv, please pip install -r requirements.txt first,"
                  "or use --offline for offline self-check.")
            sys.exit(1)
        load_dotenv()
        from discovery import OpenAIEmbedder, ToolIndex
        if os.getenv("OPENAI_API_KEY"):
            #  Direct OpenAI: both chat and embeddings go through OpenAI
            client = OpenAI()
            model = args.model
            embedder = OpenAIEmbedder(client, model=args.embed_model)
        elif os.getenv("OPENROUTER_API_KEY"):
            #  Unified fallback: OpenRouter only proxies chat completions, no embeddings API,
            #  so chat goes through OpenRouter (real model), tool retrieval uses local hash embedding.
            from offline_backend import LocalEmbedder
            client = OpenAI(api_key=os.getenv("OPENROUTER_API_KEY"),
                            base_url="https://openrouter.ai/api/v1")
            model = _to_openrouter_model(args.model)
            embedder = LocalEmbedder()
            print("OPENAI_API_KEY not detected, switching to OpenRouter fallback:")
            print(f"  · Chat model: {model}(real call)")
            print("  · Tool retrieval: local hash embedding (OpenRouter has no embeddings API).")
        else:
            print("Please set OPENAI_API_KEY or OPENROUTER_API_KEY (see env.example),"
                  "or use --offline for offline self-check.")
            sys.exit(1)

    index = ToolIndex(embedder, tools=tools) if need_index else None

    print(f"Model: {model}  |  Embedding: {embedder.name}  |  Tool library: {len(tools)} items  "
          f"|  Tasks: {len(tasks)}  |  Strategy: {[STRATEGIES[s][0] for s in strategies]}\n")

    # ---- Per-Task Run ----
    records = []           #  Each: {task, strategy, result, grade, latency}
    for task in tasks:
        print("=" * 92)
        print(f"Task [{task['id']}]: {task['prompt']}")
        print("-" * 92)
        for key in strategies:
            res, latency = run_strategy(key, client, model, task["prompt"], index, tools, args)
            g = grade(task, res["called"])
            records.append({"task": task["id"], "strategy": key, "result": res,
                            "grade": g, "latency_s": round(latency, 3)})
            cname = STRATEGIES[key][0]
            print(f"[{cname}] injection {res['injected_tokens']:>6} tokens "
                  f"(exposed {res['num_tools_exposed']} tools)  delay {latency:5.2f}s")
            if key == "prefilter":
                print(f"           pre-filter hits: {res['prefiltered']}")
            if key == "discovery":
                for line in res["trace"]:
                    if line.startswith("[discover_tools]"):
                        print(f"           {line}")
                print(f"           discovered and loaded: {res['discovered']}")
            print(f"           call trace: {res['called']}")
            print(f"           verdict: {_fmt_grade(g)}")
        print()

    _print_summary(tasks, strategies, records)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        payload = {"model": model, "embedder": embedder.name, "tool_set_size": len(tools),
                   "offline": args.offline, "strategies": strategies,
                   "records": records}
        json.dump(payload, open(args.output, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"structured result written to: {args.output}")


def _print_summary(tasks, strategies, records):
    n = len(tasks)
    print("=" * 92)
    print("Summary comparison ('Precise correct selection' = covers all capability slots and does not mistakenly select the general fallback tool)")
    print("=" * 92)
    header = f"{'Strategy':<14}{'Precise correct selection':>10}{'Task completion':>10}{'Avg injection tokens':>16}{'Total injection tokens':>14}{'Avg delay (s)':>12}"
    print(header)
    print("-" * 92)
    for key in strategies:
        rs = [r for r in records if r["strategy"] == key]
        precise = sum(int(r["grade"]["precise"]) for r in rs)
        correct = sum(int(r["grade"]["correct"]) for r in rs)
        tok = [r["result"]["injected_tokens"] for r in rs]
        lat = [r["latency_s"] for r in rs]
        avg_tok = sum(tok) / len(tok) if tok else 0
        avg_lat = sum(lat) / len(lat) if lat else 0
        print(f"{STRATEGIES[key][0]:<12}{f'{precise}/{n}':>10}{f'{correct}/{n}':>10}"
              f"{avg_tok:>16.0f}{sum(tok):>14}{avg_lat:>12.3f}")
    print("-" * 92)
    if "full" in strategies and "discovery" in strategies:
        ft = sum(r["result"]["injected_tokens"] for r in records if r["strategy"] == "full")
        at = sum(r["result"]["injected_tokens"] for r in records if r["strategy"] == "discovery")
        if at:
            print(f"Injection tokens: full injection {ft} vs active discovery {at}, avg precise per task approx {ft/at:.1f} times.")


if __name__ == "__main__":
    main()
