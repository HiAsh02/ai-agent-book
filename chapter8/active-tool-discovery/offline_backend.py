"""
Offline backend: enables the entire pipeline to run **without an OpenAI key**, used to verify mechanisms,
quantify tokens/latency, and allow readers to reproduce the comparison structure of "three strategies" at zero cost.

Contains two parts:
1) LocalEmbedder — a local hash bag-of-words embedding (Chinese character unigram/bigram + English words),
   no internet required to support semantic similarity for discover_tools / retrieval pre-filtering.
2) MockChatClient — a deterministic "scripted" model with an interface identical to the OpenAI client
   (client.chat.completions.create(...).choices[0].message.content).
   It decomposes tasks into subtasks based on keywords and follows the ReAct text protocol to call tools step by step.

Important boundary notes:
- MockChatClient is a **strongly heuristic router** and does not represent the capabilities of a real small model; therefore it **will not** reproduce
  the phenomenon of "instruction-following degradation and mis-selection of generic tools under extremely long contexts" described in the book — that requires a real small-parameter model.
- What can be truly reproduced in offline mode: ① the token count injected by each strategy (real computation via tiktoken);
  ② the structural limitation of retrieval pre-filtering "one-shot matching" (if the specialized tool for the second subtask is not selected by the initial retrieval,
  the model cannot call it → the subtask fails); ③ proactive discovery that tools can still be supplemented and tasks completed after on-demand loading.
- To observe the selection behavior of real models under a long-context tool wall, please configure a real model (see the real results table for gpt-5.6-luna in the README).
"""

import hashlib
import json
import re
from types import SimpleNamespace
from typing import Dict, List, Tuple

from tools_library import TOOLS_BY_NAME

_DIM = 512


# ---------------------------------------------------------------------------
# 1) Local embedding backend
# ---------------------------------------------------------------------------

def _tokens(text: str) -> List[str]:
    """Tokenize mixed Chinese-English text into bag-of-words tokens: English by word (and split underscores), Chinese by character unigram + bigram."""
    text = text.lower()
    toks: List[str] = []
    for w in re.findall(r"[a-z0-9]+", text):
        toks.append(w)
    han = re.findall(r"[一-鿿]", text)
    toks += han
    toks += [han[i] + han[i + 1] for i in range(len(han) - 1)]
    return toks


class LocalEmbedder:
    """Hash bag-of-words embedding: deterministic, no internet required. Similarity is driven by overlapping Chinese and English keywords."""

    name = "local-hash-%d" % _DIM

    def embed(self, texts: List[str]) -> List[List[float]]:
        out = []
        for t in texts:
            vec = [0.0] * _DIM
            for tok in _tokens(t):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                vec[h % _DIM] += 1.0
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            out.append([x / norm for x in vec])
        return out


# ---------------------------------------------------------------------------
# 2) Scripted mock model
# ---------------------------------------------------------------------------
# Intent rules: map task keywords to the "specialized tool to use" and a capability requirement description.
# Order matters (e.g., "forecast" type weather must precede generic "weather").
INTENT_RULES: List[Tuple[str, str, str]] = [
    (r"stock price|stock", "get_stock_price", "Query the real-time price and change of a stock"),
    (r"Ethereum|Bitcoin|crypto|\beth\b|\bbtc\b", "get_crypto_price", "Query the real-time price of cryptocurrencies"),
    (r"yen|exchange rate|USD.*exchange|exchange.*(JPY|USD|EUR)|currency conversion", "get_forex_rate", "Query the foreign exchange rate between two fiat currencies"),
    (r"paper|arxiv|literature|quantum computing|research progress|research advance", "arxiv_search", "Search for the latest papers in the academic paper database"),
    (r"download", "download_file", "Download a file from a URL and save it locally"),
    (r"contributions", "github_list_contributors", "Get contributor commit statistics for a GitHub repository"),
    (r"chart|visualization|draw a|plot|graph", "render_chart", "Render a visualization chart based on data"),
    (r"forecast|future|Sunday|this week|tomorrow|day after tomorrow|next week", "get_weather_forecast", "Query the weather forecast for a city for the next few days"),
    (r"weather", "get_current_weather", "Query the current weather for a city"),
    (r"calendar|schedule|event|note a|record a", "create_calendar_event", "Create an event on the calendar"),
    (r"news|public opinion|message|report|trend", "search_news", "Search for the latest news by keyword"),
]


def match_intents(prompt: str) -> List[Tuple[str, str]]:
    """Return the list of (specialized tool name, capability requirement description) involved in the task (deduplicated, order-preserving)."""
    needed: List[Tuple[str, str]] = []
    seen = set()
    for pat, tool, phrase in INTENT_RULES:
        if re.search(pat, prompt, re.IGNORECASE) and tool not in seen:
            needed.append((tool, phrase))
            seen.add(tool)
    # Weather deduplication: if "forecast" is hit, do not separately require "real-time weather".
    if "get_weather_forecast" in seen and "get_current_weather" in seen:
        needed = [(t, p) for t, p in needed if t != "get_current_weather"]
    return needed


_ARG_HINTS = {
    "symbol": "AAPL", "location": "Beijing", "query": "query", "url": "https://example.com/f.pdf",
    "path": "/tmp/paper.pdf", "owner": "pytorch", "repo": "pytorch", "base": "USD",
    "quote": "JPY", "title": "outdoor hiking", "start": "2026-07-19T09:00", "end": "2026-07-19T12:00",
    "days": 3, "data": "[]", "chart_type": "bar", "code": "print('ok')", "max_results": 3,
}


def _fill_args(tool_name: str) -> Dict:
    tool = TOOLS_BY_NAME.get(tool_name)
    if not tool:
        return {}
    props = tool["function"]["parameters"]["properties"]
    args = {}
    for key, spec in props.items():
        if key in _ARG_HINTS:
            args[key] = _ARG_HINTS[key]
        elif spec.get("type") == "integer":
            args[key] = 1
        else:
            args[key] = "auto"
    return args


def _extract_json(text: str):
    text = text.strip()
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _json(thought: str, tool: str, arguments: Dict) -> str:
    return json.dumps({"thought": thought, "tool": tool, "arguments": arguments},
                      ensure_ascii=False)


class MockChatClient:
    """Deterministic script model; interface compatible with OpenAI client subset."""

    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model=None, messages=None, temperature=0, **kw):
        content = self._respond(messages or [])
        msg = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    def _respond(self, messages: List[Dict]) -> str:
        system = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        task_prompt = next((m["content"] for m in messages if m["role"] == "user"), "")
        full_text = "\n".join(m.get("content", "") for m in messages)
        has_discover = "discover_tools" in system

        # Current "available tools" = tool names appearing in the dialogue text (system injection / discover append).
        available = set(re.findall(r'"name":\s*"([a-zA-Z_][a-zA-Z0-9_]*)"', full_text))
        available.discard("discover_tools")

        prior = []
        for m in messages:
            if m["role"] == "assistant":
                a = _extract_json(m.get("content", ""))
                if a and "tool" in a:
                    prior.append(a)
        called_ok = {a["tool"] for a in prior if a["tool"] in available}
        discover_needs = [((a.get("arguments") or {}).get("need", ""))
                          for a in prior if a.get("tool") == "discover_tools"]
        attempted = [a["tool"] for a in prior
                     if a["tool"] not in available and a["tool"] not in ("discover_tools", "finish")]

        for tool, phrase in match_intents(task_prompt):
            if tool in called_ok:
                continue
            if tool in available:
                return _json(f"Call specialized tool {tool}", tool, _fill_args(tool))
            # Target tool currently unavailable
            if has_discover:
                if discover_needs.count(phrase) >= 1:
                    continue  # Already discovered but not yet hit -> abandon this subtask
                return _json(f"I need a tool that can '{phrase}', first discover it", "discover_tools",
                             {"need": phrase})
            else:
                if attempted.count(tool) >= 1:
                    continue  # Tool not in the list, try once and give up
                return _json(f"Task requires {tool}, try calling", tool, _fill_args(tool))
        return _json("All subtasks processed", "finish", {"answer": "Completed the subtasks that can be completed."})
