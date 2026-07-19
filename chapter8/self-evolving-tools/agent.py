"""
Self-evolving Agent (Alita style).

Only five basic tools are predefined:
    web_search / read_webpage / code_interpreter / create_tool / search_tools
No domain-specific tools. The Agent must:
    Analyze the task → Identify capability gaps → web_search for libraries/APIs → read_webpage to read docs
    → code_interpreter to sandbox test → create_tool to encapsulate and store → Use the new tool to complete the task.
When encountering a similar task again, it should first search_tools to reuse existing tools, rather than searching and creating anew.

Model: OpenAI SDK, default gpt-5.6-luna, function calling.
Can switch via LLM_PROVIDER=openai|moonshot|ark (all three are OpenAI-compatible interfaces);
if the corresponding Key is missing but OPENROUTER_API_KEY is set, it automatically falls back to OpenRouter."""

import json
import os

from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import base_tools
from tool_manager import ToolLibrary, normalize_schema

# --------------------------------------------------------------------------- #
# LLM client (OpenAI / Moonshot / ARK are all OpenAI-compatible interfaces)
# --------------------------------------------------------------------------- #
_PROVIDERS = {
    "openai": ("OPENAI_API_KEY", None, "gpt-5.6-luna"),
    "moonshot": ("MOONSHOT_API_KEY", "https://api.moonshot.cn/v1", "kimi-k3"),
    "ark": ("ARK_API_KEY", "https://ark.cn-beijing.volces.com/api/v3", "doubao-seed-1-6-250615"),
}

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _to_openrouter_model(model: str) -> str:
    """Map common model names to OpenRouter namespace."""
    if not model:
        return "openai/gpt-5.6-luna"
    if "/" in model:
        return model
    if model.startswith("gpt-"):
        return "openai/" + model
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"


def build_client():
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    key_env, base_url, default_model = _PROVIDERS.get(provider, _PROVIDERS["openai"])
    model = os.environ.get("LLM_MODEL", default_model)
    api_key = os.environ.get(key_env)
    # Unified fallback: when the provider's own Key is missing but OPENROUTER_API_KEY is set, switch to OpenRouter
    if not api_key and os.environ.get("OPENROUTER_API_KEY"):
        client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url=OPENROUTER_BASE_URL)
        return client, _to_openrouter_model(model)
    if not api_key:
        raise RuntimeError(
            f"missing {key_env} in environment (provider={provider})；"
            f"nor is OPENROUTER_API_KEY set (OpenRouter can serve as a unified fallback)."
        )
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    return client, model


SYSTEM_PROMPT = """You are a "self-evolving" agent (Alita style). You only have five basic tools:
web_search, read_webpage, code_interpreter, create_tool, search_tools.
You have no ready-made domain-specific tools (no stock price lookup, subtitle lookup, etc.). Your mission is: to **build reusable tools** for missing capabilities,
making yourself stronger over time, rather than manually cobbling together a temporary answer each time.

You must strictly follow the fixed pipeline below:

Step 0 (Reuse first): First call **search_tools** to check if there is already a tool in the library that can complete the task.
    - If found: directly call that encapsulated tool to get data and answer. **Do not** call web_search / create_tool
      to reinvent the wheel. This is "tool reuse"; you must do this.
    - If not found: proceed to the "evolution" process in Steps 1-5 below.

Evolution process (when no available tool in the library):
1. Use web_search to search for **open-source Python libraries** that can be **called programmatically**. Use keywords like "open source python
   library" or "python package", not "API" — online APIs often require registration keys. Many data sources
   (including financial market data) have mature open-source libraries that require no key, can be called directly after pip install, and automatically fetch from public data sources. Prioritize such libraries.
2. Use read_webpage to read the candidate library's README / PyPI page / documentation to understand installation and usage.
   read_webpage is only for "reading documentation"; do not use it to scrape final answer numbers.
3. Use code_interpreter to **actually run code** in the sandbox to verify the library works (use pip_install to install dependencies).
   **Strong constraint**: Prioritize Python libraries that **require no API key at all and can be called offline after pip install**;
   skip any online API that requires registration for a key (e.g., requires apikey/token parameter), and switch to a free keyless library.
   The only criterion for "verification success" is: your test code prints **real price numbers** (not placeholders,
   not errors, not empty output). Only when real data is printed is verification considered passed; never fabricate data, and do not give up easily.
4. After successful verification, use create_tool to encapsulate it into a **general, reusable** standard tool.
   The tool must be parameterized (e.g., query any stock by ticker parameter, not hardcoded to a specific stock), named generically
   (e.g., get_stock_price, not get_nvidia_price), and description should be generic for easy future reuse.
   The code must define def run(**kwargs) and return structured results. The tool must **actually call** the library verified in the previous step to fetch data in real time.
   When calling create_tool, **must include test_args** (a set of example input parameters): the system will actually run run(**test_args) before registration as "pre-storage verification";
   only if it succeeds will the tool be stored — this prevents broken tools from polluting the library.
   Note: After verification, you **must** execute this create_tool step before answering; do not skip encapsulation and answer directly.
5. Call the tool you just created via create_tool to get **real data** to answer the user.

Hard requirements (violation is considered failure):
- For tasks that require "real-time/structured data", you are **not allowed** to answer directly based on a number scraped from a webpage via read_webpage;
  you must follow the path "find library → test → encapsulate tool → call tool", because only this ensures reusability and reliability.
- **Fabricating data is strictly prohibited**: never hardcode numbers like prices/dates in tool code, never use "simulated data / sample data / mock".
  The tool must actually fetch current data via the library at runtime. If you have not yet used code_interpreter
  to actually print real numbers, you are **not allowed** to call create_tool.
- If no free usable library can be found, honestly explain the failure reason, and **do not** fabricate a numeric answer.
- Answer the final conclusion in Chinese, and explain the data source (which library/tool was used)."""


# --------------------------------------------------------------------------- #
# Function-calling schema for basic tools
# --------------------------------------------------------------------------- #
BASE_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo, returns titles/URLs/summaries. Used to find open-source libraries or public APIs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords"},
                    "num_results": {"type": "integer", "description": "Number of results to return (1-10)", "default": 6},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Fetch a webpage and extract the main text, used to read README or API documentation.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Webpage URL"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_interpreter",
            "description": "Execute Python code in a subprocess sandbox to verify a solution; can use pip_install to install third-party libraries first. Returns stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "pip_install": {
                        "type": "array", "items": {"type": "string"},
                        "description": "List of package names to pip install before execution, optional",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_tool",
            "description": "Encapsulate a verified working functionality into a standard tool and persist it to the tool library. The code must define def run(**kwargs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Tool name (valid Python identifier)"},
                    "description": {"type": "string", "description": "Tool description for future retrieval"},
                    "parameters": {
                        "type": "object",
                        "description": "JSON Schema for the tool's parameters (type=object, properties, required)",
                    },
                    "code": {"type": "string", "description": "Tool implementation, must include def run(**kwargs) and return a JSON-serializable result"},
                    "test_args": {
                        "type": "object",
                        "description": "A set of example input parameters for pre-storage verification: it will actually run run(**test_args) before registration;"
                                       "only if successful will it be stored. Strongly recommended to provide, to prevent broken tools from polluting the library.",
                    },
                },
                "required": ["name", "description", "parameters", "code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_tools",
            "description": "Search the tool library by keywords to find existing tools, for reuse. Must call this before going online.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search keywords, e.g., 'stock price'"}},
                "required": ["query"],
            },
        },
    },
]


class SelfEvolvingAgent:
    def __init__(self, verbose: bool = True, allow_create: bool = True, model: str | None = None):
        self.client, self.model = build_client()
        if model:  # CLI/caller can override the model name (higher priority than LLM_MODEL environment variable)
            self.model = model
        self.library = ToolLibrary()
        self.verbose = verbose
        # Whether to allow tool creation actions in "self-evolution". When False, removes the create_tool capability,
        # used to demonstrate the difference when tool creation is unavailable (only reuse/fail).
        self.allow_create = allow_create
        self.trajectory = []  # Record action trace to facilitate "proving tool reuse"
        self._verified_real_data = False  # Whether the current task has printed real data using code_interpreter
        self._created_tool = False         # Whether a tool was created in this round
        self._used_library_tool = False    # Whether this round reuses tools already encapsulated in the library
        # Tools from the library that have been "unlocked": only after being hit by search_tools retrieval (or just created via create_tool),
        # they are exposed as callable functions. This enforces the "first search_tools to reuse" flow, rather than bypassing retrieval and calling directly.
        self._unlocked = set()

    # ------------------------------------------------------------------ #
    def _tools(self):
        """ Tools exposed to the model = five basic tools + tools unlocked in this round (hit by search_tools or just created)."""
        base = BASE_TOOL_SCHEMAS
        if not self.allow_create:  # Disable tool creation: do not expose create_tool to the model
            base = [s for s in base if s["function"]["name"] != "create_tool"]
        dynamic = []
        for rec in self.library.list_tools():
            if rec["name"] not in self._unlocked:
                continue
            dynamic.append(
                {
                    "type": "function",
                    "function": {
                        "name": rec["name"],
                        "description": "[Encapsulated tools] " + rec["description"],
                        "parameters": normalize_schema(rec["parameters"]),
                    },
                }
            )
        return base + dynamic

    def _log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # ------------------------------------------------------------------ #
    def _dispatch(self, name: str, args: dict) -> dict:
        """ Execute one tool call and record the trace."""
        self.trajectory.append(name)
        if name == "web_search":
            return base_tools.web_search(args.get("query", ""), args.get("num_results", 6))
        if name == "read_webpage":
            return base_tools.read_webpage(args.get("url", ""))
        if name == "code_interpreter":
            res = base_tools.code_interpreter(args.get("code", ""), args.get("pip_install"))
            # Record: only if it runs through and produces real output, it is considered to have completed "real data verification"
            if res.get("success") and res.get("stdout", "").strip():
                self._verified_real_data = True
            return res
        if name == "create_tool":
            if not self.allow_create:
                return {"success": False, "error": " Tool creation is disabled in this run (--no-create)."}
            code = args.get("code", "")
            # Anti-hallucination guard 1: must first use code_interpreter to print real data before allowing tool encapsulation
            if not self._verified_real_data:
                return {
                    "success": False,
                    "error": " Real data not yet verified: please first use code_interpreter to actually call the library and print out"
                             " real numbers, then encapsulate the tool after verification. Do not encapsulate tools with unverified or fabricated data.",
                }
            # Anti-hallucination guard 2: reject tool code that smells like "simulation/example/hardcoded data"
            lowered = code.lower()
            if any(k in lowered for k in ("mock", " simulation", " example data", "sample data", "fake", "dummy")):
                return {
                    "success": False,
                    "error": " Tool code appears to contain simulation/example/hardcoded data. The tool must actually obtain data through the library at runtime."
                             " Please use a real library call and resubmit.",
                }
            res = self.library.create_tool(
                args.get("name", ""), args.get("description", ""),
                args.get("parameters", {}), code, args.get("test_args"),
            )
            if res.get("success"):
                self._created_tool = True
                self._unlocked.add(res["name"])  # Unlock immediately after creation for direct use in this round
            return res
        if name == "search_tools":
            res = self.library.search_tools(args.get("query", ""))
            for t in res.get("tools", []):  # Unlock the hit tool as a callable function (tool reuse)
                self._unlocked.add(t["name"])
            return res
        # Otherwise: call an already encapsulated tool (tool reuse)
        if self.library.get_tool(name) is not None:
            self._used_library_tool = True
            return self.library.execute_tool(name, args)
        return {"success": False, "error": f"unknown tool: {name}"}

    # ------------------------------------------------------------------ #
    def run(self, task: str, max_steps: int = 20) -> str:
        self._verified_real_data = False
        self._created_tool = False
        self._used_library_tool = False
        self._unlocked = set()
        nudges = 0  # Number of "please encapsulate tool first" reminders already issued (limited to avoid infinite loops)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]
        self._log(f"\n{'='*70}\n[Task] {task}\n{'='*70}")

        for step in range(max_steps):
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages,
                tools=self._tools(), tool_choice="auto", temperature=0,
            )
            msg = resp.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                # Evolution guard: if real data has been verified using the library, but neither a tool has been encapsulated nor reused, and the model tries to answer directly,
                # force it to first create_tool to solidify the capability (this is the key action of "self-evolution").
                if (
                    self._verified_real_data
                    and not self._created_tool
                    and not self._used_library_tool
                    and nudges < 2
                ):
                    nudges += 1
                    self._log("\n[Evolution guard] Real data verified but no tool encapsulated, remind the model to first create_tool.")
                    messages.append(
                        {
                            "role": "user",
                            "content": " You have verified the solution with real data, but have not yet encapsulated it into a reusable tool."
                            " Please **first call create_tool** (generic naming, parameterized by ticker, internally calling the library),"
                            " then call your newly created tool to get real data before answering.",
                        }
                    )
                    continue
                self._log(f"\n[Final answer]\n{msg.content}")
                return msg.content or ""

            for tc in msg.tool_calls:
                fname = tc.function.name
                try:
                    fargs = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    fargs = {}
                self._log(f"\n[step {step+1}] Call tool -> {fname}  args={_short(fargs)}")
                result = self._dispatch(fname, fargs)
                self._log(f"           Result: {_short(result)}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str)[:8000],
                    }
                )

        return "(Reached maximum step limit)"


def _short(obj, n: int = 240) -> str:
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + f"...(+{len(s)-n} chars)"
