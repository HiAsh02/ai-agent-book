"""
Configuration module: centrally read environment variables.

Experiment 10-1 uses the OpenAI official SDK; all adjustable items are injected via environment variables,
making it easy to switch to other vendors compatible with the OpenAI protocol (Kimi / Doubao, etc.).
"""

import os

try:
    # Allow writing configuration in .env (optional dependency)
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is not a hard dependency
    pass


def _to_openrouter_model(model: str) -> str:
    """Map model names to the OpenRouter namespace (for fallback paths without OPENAI_API_KEY)."""
    if "/" in model:
        return model                      # Already in OpenRouter namespace, use as-is
    if model.startswith("gpt-"):
        return "openai/" + model          # gpt-* -> openai/gpt-*
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"          # Fallback: current cheap flagship


class Config:
    """Runtime configuration."""

    # Required: OpenAI API Key (this experiment defaults to OPENAI_API_KEY)
    API_KEY: str = os.environ.get("OPENAI_API_KEY", "")

    # Optional: base_url compatible with OpenAI protocol, defaults to official address
    BASE_URL: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # Optional: model name, defaults to current cheap flagship gpt-5.6-luna to control demo cost
    MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")

    # Sampling temperature, slightly lower for more stable and reproducible behavior
    TEMPERATURE: float = float(os.environ.get("OPENAI_TEMPERATURE", "0.3"))

    @classmethod
    def validate(cls) -> None:
        """Validate and apply general fallback as needed.

        0) gpt-5.x series connecting directly to OpenAI requires organization verification (and these reasoning models only accept default temperature),
           so if OPENROUTER_API_KEY is set, even if OPENAI_API_KEY is also present, prioritize
           OpenRouter to avoid organization verification hassle;
        1) Otherwise, if OPENAI_API_KEY is set -> connect directly to OpenAI (respect OPENAI_BASE_URL);
        2) Otherwise, if OPENROUTER_API_KEY is set -> switch to OpenRouter and map model name;
        3) If neither is set, report a clear error.
        """
        or_key = os.environ.get("OPENROUTER_API_KEY", "")
        # gpt-5.x (including gpt-5.6-luna and other reasoning flagships) prioritize OpenRouter to avoid organization verification.
        needs_openrouter = cls.MODEL.startswith("gpt-5") and "/" not in cls.MODEL
        if or_key and (needs_openrouter or not cls.API_KEY):
            cls.API_KEY = or_key
            cls.BASE_URL = "https://openrouter.ai/api/v1"
            cls.MODEL = _to_openrouter_model(cls.MODEL)
            return
        if cls.API_KEY:
            return
        raise SystemExit(
            "Error: No OPENAI_API_KEY or OPENROUTER_API_KEY environment variable detected.\n"
            "Please `export OPENAI_API_KEY=...` (or OPENROUTER_API_KEY),"
            "or copy env.example to .env and fill it in."
        )
