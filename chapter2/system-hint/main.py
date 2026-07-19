"""
Main entry point for System-Hint Enhanced Agent
Supports command-line tasks and interactive mode
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from agent import SystemHintAgent, SystemHintConfig, TodoStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def print_result(result: dict):
    """Print formatted result"""
    if result.get('success'):
        print("\n✅ Task completed successfully!")
        if result.get('final_answer'):
            print("\n📝 Final Answer:")
            print("-"*40)
            print(result['final_answer'])
    else:
        print("\n❌ Task failed!")
        if result.get('error'):
            print(f"Error: {result['error']}")
    
    print(f"\n📊 Statistics:")
    print(f"  - Iterations: {result.get('iterations', 0)}")
    print(f"  - Tool calls: {len(result.get('tool_calls', []))}")
    
    if result.get('trajectory_file'):
        print(f"\n💾 Trajectory saved to: {result['trajectory_file']}")
    
    if result.get('todo_list'):
        print(f"\n📋 Final TODO List:")
        for item in result['todo_list']:
            status_emoji = {
                'pending': '⏳',
                'in_progress': '🔄',
                'completed': '✅',
                'cancelled': '❌'
            }.get(item['status'], '❓')
            print(f"  [{item['id']}] {status_emoji} {item['content']} ({item['status']})")
    
    # Show tool call summary
    if result.get('tool_calls'):
        print(f"\n🔧 Tool Call Summary:")
        tool_summary = {}
        for call in result['tool_calls']:
            tool_name = call.tool_name
            if tool_name not in tool_summary:
                tool_summary[tool_name] = {
                    'count': 0,
                    'success': 0,
                    'failed': 0
                }
            tool_summary[tool_name]['count'] += 1
            if call.error:
                tool_summary[tool_name]['failed'] += 1
            else:
                tool_summary[tool_name]['success'] += 1
        
        for tool_name, stats in tool_summary.items():
            print(f"  - {tool_name}: {stats['count']} calls "
                  f"({stats['success']} success, {stats['failed']} failed)")


def get_sample_task() -> str:
    """Get the sample task for summarizing week1 and week2 projects"""
    return """Analyze and summarize the AI Agent projects in week1 and week2 directories. Create a comprehensive analysis file 'project_analysis_report.md' containing:

   - Overview of all the projects in week1 and week2 directories
   - What you have learned from the projects
    """


def execute_single_task(task: str, config: SystemHintConfig = None, verbose: bool = False,
                        provider: str = "kimi", model: str = None):
    """Execute a single task with the agent"""
    api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: Please set KIMI_API_KEY environment variable")
        print("   export KIMI_API_KEY='your-api-key-here'")
        print("   (If you only want to preview the status bar effect offline, run python main.py --mode preview)")
        return None

    if config is None:
        config = SystemHintConfig(
            enable_timestamps=True,
            enable_tool_counter=True,
            enable_todo_list=True,
            enable_detailed_errors=True,
            enable_system_state=True
        )

    agent = SystemHintAgent(
        api_key=api_key,
        provider=provider,
        model=model,
        config=config,
        verbose=verbose
    )
    
    # For project analysis tasks, navigate to parent directory
    if "week1" in task.lower() and "week2" in task.lower():
        agent.current_directory = str(Path(__file__).parent.parent)
        print(f"📁 Working directory set to: {agent.current_directory}")
    
    print("\n🚀 Executing task...")
    result = agent.execute_task(task, max_iterations=30)
    return result


def interactive_mode():
    """Run the agent in interactive mode"""
    print_section("Interactive Mode - System-Hint Agent")
    
    api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Error: Please set KIMI_API_KEY environment variable")
        print("   export KIMI_API_KEY='your-api-key-here'")
        return
    
    # Initialize agent with full features
    config = SystemHintConfig(
        enable_timestamps=True,
        enable_tool_counter=True,
        enable_todo_list=True,
        enable_detailed_errors=True,
        enable_system_state=True
    )
    
    agent = SystemHintAgent(
        api_key=api_key,
        provider="kimi",
        config=config,
        verbose=False
    )
    
    print("\n✅ Agent initialized with full system hints")
    print("\nAvailable commands:")
    print("  'sample' - Run the sample project analysis task")
    print("  'reset'  - Reset agent state and conversation")
    print("  'config' - Show current configuration")
    print("  'quit'   - Exit interactive mode")
    print("\nOr enter any task for the agent to complete.")
    
    while True:
        try:
            print("\n" + "-"*60)
            user_input = input("Task > ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("👋 Goodbye!")
                break
            
            elif user_input.lower() == 'sample':
                task = get_sample_task()
                print("\n📋 Running sample task:")
                print(task)
                
                # Navigate to parent directory for project analysis
                original_dir = agent.current_directory
                agent.current_directory = str(Path(__file__).parent.parent)
                
                result = agent.execute_task(task, max_iterations=100)
                print_result(result)
                
                # Restore directory
                agent.current_directory = original_dir
                
            elif user_input.lower() == 'reset':
                agent.reset()
                print("✅ Agent state reset")
                
            elif user_input.lower() == 'config':
                print("\n📋 Current Configuration:")
                print(f"  - Timestamps: {'✅' if config.enable_timestamps else '❌'}")
                print(f"  - Tool Counter: {'✅' if config.enable_tool_counter else '❌'}")
                print(f"  - TODO List: {'✅' if config.enable_todo_list else '❌'}")
                print(f"  - Detailed Errors: {'✅' if config.enable_detailed_errors else '❌'}")
                print(f"  - System State: {'✅' if config.enable_system_state else '❌'}")
                print(f"  - Current Directory: {agent.current_directory}")
                
            else:
                # Execute user task
                result = agent.execute_task(user_input, max_iterations=25)
                print_result(result)
                
        except KeyboardInterrupt:
            print("\n\n⚠️ Interrupted. Type 'quit' to exit.")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            logger.error(f"Error in interactive mode: {e}", exc_info=True)


def demo_basic_features():
    """Demonstrate basic system hint features"""
    print_section("Demo: Basic System Hint Features")
    
    api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Please set KIMI_API_KEY environment variable")
        return
    
    config = SystemHintConfig(
        enable_timestamps=True,
        enable_tool_counter=True,
        enable_todo_list=True,
        enable_detailed_errors=True,
        enable_system_state=True
    )
    
    agent = SystemHintAgent(
        api_key=api_key,
        provider="kimi",
        config=config,
        verbose=False
    )
    
    task = """Please complete the following tasks:
    1. Create a test directory called 'demo_output'
    2. Write a Python script that counts files in the current directory
    3. Execute the script and save the output
    4. Create a summary report of what was done
    
    Use the TODO list to track your progress."""
    
    result = agent.execute_task(task)
    print_result(result)


def demo_tool_loop_prevention():
    """Demonstrate tool call loop prevention"""
    print_section("Demo: Tool Call Loop Prevention")
    
    api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Please set KIMI_API_KEY environment variable")
        return
    
    config = SystemHintConfig(
        enable_timestamps=False,
        enable_tool_counter=True,
        enable_todo_list=False,
        enable_detailed_errors=True,
        enable_system_state=False
    )
    
    agent = SystemHintAgent(
        api_key=api_key,
        provider="kimi",
        config=config,
        verbose=False
    )
    
    task = """Try to read a file called 'nonexistent_file.txt' up to 3 times.
    After each failed attempt, note the failure and stop after 3 attempts."""
    
    result = agent.execute_task(task, max_iterations=10)
    print_result(result)
    
    if result.get('tool_calls'):
        read_file_calls = [c for c in result['tool_calls'] if c.tool_name == 'read_file']
        print(f"\n🛡️ Tool counter prevented loop: {len(read_file_calls)} read_file attempts")
        for call in read_file_calls:
            print(f"  - Call #{call.call_number}: {'Failed' if call.error else 'Success'}")


def demo_comparison():
    """Compare with and without system hints"""
    print_section("Demo: System Hints Comparison")
    
    api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Please set KIMI_API_KEY environment variable")
        return
    
    task = """Create a simple Python script that prints 'Hello World' and save it as 'hello.py'."""
    
    # With system hints
    print("\n📋 WITH System Hints:")
    config_with = SystemHintConfig(
        enable_timestamps=True,
        enable_tool_counter=True,
        enable_todo_list=True,
        enable_detailed_errors=True,
        enable_system_state=True
    )
    
    agent_with = SystemHintAgent(
        api_key=api_key,
        provider="kimi",
        config=config_with,
        verbose=False
    )
    
    result_with = agent_with.execute_task(task, max_iterations=10)
    print(f"  - Success: {result_with.get('success')}")
    print(f"  - Iterations: {result_with.get('iterations')}")
    print(f"  - Tool calls: {len(result_with.get('tool_calls', []))}")
    
    # Without system hints
    print("\n📋 WITHOUT System Hints:")
    config_without = SystemHintConfig(
        enable_timestamps=False,
        enable_tool_counter=False,
        enable_todo_list=False,
        enable_detailed_errors=False,
        enable_system_state=False
    )
    
    agent_without = SystemHintAgent(
        api_key=api_key,
        provider="kimi",
        config=config_without,
        verbose=False
    )
    
    result_without = agent_without.execute_task(task, max_iterations=10)
    print(f"  - Success: {result_without.get('success')}")
    print(f"  - Iterations: {result_without.get('iterations')}")
    print(f"  - Tool calls: {len(result_without.get('tool_calls', []))}")
    
    print("\n💡 System hints typically lead to more efficient task completion!")


def preview_status_bar(config: SystemHintConfig):
    """Offline preview: How five status bar (system hint) techniques change the context seen by the model.

    Corresponds to the five techniques in Experiment 2-8 of the book. The entire process is rendered locally, **no LLM calls are made, so no API Key is required**. Each case provides a side-by-side comparison of "without status bar vs. with status bar", intuitively showing the explicit state injected by the Agent framework at the end of the context.
    """
    from datetime import datetime as _dt

    print_section("Offline preview: How Agent status bar (System Hint) changes context")
    print(
        "Description: Each case below compares [without status bar] (model sees only raw trajectory) with\n"
        "      [with status bar] (framework distills implicit state into explicit knowledge and injects it at the end of the context).\n"
        "      Scenarios are taken from the Xfinity refund case in the book, all rendered locally without calling any API."
    )

    # Construct an Agent with a placeholder key; no network connection during construction. Fix the simulation time for stable and reproducible output.
    agent = SystemHintAgent(
        api_key="offline-preview",
        provider="kimi",
        config=config,
        verbose=False,
    )
    agent.config.simulate_time_delay = True
    agent.simulated_time = _dt(2025, 9, 14, 10, 30, 45)

    enabled = []

    # --- Case 1: Timestamp tracking -------------------------------------------------
    if config.enable_timestamps:
        enabled.append("Timestamp tracking")
        print("\n【Case 1 · Timestamp tracking】Add time prefixes to user messages and tool results")
        follow_up = "Can you call them again to follow up?"
        print("-" * 60)
        print("  Without status bar:" + follow_up)
        print("  With status bar:" + f"[{agent._get_timestamp()}] " + follow_up)
        print("  → Agent can understand the temporal relationship between \"yesterday's file\" and \"today's modification\".")

    # --- Case 2: Tool call counter -------------------------------------------
    if config.enable_tool_counter:
        enabled.append("Tool call counter")
        print("\n【Case 2 · Tool call counter】Annotate tool results with the call number")
        raw_result = json.dumps({"success": True, "output": "Call connected, no answer"})
        #  Reuse meta-information from execute_task to format the annotation
        metadata = []
        if config.enable_timestamps:
            metadata.append(f"[{agent._get_timestamp()}]")
        metadata.append("[Tool call #3 for 'phone_call']")
        print("-" * 60)
        print("  Without status bar:" + raw_result)
        print("  With status bar:" + " ".join(metadata) + "\n            " + raw_result)
        print("  → Explicit counting triggers the model's pattern recognition: actively stops when reaching the 3/3 limit, no longer repeats calls.")

    # --- Case 3: TODO list management -------------------------------------------
    if config.enable_todo_list:
        enabled.append("TODO list management")
        print("\n【Case 3 · TODO list management】Decompose multi-step tasks and continuously restate them")
        agent._tool_rewrite_todo_list(items=[
            "Call Xfinity customer service to verify refund policy",
            "Submit refund request",
            "Confirm refund received",
        ])
        agent._tool_update_todo_status(updates=[
            {"id": 1, "status": "completed"},
            {"id": 2, "status": "in_progress"},
        ])
        print("-" * 60)
        print("  Without status bar: (model must recall remaining subtasks from the long trajectory, prone to omissions)")
        print("  With status bar:")
        for line in agent._format_todo_list().splitlines():
            print("    " + line)
        print("  → TODO list acts as external memory, ensuring actions align with the overall plan.")

    # --- Case 4: Detailed error information -------------------------------------------
    if config.enable_detailed_errors:
        enabled.append("Detailed error information")
        print("\n【Case 4 · Detailed error information】Upgrade bare exceptions to diagnostics with fix suggestions")
        exc = FileNotFoundError("File not found: /home/user/refund_policy.txt")
        detailed = agent._get_detailed_error(
            exc, "read_file", {"file_path": "refund_policy.txt"}
        )
        print("-" * 60)
        print("  Without status bar:" + str(exc))
        print("  With status bar:")
        for line in detailed.splitlines():
            print("    " + line)
        print("  → Agent shifts from blind retries to analytical problem solving (verify path, check directory, use absolute path).")

    # --- Case 5: System State Awareness -------------------------------------------
    if config.enable_system_state:
        enabled.append("System State Awareness")
        print("\n[Case 5 · System State Awareness] Inject current time, directory, OS, Shell, Python version")
        print("-" * 60)
        print("  No status bar: (model doesn't know which directory or OS it's in)")
        print("  With status bar:")
        for line in agent._get_system_state().splitlines():
            print("    " + line)
        print("  → OS info enables platform-specific decisions (Linux uses apt, macOS uses brew).")

    # --- Summary: Full status bar appended to context end ---------------------------
    print_section("Status bar actually appended to context end (a role=user message)")
    hint = agent._get_system_hint()
    if hint:
        print(hint)
        print(
            "\nNote: This message has role=user, but content is auto-generated by Agent framework,"
            "appended at the very end of context—\nadjacent to the model's next token to generate, thus receiving highest attention weight;"
            "and because it's \"appended\" rather than \n\"modified\", the previously cached KV Cache prefix is unaffected."
        )
    else:
        print("(Under current config, system state and TODO are both disabled, no status bar to inject.)")

    print("\nTechniques enabled in this preview:" + ("、".join(enabled) if enabled else "(All disabled)"))
    print("Tip: Use --no-timestamps / --no-counter / --no-todo / --no-errors / --no-state")
    print("      to disable each category and observe context differences.")


def main():
    """Main function with command-line argument support"""
    parser = argparse.ArgumentParser(
        description=(
            "System-Hint Enhanced AI Agent (corresponding to Experiment 2-8 \"Agent Status Bar\" in the book)\n"
            "Demonstrates how five status bar techniques extract implicit state from context into explicit knowledge,"
            "thereby changing Agent behavior."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Preview status bar effect offline (no API Key needed, recommended to run first)\n"
            "  python main.py --mode preview\n"
            "  # View before/after comparison of a single technique (e.g., disable other four categories)\n"
            "  python main.py --mode preview --no-todo --no-errors --no-state --no-timestamps\n"
            "  # Execute a single task with a real model (requires KIMI_API_KEY)\n"
            "  python main.py --mode single --task \"create a hello world script\"\n"
            "  # Compare actual execution effect with status bar enabled/disabled\n"
            "  python main.py --mode demo --demo comparison\n"
        ),
    )

    parser.add_argument(
        "--mode",
        choices=["preview", "single", "interactive", "demo", "sample"],
        default="interactive",
        help=(
            "Execution mode: preview=offline preview status bar (no API Key);"
            "single=execute single task; interactive=interactive mode (default);"
            "demo=run built-in demo; sample=run sample task"
        )
    )

    parser.add_argument(
        "--task",
        type=str,
        help="Task description to execute (required for single mode)"
    )

    parser.add_argument(
        "--demo",
        choices=["basic", "loop", "comparison"],
        help="Demo to run (demo mode): basic=comprehensive demo, loop=loop protection, comparison=status bar enabled/disabled comparison"
    )

    parser.add_argument(
        "--provider",
        type=str,
        default="kimi",
        help="LLM provider (default: kimi, compatible with moonshot)"
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name override (default determined by provider, e.g., kimi-k3)"
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Trajectory output file path (default: trajectory.json)"
    )

    parser.add_argument(
        "--no-timestamps",
        action="store_true",
        help="Disable timestamp tracking"
    )

    parser.add_argument(
        "--no-counter",
        action="store_true",
        help="Disable tool call counter"
    )

    parser.add_argument(
        "--no-todo",
        action="store_true",
        help="Disable TODO list management"
    )

    parser.add_argument(
        "--no-errors",
        action="store_true",
        help="Disable detailed error messages"
    )

    parser.add_argument(
        "--no-state",
        action="store_true",
        help="Disable system status awareness"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Output detailed logs"
    )

    args = parser.parse_args()

    # Configure based on command-line flags
    config = SystemHintConfig(
        enable_timestamps=not args.no_timestamps,
        enable_tool_counter=not args.no_counter,
        enable_todo_list=not args.no_todo,
        enable_detailed_errors=not args.no_errors,
        enable_system_state=not args.no_state
    )
    if args.output:
        config.trajectory_file = args.output

    print("\n" + "🤖"*40)
    print("  SYSTEM-HINT ENHANCED AGENT")
    print("🤖"*40)

    if args.mode == "preview":
        preview_status_bar(config)

    elif args.mode == "single":
        if not args.task:
            print("❌ Error: --task required for single mode")
            print("Example: python main.py --mode single --task 'Create a hello world script'")
            sys.exit(1)
        
        result = execute_single_task(args.task, config, verbose=args.verbose,
                                     provider=args.provider, model=args.model)
        if result:
            print_result(result)

    elif args.mode == "sample":
        # Run the sample task
        task = get_sample_task()
        print("\n📋 Running sample task:")
        print("-"*60)
        print(task)
        print("-"*60)

        result = execute_single_task(task, config, verbose=args.verbose,
                                     provider=args.provider, model=args.model)
        if result:
            print_result(result)
    
    elif args.mode == "demo":
        if args.demo == "basic":
            demo_basic_features()
        elif args.demo == "loop":
            demo_tool_loop_prevention()
        elif args.demo == "comparison":
            demo_comparison()
        else:
            # Run all demos
            print("\nRunning all demonstrations...")
            demo_basic_features()
            input("\nPress Enter to continue...")
            demo_tool_loop_prevention()
            input("\nPress Enter to continue...")
            demo_comparison()
    
    else:  # interactive mode
        interactive_mode()
    
    print("\n👋 Thank you for using System-Hint Enhanced Agent!")


if __name__ == "__main__":
    main()
