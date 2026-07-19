"""
Phone Agent — a ReAct Agent that uses PineClaw Voice (make_phone_call) as a tool.

The upper layer is a standard ReAct loop (OpenAI function calling implementation):
    The user gives a task (e.g., "Call the broadband customer service, find out why an extra 50 yuan was deducted this month, and ask for an explanation")
        -> Agent thinks about what parameters are needed (number / goal / context)
        -> Calls the make_phone_call tool to complete the entire conversation
        -> Reads the returned [structured call record]
        -> If information is insufficient, asks follow-up questions or calls again; otherwise, gives a final report to the user

The tool make_phone_call is provided by the pine_voice module (a local simulation of the real PineClaw Voice API).
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

#  Reuse the unified client/model parsing from pine_voice (direct connection via OPENAI_API_KEY, fallback to OpenRouter if missing).
from pine_voice import make_phone_call, _get_client, default_model

#  Maximum number of tool calls (including follow-ups/redials) allowed for the agent to prevent infinite loops.
_MAX_STEPS = 6

_SYSTEM_PROMPT = (
    "You are a 'Phone Assistant' agent. The user will give you a task that requires making a phone call to complete."
    "You need to make the phone call on behalf of the user and report the results.\n\n"
    "You have a tool make_phone_call, which handles the entire phone call (dialing, IVR menu navigation, multi-turn conversation with customer service,"
    "(Transcription) All handled by the PineClaw voice agent, returning a structured call log.\n\n"
    "Working Mode (ReAct): \n"
    "1. First, clarify the number to dial, the call objective, and the context to bring (account/name/known information).\n"
    "2. Call make_phone_call to complete the call.\n"
    "3. Read the returned structured record (goal_achieved / key_fields / summary / transcript).\n"
    "4. If the goal is not achieved or information is insufficient (follow_up_needed is true), you can call again with a clearer objective."
    "(But the total number of times is limited, do not redial unnecessarily).\n"
    "5. After the goal is achieved, report to the user in concise Chinese: conclusion + key information (amount/reason/confirmation number/time, etc.)"
    "+ Follow-up suggestions (if any).\n\n"
    "Note: If there is no phone number in the task, use a reasonable placeholder number and explain it in the report."
    "Always report based on the call records actually returned by the tool, and do not fabricate information not mentioned in the call."
)

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "make_phone_call",
            "description": (
                "Make a real phone call on behalf of the user. PineClaw Voice Agent will handle dialing, IVR menu navigation,"
                "Engage in multiple rounds of dialogue with the other party and return a structured call record (including transcript, whether the goal was achieved,"
                "Extracted key fields)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {
                        "type": "string",
                        "description": "Called phone number, such as 10000 or 400-810-xxxx.",
                    },
                    "goal": {
                        "type": "string",
                        "description": "Clear goal for this call (one sentence).",
                    },
                    "context": {
                        "type": "string",
                        "description": "Auxiliary context: account, name, known amount, time, etc., can be empty.",
                    },
                },
                "required": ["phone_number", "goal"],
            },
        },
    }
]


def run_agent(
    task: str,
    on_event: Callable[[str, Any], None] | None = None,
    *,
    model: str | None = None,
    phone_hint: str | None = None,
    goal_hint: str | None = None,
    dry_run: bool = False,
) -> str:
    """
    Run the ReAct phone agent.

    Parameters:
        task:       The user's natural language task.
        on_event:   Optional callback for external observation of the agent's trajectory.
                    Event types: 'think' (agent thinking text) / 'call' (tool input parameters) /
                    'record' (structured call record) / 'final' (final report).
        model:      Override the model to use (defaults to environment variable OPENAI_MODEL).
        phone_hint: Optional phone number; if given, provided as known info to the agent (in dry-run mode, used directly as the called number).
        goal_hint:  Optional call goal; if given, provided as known info to the agent (in dry-run mode, used directly as the call goal).
        dry_run:    If true, runs a fully offline scripted ReAct trajectory (no network, no API key required).

    Returns:
        The agent's final report text for the user.
    """

    def emit(kind: str, payload: Any) -> None:
        if on_event:
            on_event(kind, payload)

    if dry_run:
        return _run_agent_dryrun(task, emit, phone_hint, goal_hint)

    model = model or default_model()

    # If a number/target is explicitly given, it is spliced into the user message as "known information", and the Agent still decides how to use it.
    hints = []
    if phone_hint:
        hints.append(f"Known phone number of the other party:{phone_hint}")
    if goal_hint:
        hints.append(f"User's clear call objective:{goal_hint}")
    user_content = task if not hints else task + "\n\n（" + "；".join(hints) + "）"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    for _ in range(_MAX_STEPS):
        resp = _get_client().chat.completions.create(
            model=model,
            messages=messages,
            tools=_TOOLS,
            tool_choice="auto",
            temperature=0.3,
        )
        msg = resp.choices[0].message

        # Append the assistant message returned by the model at this step (may contain both reasoning text and tool calls).
        messages.append(msg.model_dump(exclude_none=True))

        if msg.content:
            emit("think", msg.content)

        if not msg.tool_calls:
            # No tool call = Agent gave final answer.
            final = msg.content or ""
            emit("final", final)
            return final

        # Execute tool calls one by one (in this example, only make_phone_call).
        for tc in msg.tool_calls:
            if tc.function.name != "make_phone_call":
                result = {"error": f"unknown tool {tc.function.name}"}
            else:
                args = json.loads(tc.function.arguments or "{}")
                emit("call", args)
                result = make_phone_call(
                    phone_number=args.get("phone_number", "10000"),
                    goal=args.get("goal", task),
                    context=args.get("context", ""),
                    model=model,
                )
                emit("record", result)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": "make_phone_call",
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    # Fallback: steps exhausted without convergence, force the model to summarize once.
    messages.append(
        {
            "role": "user",
            "content": "Based on the above call record, immediately give the user a final report, do not call again.",
        }
    )
    resp = _get_client().chat.completions.create(
        model=model, messages=messages, temperature=0.3
    )
    final = resp.choices[0].message.content or ""
    emit("final", final)
    return final


def _guess_phone(task: str) -> str | None:
    """Roughly extract a digit string that looks like a phone number from the task text (>=4 digits, avoid amounts like '50 yuan')."""
    for m in re.finditer(r"\d{4,}", task):
        return m.group(0)
    return None


def _guess_context(task: str) -> str:
    """Roughly extract account and other context from the task text (heuristic for dry-run only, not exhaustive)."""
    m = re.search(r"acc[ount][^A-Za-z0-9]{0,3}([A-Za-z0-9][A-Za-z0-9\-]{2,})", task)
    if m:
        return f"account {m.group(1)}"
    return ""


def _run_agent_dryrun(
    task: str,
    emit: Callable[[str, Any], None],
    phone_hint: str | None,
    goal_hint: str | None,
) -> str:
    """
    Fully offline scripted ReAct trajectory: no LLM/phone API calls, only demonstrates the loop shape—
    Think(infer parameters) → Act(make_phone_call, dry_run) → Observe(structured record) → Report.
    """
    phone = phone_hint or _guess_phone(task) or "10010"
    goal = goal_hint or task
    context = _guess_context(task)

    emit(
        "think",
        "This is a task that requires making a phone call. I first determine the three elements of the call—"
        f"number={phone}; target={goal}; context={context or '(none)'}. Parameters are sufficient, now initiating the call.",
    )

    call_args = {"phone_number": phone, "goal": goal, "context": context}
    emit("call", call_args)
    record = make_phone_call(**call_args, dry_run=True)
    emit("record", record)

    kf = record.get("key_fields", {}) or {}
    kf_text = "；".join(f"{k}={v}" for k, v in kf.items()) or "(none)"
    final = (
        f"Called (dry-run script simulation) {phone} and completed the call.\n"
        f"Conclusion:{record.get('summary', '')}\n"
        f"Key information:{kf_text}。"
    )
    emit("final", final)
    return final
