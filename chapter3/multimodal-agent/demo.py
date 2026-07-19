"""
Demo script showcasing different extraction techniques
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from agent import MultimodalAgent, MultimodalContent
from config import ExtractionMode


class _Tee:
    """Duplicate stdout writes to a file so --output can save the transcript."""

    def __init__(self, stream, file_handle):
        self._stream = stream
        self._file = file_handle

    def write(self, data):
        self._stream.write(data)
        self._file.write(data)

    def flush(self):
        self._stream.flush()
        self._file.flush()


async def compare_extraction_modes(file_path: str, query: str, model: str = "gemini-3.5-flash"):
    """Compare different extraction modes for the same content"""
    
    print(f"\n{'='*80}")
    print(f"COMPARING EXTRACTION MODES")
    print(f"File: {file_path}")
    print(f"Query: {query}")
    print(f"{'='*80}\n")
    
    # Determine content type
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == '.pdf':
        content_type = "pdf"
    elif suffix in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        content_type = "image"
    elif suffix in ['.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg']:
        content_type = "audio"
    else:
        print(f"Unsupported file type: {suffix}")
        return
    
    # Test with native mode (Gemini)
    print("\n" + "-"*60)
    print(f"1. NATIVE MULTIMODAL MODE ({model})")
    print("-"*60)

    agent_native = MultimodalAgent(
        model=model,
        mode=ExtractionMode.NATIVE,
        enable_tools=False
    )
    
    content = MultimodalContent(type=content_type, path=file_path)
    
    try:
        result = await agent_native.process_multimodal_content(content, query)
        print(result)
    except Exception as e:
        print(f"Error: {e}")
    
    # Test with extract-to-text mode
    print("\n" + "-"*60)
    print("2. EXTRACT TO TEXT MODE")
    print("-"*60)
    
    agent_extract = MultimodalAgent(
        model=model,
        mode=ExtractionMode.EXTRACT_TO_TEXT,
        enable_tools=False
    )
    
    try:
        # First extract the content
        print("Extracting content to text...")
        extracted = await agent_extract._extract_single_content(content)
        print("\nExtracted text:")
        print(extracted)
        
        # Then answer the query
        print(f"\nAnswering query with extracted text...")
        result = await agent_extract._answer_with_context(extracted, query)
        print(result)
    except Exception as e:
        print(f"Error: {e}")
    
    # Test with extract-to-text + tools mode
    print("\n" + "-"*60)
    print("3. EXTRACT TO TEXT + MULTIMODAL TOOLS")
    print("-"*60)
    
    agent_tools = MultimodalAgent(
        model=model,
        mode=ExtractionMode.EXTRACT_TO_TEXT,
        enable_tools=True
    )
    
    try:
        print("Using extract-to-text with tools enabled for follow-up questions...")
        
        # Initial processing
        extracted = await agent_tools._extract_single_content(content)
        print(f"Extracted {len(extracted)} characters")
        
        # Simulate a conversation with follow-up
        async for chunk in agent_tools.chat(query, content, stream=True):
            print(chunk, end="", flush=True)
        print()
        
        # Follow-up question that might use tools
        if content_type == "image":
            follow_up = f"What colors are dominant in the image at {file_path}?"
        elif content_type == "pdf":
            follow_up = f"What specific data or figures are mentioned in the PDF at {file_path}?"
        else:  # audio
            follow_up = f"What is the tone or mood of the audio at {file_path}?"
            
        print(f"\nFollow-up question: {follow_up}")
        async for chunk in agent_tools.chat(follow_up, None, stream=True):
            print(chunk, end="", flush=True)
        print()
        
    except Exception as e:
        print(f"Error: {e}")


async def compare_models(file_path: str, query: str):
    """Compare different models for the same task"""
    
    print(f"\n{'='*80}")
    print(f"COMPARING MODELS")
    print(f"File: {file_path}")
    print(f"Query: {query}")
    print(f"{'='*80}\n")
    
    # Determine content type
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == '.pdf':
        content_type = "pdf"
    elif suffix in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        content_type = "image"
    elif suffix in ['.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg']:
        content_type = "audio"
    else:
        print(f"Unsupported file type: {suffix}")
        return
        
    content = MultimodalContent(type=content_type, path=file_path)
    
    # Test with different models
    models = ["gemini-3.5-flash", "gpt-5.6-luna", "doubao-1.6"]
    
    for model in models:
        print("\n" + "-"*60)
        print(f"Model: {model}")
        print("-"*60)
        
        try:
            # Skip if API key not configured
            from config import Config
            config = Config()
            
            if model == "gemini-3.5-flash" and not config.gemini_api_key:
                print("Skipping: Gemini API key not configured")
                continue
            elif model in ["gpt-5.6-luna", "gpt-5"] and not (config.openai_api_key or config.openrouter_api_key):
                print("Skipping: OpenAI API key not configured")
                continue
            elif model == "doubao-1.6" and not config.doubao_api_key:
                print("Skipping: Doubao API key not configured")
                continue
            
            agent = MultimodalAgent(
                model=model,
                mode=ExtractionMode.NATIVE if content_type != "audio" or model == "gemini-3.5-flash" else ExtractionMode.EXTRACT_TO_TEXT,
                enable_tools=False
            )
            
            result = await agent.process_multimodal_content(content, query)
            print(result)
            
        except Exception as e:
            print(f"Error: {e}")


async def demo_conversation_with_tools():
    """Demonstrate a conversation with multimodal tools"""
    
    print(f"\n{'='*80}")
    print("DEMO: CONVERSATION WITH MULTIMODAL TOOLS")
    print(f"{'='*80}\n")
    
    agent = MultimodalAgent(
        model="gemini-3.5-flash",
        mode=ExtractionMode.EXTRACT_TO_TEXT,
        enable_tools=True
    )
    
    # Simulate a conversation
    conversations = [
        ("I need help analyzing some documents. I have PDFs, images, and audio files.", None),
        ("Can you analyze the image at test_files/sample.jpg and tell me what you see?", None),
        ("Now analyze the PDF at test_files/document.pdf and summarize its main points.", None),
        ("What's in the audio file at test_files/recording.mp3?", None),
        ("Based on all these files, what's the common theme?", None)
    ]
    
    for message, content in conversations:
        print(f"\nUser: {message}")
        print("Assistant: ", end="", flush=True)
        
        try:
            async for chunk in agent.chat(message, content, stream=True):
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            print(f"\nError: {e}")
            print("(File might not exist - this is a demo)")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface for Experiment 3-7."""
    parser = argparse.ArgumentParser(
        description=(
            "Experiment 3-7: Comparison of three technical paradigms for multimodal information extraction (native multimodal / extract as text / with tools).\n"
            "Feed the same multimodal file and the same question to the three modes respectively, and observe the performance differences."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  # First, offline generate a sample with charts (no API Key required)\n"
            "  python demo.py --generate-sample\n"
            "  # Run the three-paradigm comparison with the generated chart (API Key required)\n"
            "  python demo.py --file test_files/sample_chart.png \\\n"
            '      --query \"Which quarter had the highest revenue, and what was the exact value?\"\n'
            "  # Compatible with old syntax (positional arguments)\n"
            "  python demo.py document.pdf \"Summarize the key points of this document\""
        ),
    )
    parser.add_argument(
        "file", nargs="?", default=None,
        help="The multimodal file to process (image / PDF document / audio). Can also be specified with --file",
    )
    parser.add_argument(
        "query", nargs="?", default=None,
        help="The question to ask about the file. Can also be specified with --query",
    )
    parser.add_argument(
        "--file", dest="file_opt", default=None,
        help="The multimodal file to process (equivalent to positional argument file)",
    )
    parser.add_argument(
        "--query", dest="query_opt", default=None,
        help="The question to ask about the file (equivalent to positional argument query)",
    )
    parser.add_argument(
        "--model", default="gemini-3.5-flash",
        help="Model used for native / extraction mode (default: gemini-3.5-flash)",
    )
    parser.add_argument(
        "--skip-model-comparison", action="store_true",
        help="Only run the three-paradigm comparison, skip cross-model comparison",
    )
    parser.add_argument(
        "--generate-sample", action="store_true",
        help="Offline generate sample files with charts to test_files/ and exit (no API Key required)",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Write the full comparison results to the specified file (e.g., result.txt)",
    )
    return parser


async def run_comparison(file_path: str, query: str, model: str, skip_model_comparison: bool):
    """Run the three-paradigm comparison, optionally with cross-model comparison."""
    print("="*80)
    print("MULTIMODAL AGENT DEMO")
    print("="*80)

    await compare_extraction_modes(file_path, query, model=model)
    if not skip_model_comparison:
        await compare_models(file_path, query)


async def main():
    """Experiment entry: parse arguments and run comparison."""
    parser = build_parser()
    args = parser.parse_args()

    #  Offline sample generation: no API Key needed, directly produce charts + PDF report
    if args.generate_sample:
        import create_sample
        sys.argv = ["create_sample.py"]  #  Use default output directory test_files/
        create_sample.main()
        return

    file_path = args.file_opt or args.file
    query = args.query_opt or args.query

    #  Fall back to dialogue demo without real files when file or question is missing
    if not file_path or not query:
        print("="*80)
        print("MULTIMODAL AGENT DEMO")
        print("="*80)
        print("\nNo <file> and <query> provided, switching to dialogue demo.")
        print("Usage: python demo.py --file <file> --query <question>")
        print("First generate a sample: python demo.py --generate-sample\n")
        await demo_conversation_with_tools()
        return

    #  Supports --output: write the full comparison results to disk simultaneously
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            original_stdout = sys.stdout
            sys.stdout = _Tee(original_stdout, fh)
            try:
                await run_comparison(file_path, query, args.model, args.skip_model_comparison)
            finally:
                sys.stdout = original_stdout
        print(f"\nFull comparison results have been written to:{args.output}")
    else:
        await run_comparison(file_path, query, args.model, args.skip_model_comparison)


if __name__ == "__main__":
    asyncio.run(main())
