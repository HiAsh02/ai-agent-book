"""
Global configuration: model and pricing.

When converting costs, use "price per million tokens (USD)".
Default values are taken from OpenAI gpt-4o-mini's public pricing (2024-2025):
    - Input        : $0.15  / 1M tokens
    - Cached input : $0.075 / 1M tokens   (input hitting prompt cache is billed at 50% discount)
    - Output       : $0.60  / 1M tokens

Notes:
1. Default model is gpt-5.6-luna (current cheap flagship). Preferred credential is OPENAI_API_KEY; if not set,
   automatically fallback to OPENROUTER_API_KEY and map model name to OpenRouter id (gpt-* -> openai/*).
   Since gpt-5.x direct connection to OpenAI requires organization real-name authentication, as long as OPENROUTER_API_KEY exists, prefer OpenRouter
   (see make_client_and_model). You can still use COST_DEMO_MODEL / --model to switch to any model.
2. OpenAI's prompt caching is "automatic": when the request prefix >= 1024 tokens and matches the same prefix as recent requests,
   usage.prompt_tokens_details.cached_tokens will be greater than 0,
   and those tokens are billed at the cached price (cheaper). This project uses it to truly reflect KV-cache savings.
   (OpenRouter also returns cache hits in prompt_tokens_details.cached_tokens when forwarding OpenAI.)
"""

import os
from dataclasses import dataclass

# Model used (default current cheap flagship gpt-5.6-luna; can be overridden with COST_DEMO_MODEL / --model)
MODEL = os.environ.get("COST_DEMO_MODEL", "gpt-5.6-luna")

# OpenRouter fallback: when no OPENAI_API_KEY, use OPENROUTER_API_KEY to go through OpenAI-compatible endpoint.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _to_openrouter_model(model: str) -> str:
    """Map model name to OpenRouter id: if contains '/' treat as native id; gpt-* -> openai/*;
    claude-* -> anthropic/claude-opus-4.8; else fallback to openai/gpt-5.6-luna."""
    if "/" in model:
        return model
    if model.startswith("gpt-"):
        return "openai/" + model
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"


def make_client_and_model(model: str):
    """Construct an OpenAI-compatible client and return (client, actual model name to call).

    Fallback strategy (universal OpenRouter fallback):
      - gpt-5.x and OPENROUTER_API_KEY exists -> prefer OpenRouter (direct connection requires org real-name auth);
      - else if OPENAI_API_KEY exists -> direct OpenAI, model name unchanged;
      - else if OPENROUTER_API_KEY exists -> go through OpenRouter, model name mapped via _to_openrouter_model;
      - if neither -> raise clear error.
    """
    from openai import OpenAI

    primary = os.environ.get("OPENAI_API_KEY", "").strip()
    orkey = os.environ.get("OPENROUTER_API_KEY", "").strip()
    prefer_openrouter = bool(orkey) and model.startswith("gpt-5")

    if not prefer_openrouter and primary:
        return OpenAI(timeout=60.0, max_retries=2), model
    if orkey:
        return (
            OpenAI(base_url=OPENROUTER_BASE_URL, api_key=orkey,
                   timeout=60.0, max_retries=2),
            _to_openrouter_model(model),
        )
    if primary:
        return OpenAI(timeout=60.0, max_retries=2), model
    raise RuntimeError(
        "Missing available credentials: please set OPENAI_API_KEY (direct OpenAI), or set "
        "OPENROUTER_API_KEY (automatic fallback to OpenRouter); or use --offline for offline recalculation (no key needed)."
    )

# Price per million tokens in USD (default gpt-4o-mini)
PRICE_INPUT_PER_M = 0.15      # Regular input
PRICE_CACHED_PER_M = 0.075    # Cached input (gpt-4o-mini cache read is 50% of input price)
PRICE_OUTPUT_PER_M = 0.60     # Output


@dataclass(frozen=True)
class Pricing:
    """A set of prices per million tokens in USD."""
    input_per_m: float
    cached_per_m: float
    output_per_m: float

    def cost_usd(self, prompt_tokens: int, cached_tokens: int,
                 completion_tokens: int) -> float:
        """Convert token usage to cost (USD).

        prompt_tokens   : usage.prompt_tokens, includes cached portion
        cached_tokens   : usage.prompt_tokens_details.cached_tokens, input tokens that hit cache
        completion_tokens: usage.completion_tokens

        Non-cached input = prompt_tokens - cached_tokens, billed at regular input price;
        Cached input billed at cached price.
        """
        uncached_input = max(prompt_tokens - cached_tokens, 0)
        return (
            uncached_input / 1_000_000 * self.input_per_m
            + cached_tokens / 1_000_000 * self.cached_per_m
            + completion_tokens / 1_000_000 * self.output_per_m
        )


# Presets of public unit prices for common OpenAI models (per million tokens, USD), convenient for CLI to switch with --model.
# Switching to a stronger model does not affect the KV-cache mechanism (still requires stable prefix >= 1024 tokens).
PRICING_PRESETS = {
    "gpt-4o-mini": Pricing(0.15, 0.075, 0.60),
    "gpt-4o":      Pricing(2.50, 1.25, 10.00),
    "gpt-4.1-mini": Pricing(0.40, 0.10, 1.60),
    "gpt-4.1":     Pricing(2.00, 0.50, 8.00),
}


def default_pricing() -> Pricing:
    """Return the unit price of the default model (MODEL in config); unknown models fallback to module-level PRICE_* defaults."""
    return PRICING_PRESETS.get(
        MODEL, Pricing(PRICE_INPUT_PER_M, PRICE_CACHED_PER_M, PRICE_OUTPUT_PER_M)
    )


def cost_usd(prompt_tokens: int, cached_tokens: int, completion_tokens: int,
             pricing: "Pricing | None" = None) -> float:
    """Convert token usage to cost (USD). Uses module-level unit prices by default, can pass custom Pricing."""
    p = pricing or Pricing(PRICE_INPUT_PER_M, PRICE_CACHED_PER_M, PRICE_OUTPUT_PER_M)
    return p.cost_usd(prompt_tokens, cached_tokens, completion_tokens)
