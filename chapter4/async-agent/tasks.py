"""Simulated asynchronous "terminal commands" with a task manager.

For safety (never actually run dangerous commands) and reproducibility, long tasks are implemented as "simulated scripts with progress output":
Each simulated script advances at a fixed "progress percentage per (simulated) second" until it reaches 100%.

Time acceleration: In the real world, every TICK_REAL seconds represents 1 "simulated second".
Default TICK_REAL=0.4, i.e., 2.5x speed—preserving the logic of "3%/2%/1% speed differences + whether it has passed 50%",
but compressing tens of seconds into a few seconds for easy demonstration and reproduction.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Optional

# Real seconds corresponding to 1 "simulated second" (can be overridden by environment variable).
# Default 0.4 (2.5x speed): compresses waiting time while leaving enough time window for the model's "query-judge-cancel" decision,
# ensuring that in scenario 4, "slow script canceled before reaching 50%" can be stably reproduced.
TICK_REAL = float(os.getenv("FLUX_TICK_REAL", "0.4"))

# Gear positions of "progress % per simulated second" for different scripts. Experiment 4-5 scenario 4 requires speed differences of 3% / 2% / 1%.
_SCRIPT_RATES = [
    ("fast", 3.0),
    ("mid", 2.0),
    ("slow", 1.0),
]
_DEFAULT_RATE = 4.5  # Normal long tasks for scenarios 1/2/3 (about 22 simulated seconds ≈ 5.5 real seconds to complete)


def resolve_rate(command: str) -> float:
    """ Infer the progress speed (%/simulated second) of the simulated script based on the command string."""
    low = command.lower()
    for key, rate in _SCRIPT_RATES:
        if key in low:
            return rate
    return _DEFAULT_RATE


@dataclass
class TaskState:
    """ Real-time status of an asynchronous terminal task."""

    task_id: str
    command: str
    rate: float
    progress: float = 0.0
    status: str = "running"          # running | completed | cancelled
    result: str = ""
    _task: Optional[asyncio.Task] = field(default=None, repr=False)


class TaskManager:
    """ Manage all asynchronous terminal tasks: start, query progress, cancel.

    The on_complete callback is invoked when a task completes naturally (used to inject the real result as a "new event" into the conversation).
    """

    def __init__(self, on_complete: Callable[[TaskState], Awaitable[None]],
                 log: Callable[[str, str], None]):
        self._on_complete = on_complete
        self._log = log
        self._tasks: Dict[str, TaskState] = {}
        self._counter = 0

    def start(self, command: str) -> TaskState:
        """ Start an asynchronous terminal command and immediately return its status (including task_id placeholder)."""
        self._counter += 1
        task_id = f"T{self._counter}"
        state = TaskState(task_id=task_id, command=command, rate=resolve_rate(command))
        self._tasks[task_id] = state
        state._task = asyncio.create_task(self._run(state))
        self._log("TASK", f" Start async task {task_id}: `{command}` (speed {state.rate:.0f}%/simulated second)")
        return state

    async def _run(self, state: TaskState) -> None:
        """ Advance progress in the background until completion or cancellation."""
        next_milestone = 20.0
        try:
            while state.progress < 100.0:
                await asyncio.sleep(TICK_REAL)
                state.progress = min(100.0, state.progress + state.rate)
                if state.progress >= next_milestone:
                    self._log("TASK", f"{state.task_id} `{state.command}` progress {state.progress:.0f}%")
                    next_milestone += 20.0
            state.status = "completed"
            state.result = (f"Command `{state.command}` completed: scanned 12,840 records total,"
                            f"found 3 anomaly peaks, 1 suspicious error code (HTTP 503 spike),"
                            f"average response time 128ms.")
            self._log("TASK", f"{state.task_id} Completed ✅")
            await self._on_complete(state)
        except asyncio.CancelledError:
            # Canceled: mark status and exit silently (do not inject completion result)
            state.status = "cancelled"
            self._log("TASK", f"{state.task_id} Canceled 🛑 (progress stopped at {state.progress:.0f}%）")
            raise

    def query(self, task_id: str) -> Optional[TaskState]:
        return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """ Cancel a single task by ID."""
        state = self._tasks.get(task_id)
        if state and state.status == "running":
            state.status = "cancelled"
            if state._task:
                state._task.cancel()
            return True
        return False

    def cancel_all(self) -> list[str]:
        """ Cancel all running tasks and return the list of canceled task_ids."""
        cancelled = []
        for tid, state in self._tasks.items():
            if state.status == "running":
                state.status = "cancelled"
                if state._task:
                    state._task.cancel()
                cancelled.append(tid)
        return cancelled

    def any_running(self) -> bool:
        return any(s.status == "running" for s in self._tasks.values())

    def all_states(self) -> list[TaskState]:
        return list(self._tasks.values())

    # --------------------------- Status checkpoint (persistence) ---------------------------

    def snapshot(self) -> list[dict]:
        """ Export the last known status of all tasks for checkpoint persistence.

        Note: Running asyncio coroutines cannot be serialized; only their last known progress can be recorded;
        After restart, decide whether to "rerun" or "continue from progress" based on this, which is the essence of async task state management.
        """
        return [
            {"task_id": s.task_id, "command": s.command, "rate": s.rate,
             "progress": s.progress, "status": s.status, "result": s.result}
            for s in self._tasks.values()
        ]

    def restore(self, records: list[dict]) -> None:
        """ Restore historical task status from checkpoint (without restarting coroutines).

        When restoring, mark "running" tasks as suspended—they have no live coroutine,
        only retain the progress at the moment of snapshot, waiting for the upper logic to decide how to continue.
        """
        for r in records:
            status = "suspended" if r["status"] == "running" else r["status"]
            state = TaskState(
                task_id=r["task_id"], command=r["command"], rate=r["rate"],
                progress=r["progress"], status=status, result=r.get("result", ""),
            )
            self._tasks[state.task_id] = state
            try:
                self._counter = max(self._counter, int(state.task_id.lstrip("T") or 0))
            except ValueError:
                pass
