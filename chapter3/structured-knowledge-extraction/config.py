"""
Global configuration: load environment variables, provide OpenAI client and default model name.

Only depends on the official OpenAI SDK, reads OPENAI_API_KEY.
Default model gpt-5.6-luna (cheap, sufficient for factor discovery, structured extraction, and copy generation).
"""
import os

from openai import OpenAI

try:
    # Optional: if python-dotenv is installed, automatically load .env from the same directory
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is an optional dependency
    pass

def _openrouter_model_id(model) -> str:
    """Map vendor native model names to OpenRouter model IDs (for generic OpenRouter fallback).
    Explicit OPENROUTER_MODEL environment variable takes precedence."""
    override = os.getenv("OPENROUTER_MODEL")
    if override:
        return override
    m = (model or "").strip()
    if not m:
        return "openai/gpt-5.6-luna"
    if "/" in m:
        return m
    ml = m.lower()
    if ml.startswith(("gpt-", "o1", "o3", "o4", "chatgpt")):
        return "openai/" + m
    if ml.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    if ml.startswith("kimi"):
        # kimi-k3 is not on OpenRouter; moonshotai/kimi-k2.6 is the closest hosted id.
        return "moonshotai/kimi-k2.6"
    return "openai/gpt-5.6-luna"


# Default model, can be overridden by environment variable
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

# Generic OpenRouter fallback: if no OPENAI_API_KEY but OPENROUTER_API_KEY is set,
# route chat models to OpenRouter and map model names to OpenRouter IDs.
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# gpt-5.x (including gpt-5.6*) requires organization real-name authentication on the OpenAI direct API; as long as
# OPENROUTER_API_KEY is set, prefer routing such IDs through OpenRouter.
_PREFER_OPENROUTER = bool(_OPENROUTER_API_KEY) and MODEL.lower().startswith("gpt-5")
_USE_OPENROUTER = _PREFER_OPENROUTER or ((not _OPENAI_API_KEY) and bool(_OPENROUTER_API_KEY))
if _USE_OPENROUTER:
    MODEL = _openrouter_model_id(MODEL)


def get_client() -> OpenAI:
    """Return a configured OpenAI client.

    Prefer the official endpoint (reads OPENAI_API_KEY); if missing, fall back to OpenRouter (OpenAI-compatible endpoint) when OPENROUTER_API_KEY is present."""
    # timeout + automatic retry: discovery/extraction stages may send dozens of requests consecutively; a single transient error
    # (network jitter / rate limiting / 5xx) should not interrupt the entire pipeline.
    if _OPENAI_API_KEY and not _PREFER_OPENROUTER:
        return OpenAI(api_key=_OPENAI_API_KEY, timeout=60.0, max_retries=5)
    if _OPENROUTER_API_KEY:
        return OpenAI(
            api_key=_OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            timeout=60.0,
            max_retries=5,
        )
    raise RuntimeError(
        "No OPENAI_API_KEY or OPENROUTER_API_KEY found. Please `cp env.example .env` first "
        "and fill in your OpenAI Key (or OpenRouter Key as fallback)."
    )
