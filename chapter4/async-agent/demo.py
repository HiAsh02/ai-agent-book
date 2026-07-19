"""Experiment 4-5 Command Line Entry: Asynchronous Agent with Parallel Execution, Interrupt/Cancel, and State Management.

This script provides two types of demos, distinguished by subcommands:

  [Offline Demo] No API key required; directly measures underlying behavior during async execution:
      python demo.py parallel     Wall-clock time comparison of parallel vs. serial tool calls (prints speedup)
      python demo.py interrupt    Long task interrupted/canceled during execution, then system recovers
      python demo.py state        Agent state checkpoint persistence + cross-session recovery and verification
      python demo.py offline      Runs all three offline demos above sequentially (default behavior)

  [LLM Scenario] Requires OPENAI_API_KEY (or MOONSHOT/ARK); decisions made by real models:
      python demo.py scenarios              Runs all four verification scenarios from the book sequentially
      python demo.py scenarios --scenario 1  Runs only scenario 1 (async execution + instant questioning)
      python demo.py scenarios --scenario 3  Runs only scenario 3 (interrupt mechanism)

Without any subcommand, runs [Offline Demo], so it works out of the box without internet.
For backward compatibility, `python demo.py --scenario N` is equivalent to `scenarios --scenario N`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from async_demos import OFFLINE_DEMOS, banner
from runtime import AgentRuntime

# openai is lazily imported only when running LLM scenarios; offline demos do not touch it, ensuring it works without a key or openai installed.


def _completion_params_for(model: str) -> dict:
    """Returns safe sampling parameters based on the model.

    Moonshot kimi-k3 is a [reasoning model]: must have temperature=1 and max_tokens>=2048,
    otherwise it may error or truncate. Other models use temperature=0.2 for stable decisions.
    """
    if model.startswith("kimi-k3"):
        return {"temperature": 1, "max_tokens": 4096}
    return {"temperature": 0.2}


def _map_model_for_openrouter(model: str) -> str:
    """Maps common model names to OpenRouter's `provider/model` format.

    - IDs already containing "/" (e.g., anthropic/claude-opus-4.8, google/gemini-2.5-pro) are passed through as-is.
    - gpt-*/o1-*/o3-*/o4-* -> openai/…
    - claude-* -> anthropic/claude-opus-4.8
    - Others remain unchanged (left for OpenRouter to validate).
    """
    if "/" in model:
        return model
    m = model.lower()
    if m.startswith(("gpt-", "o1-", "o3-", "o4-")):
        return f"openai/{model}"
    if m.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return model


def make_client():
    """Selects the available model service based on LLM_PROVIDER (default openai).

    Returns (client, model, completion_params).

    General fallback: when the direct provider's key is missing but OPENROUTER_API_KEY exists,
    automatically switches to OpenRouter (api_key=OPENROUTER_API_KEY, base_url=openrouter.ai/api/v1,
    and maps model names to provider/model format), so "having an OpenRouter key is enough to run".
    """
    from openai import AsyncOpenAI  # Lazy import: offline demos do not need openai
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "moonshot":
        key = os.environ["MOONSHOT_API_KEY"]
        # Default uses the current reasoning model kimi-k3 (older kimi-k2-*-preview and moonshot-v1-* are deprecated/discontinued).
        model = os.getenv("LLM_MODEL", "kimi-k3")
        client = AsyncOpenAI(api_key=key, base_url="https://api.moonshot.cn/v1")
        return client, model, _completion_params_for(model)
    if provider == "ark":
        key = os.environ["ARK_API_KEY"]
        model = os.getenv("LLM_MODEL")  # ARK requires filling in the endpoint id
        if not model:
            raise SystemExit("When using ARK, set LLM_MODEL to your inference endpoint ID")
        client = AsyncOpenAI(api_key=key, base_url="https://ark.cn-beijing.volces.com/api/v3")
        return client, model, _completion_params_for(model)
    if provider == "openrouter":
        key = os.environ["OPENROUTER_API_KEY"]
        model = _map_model_for_openrouter(os.getenv("LLM_MODEL", "openai/gpt-5.6-luna"))
        client = AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        return client, model, _completion_params_for(model)
    key = os.getenv("OPENAI_API_KEY")
    or_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("LLM_MODEL", "gpt-5.6-luna")
    # gpt-5.x (including gpt-5.6*) direct connection to OpenAI requires organization verification; as long as OPENROUTER_API_KEY is set,
    # prefer OpenRouter; when direct OPENAI_API_KEY is missing, also fall back to OpenRouter.
    if or_key and (not key or model.lower().startswith("gpt-5")):
        mapped = _map_model_for_openrouter(model)
        client = AsyncOpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1")
        return client, mapped, _completion_params_for(mapped)
    if key:
        base = os.getenv("OPENAI_BASE_URL")
        client = AsyncOpenAI(api_key=key, base_url=base) if base else AsyncOpenAI(api_key=key)
        return client, model, _completion_params_for(model)
    raise SystemExit(
        "No available LLM Key found. Please set any of the following:"
        "OPENAI_API_KEY or OPENROUTER_API_KEY (or LLM_PROVIDER=moonshot with MOONSHOT_API_KEY / "
        "LLM_PROVIDER=ark with ARK_API_KEY)."
    )


async def run_runtime(rt: AgentRuntime):
    """Run the event loop in the background."""
    return asyncio.create_task(rt.serve())


# ------------------------------- Four Scenarios -------------------------------

async def scenario_1(client, model, params):
    banner("Scenario 1 | Async Tool Execution: Respond instantly to inserted questions during long tasks")
    rt = AgentRuntime(client, model, completion_params=params)
    serve = await run_runtime(rt)

    # User issues a time-consuming log analysis task
    await rt.submit_user_message(
        "Please run the terminal command `python analyze_logs.py` (this is a time-consuming log analysis), and give me the analysis conclusion when done.",
        urgency="immediate")
    await asyncio.sleep(2.2)  # Task is running in the background

    # Meanwhile, the user asks an instant question
    await rt.submit_user_message("What time is it now?")  # Contains question mark -> respond immediately

    await rt.wait_until_idle()
    await rt.stop(); await serve


async def scenario_2(client, model, params):
    banner("Scenario 2 | Event Queue and Batch Processing: Non-urgent instructions accumulate, processed all at once when task completes")
    rt = AgentRuntime(client, model, completion_params=params)
    serve = await run_runtime(rt)

    await rt.submit_user_message(
        "Please run the terminal command `python analyze_logs.py` (time-consuming log analysis), and tell me the analysis conclusion when done.",
        urgency="immediate")
    await asyncio.sleep(1.5)

    # Send two supplementary instructions consecutively (no question mark -> non-urgent, enter queue buffer)
    await rt.submit_user_message("Remember to reply in Japanese at the end")
    await asyncio.sleep(0.4)
    await rt.submit_user_message("Format the result as a web page (HTML)")

    await rt.wait_until_idle()
    await rt.stop(); await serve


async def scenario_3(client, model, params):
    banner("Scenario 3 | Interrupt Mechanism: User 'cancel' immediately terminates execution flow and cancels async tools")
    rt = AgentRuntime(client, model, completion_params=params)
    serve = await run_runtime(rt)

    await rt.submit_user_message(
        "Please run the terminal command `python analyze_logs.py` (time-consuming log analysis), and give me the conclusion when done.",
        urgency="immediate")
    await asyncio.sleep(4.0)  # Wait for the background task to actually start running (about halfway through)

    await rt.submit_user_message("Cancel")  # Interrupt keyword -> cancel immediately

    await rt.wait_until_idle(stable=1.0)
    await rt.stop(); await serve


async def scenario_4(client, model, params):
    banner("Scenario 4｜Parallel tool cancellation and status query: three scripts racing + cancel at 50% threshold + consolidated report")
    rt = AgentRuntime(client, model, completion_params=params)
    serve = await run_runtime(rt)

    await rt.submit_user_message(
        "Run these three analysis scripts simultaneously: `python analyze_fast.py`, `python analyze_mid.py`, `python analyze_slow.py`."
        "Whichever script finishes first, you query the progress of the other two scripts; if a script's progress hasn't exceeded 50%, cancel it;"
        "After the remaining scripts finish, consolidate the results of all completed scripts into a report for me.",
        urgency="immediate")

    await rt.wait_until_idle(stable=1.5, timeout=60)
    await rt.stop(); await serve


SCENARIOS = {1: scenario_1, 2: scenario_2, 3: scenario_3, 4: scenario_4}


# ------------------------------- Subcommand Implementation -------------------------------

async def run_offline(names: list[str]) -> None:
    """Run offline demo (no API key required)."""
    for name in names:
        await OFFLINE_DEMOS[name]()


async def run_scenarios(which: int | None) -> None:
    """Run LLM-driven validation scenarios (API key required)."""
    client, model, params = make_client()
    print(f"Model used:{model}")
    todo = [which] if which else [1, 2, 3, 4]
    for i in todo:
        await SCENARIOS[i](client, model, params)
        await asyncio.sleep(0.5)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="demo.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Experiment 4-5: Asynchronous Agent demo with parallel execution, interrupt/cancel, and state management.",
        epilog=(
            "Example: \n"
            "  python demo.py                     # Default: run three offline demos sequentially (no API key required)\n"
            "  python demo.py parallel            # Wall-clock time comparison of parallel vs serial (prints speedup)\n"
            "  python demo.py interrupt           # Long-running task interrupted/canceled, then resumed\n"
            "  python demo.py state               # State checkpoint persistence + cross-session recovery and verification\n"
            "  python demo.py scenarios --scenario 3   # LLM scenario 3: interrupt mechanism (API key required)\n"
            "\nOffline demos do not require network or any key; the scenarios subcommand requires OPENAI_API_KEY (or MOONSHOT/ARK)."
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="<subcommand>")

    sub.add_parser("parallel", help="Wall-clock time comparison of parallel vs serial tool calls (offline, no key required)")
    sub.add_parser("interrupt", help="Long-running task interrupted/canceled, then system resumes (offline, no key required)")
    sub.add_parser("state", help="Agent state checkpoint persistence and cross-session recovery (offline, no key required)")
    sub.add_parser("offline", help="Run the three offline demos above sequentially (default behavior)")

    ps = sub.add_parser("scenarios", help="Four LLM validation scenarios from the book (API key required)")
    ps.add_argument("--scenario", type=int, choices=[1, 2, 3, 4],
                    help="Run only the specified scenario (1 async execution / 2 batch processing / 3 interrupt / 4 parallel cancel); if not specified, run all")
    return parser


async def main() -> None:
    # Backward compatible: `python demo.py --scenario N` is equivalent to `scenarios --scenario N`
    argv = sys.argv[1:]
    if argv and argv[0].startswith("-") and argv[0] not in ("-h", "--help"):
        argv = ["scenarios"] + argv

    args = build_parser().parse_args(argv)
    cmd = args.command or "offline"

    if cmd == "scenarios":
        await run_scenarios(args.scenario)
    elif cmd == "offline":
        await run_offline(["parallel", "interrupt", "state"])
    else:  # parallel / interrupt / state
        await run_offline([cmd])

    print("\nDemo ended.")


if __name__ == "__main__":
    asyncio.run(main())
