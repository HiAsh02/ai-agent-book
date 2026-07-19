"""
orchestrator.py — Multi-role handoff orchestrator.

Core mechanism (Experiment 10-2):
- Maintains a shared conversation history (user/assistant/tool messages) throughout.
- On each LLM call, temporarily prepend the current role's system prompt to the history,
  and expose only the current role's tool set + transfer_to_agent.
- The model can:
    1) Call its own dedicated tools (normal function calling);
    2) Call transfer_to_agent to hand over control to another role —
       the orchestrator then swaps the system prompt and tool set, but keeps the history intact,
       so the new role naturally inherits the entire conversation history (shared context).
- Loop until a role produces a final response with no tool calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from openai import OpenAI

from roles import ROLES, DEFAULT_ROLE, transfer_tool_schema
from tools import TOOL_SCHEMAS, TOOL_IMPLEMENTATIONS


# ---- Terminal coloring (no third-party dependencies) ----
class C:
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    RED = "\033[31m"


@dataclass
class Handoff:
    from_role: str
    to_role: str
    reason: str


class MultiRoleOrchestrator:
    def __init__(
        self,
        client: OpenAI,
        model: str = "gpt-5.6-luna",
        max_steps: int = 20,
        verbose: bool = True,
        start_role: str = DEFAULT_ROLE,
    ):
        if start_role not in ROLES:
            raise ValueError(f"Unknown starting role {start_role!r}, options: {list(ROLES.keys())}")
        self.client = client
        self.model = model
        self.max_steps = max_steps
        self.verbose = verbose

        self.history: List[dict] = []          # Shared conversation history (excluding system)
        self.current_role: str = start_role    # Current controlling role (customizable starting role)
        self.handoffs: List[Handoff] = []      # Record handoff chain
        self._tool_call_counts: Dict[str, int] = {}  # Deduplication count for identical tool calls (prevent infinite loops)
        # Division record: (role, kind, detail), kind ∈ {"tool", "transfer", "final"},
        # Used to print a summary of 'which role did what' after execution.
        self.activity: List[tuple] = []

    # -------------------------------------------------------------- Tool Assembly
    def _tools_for_current_role(self) -> List[dict]:
        """Tools visible to current role = dedicated tool set + transfer_to_agent."""
        role = ROLES[self.current_role]
        schemas = [TOOL_SCHEMAS[name] for name in role.tools]
        schemas.append(transfer_tool_schema())  # Every role can hand off
        return schemas

    def _messages_for_api(self) -> List[dict]:
        """Prepend the current role's system prompt to the shared history."""
        system_msg = {"role": "system", "content": ROLES[self.current_role].system_prompt}
        return [system_msg] + self.history

    # -------------------------------------------------------------- Log
    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def _log_role_banner(self):
        role = ROLES[self.current_role]
        self._log(
            f"\n{C.BOLD}{C.CYAN}┌── Current role: {role.title} ({role.name}){C.RESET}"
            f"{C.DIM}   Tools: {role.tools + ['transfer_to_agent']}{C.RESET}"
        )

    # -------------------------------------------------------------- Single Step
    def _run_one_llm_turn(self) -> Optional[str]:
        """
        Execute one round of 'model call + tool processing'.
        Return value:
          - None  means continue looping (tool call/handoff occurred)
          - str   means this is the final response (model did not call tools), process ends
        """
        self._log_role_banner()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self._messages_for_api(),
            tools=self._tools_for_current_role(),
            temperature=0,
        )
        msg = response.choices[0].message

        # No tool calls => final response
        if not msg.tool_calls:
            content = msg.content or ""
            self.history.append({"role": "assistant", "content": content})
            self.activity.append((self.current_role, "final", ""))
            self._log(f"{C.GREEN}└── [{self.current_role}] Final response:{C.RESET}\n{content}")
            return content

        # Tool calls present: first write the assistant message (with tool_calls) into history
        self.history.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        pending_transfer: Optional[Handoff] = None

        # Process each tool call and backfill a tool message for each (OpenAI requirement)
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if name == "transfer_to_agent":
                target = args.get("target_role", "")
                reason = args.get("reason", "")
                if target == self.current_role:
                    # Refuse self-handoff: let the model use its own tools or choose another role
                    result = (
                        f"Handoff failed: you are already {target} role, cannot hand off to yourself."
                        "Please use your own tools to complete the current part, or hand off to another role."
                    )
                    self._log(f"{C.RED}└── Transfer rejected: cannot hand off to self ({target}){C.RESET}")
                elif target in ROLES:
                    pending_transfer = Handoff(self.current_role, target, reason)
                    self.activity.append((self.current_role, "transfer", target))
                    result = f"Handed off to {target}. They will inherit the full conversation history and continue processing."
                    self._log(
                        f"{C.MAGENTA}└── ⇢ transfer_to_agent: "
                        f"{self.current_role} → {target}{C.RESET}\n"
                        f"    {C.YELLOW}reason:{C.RESET} {reason}"
                    )
                else:
                    result = f"Transfer failed: unknown role {target!r}. Optional:{list(ROLES.keys())}"
                    self._log(f"{C.RED}└── transfer failed: unknown role {target!r}{C.RESET}")
            else:
                impl = TOOL_IMPLEMENTATIONS.get(name)
                if impl is None:
                    result = f"Tool {name} does not exist."
                else:
                    result = impl(**args)
                    self.activity.append((self.current_role, "tool", name))
                # Anti-infinite loop: provide correction hints when the same (role, tool, parameters) is called repeatedly
                sig = f"{self.current_role}:{name}:{tc.function.arguments}"
                self._tool_call_counts[sig] = self._tool_call_counts.get(sig, 0) + 1
                if self._tool_call_counts[sig] >= 3:
                    result += (
                        "\n[System Prompt] You have repeatedly made the exact same call. Please stop repeating,"
                        " directly output the final text, or call transfer_to_agent to transfer to the next role."
                    )
                self._log(
                    f"{C.BLUE}└── 🔧 Call tool {name}{C.RESET} "
                    f"{C.DIM}args={args}{C.RESET}\n"
                    f"    {C.DIM}→ {result[:300]}{C.RESET}"
                )

            self.history.append(
                {"role": "tool", "tool_call_id": tc.id, "content": str(result)}
            )

        # After processing all tool calls in this round, if there is a transfer, switch roles (preserve history)
        if pending_transfer is not None:
            self.handoffs.append(pending_transfer)
            self.current_role = pending_transfer.to_role

        return None  # Continue loop

    # -------------------------------------------------------------- Main Loop
    def run(self, user_message: str) -> str:
        """Process one user message, run through the entire multi-role transfer flow, and return the final reply."""
        self.history.append({"role": "user", "content": user_message})
        self._log(f"{C.BOLD}👤 User:{C.RESET} {user_message}")

        final_answer = ""
        for step in range(self.max_steps):
            result = self._run_one_llm_turn()
            if result is not None:
                final_answer = result
                break
        else:
            final_answer = "(Reached maximum step limit, flow terminated)"
            self._log(f"{C.RED}{final_answer}{C.RESET}")

        return final_answer

    # -------------------------------------------------------------- Summary
    def handoff_chain_str(self) -> str:
        """Return a readable transfer chain, e.g., triage → research → data_analysis → writing → triage."""
        if not self.handoffs:
            return DEFAULT_ROLE + "(No transfer occurred)"
        chain = [self.handoffs[0].from_role]
        for h in self.handoffs:
            chain.append(h.to_role)
        return " → ".join(chain)

    def role_work_summary(self) -> str:
        """
        Return a division-of-labor overview of 'which role did what' — listed in order of first appearance,
        list the exclusive tools actually called by each role, and who produced the final reply.
        This directly confirms: on the same shared history, different specialized roles take turns to complete the task.
        """
        order: List[str] = []
        tools_by_role: Dict[str, List[str]] = {}
        final_role: Optional[str] = None
        for role, kind, detail in self.activity:
            if role not in order:
                order.append(role)
                tools_by_role[role] = []
            if kind == "tool" and detail not in tools_by_role[role]:
                tools_by_role[role].append(detail)
            elif kind == "final":
                final_role = role
        if not order:
            return "(No role activity record)"
        width = max(len(r) for r in order)
        lines: List[str] = []
        for role in order:
            used = tools_by_role[role]
            desc = "、".join(used) if used else "(Only routing/transfer, no exclusive tools used)"
            if role == final_role:
                desc += "  ⇒ Produce final reply"
            lines.append(f"  {role.ljust(width)} : {desc}")
        return "\n".join(lines)
