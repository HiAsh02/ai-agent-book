"""
Experiment 10-1 Demo Entry: Run through the three stages of "Requirements Clarification -> Code Implementation -> Code Review" with a single command.

    python demo.py                 # Default task, default model, max 3 review rollbacks
    python demo.py --list-stages   # Offline view of three-stage configuration (no API Key needed)
    python demo.py --help          # View all optional parameters

Demo task: The user wants to "write a Python script to organize the Downloads folder."
The requirement itself is vague, so the Agent in the requirements clarification stage will proactively ask questions, answered automatically by a simulated user;
Then it enters the implementation stage to write code, and the review stage strictly checks (may roll back and rewrite).
"""

import argparse

from agent import StagedAgent, stage_overview
from config import Config


USER_TASK = "Help me write a Python script to organize the Downloads folder."
DEFAULT_MAX_REVISIONS = 3


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments. When no arguments are passed, the behavior is exactly the same as the original fixed script."""
    parser = argparse.ArgumentParser(
        prog="demo.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Experiment 10-1: Staged system prompts (Requirements Clarification -> Code Implementation -> Code Review) demo.\n"
            "The same Agent switches system prompts and tool sets across three stages, playing different roles,\n"
            "while the conversation history and task state are continuously shared across stages. Running without arguments is the default demo."
        ),
        epilog=(
            "Example:\n"
            "  python demo.py                        Default task, run through three stages\n"
            "  python demo.py --list-stages          Offline view of three-stage configuration (no API Key needed)\n"
            "  python demo.py --start-stage implementation   Skip requirements clarification, start from implementation stage\n"
            "  python demo.py --interactive          Answer questions yourself during requirements clarification stage\n"
            "  python demo.py --model gpt-5.6-luna --task 'Write a script to batch rename images'"
        ),
    )
    parser.add_argument(
        "--task",
        default=USER_TASK,
        help=f"User task given to the Agent (default: {USER_TASK!r}）",
    )
    parser.add_argument(
        "--start-stage",
        choices=["requirements", "implementation"],
        default="requirements",
        help=(
            "Stage to start from (default: requirements). Choosing implementation will preset a"
            "confirmed requirement equivalent to the output of requirements clarification, starting directly from the implementation stage, convenient for debugging the latter two stages alone."
            "(The review stage depends on the code produced by the implementation stage and cannot be used as a starting point.)"
        ),
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="In the requirements clarification stage, a real person answers the Agent's questions from standard input (default uses simulated user to answer automatically).",
    )
    parser.add_argument(
        "--max-revisions",
        type=int,
        default=DEFAULT_MAX_REVISIONS,
        help=f"Maximum number of rollbacks allowed in the review stage; exceeding this forces the demo to end (default: {DEFAULT_MAX_REVISIONS}）",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Override the model name specified by the OPENAI_MODEL environment variable (default: use environment variable, currently {Config.MODEL!r}）",
    )
    parser.add_argument(
        "--list-stages",
        action="store_true",
        help="Print the three stages (role/system prompt/tool set/transition signal) offline and exit, without calling any API.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Offline path: Only show three-stage configuration, no API Key needed, no requests made.
    if args.list_stages:
        print(stage_overview())
        return

    if args.model:
        Config.MODEL = args.model

    # First parse the provider (including OpenRouter fallback), ensuring the printed model/endpoint is the final effective value.
    Config.validate()
    print("Model: %s  | base_url: %s" % (Config.MODEL, Config.BASE_URL))
    agent = StagedAgent(
        max_revisions=args.max_revisions,
        verbose=True,
        interactive=args.interactive,
    )
    agent.run(args.task, start_stage=args.start_stage)
    agent.print_summary()

    # Print the final output main file, convenient for visually confirming that the implementation stage actually wrote code
    if agent.workspace.files:
        print("\n" + "=" * 70)
        print("Final output file content:")
        print("=" * 70)
        for path, content in agent.workspace.files.items():
            print(f"\n--- {path} ---\n{content}")


if __name__ == "__main__":
    main()
