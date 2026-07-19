"""
pine_voice —— A local [simulation] client for the PineClaw Voice API.

The real PineClaw Voice API (https://pineclaw.com/, developed by the author team) is a production-grade
telephone voice API: you give it a "phone number + goal + context", and its voice agent automatically completes
dialing, IVR menu navigation ("For inquiries, press 1; for operator, press 0"), multi-turn conversation with a real person, real-time transcription,
and finally condenses the entire call into a [structured call record] as output.

This file does not touch the real telephone network, nor does it require a PineClaw key. It uses OpenAI to play the role of the "called party"
(IVR voice menu + human agent) and conducts a multi-turn dialogue with the "outgoing voice agent", thereby locally
reproducing the same input/output contract:

    record = make_phone_call(phone_number, goal, context)

The returned record maintains the same shape as the real API (transcript / goal_achieved / key_fields ...),
so the upper-layer ReAct Agent code requires almost no modification when switching to the real PineClaw SDK.

For real integration, see the "Real PineClaw Integration" section in README.md in this directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

from openai import OpenAI

# Default chat model: currently the cheap flagship. Can be overridden with OPENAI_MODEL (e.g., Moonshot's kimi-k3).
_DEFAULT_MODEL = "gpt-5.6-luna"


def _map_openrouter_model(model: str) -> str:
    """Map common model names to OpenRouter's provider/model format."""
    if "/" in model:            # Already in provider/model format, pass through as-is
        return model
    if model.startswith("gpt-"):
        return "openai/" + model
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"


# Lazy client creation: when key is missing, demo.py gives a friendly prompt instead of a bare exception at import time.
# General fallback: prefer OPENAI_API_KEY (optionally OPENAI_BASE_URL pointing to a compatible gateway, e.g., Moonshot),
# otherwise use OPENROUTER_API_KEY via OpenRouter, otherwise give a clear error.
# timeout + automatic retry to prevent a single network/SSL glitch from crashing the entire simulated call.
_client = None
_active_model = None


def _resolve() -> tuple[OpenAI, str]:
    global _client, _active_model
    if _client is not None:
        return _client, _active_model
    model = os.getenv("OPENAI_MODEL") or _DEFAULT_MODEL
    if os.getenv("OPENAI_API_KEY"):
        # Direct connection to OpenAI (or a compatible gateway specified by OPENAI_BASE_URL, e.g., Moonshot kimi-k3).
        _client = OpenAI(
            base_url=os.getenv("OPENAI_BASE_URL") or None,
            timeout=60.0,
            max_retries=3,
        )
        _active_model = model
    elif os.getenv("OPENROUTER_API_KEY"):
        # Fallback to OpenRouter: note that gpt-5.6* direct connection to OpenAI requires organizational real-name authentication; using OpenRouter bypasses this step.
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            timeout=60.0,
            max_retries=3,
        )
        _active_model = _map_openrouter_model(model)
    else:
        raise RuntimeError(
            "Neither OPENAI_API_KEY nor OPENROUTER_API_KEY detected. Please configure at least one in .env / environment variables"
            "(see env.example), or use python demo.py --dry-run for a fully offline script demo."
        )
    return _client, _active_model


def _get_client() -> OpenAI:
    return _resolve()[0]


def default_model() -> str:
    """Currently active chat model name (resolved according to OpenRouter mapping)."""
    return _resolve()[1]

# Maximum number of rounds in a simulated call between "outgoing voice agent ↔ called party" (one round = each side speaks once).
_MAX_TURNS = 8

# Termination marker: when the outgoing voice agent believes the call goal is achieved or cannot be advanced, it appends this at the end of its utterance.
_END_TOKEN = "[END_CALL]"


# --------------------------------------------------------------------------- #
# Structured call record — maintains the same shape as the real PineClaw Voice API response
# --------------------------------------------------------------------------- #
@dataclass
class CallRecord:
    call_id: str
    phone_number: str
    goal: str
    status: str                       # "completed" / "failed"
    goal_achieved: bool               # Whether the call goal was achieved
    duration_seconds: int             # Call duration (simulated value)
    summary: str                      # One-sentence call summary
    key_fields: dict[str, Any]        # Key information extracted from the call (confirmation number, amount, time, ...)
    transcript: list[dict[str, str]]  # Per-turn dialogue: {"speaker": ..., "text": ...}
    follow_up_needed: bool            # Whether further follow-up/redial is needed
    follow_up_reason: str             # If follow-up is needed, the reason

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Internal: call OpenAI to generate one utterance
# --------------------------------------------------------------------------- #
def _chat(
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    model: str | None = None,
) -> str:
    resp = _get_client().chat.completions.create(
        model=model or default_model(),
        messages=messages,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()


def _callee_system_prompt(goal: str, context: str) -> str:
    """Called party: first act as an automated IVR voice menu, then after being transferred to a human agent, play the role of a human agent."""
    return (
        "You are participating in a role-play of a [phone customer service] call, playing the role of the [called party] (enterprise customer service hotline).\n"
        "The entire call has two stages, please transition naturally:\n"
        "1) At the start, you are the [automated voice response (IVR) system]: first broadcast a welcome message, then announce a short key menu"
        "(e.g., 'For billing inquiries, press 1; for business processing, press 2; for operator, press 0').\n"
        "2) When the caller chooses to transfer to a human (press 0 or explicitly requests a human), you switch to [human customer service representative],"
        "Announce your employee ID, then respond normally.\n\n"
        "Role requirements:\n"
        "- Use colloquial Simplified Chinese throughout, as short and natural as a real phone call. No narration, no parenthetical actions.\n"
        "- You may reasonably fabricate business details of your company (e.g., deduction reasons, plans, confirmation numbers). Be specific and consistent.\n"
        f"- The caller's goal for this call is roughly:{goal}\n"
        "- You don't have to unconditionally satisfy the other party; you can first explain and then handle as needed. But when the other party is polite and the request is reasonable,"
        "you should be able to give a clear conclusion (reason/result/confirmation number, etc.).\n"
        "- Each time, only speak your (the called party's) part. Do not speak for the other party."
    )


def _caller_system_prompt(phone_number: str, goal: str, context: str) -> str:
    """Outgoing voice Agent: Represents the user making a call, navigating IVR, and achieving the goal."""
    return (
        "You are PineClaw phone voice Agent, making a real call on behalf of the user to get something done.\n"
        f"- Dialed number:{phone_number}\n"
        f"- Call goal:{goal}\n"
        f"- Known context:{context or '(No additional context)'}\n\n"
        "Behavior requirements:\n"
        "- Use colloquial Simplified Chinese throughout, polite, brief, and straight to the point.\n"
        "- At the start, if you encounter an IVR key menu, clearly state your choice (e.g., 'I press 0 to reach a human') to navigate.\n"
        "- After reaching a human, clearly state your purpose, ask questions around the goal, actively confirm and remember key information"
        "(amount, reason, confirmation number, time, etc.).\n"
        "- When the goal is achieved or the other party clearly cannot handle it, politely thank and end the call, and append the marker at the end of that sentence "
        f"{_END_TOKEN}。\n"
        "- Each time, only speak your (the caller's) part. Do not speak for the other party or add narration."
    )


def _run_dialog(
    phone_number: str, goal: str, context: str, model: str | None = None
) -> list[dict[str, str]]:
    """Drive two LLM roles to converse back and forth, producing a turn-by-turn transcript."""
    caller_sys = _caller_system_prompt(phone_number, goal, context)
    callee_sys = _callee_system_prompt(goal, context)

    # Each maintains its own message history from its perspective.
    caller_msgs = [{"role": "system", "content": caller_sys}]
    callee_msgs = [{"role": "system", "content": callee_sys}]

    transcript: list[dict[str, str]] = []

    # The called party speaks first (IVR greeting + menu).
    callee_msgs.append({"role": "user", "content": "(The call is connected. Please begin.)"})
    callee_line = _chat(callee_msgs, model=model)
    callee_msgs.append({"role": "assistant", "content": callee_line})
    caller_msgs.append({"role": "user", "content": callee_line})
    transcript.append({"speaker": "Called party", "text": callee_line})

    for _ in range(_MAX_TURNS):
        # Outgoing voice Agent speaks
        caller_line = _chat(caller_msgs, model=model)
        ended = _END_TOKEN in caller_line
        caller_line_clean = caller_line.replace(_END_TOKEN, "").strip()
        caller_msgs.append({"role": "assistant", "content": caller_line})
        callee_msgs.append({"role": "user", "content": caller_line_clean})
        transcript.append({"speaker": "Voice Agent", "text": caller_line_clean})
        if ended:
            break

        # Called party responds
        callee_line = _chat(callee_msgs, model=model)
        callee_msgs.append({"role": "assistant", "content": callee_line})
        caller_msgs.append({"role": "user", "content": callee_line})
        transcript.append({"speaker": "Called party", "text": callee_line})

    return transcript


def _extract_structured(
    goal: str, transcript: list[dict[str, str]], model: str | None = None
) -> dict[str, Any]:
    """After the call ends, use one LLM call to summarize the transcript into structured fields."""
    dialog_text = "\n".join(f"{t['speaker']}：{t['text']}" for t in transcript)
    prompt = (
        "Below is the complete transcript of a phone call. Please act as a call analyzer and output a JSON object with the following fields: \n"
        '  "goal_achieved": boolean, whether the call achieved the given goal; \n'
        '  "summary": string, a one-sentence Chinese call summary; \n'
        '  "key_fields": object, key-value pairs of key information extracted from the call (e.g., deduction reason/amount involved/'
        "confirmation number/processing result/appointment time, etc., keys in Chinese, leave empty object if none); \n"
        '  "follow_up_needed": boolean, whether the user needs further follow-up or to call again; \n'
        '  "follow_up_reason": string, if follow-up is needed, explain the reason, otherwise empty string. \n\n'
        f"【Call Goal】{goal}\n\n"
        f"【Call Transcript】\n{dialog_text}\n\n"
        "Output only JSON, no extra explanation."
    )
    raw = _chat(
        [
            {"role": "system", "content": "You are a rigorous call record structurer, output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        model=model,
    )
    return _safe_json(raw)


def _safe_json(raw: str) -> dict[str, Any]:
    """Safely extract JSON from model output (tolerate ```json wrapping)."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {
        "goal_achieved": False,
        "summary": "(Structured parsing failed, please check the original transcript)",
        "key_fields": {},
        "follow_up_needed": True,
        "follow_up_reason": "Call record could not be automatically structured.",
    }


# --------------------------------------------------------------------------- #
#  Offline dry-run — completely offline, no API Key required scripted call record
# --------------------------------------------------------------------------- #
def _dryrun_record(phone_number: str, goal: str, context: str) -> dict[str, Any]:
    """
    Return a 【scripted】 structured call record, without calling any API or going online.

    Purpose: When neither a phone account nor OPENAI_API_KEY is available, the entire ReAct loop
    (think → call make_phone_call → read structured record → report) can still run offline,
    demonstrating its shape.
    transcript / key_fields are fixed scripts, not representing any real call.
    """
    ctx = context or "(No additional context)"
    #  Derive a stable, reproducible confirmation number from the goal (rather than randomly fabricating, for easy alignment explanation).
    conf = "PC" + hashlib.sha1(goal.encode("utf-8")).hexdigest()[:8].upper()
    transcript = [
        {"speaker": "Called party", "text": "Hello, welcome to the customer service hotline. For business inquiries, press 1; for human agent, press 0."},
        {"speaker": "Voice Agent", "text": "I press 0 to transfer to a human agent."},
        {"speaker": "Called party", "text": "Hello, this is customer service agent 3021, how can I help you?"},
        {"speaker": "Voice Agent", "text": f"Hello, my request is:{goal}. Related information:{ctx}。"},
        {"speaker": "Called party",
         "text": f"Okay, we have verified and processed it for you. Your confirmation number is {conf}, you can use this to check the progress later."},
        {"speaker": "Voice Agent", "text": f"Okay, confirmation number {conf}, I have noted it, thank you, goodbye."},
    ]
    record = CallRecord(
        call_id="pc_dryrun_" + hashlib.sha1((phone_number + goal).encode()).hexdigest()[:8],
        phone_number=phone_number,
        goal=goal,
        status="completed",
        goal_achieved=True,
        duration_seconds=12 * len(transcript) + 8,
        summary=f"(dry-run script simulation) Contacted {goal} regarding \"{phone_number}\" and processed, confirmation number {conf}。",
        key_fields={"processing result": "Accepted", "Confirmation number": conf, "Other party's number": phone_number},
        transcript=transcript,
        follow_up_needed=False,
        follow_up_reason="",
    )
    return record.to_dict()


# --------------------------------------------------------------------------- #
#  Unified external entry — aligned with the real PineClaw Voice API's make_phone_call
# --------------------------------------------------------------------------- #
def make_phone_call(
    phone_number: str,
    goal: str,
    context: str = "",
    *,
    model: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Initiates a (simulated) phone call, completed entirely by the voice agent, and returns a structured call record (dict).

    Parameters:
        phone_number: The called number (this simulation does not actually dial, only records).
        goal:         The objective of this call, e.g.
                      "Query why this month's broadband bill has an extra charge of 50 yuan and request an explanation."
        context:      Auxiliary context, such as account number, name, known information, etc. (can be empty).
        model:        Override the OpenAI model used for internal simulated dialogue (defaults to OPENAI_MODEL).
        dry_run:      If true, runs a fully offline scripted path (no network, no API key required).

    Returns:
        CallRecord.to_dict(), containing transcript / goal_achieved / key_fields, etc.
    """
    if dry_run:
        return _dryrun_record(phone_number, goal, context)

    started = time.time()
    transcript = _run_dialog(phone_number, goal, context, model=model)
    structured = _extract_structured(goal, transcript, model=model)

    #  Roughly estimates a 'call duration' based on the number of dialogue turns, purely for demonstration purposes.
    duration = 12 * len(transcript) + 8

    record = CallRecord(
        call_id=f"pc_{uuid.uuid4().hex[:12]}",
        phone_number=phone_number,
        goal=goal,
        status="completed",
        goal_achieved=bool(structured.get("goal_achieved", False)),
        duration_seconds=duration,
        summary=str(structured.get("summary", "")),
        key_fields=dict(structured.get("key_fields", {}) or {}),
        transcript=transcript,
        follow_up_needed=bool(structured.get("follow_up_needed", False)),
        follow_up_reason=str(structured.get("follow_up_reason", "")),
    )
    _ = started  #  The real API uses actual start and end times; here duration is a simulated value
    return record.to_dict()
