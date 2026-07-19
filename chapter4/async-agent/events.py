"""Event model (corresponding to the Event / Trajectory concept in the design document).

Flux abstracts all agent experiences as "events", appended chronologically to a trajectory.
This file defines event types, event objects, and the logic for determining "event urgency" —
the classification basis for the two processing mechanisms in experiments 4-5:
"batch processing vs immediate interruption".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


class EventType:
    """Event type constants (corresponding to Section 2 of the design document: Inputs / Interrupts / Thinking / Actions)."""

    USER_INPUT = "user.input"          #  User input (non-urgent, uses "queued processing")
    USER_INTERRUPT = "user.interrupt"  #  User interruption (urgent, uses "cancellation processing")
    AGENT_OUTPUT = "agent.output"      #  Agent's final response to the user
    AGENT_TOOL_CALL = "agent.tool_call"  #  Agent-initiated tool call (Action)
    TOOL_RESULT = "tool.result"        #  Tool result (synchronous tool / asynchronous placeholder)
    ASYNC_RESULT = "async.result"      #  New event injected after asynchronous tool actually completes
    SYSTEM_NOTE = "system.note"        #  Framework-injected system prompt (e.g., cancellation receipt)


class Urgency:
    """Event urgency: determines which event processing mechanism to use."""

    INTERRUPT = "interrupt"  #  Cancellation processing: immediately interrupt current execution and cancel asynchronous tools
    IMMEDIATE = "immediate"  #  Immediate processing: do not interrupt background async tasks, but respond immediately (e.g., user question)
    DEFERRED = "deferred"    #  Queued processing: accumulate in pending queue, batch append when task completes


#  Interruption keywords: if matched, treat as urgent interruption
_INTERRUPT_KEYWORDS = ["Cancel", "Stop", "Abort", "Halt", "Don't do it", "stop", "cancel", "abort"]

#  Question signals: if matched, treat as requiring "immediate response" (not queued)
_QUESTION_MARKS = ("?", "？")
_QUESTION_KEYWORDS = ["What time", "How many", "How", "How to", "Why", "Is it", "Is there",
                      "? (question particle)", "? (question particle)", "what", "when", "how", "why", "which"]


def classify_urgency(text: str) -> str:
    """Determine urgency based on user message content.

    Rules (simple, explainable, easy to clarify in the book):
      1. Contains interruption keywords (cancel/stop/...) -> INTERRUPT (urgent, cancellation processing)
      2. Is a question (contains question mark or question word) -> IMMEDIATE (respond immediately, but do not interrupt background tasks)
      3. Other (supplementary instructions, e.g., "reply in Japanese") -> DEFERRED (queue, batch processing)
    """
    low = text.lower()
    if any(kw in text or kw in low for kw in _INTERRUPT_KEYWORDS):
        return Urgency.INTERRUPT
    if text.strip().endswith(_QUESTION_MARKS) or any(kw in text or kw in low for kw in _QUESTION_KEYWORDS):
        return Urgency.IMMEDIATE
    return Urgency.DEFERRED


@dataclass
class Event:
    """A trace event.

    The message field stores "OpenAI message dict that can be directly fed to LLM" (ensuring high-fidelity replay of context);
    Events without a message (if any) are only used for logging.
    """

    type: str
    message: Optional[dict] = None        # OpenAI chat format message for building LLM context
    label: str = ""                       # Human-readable log label
    task_id: Optional[str] = None         # Associated async task ID (if any)
    urgency: Optional[str] = None         # Only user input events carry this
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """ Serialized as a plain JSON-writable dict (for state checkpoint persistence)."""
        return {
            "type": self.type, "message": self.message, "label": self.label,
            "task_id": self.task_id, "urgency": self.urgency, "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        """ Restore event object from checkpoint dict."""
        return cls(
            type=d["type"], message=d.get("message"), label=d.get("label", ""),
            task_id=d.get("task_id"), urgency=d.get("urgency"),
            ts=d.get("ts", time.time()),
        )
