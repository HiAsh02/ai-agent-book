"""
agent.py —— Code Generation Agent (the "brain" of the self-healing loop)

Responsibility: Given an unparseable failed sample + error message, call OpenAI to generate a
Python parsing function `def parse(line: str) -> dict | None` that can correctly parse the format.
Supports feeding back the failure report from the previous auto-test round to regenerate (iterative repair).
"""

from __future__ import annotations

import os
import re
from typing import List, Optional

from openai import OpenAI

# .env loading (optional dependency)
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


SYSTEM_PROMPT = """You are a "log parser code generator". The user will provide you with a batch of log samples of the **same unknown format**,
and error messages from existing system parsing failures. Your task: write a Python function that parses each line of this format into structured fields.

Strict requirements:
1. Output only a Python code block (```python ... ```), no explanatory text.
2. The code block must define a function: def parse(line: str) -> dict | None
   - Input is a log line (string).
   - If the line matches the format you are parsing, return a dict with field names (English lowercase underscore) as keys and parsed content as values.
   - If the line **does not** match this format, must return None (do not raise exceptions, leave opportunity for other parsers).
3. Only use Python standard library (re, json, datetime, etc.), do not import third-party libraries.
4. No side effects such as print, input, file I/O, network access, etc.
5. Must parse all **required fields** (required_keys) specified by the user, field values cannot be empty.
6. Be robust: use regex/delimiters for parsing, tolerate spaces within field order."""


def _build_user_prompt(
    samples: List[str],
    required_keys: List[str],
    error_report: str,
    feedback: Optional[str],
) -> str:
    sample_block = "\n".join(samples)
    parts = [
        "The existing system cannot parse logs in the following format. Please generate a parsing function.",
        "",
        "[Failure sample (same new format)]",
        sample_block,
        "",
        f"[System Error]\n{error_report}",
        "",
        f"[Required parsed fields required_keys]\n{required_keys}",
    ]
    if feedback:
        parts += [
            "",
            "[The previous version of the code did not pass the automated tests. Please fix and regenerate.]",
            feedback,
        ]
    return "\n".join(parts)


def _extract_code(text: str) -> str:
    """Extract Python code blocks from the model response; fall back to the entire text when no fences are present."""
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _map_to_openrouter_model(model: str) -> str:
    """Map the direct model name to the ID on OpenRouter (non-mappable IDs fall back to the current cheap flagship)."""
    if not model or "/" in model:
        return model or "openai/gpt-5.6-luna"
    m = model.lower()
    if m.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai/" + model
    if m.startswith("claude"):
        if "haiku" in m:
            return "anthropic/claude-haiku-4.5"
        if "sonnet" in m:
            return "anthropic/claude-sonnet-4.6"
        return "anthropic/claude-opus-4.8"
    if m.startswith("gemini"):
        return "google/" + model
    return "openai/gpt-5.6-luna"


class CodeGenAgent:
    def __init__(self, model: Optional[str] = None):
        model = model or os.getenv("MODEL", "gpt-5.6-luna")
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        orkey = os.getenv("OPENROUTER_API_KEY")
        # General OpenRouter fallback: when there is no direct key, or the default gpt-5.x (direct connection requires organizational real-name authentication) is used, switch to OpenRouter.
        prefer_or = bool(orkey) and (model or "").lower().startswith("gpt-5")
        if prefer_or or (not api_key and orkey):
            api_key, base_url, model = orkey, OPENROUTER_BASE_URL, _map_to_openrouter_model(model)
        if not api_key:
            raise SystemExit("OPENAI_API_KEY (or fallback OPENROUTER_API_KEY) not found. Please set it in environment variables or .env.")
        # timeout / max_retries: automatically retry on occasional network/SSL glitches to avoid crashing the entire round
        client_kwargs = {"api_key": api_key, "timeout": 60.0, "max_retries": 3}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
        self.model = model

    def generate_parser_code(
        self,
        samples: List[str],
        required_keys: List[str],
        error_report: str,
        feedback: Optional[str] = None,
    ) -> str:
        """Call LLM to generate parser code, returning a pure Python source string."""
        user_prompt = _build_user_prompt(samples, required_keys, error_report, feedback)
        # Reasoning models (gpt-5 / o series, etc.) do not accept temperature=0.
        _reasoning = any(k in (self.model or "").lower()
                         for k in ("gpt-5", "o1", "o3", "o4", "thinking", "reasoner", "kimi-k3"))
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=1 if _reasoning else 0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        return _extract_code(resp.choices[0].message.content or "")


# ---------------------------------------------------------------------------
#  Offline (no API) code generation agent
# ---------------------------------------------------------------------------
#  The interface is exactly the same as CodeGenAgent, but instead of calling OpenAI, it returns **preset** values based on required fields.
# Parser source code. Its purpose is to deterministically demonstrate and verify the entire pipeline in environments without an API Key.
# Mechanism: failure detection → (preset) code generation → automatic testing → hot-load registration → persistent reuse.
# Note: The "generation" here returns pre-written code from a lookup table, not actually asking the LLM to write it on the fly; only when switching to
# CodeGenAgent is the real code generation.
_CANNED_PARSERS = {
    #  Vertical bar separated format: timestamp|level|module|step=N|message
    frozenset(["timestamp", "level", "module", "step", "message"]): '''import re


def parse(line: str) -> dict | None:
    pattern = (
        r"^(?P<timestamp>\\S+)\\|(?P<level>\\S+)\\|(?P<module>\\S+)"
        r"\\|step=(?P<step>\\d+)\\|(?P<message>.+)$"
    )
    match = re.match(pattern, line.strip())
    if match:
        return match.groupdict()
    return None
''',
    #  Nested bracket format: [time] (level) <tool=name> {k=v k=v} :: message
    frozenset(["timestamp", "level", "tool", "message"]): '''import re


def parse(line: str) -> dict | None:
    pattern = (
        r"\\[(?P<timestamp>.*?)\\] \\((?P<level>.*?)\\) <tool=(?P<tool>.*?)> "
        r"\\{latency_ms=(?P<latency_ms>\\d+) status=(?P<status>\\w+)\\} :: (?P<message>.*)"
    )
    match = re.match(pattern, line.strip())
    if match:
        return match.groupdict()
    return None
''',
}


class OfflineCodeGenAgent:
    """Offline mode: Look up table to return preset parser code, interface consistent with CodeGenAgent (no API Key required)."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or "offline-canned"

    def generate_parser_code(
        self,
        samples: List[str],
        required_keys: List[str],
        error_report: str,
        feedback: Optional[str] = None,
    ) -> str:
        key = frozenset(required_keys)
        code = _CANNED_PARSERS.get(key)
        if code is not None:
            return code
        #  Format not preset: return a stub that always returns None, so that automated tests fail truthfully,
        #  thereby demonstrating the branch of "test failed → abandon this format" (offline mode cannot actually write code on the fly).
        return (
            "def parse(line: str) -> dict | None:\n"
            "    # Offline mode does not have a preset parser for this format\n"
            "    return None\n"
        )
