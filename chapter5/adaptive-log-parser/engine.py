"""
engine.py —— Adaptive log parsing engine (self-healing closed-loop "runtime")

Design highlights:
- The engine maintains a **parser registry** (ordered list). For each incoming log line, it tries each parser in turn;
  whoever can parse (returns a non-empty dict) uses its result; if all fail, a ParseError is thrown — this is
  the signal for "frontend detected a new format that cannot be parsed", triggering the subsequent self-healing flow.
- Each parser is a pure function `parse(line: str) -> dict | None`:
    * Can parse → returns structured fields (dict)
    * Does not recognize the line → returns None (gives other parsers a chance, avoiding "snatching")
- Generated parsers can be persisted as parsers/*.py modules, and hot-loaded for reuse on next startup without asking the Agent again.

Note: "Visualization" is degraded here — the book uses a virtual browser + Vision LLM to verify rendering effects;
this project instead uses **data structure assertions** on parse functions (see tester.py), and the core self-healing closed loop is actually implemented.
"""

from __future__ import annotations

import importlib.util
import json
import os
from typing import Callable, Dict, List, Optional, Tuple

#  A parser = (name, parse function)
ParserFn = Callable[[str], Optional[Dict]]


class ParseError(Exception):
    """Thrown when all registered parsers fail to parse the line, carrying the original sample for Agent analysis."""

    def __init__(self, line: str):
        self.line = line
        super().__init__(f"No registered parser can parse this line:{line!r}")


def builtin_json_parser(line: str) -> Optional[Dict]:
    """Built-in basic parser: only recognizes standard JSON lines (JSON Lines).

    Format: {"timestamp": "...", "level": "INFO", "message": "..."}
    If not JSON, or lacks basic fields, returns None (not my format).
    """
    line = line.strip()
    if not (line.startswith("{") and line.endswith("}")):
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    #  At least one basic field is required to consider it a "valid JSON log"
    if not any(k in obj for k in ("timestamp", "level", "message")):
        return None
    return obj


class LogParserEngine:
    """Log parsing system: holds a set of parsers and supports hot-loading registration of new parsers."""

    def __init__(self) -> None:
        self._parsers: List[Tuple[str, ParserFn]] = []

    # -- Registration / Query --------------------------------------------------------
    def register(self, name: str, fn: ParserFn) -> None:
        """Register (or replace if same name) a parser. New parsers have higher priority, appended to the end of the list before trying."""
        #  If same name exists, remove it first to achieve "hot-update replacement"
        self._parsers = [(n, f) for (n, f) in self._parsers if n != name]
        self._parsers.append((name, fn))

    @property
    def parser_names(self) -> List[str]:
        return [n for n, _ in self._parsers]

    # -- Parsing ---------------------------------------------------------------
    def parse_line(self, line: str) -> Dict:
        """Try each parser on a line; on success, annotate _parser in the result. If all fail, throw ParseError."""
        for name, fn in self._parsers:
            try:
                result = fn(line)
            except Exception:
                #  An error from one parser does not mean others will fail; continue trying
                continue
            if result:
                return {"_parser": name, **result}
        raise ParseError(line)

    # -- Hot-loading: load parse function from .py file ----------------------------------
    @staticmethod
    def load_parser_from_file(path: str) -> ParserFn:
        """Dynamically import a parsers/*.py module and extract its parse function."""
        module_name = "genparser_" + os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module:{path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  #  Execute module, define parse
        fn = getattr(module, "parse", None)
        if not callable(fn):
            raise ImportError(f"{path}  No callable parse(line) function found in ")
        return fn

    def load_persisted(self, parsers_dir: str) -> List[str]:
        """On startup, hot-load and register all persisted parsers from the parsers/ directory (reuse historical results)."""
        loaded: List[str] = []
        if not os.path.isdir(parsers_dir):
            return loaded
        for fname in sorted(os.listdir(parsers_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            path = os.path.join(parsers_dir, fname)
            fn = self.load_parser_from_file(path)
            name = os.path.splitext(fname)[0]
            self.register(name, fn)
            loaded.append(name)
        return loaded
