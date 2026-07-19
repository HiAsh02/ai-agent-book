"""Packaging layer LLM environment resolution: provides configuration with OpenRouter fallback for GAIA experience learning examples.

This file resides in the gaia-experience packaging layer and does **not modify** the upstream AWorld fork. It centralizes the scattered
`os.getenv("LLM_API_KEY"/"LLM_BASE_URL"/"LLM_MODEL_NAME")` reads and adds a unified fallback:

- If LLM_API_KEY / OPENAI_API_KEY is set -> direct connection (uses LLM_BASE_URL, can be empty for OpenAI official)
- Otherwise, if OPENROUTER_API_KEY is set -> route through OpenRouter (https://openrouter.ai/api/v1),
  and map model names to OpenRouter naming:
      gpt-*    -> openai/gpt-*
      claude-* -> anthropic/claude-opus-4.8
      contains "/"   -> pass through as-is
      others     -> openai/gpt-5.6-luna

Default model: gpt-5.6-luna.
"""

import os

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


def resolve_llm(default_model: str = DEFAULT_MODEL, model_override: str = None) -> dict:
    """Returns the provider/model/base_url/api_key quadruple required by AgentConfig (with OpenRouter fallback).

    model_override: if a model name is explicitly given (e.g., in config.yaml or CLI), it takes precedence.
    """
    provider = os.getenv("LLM_PROVIDER", "openai")
    model = model_override or os.getenv("LLM_MODEL_NAME", default_model)
    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key and os.getenv("OPENROUTER_API_KEY"):
        api_key = os.getenv("OPENROUTER_API_KEY")
        base_url = base_url or OPENROUTER_BASE_URL
        model = to_openrouter_model(model)

    return {
        "llm_provider": provider,
        "llm_model_name": model,
        "llm_base_url": base_url,
        "llm_api_key": api_key,
    }
