"""
Unified LLM client configuration.

Defaults to OpenAI (reads OPENAI_API_KEY, model gpt-5.6-luna).
Also supports switching to Moonshot / Volcano Ark (ARK) via the environment variable LLM_PROVIDER,
both of which are compatible with OpenAI's Chat Completions + tool call interface.

    export LLM_PROVIDER=openai   # default
    export LLM_PROVIDER=moonshot # uses MOONSHOT_API_KEY
    export LLM_PROVIDER=ark      # uses ARK_API_KEY, and must set ARK_MODEL

Unified OpenRouter fallback:
    If the selected provider's own key is missing but OPENROUTER_API_KEY is set, automatically switch to
    OpenRouter (https://openrouter.ai/api/v1), and map the model name to OpenRouter naming:
        gpt-*     -> openai/gpt-*
        claude-*  -> anthropic/claude-opus-4.8
        contains "/"    -> pass through as-is
        others    -> openai/gpt-5.6-luna
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

#Default configuration for each provider: base_url / environment variable name / default model
_PROVIDERS = {
    "openai": {
        "base_url": None,  #Use SDK defaults
        "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-5.6-luna",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "key_env": "MOONSHOT_API_KEY",
        "default_model": "kimi-k3",
    },
    "ark": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "key_env": "ARK_API_KEY",
        #ARK requires using the inference endpoint id as the model, please specify via ARK_MODEL
        "default_model": os.getenv("ARK_MODEL", "doubao-seed-1-6-250615"),
    },
}


def get_provider() -> str:
    return os.getenv("LLM_PROVIDER", "openai").lower().strip()


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


def _is_reasoning_model(model: str) -> bool:
    """gpt-5.x / o1·o3·o4 / kimi-k3 / *reasoner and other reasoning models: do not accept temperature=0,
    direct connection to gpt-5.x also requires organizational real-name and has limited tool calls, so prefer OpenRouter."""
    m = (model or "").lower()
    return (m.startswith(("gpt-5", "o1", "o3", "o4"))
            or m.startswith("kimi-k3")
            or "reasoner" in m or "thinking" in m)


def _use_openrouter(cfg: dict) -> bool:
    """Two scenarios for using OpenRouter:
    1) The provider's own key is missing but OPENROUTER_API_KEY is set (unified fallback);
    2) The target is gpt-5.x and OPENROUTER_API_KEY is set — direct connection to gpt-5.x requires organizational real-name,
       and /chat/completions tool calls are limited, so even if OPENAI_API_KEY is set, prefer OpenRouter."""
    if not os.getenv("OPENROUTER_API_KEY"):
        return False
    if not os.getenv(cfg["key_env"]):
        return True
    model = os.getenv("LLM_MODEL") or cfg["default_model"]
    return (model or "").lower().startswith("gpt-5")


def get_model() -> str:
    """Allow overriding the default model with LLM_MODEL; map model name under OpenRouter fallback path."""
    provider = get_provider()
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
    cfg = _PROVIDERS[provider]
    model = os.getenv("LLM_MODEL") or cfg["default_model"]
    if _use_openrouter(cfg):
        return _to_openrouter_model(model)
    return model


def get_client() -> OpenAI:
    provider = get_provider()
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
    cfg = _PROVIDERS[provider]
    if _use_openrouter(cfg):
        return OpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url=OPENROUTER_BASE_URL)
    api_key = os.getenv(cfg["key_env"])
    if not api_key:
        raise RuntimeError(
            f"Environment variable {cfg['key_env']} is not set, and OPENROUTER_API_KEY is also not set."
            f"Please refer to env.example to configure one of them (OpenRouter can serve as a unified fallback) and retry."
        )
    kwargs = {"api_key": api_key}
    if cfg["base_url"]:
        kwargs["base_url"] = cfg["base_url"]
    return OpenAI(**kwargs)


# All LLM calls uniformly use low temperature to ensure reproducible results;
# but reasoning models (gpt-5.x / o series / kimi-k3, etc.) only accept default temperature=1,
# so the default temperature is automatically selected based on the currently resolved model (can be explicitly overridden with LLM_TEMPERATURE).
def _default_temperature() -> str:
    provider = get_provider()
    cfg = _PROVIDERS.get(provider, _PROVIDERS["openai"])
    model = os.getenv("LLM_MODEL") or cfg["default_model"]
    return "1" if _is_reasoning_model(model) else "0"


TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", _default_temperature()))
