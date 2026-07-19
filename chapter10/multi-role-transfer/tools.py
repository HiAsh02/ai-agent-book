"""
tools.py — Dedicated tool implementations for each professional role + OpenAI function-calling schema.

Design principles (in coordination with Experiment 10-2):
- Tools use "lightweight real implementations" or "controllable mocks"; the focus is not on how powerful the tools are,
  but on demonstrating the mechanism of "autonomous role handover".
- research.web_search: built-in knowledge base mock (controllable, reproducible),
  returns "No results found" honestly when no match.
- coding.execute_python: actually executes Python code and captures stdout (restricted namespace).
- data_analysis.calculate / descriptive_stats: real safe calculations.
- writing.count_characters: real Chinese and English character count.

Each tool function signature is func(**kwargs) -> str (unified return string for easy insertion into conversation history).
"""

from __future__ import annotations

import ast
import io
import math
import operator
import contextlib
from typing import Callable, Dict, List


# ---------------------------------------------------------------------------
# research role: web_search — built-in knowledge base mock
# ---------------------------------------------------------------------------

# A minimal knowledge base for "web search results". Returns built-in data when keywords match,
# ensuring the demo is reproducible without relying on the real internet.
_KNOWLEDGE_BASE = [
    {
        "keywords": ["New energy", "Automobile", "Sales", "nev", "Electric vehicle"],
        "content": (
            "【Search Result·China Passenger Car Market Information Association/CAAM】\n"
            "Annual sales of new energy vehicles in China (unit: 10,000 vehicles):\n"
            "- 2021: 352.1\n"
            "- 2022: 688.7\n"
            "- 2023: 949.5\n"
            "Note: Includes pure electric (BEV) and plug-in hybrid (PHEV) passenger vehicles."
        ),
    },
    {
        "keywords": ["Photovoltaic", "Installation", "Solar"],
        "content": (
            "【Search Result·National Energy Administration】\n"
            "Newly installed photovoltaic capacity in China (unit: GW):\n"
            "- 2021: 54.9 GW\n"
            "- 2022: 87.4 GW\n"
            "- 2023: 216.9 GW"
        ),
    },
    {
        "keywords": ["python", "gil", "Global Interpreter Lock"],
        "content": (
            "【Search Result·Technical Documentation】\n"
            "CPython's GIL (Global Interpreter Lock) ensures that only one thread executes bytecode at a time,"
            "so CPU-intensive tasks cannot be parallelized with multithreading; multiprocessing or C extensions are needed instead."
            "PEP 703 proposes an optional no-GIL build, available as an experimental feature since Python 3.13."
        ),
    },
]


def web_search(query: str) -> str:
    """Search in the built-in knowledge base (mock web search)."""
    q = (query or "").lower()
    hits: List[str] = []
    for entry in _KNOWLEDGE_BASE:
        if any(kw.lower() in q for kw in entry["keywords"]):
            hits.append(entry["content"])
    if hits:
        return "\n\n".join(hits)
    return (
        f"No authoritative data directly related to \"{query}\" was found in the built-in knowledge base."
        "Please use a more specific search term, or specify which year's data you need."
    )


# ---------------------------------------------------------------------------
# coding role: execute_python —— actually execute code and capture stdout
# ---------------------------------------------------------------------------

def execute_python(code: str) -> str:
    """Execute Python code in a restricted namespace and return its standard output."""
    safe_globals: Dict[str, object] = {
        "__builtins__": {
            "print": print,
            "range": range,
            "len": len,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "sorted": sorted,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "float": float,
            "int": int,
            "str": str,
        },
        "math": math,
    }
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, safe_globals, {})  # noqa: S102 —— teaching example under restricted namespace
    except Exception as exc:  # noqa: BLE001
        return f"Code execution error:{type(exc).__name__}: {exc}\nCaptured output:\n{buf.getvalue()}"
    out = buf.getvalue().strip()
    return out if out else "(Code executed, but no print output)"


# ---------------------------------------------------------------------------
# data_analysis role: calculate (safe expression evaluation) + descriptive_stats
# ---------------------------------------------------------------------------

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    """Safe expression evaluation supporting only arithmetic/power/modulo (does not use Python's built-in eval)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Expression contains unsupported operations; only + - * / ** % and parentheses are allowed.")


def calculate(expression: str) -> str:
    """Safely evaluate a pure mathematical expression, e.g., (949.5/352.1)**(1/2)-1."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
    except Exception as exc:  # noqa: BLE001
        return f"Calculation failed:{exc}"
    return f"{expression} = {result}"


def descriptive_stats(numbers: List[float]) -> str:
    """Return basic descriptive statistics (mean/max/min/range) for a set of numeric values."""
    if not numbers:
        return "Input is empty, cannot compute statistics."
    nums = [float(x) for x in numbers]
    n = len(nums)
    mean = sum(nums) / n
    return (
        f"Sample size={n}, mean={mean:.4f}, min={min(nums)}, "
        f"max={max(nums)}, range={max(nums) - min(nums)}"
    )


# ---------------------------------------------------------------------------
# writing role: count_characters —— count Chinese and English characters
# ---------------------------------------------------------------------------

def count_characters(text: str) -> str:
    """Count the total characters and Chinese characters in text to help control length."""
    total = len(text)
    chinese = sum(1 for ch in text if "一" <= ch <= "鿿")
    return f"Total characters={total}, of which Chinese characters={chinese}"


# ---------------------------------------------------------------------------
# Tool registry: name -> (implementation function, OpenAI schema)
# ---------------------------------------------------------------------------

# OpenAI function-calling schema for each tool.
TOOL_SCHEMAS: Dict[str, dict] = {
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search for information online (this experiment uses a built-in knowledge base mock). Used to look up data, facts, materials.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword or question"},
                },
                "required": ["query"],
            },
        },
    },
    "execute_python": {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "Execute a piece of Python code and return its print output. Suitable for writing scripts, running logic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python source code to execute, output result with print"},
                },
                "required": ["code"],
            },
        },
    },
    "calculate": {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Safely evaluate a math expression, supports + - * / ** % and parentheses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression, e.g., (949.5/352.1)**(1/2)-1"},
                },
                "required": ["expression"],
            },
        },
    },
    "descriptive_stats": {
        "type": "function",
        "function": {
            "name": "descriptive_stats",
            "description": "Compute basic descriptive statistics (mean/max/min/range) for a set of numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "numbers": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Array of numbers",
                    },
                },
                "required": ["numbers"],
            },
        },
    },
    "count_characters": {
        "type": "function",
        "function": {
            "name": "count_characters",
            "description": "Count text characters and Chinese characters to help control length.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to count"},
                },
                "required": ["text"],
            },
        },
    },
}

# Tool name -> implementation function
TOOL_IMPLEMENTATIONS: Dict[str, Callable[..., str]] = {
    "web_search": web_search,
    "execute_python": execute_python,
    "calculate": calculate,
    "descriptive_stats": descriptive_stats,
    "count_characters": count_characters,
}
