"""Experiment 5-11: Conversational UI Customization Agent.

Responsibility: Receive a natural language UI customization request (e.g., "change the send button to blue"), read the frontend source code, call OpenAI to have the model locate and rewrite the corresponding source files (color/font/text/layout/components).

Design Highlights
--------
- Only expose a small set of "customizable files" to the model (App.jsx and theme.css under frontend/src), reducing the chance of the model modifying the wrong files and making changes controllable and verifiable.
- Use the `apply_edits` tool via function calling to let the model return the "full file content to be rewritten entirely". Compared to scattered search/replace, full file rewriting is more stable for small files and less likely to break syntax.
- Before modification, snapshot the original file content; after modification, compute diff, read back assertions, and run build verification.

Environment Variables:
  OPENAI_API_KEY   (required, this experiment reads this)
  OPENAI_BASE_URL  (optional, switch to a service endpoint compatible with OpenAI protocol)
  MODEL            (optional, default gpt-5.6-luna)
  OPENROUTER_API_KEY (optional, automatically fallback to OpenRouter when no direct key is available)
"""

import os
import json
from pathlib import Path

from openai import OpenAI

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is an optional dependency
    pass


#Frontend source files customizable by the Agent (relative to frontend/).
EDITABLE_FILES = [
    "src/App.jsx",
    "src/theme.css",
]


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def map_model_to_openrouter(model: str) -> str:
    """Map direct model names to OpenRouter IDs (non-mappable IDs fallback to the current cheap flagship)."""
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


def build_client_and_model():
    model = os.getenv("MODEL", "gpt-5.6-luna")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    orkey = os.getenv("OPENROUTER_API_KEY")
    # Generic OpenRouter fallback: when no direct key is available, or default gpt-5.x (direct connection requires organization real-name authentication), switch to OpenRouter.
    prefer_or = bool(orkey) and (model or "").lower().startswith("gpt-5")
    if prefer_or or (not api_key and orkey):
        api_key, base_url, model = orkey, OPENROUTER_BASE_URL, map_model_to_openrouter(model)
    if not api_key:
        raise SystemExit("OPENAI_API_KEY (or OPENROUTER_API_KEY fallback) not found. Please set it in environment variables or .env file.")
    # timeout / max_retries: allow occasional network/SSL jitter to auto-retry without crashing the whole round
    client_kwargs = {"api_key": api_key, "timeout": 60.0, "max_retries": 3}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
    return client, model


APPLY_EDITS_TOOL = {
    "type": "function",
    "function": {
        "name": "apply_edits",
        "description": (
            "Rewrite one or more frontend source files based on the user's UI customization request."
            "Only return files that truly need modification; each file returns the complete rewritten content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Describe in one sentence what was changed this time (in Chinese).",
                },
                "files": {
                    "type": "array",
                    "description": "List of files to be rewritten.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "File path relative to frontend/,"
                                "Must be one of the editable files.",
                            },
                            "content": {
                                "type": "string",
                                "description": "Complete content of the file after rewriting.",
                            },
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            "required": ["summary", "files"],
        },
    },
}


SYSTEM_PROMPT = """You are a frontend UI customization Agent responsible for translating the user's natural language UI requirements into React (Vite) source code.

Rules:
1. Only modify the "editable files" provided by the user; do not add or delete files.
2. Prioritize minimal changes: modify colors/fonts/spacing etc. in theme.css; modify text/component structure in App.jsx.
3. Use explicit CSS color values (e.g., hex #2563eb). If the user provides a specific color value, use it.
4. Keep the code compilable: JSX/CSS syntax must be correct, do not break existing functionality.
5. Must call the apply_edits tool to return results, with files containing the complete rewritten file content.
"""


def read_editable_sources(frontend_dir: Path) -> dict:
    """Read the current content of all editable files and return {relative_path: content}."""
    sources = {}
    for rel in EDITABLE_FILES:
        p = frontend_dir / rel
        sources[rel] = p.read_text(encoding="utf-8")
    return sources


def customize(client, model, frontend_dir: Path, requirement: str) -> dict:
    """Let the model rewrite source code based on a natural language request, returning the parameter dict for apply_edits.

    Only call the model and parse tool parameters; do not write to disk (file writing and verification are done in demo.py to facilitate diff display).
    """
    sources = read_editable_sources(frontend_dir)

    file_blocks = "\n\n".join(
        f"===== File: {rel} =====\n{content}" for rel, content in sources.items()
    )
    user_prompt = (
        f"Current content of editable files:\n\n{file_blocks}\n\n"
        f"User's customization request:{requirement}\n\n"
        f"Please call apply_edits to return the full content of files that need rewriting."
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        tools=[APPLY_EDITS_TOOL],
        tool_choice={"type": "function", "function": {"name": "apply_edits"}},
        temperature=(1 if any(k in (model or "").lower()
                              for k in ("gpt-5", "o1", "o3", "o4", "thinking", "reasoner", "kimi-k3"))
                     else 0),
    )

    msg = resp.choices[0].message
    if not msg.tool_calls:
        raise RuntimeError("The model did not return an apply_edits tool call.")
    args = json.loads(msg.tool_calls[0].function.arguments)

    # Security check: only allow rewriting files in the whitelist.
    for f in args.get("files", []):
        if f["path"] not in EDITABLE_FILES:
            raise RuntimeError(f"The model attempted to modify a non-whitelisted file:{f['path']}")
    return args
