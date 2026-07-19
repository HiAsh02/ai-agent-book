#!/usr/bin/env python3
"""
Perception Tool MCP Server — Unified CLI Entry (Experiment 4-1).

In addition to serving via the MCP stdio protocol (see src/main.py), this file provides a
CLI entry point that does not depend on an MCP client, making it easy to list, invoke, and
demonstrate various perception tools:

    python cli.py list                 # List all perception tools by five categories
    python cli.py info <tool>          # View parameter signature of a tool
    python cli.py run <tool> k=v ...   # Directly invoke a tool and print JSON result
    python cli.py demo [--offline]     # Run an end-to-end perception scenario demo

Tools are organized according to the five categories of perception tools in Chapter 4 of
"Deep Understanding of AI Agents": search, multimodal understanding, file system, public
data sources, and private data sources.

Design notes:
- Each tool is an async function returning a unified ActionResponse (JSON). The CLI handles
the event loop, parses JSON, and prints it in a user-friendly manner.
- Tools are lazily imported on demand: only when a tool is actually invoked is its module
imported. Therefore, list / info / offline demo still work normally when optional
dependencies (e.g., yfinance, opencv, whisper) are missing.
"""
import argparse
import asyncio
import importlib
import inspect
import json
import logging
import sys
import tempfile
import typing
from pathlib import Path

SRC_DIR = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_DIR))

#  Five categories of Chinese titles (corresponding one-to-one to the classifications in Experiment 4-1 of the book)
CATEGORIES = {
    "search": "Search",
    "multimodal": "Multimodal understanding",
    "filesystem": "File system",
    "public": "Public data source",
    "private": "private data source",
}


class Tool(typing.NamedTuple):
    """A registration entry for a perception tool."""
    name: str          #Tool name exposed in CLI / MCP
    category: str      # 所属分类（CATEGORIES 的 key）
    module: str        #Module name under src/
    func: str          # 模块中的异步函数名
    desc: str          #  A one-sentence Chinese description
    online: bool = False   #  Whether internet access is required
    note: str = ""     # Additional notes (e.g., API Key / authorization required)


# ---------------------------------------------------------------------------
# Tool registry: consistent with the MCP tools exposed in src/main.py, and complete those declared in the README, 
#  But the three tools (crypto_price / location_search / poi_search) that were not registered in main.py before.
# ---------------------------------------------------------------------------
TOOLS: list[Tool] = [
    # ---- Search ----
    Tool("web_search", "search", "search_tools", "search_web",
         "Search the web using DuckDuckGo (free, no API key required)", online=True),
    Tool("knowledge_base_search", "search", "search_tools", "search_knowledge_base",
         "Perform full-text search in the local knowledge base directory"),
    Tool("download", "search", "search_tools", "download_file",
         "Download file from URL to local (with size/overwrite protection)", online=True),
    Tool("google_search_enhanced", "search", "google_search_enhanced", "google_search_api",
         "Google Custom Search, fallback to DuckDuckGo on failure", online=True,
         note="Google API requires GOOGLE_API_KEY, falls back automatically if not configured"),

    # ---- Multimodal Understanding ----
    Tool("webpage_reader", "multimodal", "multimodal_tools", "read_webpage",
         "Scrape and extract webpage content/links", online=True),
    Tool("webpage_read_enhanced", "multimodal", "google_search_enhanced", "read_webpage_content",
         "Enhanced web page text extraction", online=True),
    Tool("document_reader", "multimodal", "multimodal_tools", "read_document",
         "Read PDF/DOCX/PPTX document content"),
    Tool("pdf_extract", "multimodal", "document_processing_tools", "extract_pdf_text",
         "Extract PDF text (supports page range)"),
    Tool("docx_extract", "multimodal", "document_processing_tools", "extract_docx_content",
         "Extract Word (DOCX) document content"),
    Tool("pptx_extract", "multimodal", "document_processing_tools", "extract_pptx_content",
         "Extract PowerPoint (PPTX) content"),
    Tool("csv_parse", "multimodal", "document_processing_tools", "extract_csv_content",
         "Parse CSV table data"),
    Tool("image_parser", "multimodal", "multimodal_tools", "parse_image",
         "Parse image (optional LLM vision analysis)", note="use_llm requires vision model API"),
    Tool("image_ocr", "multimodal", "media_processing_tools", "extract_text_ocr",
         "Perform OCR text recognition on image", note="Requires tesseract installation"),
    Tool("image_analyze", "multimodal", "media_processing_tools", "analyze_image_ai",
         "Analyze image content with vision model", note="Requires vision model API"),
    Tool("image_metadata", "multimodal", "media_processing_tools", "get_image_metadata",
         "Read image EXIF and other metadata"),
    Tool("video_parser", "multimodal", "multimodal_tools", "parse_video",
         "Extract video metadata/sample frames"),
    Tool("video_keyframes", "multimodal", "media_processing_tools", "extract_video_keyframes",
         "Extract key frames from video"),
    Tool("video_analyze", "multimodal", "media_processing_tools", "analyze_video_ai",
         "Analyze video content with vision model", note="Requires vision model API"),
    Tool("audio_transcribe", "multimodal", "media_processing_tools", "transcribe_audio_whisper",
         "Transcribe audio to text using Whisper", note="Requires whisper installation"),
    Tool("audio_metadata", "multimodal", "media_processing_tools", "extract_audio_metadata",
         "Read audio file metadata"),
    Tool("audio_trim", "multimodal", "media_processing_tools", "trim_audio",
         "Trim audio to specified time range"),
    Tool("youtube_transcript", "multimodal", "multimodal_tools", "extract_youtube_transcript",
         "Extract YouTube video subtitles", online=True),
    Tool("youtube_download", "multimodal", "multimodal_tools", "download_youtube_video",
         "Download YouTube video", online=True),

    # ---- File System ----
    Tool("file_reader", "filesystem", "filesystem_tools", "read_file",
         "Read file content (supports encoding and truncation)"),
    Tool("grep", "filesystem", "filesystem_tools", "grep_search",
         "Search file content in directory by regex"),
    Tool("text_summarizer", "filesystem", "filesystem_tools", "summarize_text",
         "Summarize long text (extractive/truncation, placeholder implementation)"),

    # ---- Public Data Sources ----
    Tool("weather", "public", "public_data_tools", "get_weather",
         "Query weather (Open-Meteo, free no key)", online=True),
    Tool("stock_price", "public", "public_data_tools", "get_stock_price",
         "Query stock quotes", online=True),
    Tool("crypto_price", "public", "public_data_tools", "get_crypto_price",
         "Query cryptocurrency prices (CoinGecko, free no key)", online=True),
    Tool("currency_converter", "public", "public_data_tools", "convert_currency",
         "Currency exchange rate conversion (free no key)", online=True),
    Tool("wikipedia_search", "public", "public_data_tools", "search_wikipedia",
         "Search Wikipedia and return summary", online=True),
    Tool("arxiv_search", "public", "public_data_tools", "search_arxiv",
         "Search ArXiv academic papers", online=True),
    Tool("wayback_search", "public", "public_data_tools", "search_wayback",
         "Look up historical snapshots on Wayback Machine", online=True),
    Tool("location_search", "public", "public_data_tools", "search_location",
         "Geocode place/location (Nominatim, free no key)", online=True),
    Tool("poi_search", "public", "public_data_tools", "search_poi",
         "Query points of interest near coordinates (Overpass, free, no key)", online=True),
    Tool("yfinance_quote", "public", "yahoo_finance_tools", "get_stock_quote",
         "Yahoo Finance real-time quotes", online=True),
    Tool("yfinance_historical", "public", "yahoo_finance_tools", "get_historical_data",
         "Yahoo Finance historical data", online=True),
    Tool("yfinance_company_info", "public", "yahoo_finance_tools", "get_company_info",
         "Yahoo Finance company profile", online=True),
    Tool("yfinance_financials", "public", "yahoo_finance_tools", "get_financial_statements",
         "Yahoo Finance financial statements", online=True),
    Tool("pubchem_search", "public", "pubchem_tools", "search_compounds",
         "Search compounds in PubChem", online=True),
    Tool("pubchem_properties", "public", "pubchem_tools", "get_compound_properties",
         "Get PubChem compound properties", online=True),
    Tool("pubchem_synonyms", "public", "pubchem_tools", "get_compound_synonyms",
         "Get PubChem compound synonyms", online=True),
    Tool("pubchem_similar", "public", "pubchem_tools", "search_similar_compounds",
         "Search for structurally similar compounds", online=True),
    Tool("wiki_article_full", "public", "wiki_enhanced", "get_article_content",
         "Get full Wikipedia article", online=True),
    Tool("wiki_article_categories", "public", "wiki_enhanced", "get_article_categories",
         "Get Wikipedia article categories", online=True),
    Tool("wiki_article_links", "public", "wiki_enhanced", "get_article_links",
         "Get links in Wikipedia article", online=True),
    Tool("wiki_article_history", "public", "wiki_enhanced", "get_article_history",
         "Get Wikipedia article revision history", online=True),
    Tool("arxiv_paper_details", "public", "arxiv_enhanced", "get_paper_details",
         "Get ArXiv paper details", online=True),
    Tool("arxiv_download", "public", "arxiv_enhanced", "download_paper",
         "Download ArXiv paper PDF", online=True),
    Tool("arxiv_categories", "public", "arxiv_enhanced", "get_arxiv_categories",
         "List ArXiv subject categories", online=True),
    Tool("wayback_archived_content", "public", "wayback_enhanced", "get_archived_content",
         "Get Wayback archived page content", online=True),

    # ---- Private data sources ----
    Tool("calendar_events", "private", "private_data_tools", "get_calendar_events",
         "Read Google Calendar events", online=True, note="Requires Google OAuth authorization"),
    Tool("notion_search", "private", "private_data_tools", "search_notion",
         "Search Notion workspace", online=True, note="Requires NOTION_API_KEY"),
]

TOOLS_BY_NAME = {t.name: t for t in TOOLS}


# ---------------------------------------------------------------------------
# Call helper
# ---------------------------------------------------------------------------
def _load_callable(tool: Tool):
    """Lazily import and return the async function corresponding to the tool."""
    module = importlib.import_module(tool.module)
    return getattr(module, tool.func)


def _coerce(value: str, annotation):
    """Convert command-line input strings to appropriate types according to function annotations."""
    # Unwrap Optional[X] / X | None
    origin = typing.get_origin(annotation)
    if origin is typing.Union or (origin is not None and str(origin) == "<class 'types.UnionType'>"):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        annotation = args[0] if args else str
        origin = typing.get_origin(annotation)

    if annotation is bool:
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    if annotation is int:
        return int(value)
    if annotation is float:
        return float(value)
    if annotation in (list, dict) or origin in (list, dict):
        return json.loads(value)
    return value


def _parse_kwargs(func, pairs: list[str]) -> dict:
    """Parse key=value list into keyword arguments for the tool function."""
    sig = inspect.signature(func)
    kwargs = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Arguments must be in key=value form:{pair!r}")
        key, _, raw = pair.partition("=")
        key = key.strip()
        if key not in sig.parameters:
            valid = ", ".join(sig.parameters)
            raise ValueError(f"Unknown argument {key!r}, available arguments:{valid}")
        kwargs[key] = _coerce(raw, sig.parameters[key].annotation)
    return kwargs


def _unwrap(result):
    """Tool returns TextContent(JSON) or bare JSON string, uniformly parsed into dict."""
    text = getattr(result, "text", result)
    if isinstance(text, (dict, list)):
        return text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"success": True, "message": text, "metadata": {}}


async def _invoke(tool: Tool, kwargs: dict) -> dict:
    func = _load_callable(tool)
    result = await func(**kwargs)
    return _unwrap(result)


# ---------------------------------------------------------------------------
#  Subcommand implementation
# ---------------------------------------------------------------------------
def cmd_list(args) -> int:
    print("\nPerception Tool MCP Server — Tool List ({} total)".format(len(TOOLS)))
    print("=" * 72)
    cats = [args.category] if args.category else list(CATEGORIES)
    for cat in cats:
        tools = [t for t in TOOLS if t.category == cat]
        if not tools:
            continue
        print(f"\n【{CATEGORIES[cat]}】({len(tools)} )")
        print("-" * 72)
        for t in tools:
            flags = []
            if t.online:
                flags.append("Online")
            if t.note:
                flags.append(t.note)
            tag = f"  [{'；'.join(flags)}]" if flags else ""
            print(f"  {t.name:<26} {t.desc}{tag}")
    print("\nTip: `python cli.py info <tool>` to view parameters; `python cli.py run <tool> k=v` to invoke.\n")
    return 0


def cmd_info(args) -> int:
    tool = TOOLS_BY_NAME.get(args.tool)
    if tool is None:
        print(f"Tool not found:{args.tool}. Use `python cli.py list` to view all.", file=sys.stderr)
        return 1
    try:
        func = _load_callable(tool)
    except Exception as e:
        print(f"Tool {tool.name} failed to import its module (optional dependency may be missing):{e}", file=sys.stderr)
        return 1
    sig = inspect.signature(func)
    print(f"\nTool:{tool.name}   Category:{CATEGORIES[tool.category]}")
    print(f"Description:{tool.desc}")
    print(f"Implementation: src/{tool.module}.py :: {tool.func}()")
    if tool.online:
        print("Requires internet: Yes")
    if tool.note:
        print(f"Description:{tool.note}")
    print("\nParameters:")
    for name, p in sig.parameters.items():
        ann = "" if p.annotation is inspect.Parameter.empty else f": {p.annotation}"
        default = "" if p.default is inspect.Parameter.empty else f" = {p.default!r}"
        print(f"  {name}{ann}{default}")
    print(f"\nExample: python cli.py run {tool.name} " +
          " ".join(f"{n}=..." for n, p in sig.parameters.items()
                   if p.default is inspect.Parameter.empty) + "\n")
    return 0


def cmd_run(args) -> int:
    tool = TOOLS_BY_NAME.get(args.tool)
    if tool is None:
        print(f"Tool not found:{args.tool}. Use `python cli.py list` to view all.", file=sys.stderr)
        return 1
    try:
        func = _load_callable(tool)
    except Exception as e:
        print(f"Tool {tool.name} failed to import its module (optional dependency may be missing):{e}", file=sys.stderr)
        return 1
    try:
        kwargs = _parse_kwargs(func, args.params)
    except Exception as e:
        print(f"Parameter error:{e}", file=sys.stderr)
        return 1

    print(f"Invoke tool {tool.name} ...", file=sys.stderr)
    try:
        data = asyncio.run(_invoke(tool, kwargs))
    except Exception as e:
        print(f"Invocation failed:{type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get("success", True) else 2


# ---------------------------------------------------------------------------
#  End-to-end demo: Perception flow of a research assistant Agent with "local notes + external sources"
# ---------------------------------------------------------------------------
def _header(title: str) -> None:
    print("\n" + "─" * 72)
    print(f"▶ {title}")
    print("─" * 72)


async def _demo(offline: bool) -> None:
    from search_tools import search_web, search_knowledge_base
    from filesystem_tools import grep_search, read_file
    from public_data_tools import convert_currency, search_wikipedia
    from multimodal_tools import read_webpage

    #  Each tool internally uses logging.error to print the full stack trace; during the demo, the threshold is raised so only
    #  the clean status line organized by CLI is shown per step (real errors are still presented as friendly prompts).
    logging.getLogger().setLevel(logging.CRITICAL)

    print("\n" + "=" * 72)
    print("Perception Tool End-to-End Demo")
    print("Scenario: A research assistant Agent needs to \"first check local materials, then supplement with external information\"")
    print("      This demo chains five perception tools to show how the Agent 'perceives the world'" +
          ("(Offline mode: skip online steps)" if offline else ""))
    print("=" * 72)

    #  Prepare a temporary local knowledge base to avoid polluting the repository
    tmp = Path(tempfile.mkdtemp(prefix="perception_demo_"))
    (tmp / "mcp_notes.md").write_text(
        "# MCP Research Notes\n\n"
        "Model Context Protocol (MCP) is an open protocol for \n"
        "standardized context exchange between agents and tools/data sources. Sensory tools (e.g., web_search, read_file) are the senses through which agents acquire information. \n"
        "Key design considerations: granularity trade-offs, output information control, context-aware compression. \n",
        encoding="utf-8",
    )
    (tmp / "budget.md").write_text(
        "# Budget\n\nThe cloud resource budget for this research is 200 USD, which needs to be converted to RMB for reimbursement. \n",
        encoding="utf-8",
    )

    # 1) File system awareness: locate implementation in local codebase
    _header("[1/5] File system awareness: grep locate + read_file deep read (offline available)")
    data = _unwrap(await grep_search("ActionResponse", str(SRC_DIR),
                                     file_pattern="*.py", max_results=5))
    if data.get("success"):
        msg = data["message"]
        print(f"  grep 'ActionResponse' hits {msg['total_found']}  example:")
        for hit in msg["results"][:3]:
            print(f"    - {hit['file']}:{hit['line_number']}")
    base_py = _unwrap(await read_file(str(SRC_DIR / "base.py"), max_length=200))
    if base_py.get("success"):
        head = base_py["message"]["content"].strip().splitlines()[0]
        print(f"  read_file base.py first line:{head}")

    # 2) Search awareness: knowledge base retrieval (offline) + web search (online)
    _header("[2/5] Search awareness: local knowledge base retrieval (offline) + web search (online)")
    kb = _unwrap(await search_knowledge_base("MCP", str(tmp), top_k=3))
    if kb.get("success"):
        print(f"  Knowledge base retrieval 'MCP' hits {kb['message']['total_found']}  files:")
        for r in kb["message"]["results"]:
            print(f"    - {r['file']} (relevance {r['relevance']}）")
    if offline:
        print("  Web search: skipped (offline mode)")
    else:
        try:
            web = _unwrap(await search_web("Model Context Protocol", num_results=3))
            if web.get("success") and web["message"]["results"]:
                print(f"  web_search returned {web['message']['count']}  results, first:")
                top = web["message"]["results"][0]
                print(f"    - {top['title']}\n      {top['url']}")
            else:
                print("  web_search returned no results (possibly rate limited)")
        except Exception as e:
            print(f"  web_search failed (requires network):{e}")

    # 3) Public data source awareness: currency conversion (convert budget 200 USD to CNY)
    _header("[3/5] Public data source awareness: currency conversion + Wikipedia summary (online)")
    if offline:
        print("  Skipped (offline mode)")
    else:
        try:
            fx = _unwrap(await convert_currency(200, "USD", "CNY"))
            if fx.get("success"):
                m = fx["message"]
                print(f"  Budget conversion: 200 USD ≈ {m['converted_amount']:.2f} CNY"
                      f" (exchange rate {m.get('exchange_rate')}）")
        except Exception as e:
            print(f"  Currency conversion failed (requires network):{e}")
        try:
            wiki = _unwrap(await search_wikipedia("Model Context Protocol", sentences=2))
            if wiki.get("success"):
                print(f"  Wikipedia：{wiki['message']['title']}")
                print(f"    {wiki['message']['summary'][:120]}...")
            else:
                print("  Wikipedia returned no results (possibly rate limited), agent can use other sources")
        except Exception as e:
            print(f"  Wikipedia query failed (requires network):{e}")

    # 4) Multimodal understanding: read web page body
    _header("[4/5] Multimodal understanding: fetch web page body (online)")
    if offline:
        print("  Skipped (offline mode)")
    else:
        try:
            page = _unwrap(await read_webpage("https://example.com", extract_text=True))
            if page.get("success"):
                m = page["message"]
                print(f"  Page title:{m.get('title')}; Body length: {m.get('text_length', 0)} characters")
        except Exception as e:
            print(f"  Web scraping failed (network required): {e}")

    # 5) Private data sources: authorization required
    _header("[5/5] Private data source awareness: Calendar / Notion (authorization required)")
    print("  calendar_events requires Google OAuth authorization, notion_search requires NOTION_API_KEY.")
    print("  When not configured, the tool returns structured failure information, and the Agent can prompt the user to authorize accordingly.")

    print("\n" + "=" * 72)
    print("Demo complete. Key point: Perception tools are the 'senses' of the Agent—read-only, cacheable, parallelizable;")
    print("      The design key lies in granularity trade-offs and output information control (see Chapter 4).")
    print("=" * 72 + "\n")

    # Clean temporary knowledge base
    for f in tmp.glob("*"):
        f.unlink()
    tmp.rmdir()


def cmd_demo(args) -> int:
    asyncio.run(_demo(offline=args.offline))
    return 0


# ---------------------------------------------------------------------------
# Parameter parsing
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Command-line entry point for the perception tool MCP server (Experiment 4-1).\n"
                    "Organized by five perception scenarios: Search / Multimodal Understanding / File System / Public Data Sources / Private Data Sources.",
        epilog="Examples:\n"
               "  python cli.py list                         List all perception tools\n"
               "  python cli.py list --category filesystem   List only file system tools\n"
               "  python cli.py info weather                 View weather parameters\n"
               "  python cli.py run grep pattern=async directory=src   Call grep\n"
               "  python cli.py run currency_converter amount=100 from_currency=USD to_currency=CNY\n"
               "  python cli.py demo --offline               Run offline end-to-end demo\n",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    p_list = sub.add_parser("list", help="List all perception tools (grouped by five categories)")
    p_list.add_argument("--category", choices=list(CATEGORIES),
                        help="List only one category:" + " / ".join(f"{k}={v}" for k, v in CATEGORIES.items()))
    p_list.set_defaults(handler=cmd_list)

    p_info = sub.add_parser("info", help="View parameter signature and examples for a tool")
    p_info.add_argument("tool", help="Tool name (see list)")
    p_info.set_defaults(handler=cmd_info)

    p_run = sub.add_parser("run", help="Directly call a tool and print JSON result")
    p_run.add_argument("tool", help="Tool name (see list)")
    p_run.add_argument("params", nargs="*", metavar="key=value",
                       help="Tool parameters in key=value format")
    p_run.set_defaults(handler=cmd_run)

    p_demo = sub.add_parser("demo", help="Run end-to-end perception scenario demo")
    p_demo.add_argument("--offline", action="store_true",
                        help="Offline mode: run only steps that do not require network (file system / local knowledge base)")
    p_demo.set_defaults(handler=cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
