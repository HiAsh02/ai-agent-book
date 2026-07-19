"""
StagedAgent: A Coding Agent that switches system prompts and tool sets based on the "execution stage".

Design highlights (corresponding to the 6 requirements of Experiment 10-1):
1) Three stages each have clearly defined role system prompts (STAGE_PROMPTS).
2) Each stage has an independent tool set (tools.STAGE*_TOOLS).
3) Stage transitions are triggered by "specific tool calls" (complete_requirements_analysis /
   submit_for_review / request_revision / approve_code).
4) Context is continuous across stages: self.history accumulates, only the system prompt is swapped when switching stages,
   all historical messages (including previous requirements, code, review comments) are retained.
5) When review finds issues, request_revision causes the workflow to fall back to the implementation stage.
6) Each step is logged in self.logs, so different prompts leading to different behaviors can be observed.
"""

from __future__ import annotations

import json
from typing import Callable, Dict, List, Optional

from openai import OpenAI

from config import Config
from simulated_user import SimulatedUser
import tools as T


# ----------------------------------------------------------------------------
# Three-stage system prompt — one distinct "role" per stage.
# ----------------------------------------------------------------------------
STAGE_PROMPTS: Dict[str, str] = {
    "requirements": (
        "You are a rigorous 【Requirements Analyst】. Currently in the 【Requirements Clarification Phase】.\n"
        "Your sole responsibility is to clarify the user's vague requirements; never write any code.\n"
        "How it works: \n"
        "1. For unclear points, use ask_clarifying_question to ask one at a time (one question per turn).\n"
        "2. Whenever the user confirms a point, record it with save_requirement.\n"
        "3. Key issues (which file types to process, whether to recurse subdirectories, whether to keep original filenames,"
        "After clarifying and documenting details such as whether to move or copy, how to specify the target directory, etc.,"
        "Call complete_requirements_analysis to end this phase.\n"
        "Remember: You do not implement or design code; you are only responsible for clarifying and documenting requirements."
    ),
    "implementation": (
        "You are a senior software engineer. Currently in the code implementation phase.\n"
        "The requirements have already been confirmed by the requirements analyst above. Please strictly implement these requirements without adding or removing features on your own.\n"
        "How it works: \n"
        "1. Use write_file to write high-quality, readable Python code with module and function docstrings,"
        "Avoid bare except, pay attention to exception handling.\n"
        "2. Use execute_code for self-testing to confirm the logic is correct and runs.\n"
        "3. After the code is completed and self-tested, call submit_for_review to submit for review.\n"
        "If it was returned during the review stage (there will be a list of issues in the history),"
        "Please fix each issue one by one and then resubmit for review."
    ),
    "review": (
        "You are a critical [code reviewer]. Currently in the [code review phase].\n"
        "Your responsibility is to critically review the code implementing the phase submission and ensure quality.\n"
        "How it works: \n"
        "1. Objectively check the code using run_linter, run_tests, analyze_complexity in sequence.\n"
        "2. Carefully interpret the inspection results. Whenever the linter reports an issue or a test fails,"
        "must call request_revision to return the issue list to the implementation phase for fixing.\n"
        "3. Only call approve_code for approval when the check is clean, tests pass, and complexity is reasonable.\n"
        "Be strict with standards and don't ignore issues reported by the linter."
    ),
}

# Stage name -> Tool set exposed by this stage
STAGE_TOOLS = {
    "requirements": T.STAGE1_TOOLS,
    "implementation": T.STAGE2_TOOLS,
    "review": T.STAGE3_TOOLS,
}

#  Set of "signal tools" that trigger stage transitions
T_TRANSITION_TOOLS = {
    T.COMPLETE_REQUIREMENTS,
    T.SUBMIT_FOR_REVIEW,
    T.REQUEST_REVISION,
    T.APPROVE_CODE,
}

# 阶段名 -> 角色中文名（打印用）
STAGE_ROLE = {
    "requirements": "Requirements Analyst",
    "implementation": "Software Engineer",
    "review": "Code Reviewer",
}

# Linear order of stages and print titles
STAGE_ORDER = ["requirements", "implementation", "review"]
STAGE_TITLE = {
    "requirements": "Stage 1: Requirements Clarification",
    "implementation": "Stage 2: Code Implementation",
    "review": "Stage 3: Code Review",
}

# Pre-set "confirmed requirements" used when starting from stages after requirements.
# The values match the answers given by the simulated user in simulated_user.py, so this is a
# faithful reproduction of the output of the requirements clarification stage, not fabricated, to facilitate debugging the latter two stages independently.
CANONICAL_REQUIREMENTS: Dict[str, str] = {
    "file_types": "Images (jpg/png/gif), documents (pdf/doc/txt), audio (mp3/wav),"
                  "video (mp4/mov), archives (zip/rar), and the rest go to Others",
    "recursive": "Non-recursive, only organize the current level of the download folder, ignoring existing subfolders",
    "naming": "Keep original filenames; add _1/_2 suffix for conflicts to avoid overwriting",
    "move_or_copy": "Move, no longer retain these files in original location after organization",
    "destination": "Create subdirectories by category within the download folder"
                   "（Images/Documents/Audio/Video/Archives/Others）；"
                   "Root path passed via command line argument, default ~/Downloads",
}


def stage_overview() -> str:
    """Offline print of three-stage overview (roles / system prompts / tool sets / transition signals), no API Key required."""
    lines: List[str] = ["Staged system prompts · Three-stage role switching overview (offline, no API Key required)"]
    for stage in STAGE_ORDER:
        tool_names = [t["function"]["name"] for t in STAGE_TOOLS[stage]]
        transitions = [n for n in tool_names if n in T_TRANSITION_TOOLS]
        normal = [n for n in tool_names if n not in T_TRANSITION_TOOLS]
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"{STAGE_TITLE[stage]}  |  Role:{STAGE_ROLE[stage]}")
        lines.append("=" * 70)
        lines.append("System Prompt:")
        lines.append(STAGE_PROMPTS[stage])
        lines.append(f"Work Tools:{normal}")
        lines.append(f"Stage Transition Signal Tools:{transitions}")
    lines.append("")
    lines.append("Stage Transition Relationships:")
    lines.append("  requirements  --complete_requirements_analysis-->  implementation")
    lines.append("  implementation  --submit_for_review-->  review")
    lines.append("  review  --request_revision-->  implementation  (review fails, fallback to rewrite)")
    lines.append("  review  --approve_code-->  complete")
    return "\n".join(lines)


class StagedAgent:
    def __init__(
        self,
        max_revisions: int = 2,
        verbose: bool = True,
        interactive: bool = False,
    ) -> None:
        Config.validate()
        self.client = OpenAI(api_key=Config.API_KEY, base_url=Config.BASE_URL)
        self.model = Config.MODEL

        self.workspace = T.Workspace()
        self.sim_user = SimulatedUser()

        #Cross-stage shared conversation history (excluding system prompts, system prompts are concatenated per stage)
        self.history: List[dict] = []
        #Structured execution log: each entry = {stage, role, action, detail}
        self.logs: List[dict] = []

        self.stage = "requirements"
        self.revision_count = 0
        self.max_revisions = max_revisions
        self.verbose = verbose
        # When interactive=True, questions in the requirements clarification stage are answered by a human via standard input;
        # default False uses SimulatedUser preset answers, allowing the full pipeline to run unattended.
        self.interactive = interactive

    # --- Logging and Printing ------------------------------------------------------
    def _log(self, action: str, detail: str) -> None:
        entry = {
            "stage": self.stage,
            "role": STAGE_ROLE[self.stage],
            "action": action,
            "detail": detail,
        }
        self.logs.append(entry)
        if self.verbose:
            print(f"[{STAGE_ROLE[self.stage]}] {action}: {detail}")

    def _banner(self, text: str) -> None:
        if self.verbose:
            print("\n" + "=" * 70)
            print(text)
            print("=" * 70)

    # --- Tool Distribution --------------------------------------------------------
    def _dispatch_tool(self, name: str, args: dict) -> str:
        """Execute a normal tool (not a stage-transition tool) and return the tool result string to the model."""
        if name == "ask_clarifying_question":
            question = args.get("question", "")
            self._log("Ask", question)
            if self.interactive:
                answer = input(f"  [Please answer the requirements analyst's question] {question}\n  > ").strip()
                answer = answer or "No special requirements, handle according to common sense."
                self._log("User Response", answer)
            else:
                answer = self.sim_user.answer(question)
                self._log("Simulate user response", answer)
            return answer
        if name == "save_requirement":
            res = self.workspace.save_requirement(args.get("key", ""), args.get("value", ""))
            self._log("Record Requirements", f"{args.get('key')} = {args.get('value')}")
            return res
        if name == "write_file":
            res = self.workspace.write_file(args.get("path", ""), args.get("content", ""))
            self._log("Write File", res)
            return res
        if name == "read_file":
            self._log("Read File", args.get("path", ""))
            return self.workspace.read_file(args.get("path", ""))
        if name == "execute_code":
            self._log("Execute Code Self-Test", args.get("code", "")[:80].replace("\n", " ") + " ...")
            return self.workspace.execute_code(args.get("code", ""))
        if name == "run_linter":
            res = self.workspace.run_linter(args.get("file", ""))
            self._log("run_linter", res.splitlines()[0])
            return res
        if name == "run_tests":
            res = self.workspace.run_tests(args.get("file", ""))
            self._log("run_tests", res.splitlines()[0])
            return res
        if name == "analyze_complexity":
            res = self.workspace.analyze_complexity(args.get("file", ""))
            self._log("analyze_complexity", res)
            return res
        return f"Unknown tool: {name}"

    # --- Main Flow ----------------------------------------------------------
    def run(self, user_task: str, start_stage: str = "requirements") -> None:
        # The user's initial task, as the first message in the shared context
        self.history.append({"role": "user", "content": user_task})
        self._banner(f"User Task: {user_task}")

        # Stage state machine: run until approve_code or exceed safety limit
        max_total_steps = 40
        steps = 0
        done = False

        if start_stage == "implementation":
            # Skip requirements clarification, start directly from the implementation stage: preset a product equivalent to the requirements clarification output
            # Confirmed requirements, convenient for debugging the implementation/review stages individually without rerunning the clarification dialogue each time.
            self._seed_requirements()
            self._enter_stage("implementation")
        else:
            self._enter_stage("requirements")

        while not done and steps < max_total_steps:
            steps += 1
            done = self._run_one_model_turn()

        if not done:
            self._banner("Reached step limit, demo ends (approve_code not received).")

    def _seed_requirements(self) -> None:
        """When starting from a stage after requirements, preset a confirmed requirement and inject a handover message."""
        self.workspace.requirements = dict(CANONICAL_REQUIREMENTS)
        reqs = "\n".join(f"- {k}: {v}" for k, v in self.workspace.requirements.items())
        self.history.append({
            "role": "user",
            "content": (
                "【Stage Handover】（--start-stage skipped requirements clarification）The requirements analyst has confirmed the following requirements,"
                "Please implement accordingly:\n" + reqs
            ),
        })
        self._log_seed(reqs)

    def _log_seed(self, reqs: str) -> None:
        if self.verbose:
            self._banner("Preset requirements (skipped requirements clarification stage)")
            print(reqs)

    def _enter_stage(self, stage: str) -> None:
        self.stage = stage
        self._banner(
            f"Entering stage: {stage}  |  Role:{STAGE_ROLE[stage]}  |  "
            f"Available tools: {[t['function']['name'] for t in STAGE_TOOLS[stage]]}"
        )

    def _run_one_model_turn(self) -> bool:
        """
        Invoke the model once; execute all tool calls it requests.
        Return True to indicate the entire task is complete (approve_code).
        Stage-transition tools switch self.stage and return immediately, so the next round uses new prompts and new tools.
        """
        messages = [{"role": "system", "content": STAGE_PROMPTS[self.stage]}] + self.history
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=STAGE_TOOLS[self.stage],
                temperature=Config.TEMPERATURE,
            )
        except Exception as exc:  # noqa: BLE001
            # Some reasoning models (e.g., gpt-5.x) only accept default temperature; explicitly passing temperature results in 400.
            # When an error related to temperature is detected, remove temperature and retry once.
            if "temperature" in str(exc).lower():
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=STAGE_TOOLS[self.stage],
                )
            else:
                raise
        msg = response.choices[0].message

        # Add assistant message (possibly containing tool_calls) to shared history
        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        self.history.append(assistant_entry)

        if msg.content and msg.content.strip():
            self._log("Think/Speak", msg.content.strip())

        # No tool call: the model just talks. Prompt it to continue using tools to make progress.
        if not msg.tool_calls:
            self.history.append({
                "role": "user",
                "content": "Please use the tools provided in the current phase to continue advancing the task.",
            })
            return False

        #  Process all tool calls in this round one by one.  
        # Note: Even if a "phase transition tool" is encountered, the assistant message must first be processed.
        # Each tool_call must be replied with a tool message (mandated by the OpenAI protocol).
        #  Therefore, the actual phase switch/context handover is deferred until after all tools have responded.
        pending_transition: Optional[dict] = None
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if name in T_TRANSITION_TOOLS:
                tool_result, descriptor = self._transition_result(name, args)
                # Only recognize the first conversion tool, the rest only respond as ordinary
                if pending_transition is None:
                    pending_transition = descriptor
            else:
                tool_result = self._dispatch_tool(name, args)

            self.history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })

        # After all tool messages are completed, perform phase switching and context handover.
        if pending_transition is not None:
            return self._apply_transition(pending_transition)
        return False

    def _transition_result(self, name: str, args: dict):
        """
        The calculation phase conversion tool returns the tool result string to the model and returns a descriptor
        describing the "switch action to be performed later". This function only logs, without modifying history / phase.
        Returns (tool_result_str, descriptor_dict).
        """
        if name == T.COMPLETE_REQUIREMENTS:
            summary = args.get("summary", "")
            self._log("Complete requirements analysis -> hand over for implementation", summary)
            return (
                f"Requirements analysis completed:{summary}. About to enter the code implementation phase.",
                {"kind": "to_implementation"},
            )

        if name == T.SUBMIT_FOR_REVIEW:
            file = args.get("file", "")
            self._log("Submit for review -> Transfer for review", file)
            return (
                f"Submitted {file}, about to enter the review phase.",
                {"kind": "to_review", "file": file},
            )

        if name == T.REQUEST_REVISION:
            issues = args.get("issues", [])
            if isinstance(issues, str):
                issues = [issues]
            self.workspace.review_issues = list(issues)
            self.revision_count += 1
            self._log("Review failed -> rollback implementation", f"第{self.revision_count}Return:{issues}")
            return (
                "The issue list has been returned to the implementation stage.",
                {"kind": "request_revision", "issues": list(issues)},
            )

        if name == T.APPROVE_CODE:
            comment = args.get("comment", "")
            self._log("Review passed -> Task completed", comment)
            return (f"Code approved: {comment}", {"kind": "approve"})

        return ("Unknown conversion tool.", {"kind": "noop"})

    def _apply_transition(self, descriptor: dict) -> bool:
        """
        Actual stage switching: inject cross-stage handover user message + switch self.stage.
        Return True to indicate the entire task is complete.
        """
        kind = descriptor["kind"]

        if kind == "to_implementation":
            reqs = "\n".join(f"- {k}: {v}" for k, v in self.workspace.requirements.items())
            self.history.append({
                "role": "user",
                "content": (
                    "[Phase Handover] Requirements analysis completed. Confirmed requirements are as follows, please implement accordingly:\n"
                    + (reqs or "(no explicit record)")
                ),
            })
            self._enter_stage("implementation")
            return False

        if kind == "to_review":
            file = descriptor.get("file", "")
            self.history.append({
                "role": "user",
                "content": (
                    f"[Phase Handover] Implementation phase has submitted file `{file}` For review."
                    f"Current workspace files:{list(self.workspace.files)}. Please start strict review."
                ),
            })
            self._enter_stage("review")
            return False

        if kind == "request_revision":
            # Safety valve: force termination if too many retries to avoid infinite loops burning tokens
            if self.revision_count > self.max_revisions:
                self._log("Maximum number of rollbacks reached", "Force end demo")
                self.history.append({
                    "role": "user",
                    "content": "[System] Maximum number of rollbacks reached. Demo ends here.",
                })
                return True
            issue_text = "\n".join(f"- {x}" for x in descriptor.get("issues", []))
            self.history.append({
                "role": "user",
                "content": (
                    "[Phase Handover·Rollback] Review failed. Fix the following issues and resubmit:\n"
                    + issue_text
                ),
            })
            self._enter_stage("implementation")
            return False

        if kind == "approve":
            return True

        return False

    # --- Print summary after demo --------------------------------------------------
    def print_summary(self) -> None:
        self._banner("Execution summary")
        # Count actions per phase to show "different prompts -> different behavior patterns"
        by_stage: Dict[str, List[str]] = {}
        for e in self.logs:
            by_stage.setdefault(e["role"], []).append(e["action"])
        for role, actions in by_stage.items():
            from collections import Counter
            counts = Counter(actions)
            summary = ", ".join(f"{a}×{n}" for a, n in counts.items())
            print(f"[{role}] Behavior distribution:{summary}")

        print(f"\nNumber of confirmed requirements:{len(self.workspace.requirements)}")
        print(f"Output files:{list(self.workspace.files)}")
        print(f"Number of review rollbacks:{self.revision_count}")
