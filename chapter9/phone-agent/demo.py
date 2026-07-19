"""
Experiment 9-2 Demo: Complete a phone task using ReAct Agent + PineClaw Voice (simulated).

Run:
    python demo.py

It will actually call OpenAI: while driving the upper-layer ReAct Agent's decision-making, inside make_phone_call it
uses OpenAI to play the role of the callee (IVR + customer service) to complete an entire multi-turn call, and finally prints:
  (a) The Agent's ReAct trajectory (thinking + initiating make_phone_call)
  (b) The returned structured call record (multi-turn transcript + whether goal achieved + key fields)
  (c) The Agent's final report to the user based on the call result
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from agent import run_agent


def _hr(title: str = "") -> None:
    line = "─" * 72
    if title:
        print(f"\n{line}\n{title}\n{line}")
    else:
        print(line)


def _print_record(rec: dict) -> None:
    print(f"  call_id        : {rec['call_id']}")
    print(f"  Callee Number       : {rec['phone_number']}")
    print(f"  Status             : {rec['status']}  |  Goal Achieved   : {rec['goal_achieved']}")
    print(f"  Call Duration (sim): {rec['duration_seconds']} seconds")
    print(f"  Summary            : {rec['summary']}")
    print("  Key Fields:")
    if rec["key_fields"]:
        for k, v in rec["key_fields"].items():
            print(f"      - {k}: {v}")
    else:
        print("      (none)")
    print(f"  Follow-up Needed   : {rec['follow_up_needed']}  {rec.get('follow_up_reason', '')}")
    print("  Call Transcript:")
    for turn in rec["transcript"]:
        speaker = turn["speaker"]
        #  Simple alignment: Voice Agent uses >>, callee uses <<
        arrow = ">>" if speaker == "Voice Agent" else "<<"
        print(f"      {arrow} [{speaker}] {turn['text']}")


_DEFAULT_TASK = (
    "Please call the broadband customer service (hotline 10010) to inquire why my monthly bill was overcharged by 50 yuan this month,"
    "ask them to explain the reason clearly, and if it's a mistaken charge, please have them handle it. My broadband account is hz-88231."
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Experiment 9-2: ReAct Phone Agent using PineClaw Voice (make_phone_call) as a tool."
                    "Given a natural language phone task, the Agent decides the number/goal/context and (simulated) dials,"
                    "reads the structured call record, and reports back to the user.",
        epilog="Example: \n"
               "  python demo.py                       # Default broadband bill task in the book (requires OPENAI_API_KEY)\n"
               "  python demo.py --dry-run             # Fully offline: scripted ReAct trajectory, no API Key needed\n"
               "  python demo.py --task \"Call the restaurant to book a table for 4 at 7pm tonight\" --phone 021-8888\n"
               "  python demo.py --model gpt-5.6-luna        # Override model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--task", default=_DEFAULT_TASK,
                   help="Custom phone task (natural language). Default uses the broadband bill example from the book.")
    p.add_argument("--phone", default=None, metavar="Number",
                   help="Optional: the callee's phone number. When given, it is provided to the Agent as known information (under dry-run, directly used as the callee number).")
    p.add_argument("--goal", default=None, metavar="Goal",
                   help="Optional: the explicit call goal. When given, it is provided to the Agent as known information (under dry-run, directly used as the call goal).")
    p.add_argument("--model", default=None, metavar="Model",
                   help="Optional: override the model used (defaults to environment variable OPENAI_MODEL, i.e., gpt-5.6-luna).")
    p.add_argument("--dry-run", action="store_true",
                   help="Offline script mode: no internet, no API key required, only demonstrates the shape of the ReAct loop and data contract.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dry_run and not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")):
        print("Error: OPENAI_API_KEY or OPENROUTER_API_KEY not detected. Please copy env.example to .env "
              "and fill in at least one, or use python demo.py --dry-run to run a fully offline script demo.")
        sys.exit(1)

    # Example task from the book: Note that only the natural language task is given; the Agent must determine the call parameters itself.
    task = args.task

    _hr("User Task")
    print(task)
    if args.dry_run:
        print("\n[Mode] dry-run offline script simulation: The following traces and call records are fixed scripts,"
              "no LLM/phone API calls are made, only used to demonstrate the shape of the ReAct loop.")

    _hr("ReAct Agent Trace")

    def on_event(kind: str, payload) -> None:
        if kind == "think":
            print(f"\n[Agent Thought] {payload}")
        elif kind == "call":
            print("\n[Agent Tool Call make_phone_call] Parameters:")
            print(f"    phone_number = {payload.get('phone_number')}")
            print(f"    goal         = {payload.get('goal')}")
            print(f"    context      = {payload.get('context', '')}")
        elif kind == "record":
            print("\n[PineClaw returns structured call record]")
            _print_record(payload)
        elif kind == "final":
            pass  # Final report printed separately

    final = run_agent(
        task,
        on_event=on_event,
        model=args.model,
        phone_hint=args.phone,
        goal_hint=args.goal,
        dry_run=args.dry_run,
    )

    _hr("Agent's final report to the user")
    print(final)
    print()


if __name__ == "__main__":
    main()
