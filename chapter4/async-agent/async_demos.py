"""Offline demo: does not rely on any LLM / API key, directly drives the underlying primitives of the async runtime.

The four "scenarios" in `demo.py` require a real LLM to make decisions; this module extracts the three core
async capabilities from experiments 4-5 and demonstrates them in a measurable, reproducible way, **no internet or API key needed**:

  - demo_parallel  : wall-clock time comparison of parallel vs serial tool calls (real measurement, prints speedup ratio).
  - demo_interrupt : a long-running task is [interrupted/canceled], then the system [resumes] and accepts new tasks.
  - demo_state     : Agent state [checkpoint persistence] to disk, then [cross-session restoration] with verification.

These three demos collectively answer "what does async actually bring?" — using numbers and state changes, not just words.
"""

from __future__ import annotations

import asyncio
import datetime
import os
import time

from runtime import AgentRuntime, format_log
from events import Event, EventType
from tasks import TaskManager
import tasks


class Logger:
    """Colorful timestamp logger (same as runtime) with timing relative to the start of this demo."""

    def __init__(self) -> None:
        self.t0 = time.time()

    def __call__(self, source: str, text: str) -> None:
        print(format_log(self.t0, source, text), flush=True)


def banner(title: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78, flush=True)


# ============================ 1. Parallel vs Serial ============================

#A set of mutually independent [read-only perception tools] (read file / search / query database / vector retrieval).
#Read-only, no side effects, so they can be safely parallelized — this is exactly the point in the book that "perception tools are naturally suited for parallelism."
_PERCEIVE_TOOLS = [
    ("read_config.json", 0.8),
    ("web_search('Async Agent')", 1.2),
    ("db_query(orders)", 1.5),
    ("vector_lookup(memory)", 1.0),
]


async def _perceive(name: str, latency: float, log: Logger) -> tuple[str, float, float]:
    """Simulates a read-only perception call with I/O delay; returns (name, nominal delay, actual elapsed time)."""
    t0 = time.time()
    log("TOOL", f"→ {name} Starting (simulated I/O delay {latency:.1f}s）")
    await asyncio.sleep(latency)
    dt = time.time() - t0
    log("TOOL", f"✓ {name} Completed (actual {dt:.2f}s）")
    return name, latency, dt


async def demo_parallel() -> None:
    banner("Capability 1 | Parallel Tool Calls: Wall-clock time comparison of parallel vs serial")
    log = Logger()
    log("SYSTEM", "There are 4 mutually independent read-only perception tools to call (no side effects, safe to parallelize).")

    # —— Serial: await one after another ——
    log("SYSTEM", "\033[0m[Serial] Awaiting one by one (default synchronous ReAct approach)……")
    seq_start = time.time()
    for name, lat in _PERCEIVE_TOOLS:
        await _perceive(name, lat, log)
    seq_total = time.time() - seq_start

    # —— Parallel: launch all at once, asyncio.gather concurrent wait ——
    log("SYSTEM", "\033[0m[Parallel] Launching all at once, asyncio.gather concurrent wait……")
    par_start = time.time()
    await asyncio.gather(*[_perceive(name, lat, log) for name, lat in _PERCEIVE_TOOLS])
    par_total = time.time() - par_start

    slowest = max(lat for _, lat in _PERCEIVE_TOOLS)
    speedup = seq_total / par_total if par_total else float("inf")

    print("\n  ── Results Comparison ─────────────────────────────────────────────")
    print(f"  {'Tool':<26}{'Nominal Delay':>10}")
    for name, lat in _PERCEIVE_TOOLS:
        print(f"  {name:<26}{lat:>8.1f}s")
    print("  ─────────────────────────────────────────────────────────")
    print(f"  {'Serial Total Time (Σ each tool)':<26}{seq_total:>8.2f}s")
    print(f"  {'Parallel Total Time (gather)':<26}{par_total:>8.2f}s")
    print(f"  {'Parallel Theoretical Lower Bound (slowest single)':<26}{slowest:>8.2f}s")
    print(f"  {'Speedup = Serial / Parallel':<26}{speedup:>8.2f}x")
    print("  ─────────────────────────────────────────────────────────")
    print("  Conclusion: After parallelizing independent read-only calls, wall-clock time drops from \"sum\" to \"max.\"\n")


# ============================ 2. Interrupt / Cancel / Resume ============================

async def demo_interrupt() -> None:
    banner("Capability 2 | Interrupt and Cancel: Long task interrupted during execution, then system resumes")
    tasks.TICK_REAL = 0.15  # This demo slows down the pace to leave a time window for interrupting mid-execution
    log = Logger()
    completed: list = []

    async def on_complete(state) -> None:
        completed.append(state)

    tm = TaskManager(on_complete=on_complete, log=log)

    # 1) Start three background async tasks in parallel
    log("SYSTEM", "Starting three parallel background analysis tasks (fast/mid/slow)……")
    for cmd in ["python analyze_fast.py", "python analyze_mid.py", "python analyze_slow.py"]:
        tm.start(cmd)

    # 2) User asks instant questions during execution — background tasks are not blocked
    await asyncio.sleep(1.0)
    now = datetime.datetime.now().strftime("%H:%M:%S")
    log("USER", "(Instant question) What time is it now?")
    log("AGENT", f"Now {now}. Three background tasks are still running in parallel, not blocked by this query.")

    # 3) Midway through execution, the user issues an interrupt — cancel all running tasks immediately
    await asyncio.sleep(1.0)
    log("USER", "(Interrupt) Cancel")
    cancelled = tm.cancel_all()
    await asyncio.sleep(0.05)  # Let CancelledError land in each coroutine
    log("SYSTEM", f"Interrupt executed: cancelled {cancelled}(Progress frozen at the cancellation point)")

    print("\n  ── Task status after interrupt (progress frozen midway) ───────────────────")
    print(f"  {'task_id':<8}{'Command':<26}{'Status':<12}{'Progress':>6}")
    for s in tm.all_states():
        print(f"  {s.task_id:<8}{s.command:<26}{s.status:<12}{s.progress:>5.0f}%")
    print("  ─────────────────────────────────────────────────────────")

    # 4) Resume: executor is still healthy, accepts and completes a new task
    log("SYSTEM", "Interrupt handled, system returns to idle, ready to accept new tasks...")
    fresh = tm.start("python re_run_summary.py")
    await fresh._task
    log("AGENT", f"Recovered from interrupt, new task {fresh.task_id} Completed normally:"
                 f"{completed[-1].result[:36]}……")
    print("  Conclusion: Interrupt only freezes cancelled tasks; the runtime itself is unharmed and can immediately continue working.\n")


# ============================ 3. State Checkpoint: Persistence / Recovery ============================

def _seed_trajectory(rt: AgentRuntime) -> None:
    """Inject a pre-existing conversation trajectory into the runtime to simulate a session in progress."""
    rt._append(Event(EventType.USER_INPUT,
                     message={"role": "user", "content": "Analyze today's logs and summarize anomalies"},
                     label="User message: Analyze logs"))
    rt._append(Event(EventType.AGENT_TOOL_CALL,
                     message={"role": "assistant", "content": "Okay, I'll start the analysis in the background now.",
                              "tool_calls": [{"id": "call_1", "type": "function",
                                              "function": {"name": "run_terminal_command",
                                                           "arguments": '{"command": "python analyze_fast.py"}'}}]},
                     label="Call tool run_terminal_command"))
    rt._append(Event(EventType.TOOL_RESULT,
                     message={"role": "tool", "tool_call_id": "call_1",
                              "content": "Command has been started asynchronously in the background. task_id=T1."},
                     label="Tool result run_terminal_command"))


async def demo_state() -> None:
    banner("Capability 3 | State Management: Checkpoint Persistence and Cross-Session Recovery")
    tasks.TICK_REAL = 0.15
    ckpt_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoints")
    os.makedirs(ckpt_dir, exist_ok=True)
    path = os.path.join(ckpt_dir, "agent_state.json")

    # —— Session A: Generate a trajectory + two running background tasks, then persist ——
    log = Logger()
    log("SYSTEM", "Session A starts: Construct trajectory and start two background tasks...")
    rt_a = AgentRuntime(client=None, model="demo-offline")
    rt_a._t0 = log.t0  # Let two runtimes share the same time base for easy observation
    _seed_trajectory(rt_a)
    rt_a.tasks.start("python analyze_fast.py")   # In progress
    rt_a.tasks.start("python analyze_slow.py")   # In progress
    await asyncio.sleep(1.2)  # Let progress accumulate to midway

    before_traj = len(rt_a.trajectory)
    before_tasks = {s.task_id: (s.status, s.progress) for s in rt_a.tasks.all_states()}
    rt_a.save_checkpoint(path)

    #  Simulate process exit: cancel alive coroutines
    rt_a.tasks.cancel_all()
    await asyncio.sleep(0.05)
    log("SYSTEM", "Session A ends (process exits, in-memory runtime destroyed).")

    # —— Session B: new runtime, restored from disk ——
    log("SYSTEM", "Session B starts: create empty runtime, restore from checkpoint...")
    rt_b = AgentRuntime(client=None, model="demo-offline")
    rt_b._t0 = log.t0
    data = rt_b.load_checkpoint(path)

    after_traj = len(rt_b.trajectory)
    msgs = rt_b.build_messages()  #  Verify that after restoration, the context feedable to the LLM can be rebuilt

    print("\n  ── Restoration Verification ─────────────────────────────────────────────")
    print(f"  Number of trace events      Before save {before_traj}  ->  After restore {after_traj}  "
          f"[{'Consistent ✓' if before_traj == after_traj else 'Inconsistent ✗'}]")
    print(f"  Rebuildable LLM context messages {len(msgs)} (system + trace replay)")
    print(f"  {'task_id':<8}{'Command':<26}{'Progress before save':>10}  {'State after restore':<12}{'Progress':>6}")
    for rec in data["tasks"]:
        tid = rec["task_id"]
        before = before_tasks.get(tid, ("-", 0.0))
        st = rt_b.tasks.query(tid)
        print(f"  {tid:<8}{rec['command']:<26}{before[1]:>9.0f}%  "
              f"{st.status:<12}{st.progress:>5.0f}%")
    print("  ─────────────────────────────────────────────────────────")
    print(f"  Checkpoint file:{path}")
    print("  Conclusion: Traces and task progress are fully persisted and restored across sessions; running tasks are marked as suspended,")
    print("        retaining the last known progress for the upper layer to decide whether to 'rerun' or 'continue from progress'.\n")


#  Offline demo registry reused by demo.py
OFFLINE_DEMOS = {
    "parallel": demo_parallel,
    "interrupt": demo_interrupt,
    "state": demo_state,
}
