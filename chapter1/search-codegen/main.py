"""
Main entry point for GPT-5 Native Tools Agent
Interactive CLI for using web_search and code_interpreter tools
"""

import sys
import json
import logging
from typing import Optional
from agent import GPT5NativeAgent, GPT5AgentChain
from config import Config
import argparse

# Set up logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)
logger = logging.getLogger(__name__)


class InteractiveCLI:
    """Interactive command-line interface for GPT-5 Agent"""
    
    def __init__(self):
        """Initialize the CLI"""
        if not Config.validate():
            raise ValueError("Invalid configuration. Please check your .env file")
        
        self.agent = GPT5NativeAgent(
            api_key=Config.OPENROUTER_API_KEY,
            base_url=Config.OPENROUTER_BASE_URL,
            model=Config.MODEL_NAME
        )
        
        self.commands = {
            "/help": self.show_help,
            "/clear": self.clear_history,
            "/history": self.show_history,
            "/tools": self.toggle_tools,
            "/search": self.search_mode,
            "/code": self.code_mode,
            "/analyze": self.analyze_mode,
            "/config": self.show_config,
            "/reasoning": self.set_reasoning_effort,
            "/exit": self.exit_cli,
            "/quit": self.exit_cli,
        }
        
        self.use_tools = True
        self.tool_choice = "auto"
        self.reasoning_effort = "low"  # Default reasoning effort
    
    def show_help(self):
        """Display help information"""
        help_text = """
Commands:                                              
  /help     - Show this help message                    
  /clear    - Clear conversation history                
  /history  - Show conversation history                 
  /tools    - Toggle tools on/off                       
  /search   - Enter web search mode                     
  /code     - Enter code interpreter mode               
  /analyze  - Combined search + analysis mode           
  /config   - Show current configuration                
  /reasoning - Set reasoning effort (low/medium/high)   
  /exit     - Exit the application                      
                                                        
Native Tools:                                           
  • web_search - Search the internet for real-time info 
  • code_interpreter - Execute Python code and analyze  
                                                        
Usage:                                                  
  Simply type your request and the agent will use       
  appropriate tools automatically.                      
                                                        
Examples:                                               
  "Which two capitals among the 10 ASEAN capitals are closest? Provide your detailed analysis and reasoning process."
  "Search Bitcoin price over the past year, calculate yield, maximum drawdown, annualized volatility and other key indicators."
        """
        print(help_text)
    
    def clear_history(self):
        """Clear conversation history"""
        self.agent.clear_history()
        print("✅ Conversation history cleared")
    
    def show_history(self):
        """Display conversation history"""
        history = self.agent.get_history()
        if not history:
            print("📭 No conversation history")
            return
        
        print("\n" + "="*60)
        print("CONVERSATION HISTORY")
        print("="*60)
        
        for i, msg in enumerate(history, 1):
            role = msg["role"].upper()
            content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
            print(f"\n[{i}] {role}:\n{content}")
        
        print("="*60)
    
    def toggle_tools(self):
        """Toggle tool usage on/off"""
        self.use_tools = not self.use_tools
        status = "enabled" if self.use_tools else "disabled"
        print(f"🔧 Tools {status}")
    
    def search_mode(self):
        """Enter web search mode"""
        print("\n🔍 Web Search Mode")
        print("Enter your search query (or 'back' to return):")
        
        query = input("> ").strip()
        if query.lower() == "back":
            return
        
        request = f"Search the web for: {query}"
        self._process_request(request, force_tools=True)
    
    def code_mode(self):
        """Enter code interpreter mode"""
        print("\n💻 Code Interpreter Mode")
        print("Enter your code or computational request (or 'back' to return):")
        
        request = input("> ").strip()
        if request.lower() == "back":
            return
        
        enhanced_request = f"Use the code interpreter to: {request}"
        self._process_request(enhanced_request, force_tools=True)
    
    def analyze_mode(self):
        """Combined search and analysis mode"""
        print("\n🔬 Search & Analyze Mode")
        print("Enter topic to research and analyze (or 'back' to return):")
        
        topic = input("> ").strip()
        if topic.lower() == "back":
            return
        
        print("\nOptional: Enter Python code for analysis (press Enter to skip):")
        code = input("> ").strip()
        
        if code:
            result = self.agent.search_and_analyze(topic, code)
        else:
            result = self.agent.search_and_analyze(topic)
        
        self._display_result(result)
    
    def show_config(self):
        """Display current configuration"""
        Config.display()
        print(f"\nCurrent Settings:")
        print(f"  Tools Enabled: {self.use_tools}")
        print(f"  Tool Choice: {self.tool_choice}")
        print(f"  Reasoning Effort: {self.reasoning_effort}")
    
    def set_reasoning_effort(self):
        """Set the reasoning effort level"""
        print("\n🧠 Set Reasoning Effort")
        print("Options: low, medium, high")
        print(f"Current: {self.reasoning_effort}")
        
        effort = input("Enter new effort level: ").strip().lower()
        if effort in ["low", "medium", "high"]:
            self.reasoning_effort = effort
            print(f"✅ Reasoning effort set to: {effort}")
        else:
            print(f"❌ Invalid effort level. Must be low, medium, or high")
    
    def exit_cli(self):
        """Exit the application"""
        print("\n👋 Goodbye!")
        sys.exit(0)
    
    def _process_request(self, request: str, force_tools: bool = False):
        """
        Process a user request
        
        Args:
            request: User request
            force_tools: Force tool usage regardless of settings
        """
        use_tools = force_tools or self.use_tools
        
        result = self.agent.process_request(
            request,
            use_tools=use_tools,
            tool_choice=self.tool_choice if use_tools else "none",
            temperature=Config.DEFAULT_TEMPERATURE,
            max_tokens=Config.DEFAULT_MAX_TOKENS,
            reasoning_effort=self.reasoning_effort
        )
        
        self._display_result(result)
    
    def _display_result(self, result: dict):
        """
        Display the result of a request
        
        Args:
            result: Result dictionary from agent
        """
        print("\n" + "="*60)
        
        if result["success"]:
            # Display tool usage
            if result["tool_calls"]:
                print("🔧 Tools Used:")
                for tool in result["tool_calls"]:
                    print(f"  • {tool.tool_type.value}")
                print()
            
            # Display response
            print("📝 Response:")
            print("-"*60)
            print(result["response"])
            print("-"*60)
            
            # Display token usage
            if result.get("usage"):
                usage = result["usage"]
                total = usage.get("total_tokens", 0)
                if total:
                    print(f"\n📊 Tokens used: {total}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
        
        print("="*60)
    
    def run(self):
        """Run the interactive CLI"""
        print("\n" + "="*60)
        print("     🤖 GPT-5 Native Tools Agent")
        print("     Powered by OpenRouter API")
        print("="*60)
        
        self.show_help()
        
        while True:
            try:
                print("\n💬 Enter your request (or /help for commands):")
                user_input = input("> ").strip()
                
                if not user_input:
                    continue
                
                # Check for commands
                if user_input.startswith("/"):
                    command = user_input.split()[0].lower()
                    if command in self.commands:
                        self.commands[command]()
                    else:
                        print(f"❌ Unknown command: {command}")
                        print("Type /help for available commands")
                else:
                    # Process as regular request
                    self._process_request(user_input)
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted. Type /exit to quit or continue chatting.")
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                print(f"❌ An error occurred: {str(e)}")


def _run_single(args):
    """Execute single request (single / dry-run mode), print readable trace and save results as needed."""
    # dry-run only assembles the request body without network access, so no real API Key is needed
    api_key = Config.OPENROUTER_API_KEY or ("sk-or-DRYRUN-PLACEHOLDER" if args.dry_run else "")

    agent = GPT5NativeAgent(
        api_key=api_key,
        base_url=Config.OPENROUTER_BASE_URL,
        model=args.model or Config.MODEL_NAME
    )

    result = agent.process_request(
        args.request,
        use_tools=not args.no_tools,
        temperature=Config.DEFAULT_TEMPERATURE,
        max_tokens=Config.DEFAULT_MAX_TOKENS,
        reasoning_effort=args.reasoning,
        verbosity=args.verbosity,
        dry_run=args.dry_run
    )

    # dry-run: print the complete request body (native tool definitions + parameters) to be sent to the model
    if result.get("dry_run"):
        print("\n" + "=" * 60)
        print("🧪 Dry-run: Below is the request body to be sent to GPT-5 (no network)")
        print("=" * 60)
        print(f"Model: {result['model']}")
        print(f"Task: {args.request}")
        print("-" * 60)
        print(json.dumps(result["request"], indent=2, ensure_ascii=False))
        print("=" * 60)
    elif result["success"]:
        print("\n" + "=" * 60)
        print("📝 Response:")
        print("-" * 60)
        print(result["response"])
        print("-" * 60)
        usage = result.get("usage") or {}
        if usage:
            print(
                f"📊 Tokens - Input: {usage.get('input_tokens', 'N/A')}, "
                f"Output: {usage.get('output_tokens', 'N/A')}, "
                f"Reasoning: {usage.get('output_tokens_details', {}).get('reasoning_tokens', 0)}, "
                f"Total: {usage.get('total_tokens', 'N/A')}"
            )
        print("=" * 60)
    else:
        print(f"❌ Error: {result.get('error')}")

    # Optionally save the complete result (including trace/request body) as JSON for review
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"💾 Result saved to: {args.output}")

    if not result["success"]:
        sys.exit(1)


def main():
    """Main entry: parse command line arguments and dispatch to interactive / single / test mode."""
    parser = argparse.ArgumentParser(
        description="GPT-5 Native Tool Agent —— Demo Experiment 1.3: Native Deep Research capability with web search + code interpreter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python main.py                                    # Interactive mode (default)
  python main.py --mode single --request "Which two capitals among the 10 ASEAN capitals are closest?"
  python main.py --mode single --request "Analyze Bitcoin trend over the past month" --reasoning high --verbosity high
  python main.py --mode single --request "..." --output result.json
  python main.py --dry-run --request "..."          # Offline view request body (native tool definitions), no API Key needed
  python main.py --mode test --test basic           # Run specified test case
""",
    )

    parser.add_argument(
        "--mode",
        choices=["interactive", "single", "test"],
        default="interactive",
        help="Run mode: interactive conversation (default) / single request / test run",
    )
    parser.add_argument(
        "--request",
        type=str,
        help="Task or query content in single / dry-run mode",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Override model name (default from config {Config.MODEL_NAME}）",
    )
    parser.add_argument(
        "--reasoning",
        choices=["low", "medium", "high"],
        default="low",
        help="Reasoning Effort (low/medium/high, default low)",
    )
    parser.add_argument(
        "--verbosity",
        choices=["low", "medium", "high"],
        default=None,
        help="Verbosity (low/medium/high, default follows model)",
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable native tools (web_search / code_interpreter)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save complete result (including trace/request body) as JSON file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Assemble and print request body offline (including native tool definitions), no API call, no API Key needed",
    )
    parser.add_argument(
        "--test",
        type=str,
        help="Run specified test case in test mode (basic/analysis/complex/code/reasoning/search_analyze/chain)",
    )

    args = parser.parse_args()

    # dry-run: offline path, skip API Key validation
    if args.dry_run:
        if not args.request:
            print("❌ --dry-run requires --request")
            sys.exit(1)
        _run_single(args)
        return

    # Other modes require valid configuration
    if not Config.validate():
        print("❌ Configuration error!")
        print("Please create .env file and fill in OPENROUTER_API_KEY")
        print("\nExample .env:")
        print("OPENROUTER_API_KEY=sk-or-v1-your-key-here")
        sys.exit(1)

    if args.mode == "interactive":
        cli = InteractiveCLI()
        cli.run()

    elif args.mode == "single":
        if not args.request:
            print("❌ single mode requires --request parameter")
            sys.exit(1)
        _run_single(args)

    elif args.mode == "test":
        from test_agent import TestGPT5Agent, run_single_test

        if args.test:
            run_single_test(args.test)
        else:
            tester = TestGPT5Agent()
            tester.run_all_tests()


if __name__ == "__main__":
    main()
