"""
Main Program - Web Search Agent Usage Example

Demonstrates the ReAct loop (Reasoning + Acting) from Chapter 1: the model first thinks, then calls the $web_search
action, observes the search results, and continues thinking until it synthesizes a final answer. The ReAct trace is printed step by step during execution.
"""

import os
import sys
import json
import argparse
import logging
from typing import Optional
from agent import WebSearchAgent, run_offline_demo
from config import Config

# Set up logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)
logger = logging.getLogger(__name__)


def _save_output(path: str, payload: dict):
    """Save the question, ReAct trace, and answer as a JSON file"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Results saved to: {path}")


def run_interactive_mode(agent: WebSearchAgent, output: Optional[str] = None):
    """
    Interactive Mode - Continuous conversation with the Agent

    Args:
        agent: WebSearchAgent instance
        output: optional, path to JSON file for saving each Q&A trace
    """
    print("\n" + "="*60)
    print("🤖 Kimi Web Search Agent - Interactive Mode")
    print("="*60)
    print("Enter your question, the Agent will automatically search and answer")
    print("Type 'quit' or 'exit' to exit")
    print("Type 'clear' to clear conversation history")
    print("="*60 + "\n")

    while True:
        try:
            # Get user input
            user_input = input("Your question: ").strip()

            # Check exit command
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break

            # Check clear command
            if user_input.lower() == 'clear':
                agent.clear_history()
                print("✅ Conversation history cleared\n")
                continue

            # Check empty input
            if not user_input:
                print("❌ Please enter a question\n")
                continue

            # Show thinking
            print("\n🔍 Agent is searching and thinking (ReAct trace below)...\n")

            # Get answer (trace already printed in agent when verbose=True)
            answer = agent.search_and_answer(user_input, max_iterations=Config.MAX_SEARCH_ITERATIONS)

            # Show answer
            print("\n" + "="*60)
            print("📝 Agent answer:")
            print("-"*60)
            print(answer)
            print("="*60 + "\n")

            if output:
                _save_output(output, {"question": user_input,
                                      "trace": agent.get_trace(),
                                      "answer": answer})

        except KeyboardInterrupt:
            print("\n\n👋 Interrupt detected, exiting program")
            break
        except Exception as e:
            logger.error(f"Error processing question: {str(e)}")
            print(f"\n❌ Error: {str(e)}\n")


def run_single_question(agent: WebSearchAgent, question: str,
                        max_iterations: int, output: Optional[str] = None):
    """
    Single Question Mode - Answer one question then exit

    Args:
        agent: WebSearchAgent instance
        question: the question to answer
        max_iterations: maximum ReAct iterations
        output: optional, path to JSON file for saving trace
    """
    print("\n" + "="*60)
    print("🤖 Kimi Web Search Agent")
    print("="*60)
    print(f"Question: {question}")
    print("-"*60)
    print("🔍 ReAct trace (Think → Act → Observe):\n")

    try:
        answer = agent.search_and_answer(question, max_iterations=max_iterations)
        print("\n📝 Answer:")
        print("-"*60)
        print(answer)
        print("="*60 + "\n")

        if output:
            _save_output(output, {"question": question,
                                  "trace": agent.get_trace(),
                                  "answer": answer})
    except Exception as e:
        logger.error(f"Error processing question: {str(e)}")
        print(f"\n❌ Error: {str(e)}\n")


def build_parser() -> argparse.ArgumentParser:
    """Build command-line argument parser (Chinese help)"""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Kimi Web Search Agent — Demonstrates a search agent using the ReAct loop (Think → Act → Observe).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python main.py                                  # Interactive mode
  python main.py "Who won the 2024 Nobel Prize in Physics?"    # Single query, prints ReAct trace
  python main.py --provider offline-demo          # Offline demo of ReAct loop (no API Key needed)
  python main.py "Bitcoin current price" --max-steps 3 --output result.json
""",
    )
    parser.add_argument("query", nargs="*",
                        help="Question to ask; omit to enter interactive mode")
    parser.add_argument("--provider", choices=["kimi", "offline-demo"], default="kimi",
                        help="Search backend: kimi=uses Kimi's built-in $web_search (requires API Key);"
                             "offline-demo=offline replay of example trace (default kimi)")
    parser.add_argument("--model", default=Config.DEFAULT_MODEL,
                        help=f"Model name to use (default {Config.DEFAULT_MODEL}）")
    parser.add_argument("--max-steps", type=int, default=Config.MAX_SEARCH_ITERATIONS,
                        help=f"Maximum ReAct iterations (default {Config.MAX_SEARCH_ITERATIONS}）")
    parser.add_argument("--base-url", default=Config.KIMI_BASE_URL,
                        help=f"API base URL (default {Config.KIMI_BASE_URL}）")
    parser.add_argument("--api-key", default=None,
                        help="Kimi API Key (default read from MOONSHOT_API_KEY / KIMI_API_KEY environment variables)")
    parser.add_argument("--output", "-o", default=None,
                        help="Save question, ReAct trace, and answer to specified JSON file")
    parser.add_argument("--quiet", action="store_true",
                        help="Do not print ReAct trace in real time (default prints)")
    return parser


def main(argv: Optional[list] = None):
    """Main function: parse command-line arguments and dispatch to appropriate mode"""
    parser = build_parser()
    args = parser.parse_args(argv)
    question = " ".join(args.query).strip()

    #  Offline demo mode: no API Key needed, replays example trace to show ReAct loop
    if args.provider == "offline-demo":
        demo_question = question or "What is Moonshot AI's Context Caching technology?"
        print("\n" + "="*60)
        print("🧪 Offline demo mode (example trace, not real search results)")
        print("="*60)
        print(f"Question: {demo_question}")
        print("-"*60)
        print("🔍 ReAct trace (Think → Act → Observe):\n")
        result = run_offline_demo(demo_question, verbose=not args.quiet)
        print("\n📝 Answer:")
        print("-"*60)
        print(result["answer"])
        print("="*60 + "\n")
        if args.output:
            _save_output(args.output, result)
        return

    #  Online mode: requires API Key
    api_key = Config.get_api_key(args.api_key)
    if not api_key and not os.getenv("OPENROUTER_API_KEY"):
        Config.validate()
        print("Tip: You can also set OPENROUTER_API_KEY as a general fallback.")
        sys.exit(1)

    #  Creating Agent
    try:
        agent = WebSearchAgent(
            api_key=api_key,
            base_url=args.base_url,
            model=args.model,
            verbose=not args.quiet,
        )
        logger.info("Agent initialized successfully")
    except Exception as e:
        logger.error(f"Agent initialization failed: {str(e)}")
        sys.exit(1)

    #  If there is a question, answer once; otherwise enter interactive mode
    if question:
        run_single_question(agent, question, args.max_steps, args.output)
    else:
        run_interactive_mode(agent, args.output)


if __name__ == "__main__":
    main()
