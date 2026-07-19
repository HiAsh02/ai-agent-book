#!/usr/bin/env python3
"""
Main script for Log Sanitization using Local LLM
"""

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from config import OUTPUT_DIR, OLLAMA_MODEL
import regex_sanitizer
from samples import SAMPLES


def main(test_id: Optional[str] = None, limit: Optional[int] = None,
         model: str = OLLAMA_MODEL):
    """
    Main function to run log sanitization
    
    Args:
        test_id: Specific test case ID to process (optional)
        limit: Maximum number of test cases to process (optional)
    """
    print("🚀 Starting Log Sanitization with Local LLM")
    print("=" * 60)

    # Initialize components
    try:
        from agent import LogSanitizationAgent
        from test_loader import TestCaseLoader

        print("📦 Loading test cases from user-memory-evaluation...")
        loader = TestCaseLoader()

        print(f"🤖 Initializing Ollama agent (model: {model})...")
        agent = LogSanitizationAgent(model=model)

    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return 1
    
    # Get test cases to process
    if test_id:
        # Process specific test case
        print(f"\n📋 Processing specific test case: {test_id}")
        conversations = loader.get_test_case_conversations(test_id)
        
        if not conversations:
            print(f"❌ Test case {test_id} not found or has no conversations")
            return 1
        
        agent.process_test_case(test_id, conversations)
        
    else:
        # Process Layer 3 test cases (most complex, likely to have PII)
        print("\n📋 Getting Layer 3 test cases...")
        test_cases = loader.get_layer3_test_cases()
        
        if not test_cases:
            print("❌ No Layer 3 test cases found")
            return 1
        
        print(f"Found {len(test_cases)} Layer 3 test cases")
        
        # Apply limit if specified
        if limit:
            test_cases = test_cases[:limit]
            print(f"Processing first {limit} test cases")
        
        # Process each test case
        for i, tc in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}] Test Case: {tc['test_id']}")
            print(f"   Title: {tc['title']}")
            print(f"   Conversations: {tc['num_conversations']}")
            
            # Get conversation histories
            conversations = loader.get_test_case_conversations(tc['test_id'])
            
            if conversations:
                agent.process_test_case(tc['test_id'], conversations)
            else:
                print(f"   ⚠️  No conversations found for {tc['test_id']}")
    
    print("\n" + "=" * 60)
    print("✅ Log Sanitization Complete!")
    print(f"📁 Results saved to: {OUTPUT_DIR}")
    
    return 0


def demo_regex_mode():
    """Offline Rule Masking Demo: Show before/after and category summary for multiple representative samples"""
    print("🎯 Offline Rule Masking Demo (regex mode, no Ollama needed)")
    print("=" * 60)
    print(f"Total {len(SAMPLES)} representative samples covering keys/tokens/private keys/PII and other categories\n")

    total = Counter()
    total_hits = 0
    for name, text in SAMPLES:
        redacted, findings = regex_sanitizer.sanitize(text)
        regex_sanitizer.print_report(name, text, redacted, findings)
        total.update(regex_sanitizer.summarize(findings))
        total_hits += len(findings)

    print(f"\n{'=' * 64}")
    print("Masking Category Summary (across all samples)")
    print("=" * 64)
    for category, count in total.most_common():
        label = regex_sanitizer.CATEGORY_LABELS.get(category, category)
        print(f"   {label:<16} {count} occurrences")
    print(f"\n   Total masked {total_hits} sensitive items across {len(total)} categories")
    return 0


def sanitize_file(input_path: str, output_path: Optional[str] = None,
                  mode: str = "regex", model: str = OLLAMA_MODEL):
    """Apply masking to any log file and write results to output file"""
    in_file = Path(input_path)
    if not in_file.exists():
        print(f"❌ Input file does not exist: {input_path}")
        return 1

    text = in_file.read_text(encoding="utf-8", errors="replace")
    out_file = Path(output_path) if output_path else in_file.with_suffix(in_file.suffix + ".sanitized")

    if mode == "regex":
        print(f"🔍 Masking with offline rule engine: {input_path}")
        redacted, findings = regex_sanitizer.sanitize(text)
        counts = regex_sanitizer.summarize(findings)
    else:
        print(f"🔍 Masking with local LLM ({model}): {input_path}")
        try:
            from agent import LogSanitizationAgent
        except Exception as e:
            print(f"❌ Failed to load LLM engine: {e}")
            return 1
        agent = LogSanitizationAgent(model=model)
        pii_values, _ = agent.detect_pii(text)
        redacted, _ = agent.sanitize_text(text, pii_values)
        counts = Counter({"pii": len(pii_values)})
        findings = pii_values

    out_file.write_text(redacted, encoding="utf-8")

    print(f"\n✅ Masking results written to: {out_file}")
    print(f"   Total masked {sum(counts.values())} sensitive items")
    for category, count in counts.most_common():
        label = regex_sanitizer.CATEGORY_LABELS.get(category, category)
        print(f"   - {label}: {count} occurrences")
    return 0


def demo_mode(model: str = OLLAMA_MODEL):
    """Run a quick demo with sample PII-containing text (local LLM mode)"""
    print("🎯 Running Demo Mode (LLM)")
    print("=" * 60)

    # Create a sample conversation with Level 3 PII
    sample_conversation = {
        'conversation_id': 'demo_001',
        'timestamp': '2024-01-01 10:00:00',
        'messages': [
            {
                'role': 'user',
                'content': 'I need to update my information. My SSN is 123-45-6789.'
            },
            {
                'role': 'assistant',
                'content': 'I can help you update your information. Can you confirm your credit card?'
            },
            {
                'role': 'user',
                'content': 'Yes, it\'s 4532 1234 5678 9012. Also, my medical record number is MRN-789456.'
            },
            {
                'role': 'assistant',
                'content': 'Thank you. I\'ve noted your SSN ending in 6789 and card ending in 9012.'
            },
            {
                'role': 'user',
                'content': 'Great. My driver\'s license is DL-123456789 and passport is P987654321.'
            }
        ]
    }
    
    try:
        from agent import LogSanitizationAgent
        agent = LogSanitizationAgent(model=model)
        print("\n📝 Sample conversation created with Level 3 PII")
        print("🔍 Detecting and sanitizing PII...\n")
        
        result = agent.sanitize_conversation(sample_conversation, 'demo')
        
        print("\n" + "=" * 60)
        print("DEMO RESULTS")
        print("=" * 60)
        print(f"PII Items Found: {len(result['pii_found'])}")
        for pii in result['pii_found']:
            print(f"  - {pii}")
        
        print(f"\nReplacements Made: {result['replacements_made']}")
        print("\n--- SANITIZED TEXT ---")
        print(result['sanitized_text'])
        
        # Save demo results
        agent.save_sanitized_log('demo', [result])
        agent.metrics_collector.save_metrics()
        agent.metrics_collector.print_summary()
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Log Masking Experiment: Detect and mask sensitive information from Agent logs / tool outputs"
                    "(API keys, tokens, private keys, credit cards, ID numbers, phone numbers, emails, etc.).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Two masking engines:
  regex  Offline rule engine (default), based on regex + validation algorithms, no Ollama needed, deterministic results, fast
  llm    Local LLM engine, calls a small model (default qwen3:0.6b) via Ollama for semantic Level 3 PII recognition

Common examples:
  python main.py --demo                     # Run built-in samples offline, show before/after and masking summary
  python main.py --demo --mode llm          # Run demo samples with local LLM
  python main.py --input app.log            # Mask a log file offline
  python main.py --input app.log -o out.log # Specify output file
  python main.py --input app.log --mode llm # Mask file with local LLM
  python main.py                            # (LLM) Batch process Layer 3 test cases in chapter3 evaluation framework
  python main.py --test-id layer3_01_travel_coordination
  python main.py --limit 3 --model qwen3:1.7b
""",
    )

    parser.add_argument(
        '--mode',
        choices=['regex', 'llm'],
        default='regex',
        help='Masking engine: regex=offline rules (default), llm=local Ollama model.'
             '(Note: batch evaluation path without --demo/--input always uses LLM)'
    )

    parser.add_argument(
        '-i', '--input',
        type=str,
        metavar='FILE',
        help='Path to log file to be masked (use with --mode to select engine)'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        metavar='FILE',
        help='Output file path for masking results (only effective with --input mode, defaults to <input>.sanitized)'
    )

    parser.add_argument(
        '--model',
        type=str,
        default=OLLAMA_MODEL,
        help=f'Ollama model name (default {OLLAMA_MODEL}), only effective in llm mode'
    )

    parser.add_argument(
        '--test-id',
        type=str,
        help='Only process test cases with the specified ID (LLM batch path)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of test cases to process (LLM batch path)'
    )

    parser.add_argument(
        '--demo',
        action='store_true',
        help='Run demo: default offline rule engine runs built-in representative samples; add --mode llm to use local LLM'
    )

    args = parser.parse_args()

    if args.input:
        exit_code = sanitize_file(args.input, args.output, mode=args.mode, model=args.model)
    elif args.demo:
        if args.mode == 'llm':
            exit_code = demo_mode(model=args.model)
        else:
            exit_code = demo_regex_mode()
    else:
        exit_code = main(test_id=args.test_id, limit=args.limit, model=args.model)

    sys.exit(exit_code)
