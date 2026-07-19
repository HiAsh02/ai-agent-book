"""Main entry point for Agentic RAG system"""

import os
import json
import logging
import argparse
from typing import Optional
from config import Config, KnowledgeBaseType
from agent import AgenticRAG
from chunking import DocumentIndexer


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def setup_environment():
    """Setup environment and check requirements"""
    # Check for required API keys
    config = Config.from_env()
    
    # Check LLM API key
    try:
        api_key = config.llm.get_api_key(config.llm.provider)
        if not api_key:
            logger.warning(f"No API key found for provider {config.llm.provider}")
            logger.info("Please set the appropriate environment variable:")
            logger.info("  - MOONSHOT_API_KEY for Kimi")
            logger.info("  - ARK_API_KEY for Doubao")
            logger.info("  - SILICONFLOW_API_KEY for SiliconFlow")
            logger.info("  - OPENAI_API_KEY for OpenAI")
            return False
    except Exception as e:
        logger.error(f"Error checking API keys: {e}")
        return False
    
    # Check knowledge base setup
    if config.knowledge_base.type == KnowledgeBaseType.LOCAL:
        # Check if local retrieval pipeline is running
        import requests
        try:
            response = requests.get(f"{config.knowledge_base.local_base_url}/health")
            if response.status_code != 200:
                logger.warning("Local retrieval pipeline not responding")
                logger.info(f"Please ensure the retrieval pipeline is running at {config.knowledge_base.local_base_url}")
                logger.info("Run: cd ../retrieval-pipeline && python main.py")
        except:
            logger.warning("Cannot connect to local retrieval pipeline")
            logger.info("Will continue anyway - searches may fail")
    
    elif config.knowledge_base.type == KnowledgeBaseType.DIFY:
        if not config.knowledge_base.dify_api_key:
            logger.warning("Dify API key not set")
            logger.info("Please set DIFY_API_KEY environment variable")
    
    return True


def run_interactive_mode(agent: AgenticRAG, mode: str = "agentic"):
    """Run interactive query mode"""
    kb = agent.config.knowledge_base
    active_top_k = kb.offline_top_k if kb.type == KnowledgeBaseType.OFFLINE else kb.local_top_k
    print(f"\n{'='*60}")
    print(f"Agentic RAG System - {mode.capitalize()} Mode")
    print(f"Verbose: {'Enabled' if agent.config.agent.verbose else 'Disabled'} | KB: {kb.type.value} | Top-K: {active_top_k}")
    print(f"{'='*60}")
    print("Type 'quit' or 'exit' to stop")
    print("Type 'clear' to clear conversation history")
    print("Type 'mode' to switch between agentic/non-agentic modes")
    print(f"{'='*60}\n")
    
    current_mode = mode
    
    while True:
        try:
            user_input = input("\n[USER] > ").strip()
            
            if user_input.lower() in ['quit', 'exit']:
                print("\nGoodbye!")
                break
            
            if user_input.lower() == 'clear':
                agent.clear_history()
                print("Conversation history cleared.")
                continue
            
            if user_input.lower() == 'mode':
                current_mode = "non-agentic" if current_mode == "agentic" else "agentic"
                print(f"Switched to {current_mode} mode")
                continue
            
            if not user_input:
                continue
            
            # Process query
            print(f"\n[ASSISTANT ({current_mode})] > ", end="", flush=True)
            
            if current_mode == "agentic":
                response = agent.query(user_input, stream=True)
            else:
                response = agent.query_non_agentic(user_input, stream=True)
            
            # Handle streaming response
            if hasattr(response, '__iter__'):
                for chunk in response:
                    print(chunk, end="", flush=True)
                print()  # New line after response
            else:
                print(response)
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'quit' to exit.")
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"\nError processing query: {e}")


def run_batch_mode(agent: AgenticRAG, queries_file: str, output_file: str, mode: str = "agentic"):
    """Run batch queries from file"""
    try:
        with open(queries_file, 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Error reading queries file: {e}")
        return
    
    results = []
    
    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/{len(queries)}] Processing: {query[:100]}...")
        
        try:
            if mode == "agentic":
                response = agent.query(query, stream=False)
            else:
                response = agent.query_non_agentic(query, stream=False)
            
            results.append({
                "query": query,
                "response": response,
                "mode": mode
            })
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            results.append({
                "query": query,
                "response": f"Error: {str(e)}",
                "mode": mode
            })
    
    # Save results
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving results: {e}")


def run_comparison_mode(agent: AgenticRAG, query: str):
    """Run both modes and compare results"""
    print(f"\n{'='*60}")
    print("Comparison Mode - Running both Agentic and Non-Agentic")
    print(f"{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")
    
    # Run non-agentic mode
    print("\n[NON-AGENTIC MODE]")
    print("-" * 40)
    non_agentic_response = agent.query_non_agentic(query, stream=False)
    print(non_agentic_response)
    
    # Clear history for fair comparison
    agent.clear_history()
    
    # Run agentic mode
    print("\n[AGENTIC MODE]")
    print("-" * 40)
    agentic_response = agent.query(query, stream=False)
    print(agentic_response)
    
    print(f"\n{'='*60}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Agentic RAG System: Comparing the 'Agentic (multi-turn iterative retrieval)' and 'Non-agentic (single retrieval)' paradigms.",
        epilog=(
            "Example:\n"
            "  python main.py --kb-type offline --query \"How to sentence for drunk driving causing serious injury with a prior theft record\"\n"
            "  python main.py --query \"How many years for intentional homicide\" --mode compare --kb-type offline\n"
            "  python compare_offline.py   # Pure offline retrieval comparison, no API or external services required\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    #  Mode Selection
    parser.add_argument("--mode", choices=["agentic", "non-agentic", "compare"],
                        default="agentic",
                        help="Query mode: agentic=agentic multi-turn retrieval / non-agentic=single retrieval / compare=same query comparison (default: agentic)")

    #  Query Options
    parser.add_argument("--query", type=str, help="Single query question; if not specified, enter interactive mode")
    parser.add_argument("--batch", type=str, help="Batch query file path (one question per line)")
    parser.add_argument("--output", type=str, default="results.json",
                        help="Output file path for batch results (default: results.json)")

    #  Configuration Options
    parser.add_argument("--provider", type=str, help="LLM provider (e.g., kimi / doubao / openai)")
    parser.add_argument("--model", type=str, help="LLM model name (if not specified, use provider's default model)")
    parser.add_argument("--kb-type", choices=["offline", "local", "dify"],
                        help="Knowledge base backend: offline=built-in offline BM25 (no service/API required) / local=retrieval pipeline service / dify=Dify API")
    parser.add_argument("--corpus", type=str,
                        help="Legal corpus directory for offline backend (only effective with --kb-type offline, default: laws)")
    parser.add_argument("--top-k", type=int, dest="top_k",
                        help="Retrieval depth: number of chunks returned per retrieval (default: offline=5, local=3)")
    parser.add_argument("--verbose", action="store_true", help="Output detailed Agent reasoning trace (enabled by default)")
    parser.add_argument("--no-verbose", action="store_true", help="Disable verbose logging")

    #  Index Options
    parser.add_argument("--index", type=str, help="File or directory path to index")
    parser.add_argument("--chunk-size", type=int, default=2048, help="Chunk size for indexing (characters, default: 2048)")

    args = parser.parse_args()
    
    # Setup environment
    if not setup_environment():
        logger.warning("Environment setup incomplete, continuing anyway...")
    
    # Load or create config
    config = Config.from_env()
    
    # Set verbose mode by default (can be disabled with --no-verbose)
    config.agent.verbose = True  # Default to verbose mode
    
    # Override config with command line args
    if args.provider:
        config.llm.provider = args.provider
    if args.model:
        config.llm.model = args.model
    if args.kb_type:
        config.knowledge_base.type = KnowledgeBaseType(args.kb_type)
    if args.corpus:
        config.knowledge_base.offline_corpus_path = args.corpus
    if args.top_k:
        #Set retrieval depth for both offline and local backends simultaneously to keep behavior consistent
        config.knowledge_base.offline_top_k = args.top_k
        config.knowledge_base.local_top_k = args.top_k

    # Handle verbose mode (default is True, can be disabled with --no-verbose)
    if args.no_verbose:
        config.agent.verbose = False
    elif args.verbose:
        config.agent.verbose = True  # Explicitly set if --verbose is used
    
    # Handle indexing if requested
    if args.index:
        print(f"\n{'='*60}")
        print("Indexing Documents")
        print(f"{'='*60}")
        
        config.chunking.chunk_size = args.chunk_size
        indexer = DocumentIndexer(config.knowledge_base, config.chunking)
        
        from pathlib import Path
        path = Path(args.index)
        
        if path.is_file():
            result = indexer.index_file(str(path))
        elif path.is_dir():
            result = indexer.index_directory(str(path))
        else:
            print(f"Path not found: {path}")
            return
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"{'='*60}\n")
    
    # Create agent
    agent = AgenticRAG(config)
    
    # Handle different execution modes
    if args.query and args.mode == "compare":
        # Comparison mode with single query
        run_comparison_mode(agent, args.query)
        
    elif args.query:
        # Single query mode
        kb = config.knowledge_base
        active_top_k = kb.offline_top_k if kb.type == KnowledgeBaseType.OFFLINE else kb.local_top_k
        print(f"\n[Query] {args.query}")
        print(f"[Mode] {args.mode}")
        print(f"[KB] {kb.type.value}")
        print(f"[Verbose] {'Enabled' if config.agent.verbose else 'Disabled'}")
        print(f"[Top-K] {active_top_k}")
        print("-" * 40)
        
        if args.mode == "agentic":
            response = agent.query(args.query, stream=False)
        else:
            response = agent.query_non_agentic(args.query, stream=False)
        
        print(response)
        
    elif args.batch:
        # Batch mode
        run_batch_mode(agent, args.batch, args.output, args.mode)
        
    else:
        # Interactive mode (default)
        run_interactive_mode(agent, args.mode)


if __name__ == "__main__":
    main()
