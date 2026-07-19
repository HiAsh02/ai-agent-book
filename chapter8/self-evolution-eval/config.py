"""
Experiment 8-6 Configuration Module: Unified API Key Reading and OpenAI Client Construction.

Supports the following OpenAI-compatible services (selected by PROVIDER):
- openai   (default, reads OPENAI_API_KEY, default model gpt-5.6-luna)
- moonshot (reads MOONSHOT_API_KEY, Kimi, default kimi-k3)
- ark      (reads ARK_API_KEY, Volcengine Ark)

Unified OpenRouter fallback:
    If the selected provider's own Key is missing but OPENROUTER_API_KEY is set, automatically switch to
    OpenRouter (https://openrouter.ai/api/v1), and map the model name to OpenRouter naming:
        gpt-*     -> openai/gpt-*
        claude-*  -> anthropic/claude-opus-4.8
        contains "/"    -> pass through as-is
        others    -> openai/gpt-5.6-luna
    This allows one-click execution even without a direct OpenAI Key.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


#Base URL and default model for each provider
_PROVIDERS = {
    "openai": {
        "key_env": "OPENAI_API_KEY",
        "base_url": None,  #OpenAI official default address
        "default_model": "gpt-5.6-luna",
    },
    "moonshot": {
        "key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k3",
    },
    "ark": {
        "key_env": "ARK_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "doubao-seed-1-6-250615",
    },
}


def _to_openrouter_model(model: str) -> str:
    """Map common model names to the OpenRouter namespace."""
    if not model:
        return "openai/gpt-5.6-luna"
    if "/" in model:
        return model
    if model.startswith("gpt-"):
        return "openai/" + model
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"


class Config:
    #Default model for the Agent under test (tool creation)
    PROVIDER: str = os.getenv("PROVIDER", "openai").lower()
    AGENT_MODEL: str = os.getenv("AGENT_MODEL", "gpt-5.6-luna")
    #Model used by LLM-as-a-Judge (Layer 3 tool creation quality scoring)
    JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", "gpt-5.6-luna")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))

    @classmethod
    def provider_meta(cls) -> dict:
        if cls.PROVIDER not in _PROVIDERS:
            raise ValueError(
                f"Unknown PROVIDER={cls.PROVIDER}, options:{list(_PROVIDERS)}"
            )
        return _PROVIDERS[cls.PROVIDER]

    @classmethod
    def _use_openrouter(cls) -> bool:
        """When the selected provider's Key is missing but OPENROUTER_API_KEY is set, fall back to OpenRouter."""
        meta = cls.provider_meta()
        return (not os.getenv(meta["key_env"])) and bool(os.getenv("OPENROUTER_API_KEY"))

    @classmethod
    def map_model(cls, model: str) -> str:
        """Under the OpenRouter fallback path, map the model name to OpenRouter naming; otherwise return as-is."""
        return _to_openrouter_model(model) if cls._use_openrouter() else model

    @classmethod
    def get_client(cls) -> OpenAI:
        """Construct and return an OpenAI-compatible client (prefer direct connection, fall back to OpenRouter when Key is missing)."""
        meta = cls.provider_meta()
        if cls._use_openrouter():
            return OpenAI(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                base_url=OPENROUTER_BASE_URL,
            )
        api_key = os.getenv(meta["key_env"], "")
        if not api_key:
            raise RuntimeError(
                f"Not found {meta['key_env']}, and OPENROUTER_API_KEY is not set."
                f"Please configure one of them in .env (OpenRouter can serve as a unified fallback)."
            )
        kwargs = {"api_key": api_key}
        if meta["base_url"]:
            kwargs["base_url"] = meta["base_url"]
        return OpenAI(**kwargs)

    @classmethod
    def resolve_default_model(cls, override: Optional[str] = None) -> str:
        """Parse the model for the Agent under test: handle provider default fallback and OpenRouter naming mapping."""
        meta = cls.provider_meta()
        model = override or cls.AGENT_MODEL
        #For non-openai providers, if the default value is still gpt-*, fall back to that provider's default model
        if not override and cls.PROVIDER != "openai" and model.startswith("gpt-"):
            model = meta["default_model"]
        return cls.map_model(model)
