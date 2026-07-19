"""Flux async Agent runtime (experiment 4-5 core).

Implements the event processing loop from Section 5 of the design document, focusing on the four capabilities of experiments 4-5:
  1. Async tool execution: run_terminal_command immediately returns a placeholder, the task runs in the background.
  2. Event queue and batch processing: non-urgent events go to pending, and when async results arrive, they are appended in one batch.
  3. Interruption mechanism: user "cancel/stop" immediately cancels the current turn + all async tools, and leaves a trace.
  4. Cancellation and status query for parallel tools: query_task / cancel_task operate by ID;
     after async completion, inject the real result into the conversation as a "new event".

Architecture (three coroutines cooperating, all based on asyncio single-thread):
  - inbox queue: all incoming events (user input, interruption, async completion notification) first enter inbox.
  - _dispatcher: takes events from inbox -> determines urgency -> routes (immediate processing / queuing / interruption).
  - _worker: takes "event batches" from work queue -> appends to trace -> runs one LLM turn (run_llm_turn).
    Each LLM turn is a cancellable subtask (turn_task); when interrupted, directly cancel it.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import time
from typing import Optional

from events import Event, EventType, Urgency, classify_urgency
from tasks import TaskManager, TaskState

# ------------------------- LLM tool definitions (function calling) -------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_terminal_command",
            "description": ("Execute a (simulated) time-consuming terminal command, e.g., a log analysis script."
                            "After calling, the command runs in the background; this tool immediately returns a task_id placeholder,"
                            "and does not block. When the task actually completes, its result will appear in the conversation as a new system event."),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The terminal command to execute, e.g., `python analyze_logs.py`"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Return the current time immediately. Used to answer instant questions like 'what time is it'.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_task",
            "description": "Query the current progress and status of a background async task.",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "string", "description": "Task ID, e.g., T1"}},
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_task",
            "description": "Cancel a running background async task by task_id.",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "string", "description": "Task ID, e.g., T1"}},
                "required": ["task_id"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are an async Agent (based on the Flux framework). You can call tools to complete tasks.

Key behavioral guidelines:
1. run_terminal_command is [async]: after calling, the command runs in the background and immediately returns a task_id.
   You should briefly inform the user "the task has been started in the background", then [end this round of reply, do not wait for the result].
2. When you see a message like "[System event | Async task completed] task_id=... result: ...",
   it means the background task has actually completed; then provide analysis/integration conclusions based on the result.
3. If the user asks a short question (e.g., "what time is it?") while a background task is running,
   immediately answer with the corresponding tool (e.g., get_current_time), [do not wait] for the background task.
4. You can use query_task to query the progress of any background task, and cancel_task to cancel a task by ID.
5. When receiving "[User interruption]", immediately stop current work and briefly confirm the stop.
6. Strictly follow the plan given by the user (e.g., "whoever finishes first, check the progress of the rest; cancel if not past 50%").
   Note: only cancel tasks whose [progress does not exceed 50%]; tasks whose progress has exceeded 50% should be [kept and waited for completion], do not cancel them.
   For each running task, query progress only once to decide cancel/keep, do not query repeatedly.
7. Answer concisely, in Chinese, unless the user explicitly requests another language or format.
"""

MAX_STEPS = 8  # Maximum number of tool call round trips in a single turn (to prevent infinite loops)

# Log colors (one color per source), shared by runtime and offline demo scripts.
_LOG_COLORS = {
    "USER": "\033[96m", "AGENT": "\033[92m", "TOOL": "\033[93m",
    "TASK": "\033[95m", "SYSTEM": "\033[90m", "TRAJ": "\033[94m",
    "STATE": "\033[95m",
}


def format_log(t0: float, source: str, text: str) -> str:
    """ Render a log line as a colored string of `[relative seconds] source | text`."""
    color = _LOG_COLORS.get(source, "")
    reset = "\033[0m" if color else ""
    return f"[{time.time() - t0:6.2f}s] {color}{source:6}{reset} | {text}"


class AgentRuntime:
    def __init__(self, client, model: str, start_time: Optional[float] = None,
                 completion_params: Optional[dict] = None):
        self.client = client
        self.model = model
        # Sampling parameters passed to chat.completions.create. Default temperature=0.2 suitable for gpt-5.6-luna;
        # reasoning models (e.g., Moonshot kimi-k3) need temperature=1 and max_tokens>=2048, passed by make_client.
        self.completion_params = completion_params or {"temperature": 0.2}
        self._t0 = start_time or time.time()

        self.trajectory: list[Event] = []          # Trace (working memory)
        self.inbox: asyncio.Queue = asyncio.Queue()  # All incoming raw events
        self.work: asyncio.Queue = asyncio.Queue()   # Event batches to be processed
        self.pending: list[Event] = []               # Queue buffer for non-urgent events

        self.tasks = TaskManager(on_complete=self._on_task_complete, log=self.log)
        self.turn_task: Optional[asyncio.Task] = None
        self.running = True
        self._STOP = object()

    # ------------------------------- Logging -------------------------------

    def log(self, source: str, text: str) -> None:
        print(format_log(self._t0, source, text), flush=True)

    def _append(self, event: Event) -> None:
        """ Append an event to the trace and print the trace for record."""
        self.trajectory.append(event)
        self.log("TRAJ", f"+ {event.type:18} {event.label}")

    def build_messages(self) -> list[dict]:
        """ Render the trace as a list of OpenAI chat messages."""
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for e in self.trajectory:
            if e.message:
                msgs.append(e.message)
        return msgs

    # ------------------------- External interface: submit event -------------------------

    async def submit_user_message(self, text: str, urgency: Optional[str] = None) -> None:
        """ Submit a user message (demo uses this to simulate user input)."""
        u = urgency or classify_urgency(text)
        if u == Urgency.INTERRUPT:
            ev = Event(EventType.USER_INTERRUPT, urgency=u,
                       message={"role": "user", "content": f"[User interruption] {text}"},
                       label=f"User interruption:{text}")
        else:
            ev = Event(EventType.USER_INPUT, urgency=u,
                       message={"role": "user", "content": text},
                       label=f"User message ({u}）：{text}")
        self.log("USER", f"({u}) {text}")
        await self.inbox.put(ev)

    async def _on_task_complete(self, state: TaskState) -> None:
        """ Async task naturally completes -> inject the real result as a [new event] into the inbox."""
        ev = Event(
            EventType.ASYNC_RESULT, task_id=state.task_id,
            message={"role": "user",
                     "content": (f"[System event | Async task completed] task_id={state.task_id} "
                                 f"command=`{state.command}` result:{state.result}")},
            label=f"async complete {state.task_id}",
        )
        await self.inbox.put(ev)

    # ------------------------------- Main Loop -------------------------------

    async def serve(self) -> None:
        dispatcher = asyncio.create_task(self._dispatcher())
        worker = asyncio.create_task(self._worker())
        await asyncio.gather(dispatcher, worker)

    def _is_idle(self) -> bool:
        return (not self.tasks.any_running()
                and self.work.empty()
                and self.inbox.empty()
                and (self.turn_task is None or self.turn_task.done()))

    def _drain_pending(self) -> list[Event]:
        drained, self.pending = self.pending, []
        return drained

    async def _dispatcher(self) -> None:
        """Event dispatch: implement the two processing mechanisms from design document 5.1."""
        while self.running:
            ev = await self.inbox.get()
            if ev is self._STOP:
                await self.work.put(self._STOP)
                break

            if ev.type == EventType.USER_INTERRUPT:
                # —— Cancellation mode: immediately interrupt current turn + cancel all async tools ——
                await self._handle_interrupt(ev)

            elif ev.type == EventType.ASYNC_RESULT:
                # —— Async result arrival: batch append all pending events, then trigger LLM ——
                batch = [ev] + self._drain_pending()
                if len(batch) > 1:
                    self.log("SYSTEM", f"Async result arrived, batch processing {len(batch)-1} backlogged non-urgent events")
                await self.work.put(batch)

            elif ev.type == EventType.USER_INPUT:
                if ev.urgency == Urgency.IMMEDIATE:
                    # Process immediately (e.g., user questions), without interrupting background async tasks
                    await self.work.put([ev])
                elif self._is_idle():
                    # During idle, normal commands are also processed directly (e.g., tasks issued at start)
                    await self.work.put([ev])
                else:
                    # Queue processing: accumulate to pending, batch append on next async result
                    self.pending.append(ev)
                    self.log("SYSTEM", f"Event entering queue buffer (currently backlogged {len(self.pending)} items)")

    async def _handle_interrupt(self, ev: Event) -> None:
        # 1) Cancel ongoing LLM turn
        if self.turn_task and not self.turn_task.done():
            self.turn_task.cancel()
        # 2) Cancel all background async tools
        cancelled = self.tasks.cancel_all()
        # 3) Assemble interrupt batch: interrupt event + system receipt + discarded backlogged events (for traceability)
        note = Event(
            EventType.SYSTEM_NOTE,
            message={"role": "user",
                     "content": (f"[System] Interrupt executed: cancelled background tasks {cancelled or '(none)'}。"
                                 f"Briefly confirm to the user that it has stopped.")},
            label=f"Interrupt receipt, cancel task {cancelled or '(none)'}",
        )
        batch = [ev, note] + self._drain_pending()
        await self.work.put(batch)

    async def _worker(self) -> None:
        """Process events in batches: append to trace then run a cancellable LLM turn."""
        while self.running:
            batch = await self.work.get()
            if batch is self._STOP:
                break
            self.turn_task = asyncio.create_task(self._process_batch(batch))
            try:
                await self.turn_task
            except asyncio.CancelledError:
                self.log("SYSTEM", "Current LLM turn has been interrupted and cancelled")

    async def _process_batch(self, batch: list[Event]) -> None:
        for e in batch:
            self._append(e)
        await self.run_llm_turn()

    # ------------------------------- LLM turn -------------------------------

    async def run_llm_turn(self) -> None:
        """Call LLM for decision; synchronous tools execute in-place and backfill, async tools start and return placeholders."""
        for _ in range(MAX_STEPS):
            messages = self.build_messages()
            _t = time.time()
            resp = await self.client.chat.completions.create(
                model=self.model, messages=messages,
                tools=TOOL_SCHEMAS, tool_choice="auto", **self.completion_params,
            )
            self.log("SYSTEM", f"LLM call took {time.time()-_t:.2f}s（{len(messages)} messages)")
            msg = resp.choices[0].message

            assistant_msg: dict = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ]

            self._append(Event(
                EventType.AGENT_TOOL_CALL if msg.tool_calls else EventType.AGENT_OUTPUT,
                message=assistant_msg,
                label=("Call tool " + ", ".join(tc.function.name for tc in msg.tool_calls)
                       if msg.tool_calls else "Reply to user"),
            ))

            if msg.content and msg.content.strip():
                self.log("AGENT", msg.content.strip())

            if not msg.tool_calls:
                return  # End of turn: Agent gave final reply

            # Execute each tool call
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result_text = self._exec_tool(name, args)
                self._append(Event(
                    EventType.TOOL_RESULT,
                    message={"role": "tool", "tool_call_id": tc.id, "content": result_text},
                    label=f"Tool result {name}",
                ))

    def _exec_tool(self, name: str, args: dict) -> str:
        """The text result of executing the tool, returned to the LLM."""
        if name == "run_terminal_command":
            command = args.get("command", "")
            state = self.tasks.start(command)
            return (f"The command has been started asynchronously in the background. task_id={state.task_id}, command=`{command}`。"
                    f"I will not block and wait; when the task completes, its result will be returned as a system event."
                    f"You can use query_task('{state.task_id}') to check progress or cancel_task('{state.task_id}') to cancel.")

        if name == "get_current_time":
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log("TOOL", f"get_current_time -> {now}")
            return f"Current time is {now}。"

        if name == "query_task":
            tid = args.get("task_id", "")
            st = self.tasks.query(tid)
            if not st:
                return f"Task not found {tid}。"
            self.log("TOOL", f"query_task({tid}) -> {st.status} {st.progress:.0f}%")
            return f"task_id={tid} command=`{st.command}` status={st.status} progress={st.progress:.0f}%。"

        if name == "cancel_task":
            tid = args.get("task_id", "")
            st = self.tasks.query(tid)
            progress = f"{st.progress:.0f}%" if st else "Unknown"
            ok = self.tasks.cancel(tid)
            self.log("TOOL", f"cancel_task({tid}) -> {'Cancelled' if ok else 'Cannot cancel'} (progress {progress})")
            return (f"Task {tid} cancelled (progress at cancellation {progress}）。" if ok
                    else f"Task {tid} cannot be cancelled (may have completed or does not exist).")

        return f"Unknown tool: {name}"

    # ------------------------------- Wrap-up -------------------------------

    async def wait_until_idle(self, stable: float = 1.3, timeout: float = 90.0) -> None:
        """Block until the system remains idle for stable seconds (or timeout)."""
        start = time.time()
        last_busy = time.time()
        while True:
            busy = (self.tasks.any_running() or not self.work.empty()
                    or not self.inbox.empty() or bool(self.pending)
                    or (self.turn_task is not None and not self.turn_task.done()))
            now = time.time()
            if busy:
                last_busy = now
            elif now - last_busy >= stable:
                return
            if now - start >= timeout:
                self.log("SYSTEM", "wait_until_idle timeout returned")
                return
            await asyncio.sleep(0.1)

    async def stop(self) -> None:
        self.running = False
        await self.inbox.put(self._STOP)

    # ------------------------- State Checkpoint (Persist / Restore) -------------------------

    def snapshot(self) -> dict:
        """Export the agent's persistable state as a JSON-friendly dictionary.

        State = trace (working memory) + last known state of all async tasks. This is the basis for
        cross-session recovery: after a process restart, the conversation context and background task
        progress can be restored from this.
        """
        return {
            "model": self.model,
            "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "trajectory": [e.to_dict() for e in self.trajectory],
            "tasks": self.tasks.snapshot(),
        }

    def save_checkpoint(self, path: str) -> str:
        """Write the current state to a checkpoint file (JSON) and return the file path."""
        data = self.snapshot()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.log("STATE", f"Checkpoint saved -> {path}"
                          f"（{len(data['trajectory'])} trace events, {len(data['tasks'])} tasks)")
        return path

    def load_checkpoint(self, path: str) -> dict:
        """Restore trajectory and task state from checkpoint file (overwrite current state in place)."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.trajectory = [Event.from_dict(d) for d in data.get("trajectory", [])]
        self.tasks.restore(data.get("tasks", []))
        self.log("STATE", f"Restored from checkpoint <- {path}"
                          f"（{len(self.trajectory)} trace events, {len(data.get('tasks', []))} tasks)")
        return data
