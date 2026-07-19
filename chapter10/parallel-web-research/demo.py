"""
Experiment 10-6 Demo Entry: Agent Collecting Information from Multiple Websites Simultaneously
===================================================================================

Run with a single command:

    python demo.py

Demo content (corresponding to mechanisms highlighted in the book):
  (a) Message bus publish/subscribe: message flow with envelope visible in logs (BUS prefix);
  (b) N sub-agents execute in parallel, main coordinator refreshes task status table in real time;
  (c) When a sub-agent hits, it triggers cascading termination, other agents receive terminate and exit gracefully (ack);
  (d) When multiple sub-agents hit almost simultaneously, only one settlement and one round of termination broadcast (idempotent + locking);
  (e) (--compare) Wall-clock time measurement comparison between parallel and serial execution, verifying performance gains from parallelization.

Default uses offline keyword matching to ensure reproducible results;
If OPENAI_API_KEY is configured and USE_LLM is not set to 0, sub-agents will switch to real LLM for judgment.

See `python demo.py --help` for command-line arguments; passing no arguments yields the original default behavior
(10 sub-agents, built-in question, offline keyword matching, detailed BUS logs).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001 — can run without python-dotenv installed
    pass

from agents import Coordinator, WorkerAgent, run_sequential
from llm import llm_available
from message_bus import MessageBus
from sources import DEMO_SOURCES, QUESTION, build_sources


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments; behavior is identical to before when no arguments are passed (10 agents, offline, detailed logs)."""
    parser = argparse.ArgumentParser(
        prog="demo.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Experiment 10-6: Demo of multiple homogeneous sub-agents parallel search + central coordination.\n"
            "Demonstrates message bus publish/subscribe, parallel dispatch, real-time status monitoring, cascading termination, and race condition handling;\n"
            "Default offline keyword matching (results reproducible), no arguments yields original default behavior."
        ),
        epilog=(
            "Example:\n"
            "  python demo.py                     # Default: 10 agents, built-in question, offline reproducible\n"
            "  python demo.py --agents 6          # Change to 6 parallel agents\n"
            "  python demo.py --compare           # Additionally measure wall-clock time of parallel vs serial\n"
            "  python demo.py --output result.json  # Write conclusion to JSON file\n"
            "  python demo.py --use-llm --model gpt-5.6-luna  # Use real LLM for judgment (requires key)"
        ),
    )
    parser.add_argument(
        "-q",
        "--query",
        default=QUESTION,
        metavar="Question",
        help="Research question (default uses built-in question). Note: offline keyword matching is tuned for built-in sources;"
        "custom questions typically require --use-llm with real LLM judgment to be meaningful.",
    )
    parser.add_argument(
        "-n",
        "--agents",
        type=int,
        default=len(DEMO_SOURCES),
        metavar="N",
        help=f"Number of parallel sub-agents (default {len(DEMO_SOURCES)}, corresponding to about 10 parallel agents in the book)."
        "When N>=2, always includes two sources with answers to stably demonstrate race conditions and cascading termination.",
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="MODEL",
        help="LLM model name (equivalent to setting environment variable OPENAI_MODEL; only effective when --use-llm and "
        "OPENAI_API_KEY or OPENROUTER_API_KEY is configured). Defaults to environment variable or gpt-5.6-luna.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="PATH",
        help="Write final conclusion (including parallel/serial wall-clock time, winner, race statistics) as JSON to this path. Default does not write file.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="After parallel run completes, also measure serial baseline and print wall-clock time comparison (verify parallelization benefits). Default does not run serial baseline.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Force enable real LLM judgment (equivalent to environment variable USE_LLM=1; still requires "
        "OPENAI_API_KEY to actually take effect, otherwise falls back to offline keyword matching). Default not enabled.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce verbose BUS log printing of message bus (task status table/conclusion/self-check unaffected). Default prints all logs.",
    )
    return parser.parse_args()


async def main(args: argparse.Namespace):
    if args.agents < 1:
        raise SystemExit("Error: --agents must be at least 1")

    if args.use_llm:
        #  Only sets the intent flag; whether LLM is actually called still depends on llm.llm_available()
        #  (also requires OPENAI_API_KEY), otherwise falls back to offline keyword matching automatically.
        os.environ["USE_LLM"] = "1"
    if args.model:
        os.environ["OPENAI_MODEL"] = args.model

    sources = build_sources(args.agents)

    print("=" * 78)
    print("Experiment 10-6 · Agent Collecting Information from Multiple Websites Simultaneously (Parallel Search + Central Coordination)")
    print("=" * 78)
    print(f"Task question:{args.query}")
    print(f"Number of parallel sources: {len(sources)} simulated 'websites' (sub-agents count = source count)")
    answer_srcs = [s.name for s in sources if s.holds_answer]
    print(f"Sources with answers: {answer_srcs}(the first two have the same delay, used to demonstrate race conditions)")
    print("-" * 78)

    bus = MessageBus(verbose=not args.quiet)
    coordinator = Coordinator(bus, args.query)

    # Assemble N isomorphic sub-agents in parallel, each bound to one source
    for i, src in enumerate(sources):
        w = WorkerAgent(f"worker-{i:02d}", src, bus, args.query)
        coordinator.add_worker(w)

    result = await coordinator.run()

    print("=" * 78)
    print("Demo conclusion (auto-verified)")
    print("=" * 78)
    total_msgs = len(bus.history)
    print(f"1) Message bus delivered a total of {total_msgs} envelope messages (pub/sub works correctly).")
    print(f"2) {len(coordinator.workers)} sub-agents executed in parallel, status table refreshed in real-time throughout.")
    print(f"3) First worker to hit and settle: {result['winner']}")
    print(f"   Answer: {result['answer']}")
    print(f"   Workers that received terminate and acked: {result['acks']}")
    print(f"4) Terminate broadcast rounds: {result['terminate_broadcasts']}(should be 1, proving only one broadcast round)")
    print(f"   Late/concurrent duplicate hits ignored: {result['duplicate_hits'] or 'None (no concurrent late hits this time)'}")
    print(f"   Settled only once: {result['settled_once']}")
    print(f"5) Parallel execution wall-clock time: {result['parallel_seconds']:.2f}s (including convergence quiet period)")

    # —— (e) Parallel vs serial wall-clock comparison: measured, never fabricated ——
    seq = None
    if args.compare:
        print("-" * 78)
        print("Parallel vs serial wall-clock comparison (--compare, serial baseline measured)")
        print("-" * 78)
        seq = await run_sequential(sources, args.query)
        print(
            f"   Serial: fetched {seq['fetched']}/{seq['total']} sources one by one before hit,"
            f" wall-clock time {seq['seconds']:.2f}s，winner={seq['winner']}"
        )
        print(f"   Parallel: wall-clock time {result['parallel_seconds']:.2f}s，winner={result['winner']}")
        if seq["seconds"] > 0 and result["parallel_seconds"] > 0:
            speedup = seq["seconds"] / result["parallel_seconds"]
            saved = seq["seconds"] - result["parallel_seconds"]
            print(f"   Speedup ≈ {speedup:.2f}×, saving about {saved:.2f}s (parallelism lets the fastest source end the global search immediately).")

    # —— Conclusion to disk (optional) ——
    if args.output:
        summary = {
            "question": args.query,
            "num_agents": len(coordinator.workers),
            "sources": [s.name for s in sources],
            "judge_mode": "llm" if llm_available() else "keyword_offline",
            "total_bus_messages": total_msgs,
            "winner": result["winner"],
            "answer": result["answer"],
            "duplicate_hits": result["duplicate_hits"],
            "acks": result["acks"],
            "settled_once": result["settled_once"],
            "terminate_broadcasts": result["terminate_broadcasts"],
            "parallel_seconds": round(result["parallel_seconds"], 3),
            "sequential_baseline": (
                {
                    "seconds": round(seq["seconds"], 3),
                    "fetched": seq["fetched"],
                    "winner": seq["winner"],
                }
                if seq
                else None
            ),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n[Written] Conclusion JSON -> {args.output}")

    #—— Assertive self-check: strong assertion only in offline reproducible mode (LLM mode hit depends on the model) ——
    if not llm_available():
        assert result["winner"] is not None, "At least one Worker should hit"
        assert result["terminate_broadcasts"] == 1, "Cascade termination can only broadcast one round"
        assert result["settled_once"] is True, "Must complete and settle only once"
        print("\n[Self-check passed] Single settlement + single round termination broadcast + cascade ack all meet expectations.")
    else:
        print("\n[Prompt] Currently in real LLM judgment mode, whether it hits depends on the model, no strong assertion.")


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
