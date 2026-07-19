"""
demo.py — Experiment 10-2 demo entry: multi-role transfer / transfer_to_agent

Minimal run (one command, runs default composite task):
    python demo.py

Other common usages:
    python demo.py --list-roles              # Offline: print role roster and exit (no API Key needed)
    python demo.py --scenario coding         # Switch to a built-in scenario (routes to coding role)
    python demo.py --task "..."              # Custom task
    python demo.py --role research            # Specify starting role (default is triage front desk)
    python demo.py --interactive             # Interactive multi-turn dialogue (roles and shared history persist across turns)
    python demo.py --model gpt-5.6-luna --max-steps 30

Demonstrates a composite task requiring [multiple cross-domain switches], expected to produce
    triage → research → data_analysis → writing
autonomous handoff chain — each handoff is triggered by the current role judging and calling transfer_to_agent.
"""

from __future__ import annotations

import argparse
import os
import sys

from openai import OpenAI

from roles import ROLES, DEFAULT_ROLE
from orchestrator import MultiRoleOrchestrator, C


def _to_openrouter_model(model: str) -> str:
    """Map model name to OpenRouter namespace (for fallback path without OPENAI_API_KEY)."""
    if "/" in model:
        return model                      #  Already OpenRouter namespace, use as-is
    if model.startswith("gpt-"):
        return "openai/" + model          # gpt-* -> openai/gpt-*
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"          #  Fallback: current cheap flagship

#  Try to read .env (optional dependency, can run without it if already exported in shell)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
#  Built-in scenarios: each deliberately spans multiple domains to force multiple autonomous handoffs.
#  Key name used for --scenario; value is (task text, one-sentence description).
# ---------------------------------------------------------------------------
COMPOSITE_TASK = (
    "I am preparing materials for investors. Please help me: \n"
    "1) Look up China's new energy vehicle sales for 2021, 2022, and 2023; \n"
    "2) Calculate the compound annual growth rate (CAGR) for these three years; \n"
    "3) Write a Chinese summary of the data and CAGR conclusion for investors, no more than 120 characters."
)

SCENARIOS: dict[str, tuple[str, str]] = {
    "cagr": (
        COMPOSITE_TASK,
        "Default scenario. Spans retrieval/computation/writing three domains: look up sales → calculate CAGR → write investment summary,"
        "Expected chain triage → research → data_analysis → writing.",
    ),
    "solar": (
        "Look up China's new photovoltaic installed capacity for 2021, 2022, and 2023,"
        "calculate the CAGR for these three years, then write a one-sentence conclusion for readers.",
        "Similar chain for another dataset (research → data_analysis → writing), verifying mechanism rather than memorizing answers.",
    ),
    "coding": (
        "Write a Python script: compute the first 20 Fibonacci numbers and their sum;"
        "after running the script, explain the result in one sentence to a non-technical audience.",
        "Routes to coding role to actually run code with execute_python, then wrapped up by writing/triage.",
    ),
}
DEFAULT_SCENARIO = "cagr"


def print_roster():
    """Print role roster, proving there are 5 roles each with different system prompts/tool sets."""
    print(f"{C.BOLD}=== Role Roster (total {len(ROLES)} professional roles) ==={C.RESET}")
    for name, role in ROLES.items():
        default_tag = "(default entry)" if name == DEFAULT_ROLE else ""
        tools = role.tools + ["transfer_to_agent"]
        first_line = role.system_prompt.strip().splitlines()[0]
        print(
            f"{C.CYAN}• {name}{C.RESET} — {role.title}{default_tag}\n"
            f"    Tool set: {tools}\n"
            f"    System prompt (first sentence): {first_line}"
        )
    print()


def print_scenarios():
    """Print built-in scenario list (for --help / --list-roles reference)."""
    print(f"{C.BOLD}=== Built-in Scenarios (--scenario) ==={C.RESET}")
    for key, (_task, desc) in SCENARIOS.items():
        default_tag = "(default)" if key == DEFAULT_SCENARIO else ""
        print(f"{C.CYAN}• {key}{C.RESET}{default_tag} — {desc}")
    print()


def parse_args() -> argparse.Namespace:
    """Command-line arguments — all optional; when omitted, behavior is exactly the same as the original version (runs default composite task)."""
    parser = argparse.ArgumentParser(
        prog="demo.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Experiment 10-2 demo: multi-role transfer / transfer_to_agent.\n"
            "On a piece of shared conversation history, 5 professional roles autonomously hand off via transfer_to_agent,"
            "triggering a handoff chain like triage → research → data_analysis → writing."
        ),
        epilog=(
            "Example: \n"
            "  python demo.py                     # Run default scenario (new energy vehicle CAGR investment summary)\n"
            "  python demo.py --list-roles        # Offline: list roles/scenarios only, no API calls\n"
            "  python demo.py --scenario coding   # Switch to a scenario that routes to the coding role\n"
            "  python demo.py --task 'Help me...' # Custom task\n"
            "  python demo.py --role research     # Start from the research role\n"
            "  python demo.py --interactive       # Interactive multi-turn, roles and shared history persist across turns\n"
        ),
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default=DEFAULT_SCENARIO,
        help=f"Select a built-in scenario (default {DEFAULT_SCENARIO}); overridden by --task. Options:{list(SCENARIOS.keys())}",
    )
    parser.add_argument(
        "--task",
        default=None,
        help="Custom task text, overrides --scenario; if not provided, uses the selected built-in scenario.",
    )
    parser.add_argument(
        "--role",
        "--starting-role",
        dest="role",
        choices=list(ROLES.keys()),
        default=DEFAULT_ROLE,
        help=f"Specify starting role (default {DEFAULT_ROLE} front triage). Options:{list(ROLES.keys())}",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive multi-turn mode: reuse the same orchestrator, roles and shared history persist across turns (Ctrl-C / type exit to quit).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override OPENAI_MODEL environment variable (defaults to environment variable, or gpt-5.6-luna if not set).",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=20,
        help="Hard upper limit on LLM rounds per single user message to prevent infinite loops (default 20).",
    )
    parser.add_argument(
        "--list-roles",
        action="store_true",
        help="Offline: print role roster and built-in scenarios then exit, no API Key needed (for self-check).",
    )
    return parser.parse_args()


def print_run_summary(orch: MultiRoleOrchestrator, final: str):
    """Print the handoff chain, division of labor overview, and final results for one run."""
    print(f"\n{C.BOLD}================ Run Summary ================{C.RESET}")
    print(f"{C.MAGENTA}Autonomous handoff chain:{C.RESET} {orch.handoff_chain_str()}")
    print(f"{C.MAGENTA}Handoff count:{C.RESET} {len(orch.handoffs)}")
    for i, h in enumerate(orch.handoffs, 1):
        print(f"  {i}. {h.from_role} → {h.to_role}  |  reason: {h.reason}")
    print(f"\n{C.MAGENTA}Role division (who used what tools, who produced the final response):{C.RESET}")
    print(orch.role_work_summary())
    print(f"\n{C.GREEN}Final result:{C.RESET}\n{final}")


def run_interactive(orch: MultiRoleOrchestrator):
    """Interactive multi-turn: same orchestrator reused across turns, shared history and current role persist."""
    print(
        f"{C.BOLD}=== Interactive Multi-turn Mode ==={C.RESET}\n"
        f"{C.DIM}Enter your request and press Enter; type exit / quit or press Ctrl-C to exit."
        f"Roles and conversation history persist across turns (shared context).{C.RESET}"
    )
    turn = 0
    while True:
        try:
            user_message = input(f"\n{C.BOLD}👤 You (current control is with {orch.current_role}）> {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExited interactive mode.")
            break
        if not user_message:
            continue
        if user_message.lower() in {"exit", "quit", "q"}:
            print("Exited interactive mode.")
            break
        turn += 1
        final = orch.run(user_message)
        print_run_summary(orch, final)


def main():
    args = parse_args()

    # ---- Offline self-check path: no API Key required ----
    if args.list_roles:
        print_roster()
        print_scenarios()
        return

    model = args.model or os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")

    # General fallback: prioritize direct connection to OPENAI_API_KEY; otherwise use OPENROUTER_API_KEY via OpenRouter;
    # If neither is set, report a clear error.
    # Special case: gpt-5.x series direct connection to OpenAI requires organization verification, and its /v1/chat/completions has limited support for
    # reasoning models with tools (reasoning_effort restriction). Therefore, if OPENROUTER_API_KEY is set,
    # gpt-5.x will prefer OpenRouter to avoid direct connection errors.
    prefer_openrouter = model.startswith("gpt-5") and os.environ.get("OPENROUTER_API_KEY")
    api_key = None if prefer_openrouter else os.environ.get("OPENAI_API_KEY")
    if api_key:
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    elif os.environ.get("OPENROUTER_API_KEY"):
        api_key = os.environ["OPENROUTER_API_KEY"]
        base_url = "https://openrouter.ai/api/v1"
        model = _to_openrouter_model(model)
        why = "gpt-5.x prefers OpenRouter" if prefer_openrouter else "OPENAI_API_KEY not detected"
        print(f"（{why}, switching to OpenRouter; model mapping is {model}）")
    else:
        print("Error: environment variable OPENAI_API_KEY or OPENROUTER_API_KEY not found. Please set and retry.",
              file=sys.stderr)
        print("(Tip: to only view the role/scenario list, run `python demo.py --list-roles`, no Key required.)",
              file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)

    print_roster()

    orch = MultiRoleOrchestrator(
        client=client,
        model=model,
        max_steps=args.max_steps,
        verbose=True,
        start_role=args.role,
    )

    if args.interactive:
        print(f"{C.BOLD}=== Model model={model}, starting role {args.role} ==={C.RESET}")
        run_interactive(orch)
        return

    # ---- Scripted: single composite task, run end-to-end once ----
    task = args.task if args.task is not None else SCENARIOS[args.scenario][0]
    scenario_tag = "Custom task" if args.task is not None else f"Scenario {args.scenario}"
    print(f"{C.BOLD}=== Starting execution ({scenario_tag}，model={model}, starting role={args.role}）==={C.RESET}")

    final = orch.run(task)
    print_run_summary(orch, final)


if __name__ == "__main__":
    main()
