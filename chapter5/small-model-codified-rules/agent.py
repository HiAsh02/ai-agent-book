"""
Aviation Customer Service Agent (Experiment 5-3)

Two modes:
  - control: System prompt contains only natural language policy; tool descriptions are minimal, without expected_* parameters;
    tools perform no internal validation (naive execution). Policy compliance relies entirely on model reasoning.
  - codified (experimental): Triple safeguards—
      (1) System prompt retains the same natural language policy;
      (2) Tool descriptions list the full policy and guide the model to "check each item before calling" via optional expected_* parameters;
      (3) Tools perform code-level validation against database ground truth, rejecting violations.
"""

from __future__ import annotations

import json
import os
import time

from openai import OpenAI

from airline_env import AirlineEnv


MODEL = os.environ.get("MODEL", "gpt-5.6-luna")  #  Default to small model as representative (core of this experiment: small model + codified rules)
MAX_TURNS = 6

# --- Generic OpenRouter fallback ---
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _map_to_openrouter_model(model: str) -> str:
    """Map direct model names to OpenRouter IDs (non-mappable IDs fall back to the current cheap flagship)."""
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


# ---------------------------------------------------------------------------
#  Natural language policy (shared by both groups, placed in system prompt)
# ---------------------------------------------------------------------------
NL_POLICY = """You are a customer service agent for SkyWing Airlines, assisting passengers with booking inquiries and cancellations.

【Refund Policy (Natural Language)】
- Basic economy tickets (basic_economy) are non-refundable by default.
- Exception 1: Full refund within 24 hours of booking.
- Exception 2: Full refund if the flight is canceled by the airline or experiences a major delay (delay ≥ 3 hours).
- Economy flex (economy_flex) and business class (business) tickets are fully refundable.
- If non-refundable: Politely explain the policy and proactively offer alternatives (e.g., keep the ticket for rebooking, apply for travel credit),
  never issue a refund to the user.

First determine eligibility for refund, then decide whether to call the cancellation/refund tool. Information provided by the passenger (cabin class, booking time, etc.)
may be inaccurate; rely on the booking information retrieved by the system."""

CONTROL_SYSTEM = NL_POLICY

CODIFIED_SYSTEM = NL_POLICY + """

【Operational Requirements】
Before calling cancel_reservation, first use get_reservation to retrieve actual booking details, check each item of the refund policy,
and honestly fill in your judgment in the expected_refundable / expected_reason parameters (this is a pre-call checklist).
The system will validate against database ground truth: if your judgment conflicts with the truth or violates policy, the call will be rejected."""


# ---------------------------------------------------------------------------
#  Tool schema
# ---------------------------------------------------------------------------
GET_RESERVATION_TOOL = {
    "type": "function",
    "function": {
        "name": "get_reservation",
        "description": "Retrieve detailed booking information (cabin class, booking time, time since booking, flight status, price, etc., all system ground truth).",
        "parameters": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string", "description": "Booking ID, e.g., R001"},
            },
            "required": ["reservation_id"],
        },
    },
}

CONTROL_CANCEL_TOOL = {
    "type": "function",
    "function": {
        "name": "cancel_reservation",
        "description": "Cancel a booking and process refund.",
        "parameters": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string", "description": "Booking ID"},
            },
            "required": ["reservation_id"],
        },
    },
}

CODIFIED_CANCEL_TOOL = {
    "type": "function",
    "function": {
        "name": "cancel_reservation",
        "description": (
            "Cancel booking and process refund according to policy. Before calling, check each item of the refund policy (this is a checklist):\n"
            "1) Is the cabin class basic_economy? Non-basic economy tickets are refundable.\n"
            "2) If basic economy: Was the booking made within 24 hours? (Based on system-returned hours_since_booking)\n"
            "3) If basic economy: Was the flight canceled by the airline or delayed ≥ 3 hours (major delay)?\n"
            "Only non-basic tickets (satisfying 1) or basic tickets meeting one of the exceptions (2/3) are refundable.\n"
            "Fill in your conclusion honestly in expected_refundable / expected_reason."
            "The system will validate against database ground truth; non-refundable calls will be rejected."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string", "description": "Booking ID"},
                "expected_refundable": {
                    "type": "boolean",
                    "description": "Your judgment on whether this booking is refundable after checking the policy (checklist self-reported value).",
                },
                "expected_reason": {
                    "type": "string",
                    "enum": ["flexible_fare", "within_24h", "airline_caused", "non_refundable_basic_economy"],
                    "description": "The policy basis for your refundable/non-refundable judgment.",
                },
            },
            "required": ["reservation_id", "expected_refundable", "expected_reason"],
        },
    },
}


def _make_client(model: str | None = None):
    """Construct client and resolve model name, including generic OpenRouter fallback. Returns (client, resolved_model).

    - With OPENAI_API_KEY: direct connection; but if model is gpt-5.x and OPENROUTER_API_KEY is also set,
      prefer OpenRouter (direct gpt-5.6 requires organizational real-name authentication).
    - Without OPENAI_API_KEY but with OPENROUTER_API_KEY: switch to OpenRouter (model name auto-mapped).
    """
    model = model or MODEL
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    orkey = os.environ.get("OPENROUTER_API_KEY")
    prefer_or = bool(orkey) and (model or "").lower().startswith("gpt-5")
    if prefer_or or (not api_key and orkey):
        api_key, base_url, model = orkey, OPENROUTER_BASE_URL, _map_to_openrouter_model(model)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY (or OPENROUTER_API_KEY fallback) not set, please refer to env.example for configuration.")
    kw = {"api_key": api_key}
    if base_url:
        kw["base_url"] = base_url
    return OpenAI(**kw), model


def _dispatch(env: AirlineEnv, mode: str, name: str, args: dict) -> dict:
    """Route the model's tool calls to the corresponding mode's environment method."""
    if name == "get_reservation":
        return env.get_reservation(args.get("reservation_id", ""))
    if name == "cancel_reservation":
        if mode == "control":
            return env.cancel_reservation_naive(args.get("reservation_id", ""))
        return env.cancel_reservation_codified(
            args.get("reservation_id", ""),
            expected_refundable=args.get("expected_refundable"),
            expected_reason=args.get("expected_reason"),
        )
    return {"status": "error", "message": f"Unknown tool {name}"}


def run_agent(env: AirlineEnv, user_message: str, mode: str, verbose: bool = False,
              model: str | None = None) -> dict:
    """Run a single case, returning {final_text, transcript}. The env is modified in place (state is ground truth).

    When model is empty, fall back to module-level default MODEL (small model). In three-way controlled experiments,
    this can be used to run the "control group" on a larger model, verifying whether "small model + codified rules"
    can match "large model bare run".
    """
    assert mode in ("control", "codified")
    client, model = _make_client(model or MODEL)

    if mode == "control":
        system, tools = CONTROL_SYSTEM, [GET_RESERVATION_TOOL, CONTROL_CANCEL_TOOL]
    else:
        system, tools = CODIFIED_SYSTEM, [GET_RESERVATION_TOOL, CODIFIED_CANCEL_TOOL]

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message},
    ]
    transcript: list[dict] = []
    final_text = ""

    for _turn in range(MAX_TURNS):
        resp = _chat_with_retry(client, messages, tools, model=model)
        msg = resp.choices[0].message

        if msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = _dispatch(env, mode, tc.function.name, args)
                transcript.append({"tool": tc.function.name, "args": args, "result": result})
                if verbose:
                    print(f"    [tool] {tc.function.name}({args}) -> {result.get('status')}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            continue

        final_text = msg.content or ""
        messages.append({"role": "assistant", "content": final_text})
        break

    return {"final_text": final_text, "transcript": transcript}


def _chat_with_retry(client: OpenAI, messages, tools, model: str | None = None, retries: int = 3):
    last_err = None
    model = model or MODEL
    #  Reasoning models (gpt-5 / o series, etc.) do not accept temperature=0; others remain fixed at 0 to maximize reproducibility.
    _reasoning = any(k in (model or "").lower()
                     for k in ("gpt-5", "o1", "o3", "o4", "thinking", "reasoner", "kimi-k3"))
    for i in range(retries):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                temperature=1 if _reasoning else 0.0,  #  Minimize randomness for reproducibility
            )
        except Exception as e:  # noqa: BLE001 —— network/rate limits, etc., simple retry
            last_err = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"OpenAI call failed:{last_err}")
