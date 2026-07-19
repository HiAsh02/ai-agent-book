#!/usr/bin/env python3
"""
Quick Start Script - One-Click Experience of Kimi Web Search Agent
"""

import os
import sys
from agent import WebSearchAgent
from config import Config

# Color Output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_colored(text, color):
    """Print colored text"""
    print(f"{color}{text}{Colors.END}")


def print_banner():
    """Print welcome banner"""
    banner = """
╔══════════════════════════════════════════════════════════╗
║         🤖 Kimi Web Search Agent - Quick Experience       ║
║                                                          ║
║  Intelligent search assistant based on Kimi API           ║
║  Automatically searches web information and generates     ║
║  intelligent answers                                      ║
╚══════════════════════════════════════════════════════════╝
"""
    print_colored(banner, Colors.CYAN)


def check_api_key():
    """Check API Key Configuration"""
    api_key = os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        # Backward compatibility: try old environment variable name
        api_key = os.getenv("KIMI_API_KEY")
    
    if not api_key:
        print_colored("\n⚠️  No API Key detected", Colors.WARNING)
        print("\nPlease configure as follows:")
        print("1. Visit https://platform.moonshot.ai/ to get an API Key")
        print("2. Set environment variable:")
        print("   export MOONSHOT_API_KEY='your-api-key'")
        print("   (or use: export KIMI_API_KEY='your-api-key')")
        print("\nOr enter API Key directly (enter 'skip' to skip):")
        
        user_input = input("> ").strip()
        
        if user_input.lower() == 'skip':
            return None
        elif user_input:
            return user_input
        else:
            return None
    
    print_colored("✅ API Key configured", Colors.GREEN)
    return api_key


def demo_search(agent):
    """Demo Search Function"""
    print_colored("\n📝 Demo Search Function", Colors.HEADER)
    print("-" * 60)
    
    demo_questions = [
        "What new product did OpenAI recently release?",
        "What are the important AI breakthroughs in 2024?",
        "How to start learning machine learning?",
    ]
    
    print("Select a demo question, or enter your own question:")
    for i, q in enumerate(demo_questions, 1):
        print(f"{i}. {q}")
    print("0. Enter custom question")
    
    choice = input("\nPlease select (0-3): ").strip()
    
    try:
        choice = int(choice)
        if choice == 0:
            question = input("Please enter your question: ").strip()
            if not question:
                print_colored("❌ Question cannot be empty", Colors.FAIL)
                return
        elif 1 <= choice <= len(demo_questions):
            question = demo_questions[choice - 1]
        else:
            print_colored("❌ Invalid selection", Colors.FAIL)
            return
    except ValueError:
        print_colored("❌ Please enter a number", Colors.FAIL)
        return
    
    print_colored(f"\n🔍 Searching: {question}", Colors.BLUE)
    print("Please wait, the Agent is searching and analyzing...")
    print("-" * 60)
    
    try:
        answer = agent.search_and_answer(question)
        print_colored("\n📖 Agent Answer:", Colors.GREEN)
        print(answer)
    except Exception as e:
        print_colored(f"\n❌ Search failed: {str(e)}", Colors.FAIL)


def interactive_mode(agent):
    """Interactive Mode"""
    print_colored("\n💬 Entering Interactive Mode", Colors.HEADER)
    print("You can ask questions continuously; type 'quit' to exit")
    print("-" * 60)
    
    while True:
        question = input("\nYour question: ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            print_colored("👋 Thank you for using!", Colors.GREEN)
            break
        
        if not question:
            continue
        
        print_colored("🔍 Searching...", Colors.BLUE)
        
        try:
            answer = agent.search_and_answer(question)
            print_colored("\n📖 Answer:", Colors.GREEN)
            print(answer)
        except Exception as e:
            print_colored(f"❌ Error: {str(e)}", Colors.FAIL)


def main():
    """Main Function"""
    print_banner()
    
    # Checking API Key
    api_key = check_api_key()
    if not api_key:
        print_colored("\n⚠️  Cannot proceed, API Key needs to be configured", Colors.WARNING)
        sys.exit(1)
    
    # Creating Agent
    try:
        print_colored("\n🚀 Initializing Agent...", Colors.BLUE)
        agent = WebSearchAgent(api_key=api_key)
        print_colored("✅ Agent Ready", Colors.GREEN)
    except Exception as e:
        print_colored(f"❌ Initialization failed: {str(e)}", Colors.FAIL)
        sys.exit(1)
    
    # Select Mode
    print("\nSelect usage mode:")
    print("1. Demo Search (Quick Experience)")
    print("2. Interactive Mode (Continuous Conversation)")
    print("3. Exit")
    
    mode = input("\nPlease select (1-3): ").strip()
    
    if mode == "1":
        demo_search(agent)
        # Ask whether to continue
        cont = input("\nEnter Interactive Mode? (y/n): ").strip().lower()
        if cont == 'y':
            interactive_mode(agent)
    elif mode == "2":
        interactive_mode(agent)
    elif mode == "3":
        print_colored("👋 Goodbye!", Colors.GREEN)
    else:
        print_colored("❌ Invalid selection", Colors.FAIL)
    
    print_colored("\nThank you for using Kimi Web Search Agent!", Colors.CYAN)
    print("For more features, see:")
    print("- README.md: Full Documentation")
    print("- examples.py: Advanced Examples")
    print("- main.py: Main Program")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n👋 Program Interrupted", Colors.WARNING)
    except Exception as e:
        print_colored(f"\n❌ Error occurred: {str(e)}", Colors.FAIL)
        sys.exit(1)
