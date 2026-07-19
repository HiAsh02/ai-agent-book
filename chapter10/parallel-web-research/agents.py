"""
Main Coordinator and Sub-Agent (Worker)
===========================================

Implement the core coordination mechanism of Experiment 10-6:

1. Parallel dispatch: Coordinator starts N homogeneous Workers simultaneously, each searching one "website/source".
2. Message bus: Workers and Coordinator communicate via ``MessageBus`` using envelopes.
3. Real-time monitoring (push paradigm): Workers actively report ``status_update`` during execution,
   Coordinator maintains a task status table and refreshes printing in real time.
4. Cascading termination: When a Worker hits the target, Coordinator broadcasts ``terminate``,
   other Workers check the signal at safe points in the loop, ack, and exit gracefully.
5. Race condition handling: Multiple Workers may hit almost simultaneously; Coordinator uses ``asyncio.Lock``
   + idempotent flag to ensure **only one settlement and one round of termination broadcast**.

State machine: submitted -> running -> (needs_input) -> succeeded / failed / terminated
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from llm import judge_answer, llm_available
from message_bus import BROADCAST, MessageBus, _now
from sources import Source


class TaskState(str, Enum):
    SUBMITTED = "Submitted"
    RUNNING = "Running"
    NEEDS_INPUT = "Needs Input"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    TERMINATED = "Terminated"


@dataclass
class TaskRecord:
    """A row in the Coordinator status table: real-time status of a Worker."""

    worker_id: str
    source_name: str
    state: TaskState = TaskState.SUBMITTED
    note: str = ""
    updated: float = field(default_factory=_now)


# ————————————————————————————— Sub-Agent —————————————————————————————
class WorkerAgent:
    """
    A homogeneous sub-agent: responsible for fetching and searching a single source.
    Receives task_assigned / terminate via the message bus, reports status_update / result / ack.
    """

    def __init__(self, worker_id: str, source: Source, bus: MessageBus, question: str):
        self.id = worker_id
        self.source = source
        self.bus = bus
        self.question = question
        # Subscribe: only care about task_assigned and terminate sent to itself or broadcast
        self.sub = bus.subscribe(worker_id, types=["task_assigned", "terminate"])
        self._terminated = asyncio.Event()

    async def _report(self, state: TaskState, note: str = "", type: str = "status_update"):
        """Push a status update to the Coordinator (push paradigm for real-time monitoring)."""
        await self.bus.send(
            self.id,
            "coordinator",
            type,
            {"state": state.value, "note": note, "source": self.source.name},
        )

    async def _drain_signals(self) -> bool:
        """
        Check at a safe point whether a terminate signal has been received (non-blocking).
        If received, ack and return True; the caller exits gracefully based on this.
        """
        while not self.sub.inbox.empty():
            env = self.sub.inbox.get_nowait()
            if env.type == "terminate":
                self._terminated.set()
        if self._terminated.is_set():
            await self.bus.send(
                self.id, "coordinator", "ack",
                {"acked": "terminate", "source": self.source.name},
            )
            await self._report(TaskState.TERMINATED, "Received terminate signal, exiting safely")
            return True
        return False

    async def run(self):
        """
        Worker main loop: multiple steps of "fetch + search", checking terminate signal between each step.
        Splitting a single fetch into multiple steps simulates the multi-turn operations of a real Computer Use Agent,
        and provides "safety checkpoints" for cascading termination.
        """
        # Waiting for Coordinator to dispatch task (task_assigned)
        env = await self.sub.get()
        while env.type != "task_assigned":
            env = await self.sub.get()
        await self._report(TaskState.RUNNING, "Start fetching source")

        steps = 3  # Split fetch into 3 steps to create interruptible checkpoints
        per_step = max(self.source.latency / steps, 0.05)
        collected = ""
        for i in range(1, steps + 1):
            # —— Safety checkpoint: check if termination is requested ——
            if await self._drain_signals():
                return
            # —— Execute one fetch step (simulate one round of Computer Use operation time) ——
            await asyncio.sleep(per_step)
            collected = self.source.content  # Fetched text; determine if hit in the last step
            await self._report(TaskState.RUNNING, f"Fetch progress {i}/{steps}")

        # Check termination again (may have been received during last step's time consumption)
        if await self._drain_signals():
            return

        # —— Use (optional) LLM or keywords to determine if answer is hit ——
        answer = await judge_answer(self.question, collected)
        if answer:
            # Hit: send result back to Coordinator (may race with other Workers)
            await self.bus.send(
                self.id, "coordinator", "result",
                {"found": True, "answer": answer, "source": self.source.name},
            )
            await self._report(TaskState.SUCCEEDED, f"Hit:{answer}")
        else:
            await self.bus.send(
                self.id, "coordinator", "result",
                {"found": False, "source": self.source.name},
            )
            await self._report(TaskState.FAILED, "No answer found from this source")


# ————————————————————————————— Main Coordinator —————————————————————————————
class Coordinator:
    """
    Central coordinator: dispatches sub-agents in parallel, maintains status table, settles first hit, broadcasts cascading termination.
    """

    def __init__(self, bus: MessageBus, question: str):
        self.bus = bus
        self.question = question
        # Subscribe to all message types reported by sub-agents
        self.sub = bus.subscribe("coordinator", types=["status_update", "result", "ack"])
        self.table: Dict[str, TaskRecord] = {}
        self.workers: List[WorkerAgent] = []

        # —— Key states for race condition handling ——
        self._settle_lock = asyncio.Lock()   #  Ensure settlement and termination broadcast are mutually exclusive
        self._settled = False                # Idempotency flag: whether already settled
        self.winner: Optional[str] = None    # First hit Worker
        self.answer: Optional[str] = None
        self.duplicate_hits: List[str] = []  # Record "late hit" to prove race condition was correctly ignored

        self._acks: set[str] = set()
        self._expected_workers = 0

    def add_worker(self, worker: WorkerAgent):
        self.workers.append(worker)
        self.table[worker.id] = TaskRecord(worker.id, worker.source.name)

    def _print_table(self, reason: str):
        """Refresh and print the task status table in real time."""
        print(f"\n  ──  Task Status Table ({reason}） ──")
        for rec in self.table.values():
            print(
                f"     {rec.worker_id:<10} source={rec.source_name:<12} "
                f"Status={rec.state.value:<5} {('| ' + rec.note) if rec.note else ''}"
            )
        print()

    async def _dispatch(self):
        """Parallel dispatch: send task_assigned to each Worker."""
        self._expected_workers = len(self.workers)
        for w in self.workers:
            self.table[w.id].state = TaskState.SUBMITTED
            await self.bus.send(
                "coordinator", w.id, "task_assigned",
                {"question": self.question, "source": w.source.name},
            )
        self._print_table("All sub-agents have been dispatched")

    async def _settle_if_first(self, worker_id: str, answer: str) -> bool:
        """
        Race handling core: use lock + idempotent flag to ensure settlement only once and broadcast termination only one round.
        Return True to indicate this is the "first valid hit".
        """
        async with self._settle_lock:
            if self._settled:
                #  Late hit: already settled, ignore directly (idempotent)
                self.duplicate_hits.append(worker_id)
                print(
                    f"  [Race condition] {worker_id} also matched, but has been {self.winner}  Settlement —— "
                    f"Ignore this hit, do not repeat the broadcast termination."
                )
                return False
            # First hit: settle and broadcast round termination
            self._settled = True
            self.winner = worker_id
            self.answer = answer
            print(f"  [Settlement] First hit from {worker_id} —— Lock settlement, broadcast one round of terminate.")
            await self.bus.send(
                "coordinator", BROADCAST, "terminate",
                {"reason": "answer_found", "winner": worker_id},
            )
            return True

    async def run(self, quiet_period: float = 2.5) -> dict:
        """
        Coordinate main loop: dispatch -> listen for report -> settle first hit -> collect ack -> summarize.
        """
        mode = "LLM judgment" if llm_available() else "Keyword Judgment (Offline Reproducible)"
        print(f"  [Coordinator] Judgment mode: {mode}\n")
        t0 = time.monotonic()  #  Record the wall clock start point of parallel execution
        await self._dispatch()

        #  Start all Worker coroutines
        worker_tasks = [asyncio.create_task(w.run()) for w in self.workers]

        done_states = {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.TERMINATED}
        last_terminate_time: Optional[float] = None

        while True:
            env = await self.sub.get_nowait_or_wait(timeout=0.5)
            if env is None:
                # No new messages: if settled and past the silent period, consider converged and exit
                if self._settled and last_terminate_time is not None:
                    if _now() - last_terminate_time > quiet_period:
                        break
                # All Workers have entered the final state and exited
                if all(r.state in done_states for r in self.table.values()):
                    break
                continue

            rec = self.table.get(env.sender_id)

            if env.type == "status_update" and rec:
                prev = rec.state
                rec.state = TaskState(env.payload["state"])
                rec.note = env.payload.get("note", "")
                rec.updated = _now()
                #  Refresh the state table only when the "state machine transitions" to avoid screen flooding on every step.
                if rec.state != prev:
                    self._print_table(f"{env.sender_id} -> {rec.state.value}")

            elif env.type == "result":
                if env.payload.get("found"):
                    is_first = await self._settle_if_first(
                        env.sender_id, env.payload["answer"]
                    )
                    if is_first:
                        last_terminate_time = _now()

            elif env.type == "ack":
                self._acks.add(env.sender_id)
                print(f"  [ack] {env.sender_id} Confirmed termination ({len(self._acks)} (already ack)")

        # Wait for all Worker coroutines to finish
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        elapsed = time.monotonic() - t0  # Wall-clock time of parallel execution (including convergence quiet period)
        self._print_table(" Final state")

        return {
            "winner": self.winner,
            "answer": self.answer,
            "duplicate_hits": self.duplicate_hits,
            "acks": sorted(self._acks),
            "settled_once": self._settled,
            "terminate_broadcasts": sum(
                1 for e in self.bus.history if e.type == "terminate"
            ),
            "parallel_seconds": elapsed,
        }


# ————————————————————————— Serial Baseline (Performance Comparison) —————————————————————————
async def run_sequential(sources: List[Source], question: str) -> dict:
    """
    Serial baseline: fetch and judge sources one by one, stop on first hit.

    Used to compare wall-clock benefit of parallel execution (corresponding to the experiment requirement "record and compare parallel/serial time differences" in the book).
    Here we truly await ``source.fetch()`` one after another, so the time is **measured** not estimated—
    no data fabrication; the hit judgment reuses the same :func:`judge_answer` as the parallel version.
    """
    t0 = time.monotonic()
    winner: Optional[str] = None
    answer: Optional[str] = None
    fetched = 0
    for src in sources:
        fetched += 1
        text = await src.fetch()
        ans = await judge_answer(question, text)
        if ans:
            winner, answer = src.name, ans
            break
    return {
        "seconds": time.monotonic() - t0,
        "winner": winner,
        "answer": answer,
        "fetched": fetched,
        "total": len(sources),
    }
