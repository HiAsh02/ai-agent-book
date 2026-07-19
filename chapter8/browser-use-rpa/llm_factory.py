"""Wrapper LLM factory: provides a unified model client with OpenRouter fallback for browser-use examples.

This file resides in the RPA wrapper layer and does **not modify** the upstream browser-use fork. It selects the provider based on environment variables:
- gemini-* models            -> ChatGoogle (uses GOOGLE_API_KEY)
- OPENAI_API_KEY present     -> direct OpenAI
- Otherwise OPENROUTER_API_KEY present -> use OpenRouter, mapping model names to OpenRouter naming:
      gpt-*    -> openai/gpt-*
      claude-* -> anthropic/claude-opus-4.8
      contains "/"   -> pass through as-is
      others     -> openai/gpt-5.6-luna

Default model: gpt-5.6-luna.
"""

import os

from browser_use import ChatOpenAI, ChatGoogle

DEFAULT_MODEL = "gpt-5.6-luna"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def to_openrouter_model(model: str) -> str:
    if not model:
        return "openai/gpt-5.6-luna"
    if "/" in model:
        return model
    if model.startswith("gpt-"):
        return "openai/" + model
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"


def make_llm(model: str = None):
    """Constructs an LLM client based on environment variables (OpenAI direct connection preferred, OpenRouter fallback when key is missing)."""
    model = model or DEFAULT_MODEL
    if model.startswith("gemini"):
        return ChatGoogle(model=model)
    if os.getenv("OPENAI_API_KEY"):
        return ChatOpenAI(model=model)
    if os.getenv("OPENROUTER_API_KEY"):
        return ChatOpenAI(
            model=to_openrouter_model(model),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=OPENROUTER_BASE_URL,
        )
    raise RuntimeError(
        "Neither OPENAI_API_KEY nor OPENROUTER_API_KEY detected. Please configure one in .env"
        "(OpenRouter can serve as a unified fallback)."
    )
