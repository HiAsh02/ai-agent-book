"""
Optional LLM judgment layer
=================

After the sub-agent captures the web page text, it needs to determine "whether this content answers the target question."
- By default, the controllable keyword judgment of ``sources.keyword_judge`` is used (no internet required, results reproducible);
- If ``OPENAI_API_KEY`` is set and not forced offline, the real LLM is called for judgment,
  demonstrating the path where "the sub-agent uses a large model to make real decisions."

Coordination / bus / termination / race condition mechanisms are independent of the LLM and are always real implementations;
the LLM only affects the judgment of "whether a single source contains the answer," which is a pluggable part.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from sources import keyword_judge


def _to_openrouter_model(model: str) -> str:
    """Map model names to the OpenRouter namespace (for fallback path without OPENAI_API_KEY)."""
    if "/" in model:
        return model                      # is already in OpenRouter namespace, use as is
    if model.startswith("gpt-"):
        return "openai/" + model          # gpt-* -> openai/gpt-*
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"          # Fallback: current cheap flagship


def _loads_lenient(content: str):
    """Fault-tolerant JSON parsing: handles cases where some models wrap JSON in ```json ... ``` code fences."""
    s = (content or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1] if "\n" in s else s
        s = s.rsplit("```", 1)[0].strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return json.loads(s)


def llm_available() -> bool:
    """Whether conditions for calling the real LLM are met.

    Note: The focus of this experiment is on mechanisms like "parallel coordination / message bus / cascading termination / race settlement,"
    not on LLM retrieval quality. To ensure the demo is **reproducible** (only sources that truly contain the answer are hit,
    thereby stably triggering race conditions and cascading termination), deterministic keyword judgment is used by default.
    Only when USE_LLM=1 is explicitly set is the real LLM judgment enabled (may hallucinate on mock sources, for experience only).

    Key resolution: priority to OPENAI_API_KEY; if absent, fallback to OPENROUTER_API_KEY (via OpenRouter).
    """
    if os.getenv("USE_LLM", "").lower() not in ("1", "true", "yes"):
        return False
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY"))


async def judge_answer(question: str, text: str) -> Optional[str]:
    """
    Determine whether text answers the question. If hit, return the answer string; otherwise return None.
    Prefer LLM; fallback to keyword judgment when unavailable or on error, ensuring the demo always runs.
    """
    if not llm_available():
        return keyword_judge(text)

    try:
        # Lazy import to avoid affecting keyword path when openai is not installed
        from openai import AsyncOpenAI

        model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        # General fallback: prefer direct OPENAI_API_KEY; otherwise use OPENROUTER_API_KEY via OpenRouter.
        if os.getenv("OPENAI_API_KEY"):
            client = AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL") or None,
            )
        else:
            client = AsyncOpenAI(
                api_key=os.getenv("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1",
            )
            model = _to_openrouter_model(model)
        prompt = (
            f"Question:{question}\n\n"
            f"Web page content:{text}\n\n"
            "Strictly judge based only on the above 'Web page content', **do not use your own knowledge**."
            "Only count as a hit if the web page content **actually contains** the specific answer to the question."
            "If hit, output only JSON: {\"found\": true, \"answer\": \"<answer extracted from web page content>\"};"
            "If the web page content does not directly provide the answer (even if you know it), always output {\"found\": false}."
            "Output only JSON, no other text."
        )
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = _loads_lenient(resp.choices[0].message.content)
        if data.get("found"):
            return data.get("answer") or text
        return None
    except Exception as exc:  # noqa: BLE001 —— any exception falls back to offline judgment
        print(f"  [llm] call failed, fallback to keyword judgment:{exc}")
        return keyword_judge(text)
