"""
Experiment 8-4 Tool Library: 120+ cross-domain tool definitions.

Design highlights:
1) Each tool has a real, readable name / description / parameters (OpenAI function schema).
2) Domains cover finance / news / web / arxiv / file / github / code / geo / weather /
   media / language / email / db / ecommerce / social / crypto / util, etc.
3) Intentionally mix in many "generic/synonymous" tools (web_search / universal_search / quick_answer ...),
   which compete with "specialized tools" when fully injected, inducing the model to choose incorrectly (e.g., using web_search to look up stock prices).
4) Tool execution only does lightweight mocking — this experiment cares about "whether the correct tool is selected", not the actual tool results.

Exports:
- ALL_TOOLS          : List[dict]  OpenAI tools array (126 items)
- TOOLS_BY_NAME      : Dict[str, dict]
- TOOL_IMPLS         : Dict[str, callable]  mock execution functions
- BASE_TOOL_NAMES    : small set of basic tools retained in the system under active discovery mode
- GENERIC_TOOL_NAMES : set of generic/fallback tools (used to count "whether a generic tool replaced a specialized tool")
- select_tools       : truncate tool subset by --tool-set-size (demonstrates the impact of tool set size)
- TASKS              : List[dict]  evaluation tasks and their scoring criteria
"""

from typing import Dict, List


def _tool(name: str, description: str, params: Dict) -> Dict:
    """Construct an OpenAI function-calling tool schema."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": params,
                "required": list(params.keys()),
            },
        },
    }


def _s(desc: str) -> Dict:
    return {"type": "string", "description": desc}


def _i(desc: str) -> Dict:
    return {"type": "integer", "description": desc}


# ---------------------------------------------------------------------------
#Tool definitions (grouped by domain)
# ---------------------------------------------------------------------------

_DEFS: List[Dict] = []

# --- finance (specialized, 10) ---
_DEFS += [
    _tool("get_stock_price", "Get the real-time latest stock price, change percentage, and volume for a given ticker (professional financial data source).",
          {"symbol": _s("Stock ticker, e.g., AAPL, TSLA")}),
    _tool("get_stock_history", "Get historical K-line data for a stock.",
          {"symbol": _s("Stock ticker"), "range": _s("Time range, e.g., 1mo/1y")}),
    _tool("get_company_financials", "Get financial report data (revenue, profit, balance sheet) for a listed company.",
          {"symbol": _s("Stock ticker")}),
    _tool("get_forex_rate", "Get real-time foreign exchange rate between two fiat currencies.",
          {"base": _s("Base currency, e.g., USD"), "quote": _s("Quote currency, e.g., JPY")}),
    _tool("get_crypto_price", "Get the real-time price of a specified cryptocurrency (USD denominated).",
          {"symbol": _s("Cryptocurrency code, e.g., BTC, ETH")}),
    _tool("get_market_index", "Get the real-time level of a stock market index, e.g., S&P 500, Nasdaq.",
          {"index": _s("Index code, e.g., SPX, IXIC")}),
    _tool("get_earnings_calendar", "Query the earnings release calendar for a company.", {"symbol": _s("Stock ticker")}),
    _tool("get_analyst_ratings", "Get analyst ratings and target price for a stock.", {"symbol": _s("Stock ticker")}),
    _tool("get_dividend_history", "Get historical dividend records for a stock.", {"symbol": _s("Stock ticker")}),
    _tool("convert_currency", "Convert an amount from one currency to another at the latest exchange rate.",
          {"amount": {"type": "number", "description": "Amount"},
           "from_currency": _s("Source currency"), "to_currency": _s("Target currency")}),
]

# --- news (specialized, 4) ---
_DEFS += [
    _tool("search_news", "Search for the latest news articles by keyword, returning title, source, time, and summary (news aggregation source).",
          {"query": _s("Search keyword"), "lang": _s("Language, e.g., zh/en")}),
    _tool("get_top_headlines", "Get top headlines for a category/country.",
          {"category": _s("Category, e.g., business/tech"), "country": _s("Country code, e.g., us/cn")}),
    _tool("get_news_by_source", "Get the latest reports from a specified news media source.", {"source": _s("Media source, e.g., reuters")}),
    _tool("summarize_article", "Scrape and summarize the core content of a news article.", {"url": _s("Article URL")}),
]

# --- web / generic (general retrieval, misleading selection, 8) ---
_DEFS += [
    _tool("web_search", "General web search, can query almost any real-time information and give answers,"
                        "including stock prices, exchange rates, weather, news, encyclopedia, code, geography, and other questions—one tool for most queries.",
          {"query": _s("Search keyword")}),
    _tool("universal_search", "Universal search assistant, can answer questions on any topic,"
                             "covering information queries in finance, technology, life, academia, and all fields.", {"query": _s("Query")}),
    _tool("quick_answer", "Give quick and short answers to any question, suitable for instant queries like prices, weather, news, common knowledge, etc.",
          {"question": _s("Question")}),
    _tool("google_search", "Search the web using Google, can query the latest information on any topic.", {"query": _s("Query")}),
    _tool("bing_search", "Search the web using Bing, can query the latest information on any topic.", {"query": _s("Query")}),
    _tool("fetch_url", "Scrape the raw content of a given URL.", {"url": _s("Webpage URL")}),
    _tool("scrape_webpage", "Scrape a webpage and extract structured content by CSS selector.",
          {"url": _s("Webpage URL"), "selector": _s("CSS selector")}),
    _tool("ask_knowledge_base", "Ask a general knowledge base and get encyclopedia-style answers.", {"question": _s("Question")}),
]

# --- arxiv / academic (academic dedicated, 5) ---
_DEFS += [
    _tool("arxiv_search", "Search papers in the arXiv repository, return paper titles, authors, abstracts, and PDF links by relevance/time.",
          {"query": _s("Search keyword"), "max_results": _i("Number of papers to return")}),
    _tool("arxiv_get_paper", "Get detailed information of a single paper by arXiv ID.", {"arxiv_id": _s("arXiv ID")}),
    _tool("semantic_scholar_search", "Search academic papers on Semantic Scholar.", {"query": _s("Keywords")}),
    _tool("get_citations", "Get the citation list of a paper.", {"paper_id": _s("Paper ID")}),
    _tool("search_pubmed", "Search biomedical literature on PubMed.", {"query": _s("Keywords")}),
]

# --- file / download (file download, 10) ---
_DEFS += [
    _tool("download_file", "Download a file (PDF/image/archive, etc.) from a given URL and save it locally.",
          {"url": _s("File URL"), "path": _s("Local save path")}),
    _tool("upload_file", "Upload a local file to remote storage.", {"path": _s("Local file path")}),
    _tool("read_file", "Read the content of a local text file.", {"path": _s("File path")}),
    _tool("write_file", "Write content to a local file.", {"path": _s("File path"), "content": _s("Content to write")}),
    _tool("list_directory", "List files in a directory.", {"path": _s("Directory path")}),
    _tool("delete_file", "Delete a local file.", {"path": _s("File path")}),
    _tool("convert_document", "Convert document format, e.g., docx→pdf.",
          {"path": _s("File path"), "target_format": _s("Target format")}),
    _tool("extract_text_from_pdf", "Extract text from a PDF file.", {"path": _s("PDF path")}),
    _tool("compress_files", "Compress multiple files into an archive.", {"paths": _s("Comma-separated file paths")}),
    _tool("unzip_archive", "Decompress an archive.", {"path": _s("Archive path")}),
]

# --- github / dev (code hosting specific, 8) ---
_DEFS += [
    _tool("github_get_repo", "Get basic information about a GitHub repository (stars, language, description, etc.).",
          {"owner": _s("Repository owner"), "repo": _s("Repository name")}),
    _tool("github_list_contributors", "List contributors of a GitHub repository and their commit counts (using GitHub API).",
          {"owner": _s("Repository owner"), "repo": _s("Repository name")}),
    _tool("github_list_issues", "List issues of a GitHub repository.",
          {"owner": _s("Repository owner"), "repo": _s("Repository name")}),
    _tool("github_get_commits", "Get commit history of a GitHub repository.",
          {"owner": _s("Repository owner"), "repo": _s("Repository name")}),
    _tool("github_search_code", "Search code on GitHub by keyword.", {"query": _s("Search keyword")}),
    _tool("github_get_pull_requests", "List PRs of a GitHub repository.",
          {"owner": _s("Repository owner"), "repo": _s("Repository name")}),
    _tool("github_get_user", "Get GitHub user profile.", {"username": _s("Username")}),
    _tool("gitlab_get_project", "Get GitLab project information.", {"project_id": _s("Project ID")}),
]

# --- code / analysis (Code Execution and Visualization, 6) ---
_DEFS += [
    _tool("code_interpreter", "Execute Python code in a sandbox for data analysis, statistics, and generating/rendering visual charts.",
          {"code": _s("Python code to execute")}),
    _tool("render_chart", "Render bar/line/pie charts directly based on given data.",
          {"data": _s("JSON data"), "chart_type": _s("Chart type, e.g., bar/line/pie")}),
    _tool("run_shell_command", "Execute shell commands on the server.", {"command": _s("Command")}),
    _tool("lint_code", "Perform static code analysis.", {"code": _s("Code"), "language": _s("Language")}),
    _tool("format_code", "Format code.", {"code": _s("Code"), "language": _s("Language")}),
    _tool("execute_sql", "Execute SQL queries.", {"query": _s("SQL statement")}),
]

# --- geo / maps (Geography, 6) ---
_DEFS += [
    _tool("geocode_address", "Convert an address to latitude/longitude coordinates.", {"address": _s("Address")}),
    _tool("reverse_geocode", "Convert latitude/longitude to an address.", {"lat": _s("Latitude"), "lon": _s("Longitude")}),
    _tool("get_directions", "Get navigation route between two locations.", {"origin": _s("Origin"), "destination": _s("Destination")}),
    _tool("get_distance", "Calculate distance between two locations.", {"origin": _s("Origin"), "destination": _s("Destination")}),
    _tool("search_places", "Search for places/businesses near a specified location.",
          {"query": _s("Keywords"), "location": _s("Location")}),
    _tool("get_timezone", "Get timezone based on coordinates.", {"lat": _s("Latitude"), "lon": _s("Longitude")}),
]

# --- weather (weather-specific, 3) ---
_DEFS += [
    _tool("get_current_weather", "Get real-time weather (temperature, humidity, weather conditions) for a specified city.", {"location": _s("City name")}),
    _tool("get_weather_forecast", "Get weather forecast for a specified city for the next several days (professional meteorological data source).",
          {"location": _s("City name"), "days": _i("Forecast days")}),
    _tool("get_air_quality", "Get the Air Quality Index (AQI) for a specified city.", {"location": _s("City name")}),
]

# --- media (multimedia, 6) ---
_DEFS += [
    _tool("generate_image", "Generate an image based on a text prompt.", {"prompt": _s("Image description")}),
    _tool("caption_image", "Generate a text description for an image.", {"url": _s("Image URL")}),
    _tool("transcribe_audio", "Transcribe audio to text.", {"url": _s("Audio URL")}),
    _tool("text_to_speech", "Synthesize speech from text.", {"text": _s("Text")}),
    _tool("video_summarize", "Summarize the content of a video.", {"url": _s("Video URL")}),
    _tool("ocr_image", "Recognize text in an image.", {"url": _s("Image URL")}),
]

# --- language / NLP (text processing, 8) ---
_DEFS += [
    _tool("translate_text", "Translate text into a target language.", {"text": _s("Text"), "target_lang": _s("Target language")}),
    _tool("detect_language", "Detect the language of text.", {"text": _s("Text")}),
    _tool("summarize_text", "Summarize a piece of text.", {"text": _s("Text")}),
    _tool("paraphrase_text", "Rewrite/polish a piece of text.", {"text": _s("Text")}),
    _tool("correct_grammar", "Correct grammatical errors in text.", {"text": _s("Text")}),
    _tool("sentiment_analysis", "Analyze the sentiment of text.", {"text": _s("Text")}),
    _tool("extract_keywords", "Extract keywords from text.", {"text": _s("Text")}),
    _tool("named_entity_recognition", "Recognize named entities in text.", {"text": _s("Text")}),
]

# --- email / comm / calendar (Communication & Calendar, 7) ---
_DEFS += [
    _tool("send_email", "Send an email.",
          {"to": _s("Recipient"), "subject": _s("Subject"), "body": _s("Body")}),
    _tool("read_inbox", "Read emails from the mailbox.", {"folder": _s("Folder, e.g., inbox")}),
    _tool("create_calendar_event", "Create an event/appointment on the user's calendar (dedicated calendar service).",
          {"title": _s("Event title"), "start": _s("Start time"), "end": _s("End time")}),
    _tool("list_calendar_events", "List calendar events for a given date.", {"date": _s("Date YYYY-MM-DD")}),
    _tool("send_slack_message", "Send a message to a Slack channel.", {"channel": _s("Channel"), "text": _s("Content")}),
    _tool("send_sms", "Send an SMS.", {"number": _s("Phone number"), "text": _s("Content")}),
    _tool("make_phone_call", "Make a phone call and read a script.", {"number": _s("Phone number"), "script": _s("Script")}),
]

# --- database / storage (Storage, 7) ---
_DEFS += [
    _tool("query_database", "Execute a read-only query on the business database.", {"sql": _s("SQL query")}),
    _tool("insert_record", "Insert a record into a data table.", {"table": _s("Table name"), "data": _s("JSON data")}),
    _tool("get_record", "Read a record by primary key.", {"table": _s("Table name"), "id": _s("Primary key")}),
    _tool("redis_get", "Read a Redis key-value pair.", {"key": _s("Key")}),
    _tool("redis_set", "Write Redis key-value.", {"key": _s("Key"), "value": _s("Value")}),
    _tool("s3_upload", "Upload file to S3.", {"bucket": _s("Bucket"), "key": _s("Object key"), "path": _s("Local path")}),
    _tool("s3_download", "Download file from S3.", {"bucket": _s("Bucket"), "key": _s("Object key")}),
]

# --- ecommerce / travel (8) ---
_DEFS += [
    _tool("search_products", "Search for products on e-commerce platform.", {"query": _s("Keywords")}),
    _tool("get_product_details", "Get product details.", {"product_id": _s("Product ID")}),
    _tool("add_to_cart", "Add product to shopping cart.", {"product_id": _s("Product ID"), "qty": _i("Quantity")}),
    _tool("track_shipment", "Query express logistics.", {"tracking_no": _s("Tracking number")}),
    _tool("search_flights", "Search flights.",
          {"origin": _s("Departure"), "destination": _s("Destination"), "date": _s("Date")}),
    _tool("search_hotels", "Search hotels.",
          {"location": _s("City"), "checkin": _s("Check-in date"), "checkout": _s("Check-out date")}),
    _tool("book_restaurant", "Book a restaurant.",
          {"name": _s("Restaurant name"), "time": _s("Time"), "party": _i("Number of people")}),
    _tool("get_product_reviews", "Get product reviews.", {"product_id": _s("Product ID")}),
]

# --- social (5) ---
_DEFS += [
    _tool("post_tweet", "Post a tweet.", {"text": _s("Content")}),
    _tool("search_tweets", "Search tweets.", {"query": _s("Keywords")}),
    _tool("get_user_profile", "Get social platform user profile.",
          {"platform": _s("Platform"), "username": _s("Username")}),
    _tool("get_trending_topics", "Get trending topics.", {"region": _s("Region")}),
    _tool("get_reddit_posts", "Get posts from a subreddit.", {"subreddit": _s("Subreddit")}),
]

# --- crypto / blockchain (blockchain, 3) ---
_DEFS += [
    _tool("get_wallet_balance", "Query on-chain wallet balance.", {"address": _s("Wallet address")}),
    _tool("get_gas_price", "Query on-chain gas price.", {"chain": _s("Chain name, e.g., ethereum")}),
    _tool("get_nft_metadata", "Get NFT metadata.", {"contract": _s("Contract address"), "token_id": _s("token ID")}),
]

# --- misc util (miscellaneous tools, 10) ---
_DEFS += [
    _tool("calculator", "Evaluate a mathematical expression.", {"expression": _s("Mathematical expression")}),
    _tool("get_current_time", "Get current time in a specified timezone.", {"timezone": _s("Timezone, e.g., Asia/Shanghai")}),
    _tool("generate_uuid", "Generate a UUID.", {"version": _i("UUID version")}),
    _tool("get_random_number", "Generate a random number within a range.", {"min": _i("Minimum value"), "max": _i("Maximum value")}),
    _tool("url_shortener", "Generate a short link.", {"url": _s("Original URL")}),
    _tool("qr_code_generator", "Generate a QR code.", {"data": _s("QR code content")}),
    _tool("password_generator", "Generate a random password.", {"length": _i("Password length")}),
    _tool("get_ip_info", "Query IP geolocation information.", {"ip": _s("IP address")}),
    _tool("dns_lookup", "Query domain DNS records.", {"domain": _s("Domain name")}),
    _tool("ping_host", "Test host connectivity.", {"host": _s("Hostname")}),
]


# --- More domain tools (supplement 120+, 12) ---
_DEFS += [
    _tool("get_commodity_price", "Get real-time prices of commodities (gold/oil, etc.).", {"commodity": _s("Commodity name, e.g., gold/oil")}),
    _tool("get_bond_yield", "Get government bond yields.", {"country": _s("Country"), "maturity": _s("Maturity, e.g., 10y")}),
    _tool("get_flight_status", "Query real-time flight status.", {"flight_no": _s("Flight number")}),
    _tool("get_traffic_info", "Query real-time traffic conditions for a road segment.", {"road": _s("Road segment/city")}),
    _tool("book_taxi", "Call a taxi/ride-hailing car.", {"pickup": _s("Pickup location"), "dropoff": _s("Destination")}),
    _tool("get_horoscope", "Get horoscope.", {"sign": _s("Zodiac sign")}),
    _tool("get_recipe", "Get a recipe based on ingredients or dish name.", {"dish": _s("Dish name")}),
    _tool("get_definition", "Look up word definitions.", {"word": _s("Word")}),
    _tool("currency_list", "List supported currency codes.", {"region": _s("Region")}),
    _tool("get_holidays", "Query official holidays for a country in a given year.", {"country": _s("Country"), "year": _i("Year")}),
    _tool("unit_convert", "Unit conversion (length, weight, temperature, etc.).",
          {"value": {"type": "number", "description": "Value"}, "from_unit": _s("Source unit"), "to_unit": _s("target unit")}),
    _tool("get_wikipedia_summary", "Get a summary of a Wikipedia article.", {"title": _s("article title")}),
]


# ---------------------------------------------------------------------------
# export structure
# ---------------------------------------------------------------------------

ALL_TOOLS: List[Dict] = _DEFS
TOOLS_BY_NAME: Dict[str, Dict] = {t["function"]["name"]: t for t in ALL_TOOLS}
assert len(ALL_TOOLS) == len(TOOLS_BY_NAME), "Duplicate tool name!"

# In active discovery mode, a small set of basic tools reserved by the system (excluding any domain-specific tools).
BASE_TOOL_NAMES = ["calculator", "get_current_time"]

# General/fallback tools: if these are invoked in tasks requiring specialized tools, it is considered "using a general tool instead of a specialized tool."
GENERIC_TOOL_NAMES = {
    "web_search", "universal_search", "quick_answer", "google_search",
    "bing_search", "fetch_url", "scrape_webpage", "ask_knowledge_base",
}


def select_tools(size: int = None, tasks: "List[Dict]" = None) -> List[Dict]:
    """Truncate a tool subset according to --tool-set-size to demonstrate the impact of "tool set size" on each strategy.

    The subset **always** includes: basic tools, all general/fallback tools (inducement items), and the specialized tools involved in the scoring slots of the selected task;
    the remaining slots are filled in the original order of ALL_TOOLS until reaching the specified size.
    If size is empty or >= the full library size, return all tools (default behavior).
    """
    if size is None or size >= len(ALL_TOOLS):
        return ALL_TOOLS
    keep = set(BASE_TOOL_NAMES) | set(GENERIC_TOOL_NAMES)
    for task in (tasks if tasks is not None else TASKS):
        for slot in task["required_slots"]:
            keep.update(slot)
    size = max(size, len(keep))
    required = [t for t in ALL_TOOLS if t["function"]["name"] in keep]
    others = [t for t in ALL_TOOLS if t["function"]["name"] not in keep]
    return required + others[: size - len(required)]


# ---------------------------------------------------------------------------
# mock execution
# ---------------------------------------------------------------------------

def _mock_result(name: str, args: Dict) -> str:
    """Return decent mock results for commonly used tools, and generic placeholder results for the rest."""
    import json
    canned = {
        "get_stock_price": {"symbol": args.get("symbol"), "price": 227.52,
                            "change_pct": -1.83, "currency": "USD", "source": "NASDAQ"},
        "get_crypto_price": {"symbol": args.get("symbol"), "price": 3125.4, "currency": "USD"},
        "get_forex_rate": {"base": args.get("base"), "quote": args.get("quote"), "rate": 156.7},
        "convert_currency": {"amount": args.get("amount"), "from": args.get("from_currency"),
                             "to": args.get("to_currency"), "result": 15670.0, "rate": 156.7},
        "search_news": {"results": [
            {"title": "Apple shares slip on iPhone demand concerns", "source": "Reuters"},
            {"title": "Analysts weigh in on AAPL pullback", "source": "Bloomberg"}]},
        "arxiv_search": {"results": [
            {"id": "2406.00001", "title": "Efficient Transformers Revisited",
             "pdf": "https://arxiv.org/pdf/2406.00001"},
            {"id": "2406.00002", "title": "Sparse Attention Transformers",
             "pdf": "https://arxiv.org/pdf/2406.00002"},
            {"id": "2406.00003", "title": "Transformer Scaling Laws 2024",
             "pdf": "https://arxiv.org/pdf/2406.00003"}]},
        "download_file": {"saved": args.get("path"), "bytes": 482113, "status": "ok"},
        "github_list_contributors": {"contributors": [
            {"login": "alice", "commits": 1240}, {"login": "bob", "commits": 830},
            {"login": "carol", "commits": 617}]},
        "code_interpreter": {"stdout": "chart saved to /tmp/contrib.png", "status": "ok"},
        "render_chart": {"chart": "/tmp/contrib.png", "status": "ok"},
        "get_weather_forecast": {"location": args.get("location"),
                                 "forecast": [{"day": "Sun", "cond": "Sunny", "high": 31}]},
        "get_current_weather": {"location": args.get("location"), "cond": "Clear", "temp": 28},
        "create_calendar_event": {"event": args.get("title"), "status": "created"},
    }
    if name in canned:
        return json.dumps(canned[name], ensure_ascii=False)
    return json.dumps({"tool": name, "args": args, "status": "ok",
                       "result": f"<{name} mock result for "}, ensure_ascii=False)


# All tools share a single mock dispatcher
TOOL_IMPLS: Dict[str, callable] = {
    name: (lambda args, n=name: _mock_result(n, args)) for name in TOOLS_BY_NAME
}


# ---------------------------------------------------------------------------
# Evaluation tasks and scoring criteria
# ---------------------------------------------------------------------------
# required_slots: List[List[str]]
#   Each inner list is the set of acceptable tools for "one capability slot" (hitting any one fills that slot).
#   A task is judged as "correctly selected" if and only if all slots are filled.
# These tasks require cross-domain collaboration and all have the trap that "general tools are easily mis-selected."

TASKS: List[Dict] = [
    {
        "id": "finance+news",
        "prompt": "How is Apple's stock price doing recently? Can you find any related news to explain the reason?",
        "required_slots": [
            ["get_stock_price"],
            ["search_news", "get_top_headlines", "get_news_by_source"],
        ],
    },
    {
        "id": "arxiv+download",
        "prompt": "I want to see the latest research papers in the transformer field. Help me find a few recent ones and download the top three.",
        "required_slots": [
            ["arxiv_search"],
            ["download_file"],
        ],
    },
    {
        "id": "github+viz",
        "prompt": "Check the pytorch/pytorch repository to see who has contributed the most. It would be best to draw a chart of each person's commit counts.",
        "required_slots": [
            ["github_list_contributors"],
            ["code_interpreter", "render_chart"],
        ],
    },
    {
        "id": "weather+calendar",
        "prompt": "What's the weather like in Beijing this Sunday? If it's sunny, help me add an 'outdoor hiking' event to my calendar.",
        "required_slots": [
            ["get_weather_forecast"],
            ["create_calendar_event"],
        ],
    },
    {
        "id": "forex+weather",
        "prompt": "How many Japanese yen can 100 US dollars get now? Also, tell me the current weather in Tokyo.",
        "required_slots": [
            ["get_forex_rate", "convert_currency"],
            ["get_current_weather"],
        ],
    },
    {
        "id": "crypto+news",
        "prompt": "What's the price of Ethereum now? Also, any latest related news?",
        "required_slots": [
            ["get_crypto_price"],
            ["search_news", "get_top_headlines", "get_news_by_source"],
        ],
    },
    # The following two are "general tool inducement" tasks: the wording is vague, making it easy for the model to mistakenly use general fallback tools like web_search,
    # while there are actually more suitable specialized tools. Used to demonstrate "full injection misselects general tools, active discovery selects specialized tools."
    {
        "id": "opinion (inducement)",
        "prompt": "Help me understand the recent news and public sentiment about Tesla.",
        "required_slots": [
            ["search_news", "get_news_by_source", "get_top_headlines"],
        ],
    },
    {
        "id": "academic (inducement)",
        "prompt": "Help me find out about the latest scientific research progress in 'quantum computing'.",
        "required_slots": [
            ["arxiv_search", "semantic_scholar_search", "search_pubmed"],
        ],
    },
]


def grade(task: Dict, called_tools: List[str]) -> Dict:
    """Score a task based on the tools actually invoked."""
    called = set(called_tools)
    filled = []
    missed = []
    for slot in task["required_slots"]:
        if any(t in called for t in slot):
            filled.append(slot)
        else:
            missed.append(slot)
    used_generic = sorted(called & GENERIC_TOOL_NAMES)
    correct = len(missed) == 0
    return {
        "correct": correct,                       # Whether all capability slots are covered
        #  Precise selection = covering all capability slots without misusing general fallback tools (web_search, etc.)
        "precise": correct and not used_generic,
        "filled_slots": len(filled),
        "total_slots": len(task["required_slots"]),
        "missed_slots": missed,
        "used_generic_substitute": used_generic,
    }


if __name__ == "__main__":
    print(f"Total tools: {len(ALL_TOOLS)}")
    print(f"Basic tools: {BASE_TOOL_NAMES}")
    print(f"Number of tasks: {len(TASKS)}")
