"""
In-process Async Message Bus
============================

Mimics the semantics of Redis Pub/Sub but runs entirely within a single-process asyncio event loop,
without needing to deploy a real Redis. It serves as the communication backbone for "central coordination" in Experiment 10-6:

- Each message is wrapped in an ``Envelope`` with sender_id / target / type / payload;
- Agents get a subscription handle via ``subscribe()`` and receive messages by type;
- Agents send messages to a specific target or broadcast to everyone via ``publish()``;
- The bus itself does no business logic, only "reliably delivers envelopes to subscribers."

Design highlights:
- Uses ``asyncio.Queue`` as each subscriber's inbox, naturally thread/coroutine-safe;
- When ``target`` is ``BROADCAST``, delivers to all subscribers of that type (except the sender);
- Prints event logs with timestamps, making the publish/subscribe message flow visible in demos.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#  Broadcast target constant: send to all subscribers
BROADCAST = "*"

#  Global monotonically increasing message sequence number for tracking order in logs
_seq_counter = itertools.count(1)

#  Demo start time, used to print relative timestamps (more readable)
_START_TIME = time.monotonic()


def _now() -> float:
    """Returns seconds since demo start (relative timestamp)."""
    return time.monotonic() - _START_TIME


@dataclass
class Envelope:
    """Message envelope: the smallest unit flowing in the bus."""

    sender_id: str            #  Sender ID
    target: str               #  Target Agent ID, or BROADCAST for broadcast
    type: str                 #  Message type: task_assigned / status_update / result / terminate / ack ...
    payload: Dict[str, Any] = field(default_factory=dict)  #  JSON payload
    seq: int = field(default_factory=lambda: next(_seq_counter))  #  Global sequence number
    ts: float = field(default_factory=_now)                       #  Relative timestamp

    def short(self) -> str:
        """Compact single-line representation for logging."""
        tgt = "ALL" if self.target == BROADCAST else self.target
        body = json.dumps(self.payload, ensure_ascii=False)
        if len(body) > 80:
            body = body[:77] + "..."
        return (
            f"[t={self.ts:6.2f}s #{self.seq:<3}] "
            f"{self.sender_id:>11} -> {tgt:<11} | {self.type:<14} | {body}"
        )


class Subscription:
    """Subscription handle: internally an inbox queue + a set of interested message types."""

    def __init__(self, owner_id: str, types: Optional[List[str]]):
        self.owner_id = owner_id
        # types=None means subscribe to all types
        self.types = set(types) if types else None
        self.inbox: "asyncio.Queue[Envelope]" = asyncio.Queue()

    def accepts(self, env: Envelope) -> bool:
        return self.types is None or env.type in self.types

    async def get(self) -> Envelope:
        return await self.inbox.get()

    async def get_nowait_or_wait(self, timeout: float) -> Optional[Envelope]:
        """Fetch a message with timeout; returns None on timeout (useful for child agents polling for termination signal in a loop)."""
        try:
            return await asyncio.wait_for(self.inbox.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class MessageBus:
    """Async message bus: register subscribers, deliver envelopes, print message flow logs."""

    def __init__(self, verbose: bool = True):
        # owner_id -> list of subscriptions for that owner
        self._subs: Dict[str, List[Subscription]] = {}
        self.verbose = verbose
        #  Record all envelopes that have flowed through the bus for post-hoc statistics/assertions
        self.history: List[Envelope] = []

    def subscribe(self, owner_id: str, types: Optional[List[str]] = None) -> Subscription:
        """Register a subscriber and return a subscription handle. types=None means receive all types."""
        sub = Subscription(owner_id, types)
        self._subs.setdefault(owner_id, []).append(sub)
        return sub

    async def publish(self, env: Envelope) -> None:
        """Deliver an envelope to the bus: broadcast or point-to-point."""
        self.history.append(env)
        if self.verbose:
            print("  BUS " + env.short())

        delivered = 0
        for owner_id, sub_list in self._subs.items():
            #  Point-to-point: deliver only to the specified target
            if env.target != BROADCAST and owner_id != env.target:
                continue
            #  Do not deliver back to the sender during broadcast
            if env.target == BROADCAST and owner_id == env.sender_id:
                continue
            for sub in sub_list:
                if sub.accepts(env):
                    await sub.inbox.put(env)
                    delivered += 1

        #  Yield the event loop to ensure messages are picked up by the peer as soon as possible (closer to real push timing)
        await asyncio.sleep(0)

    # —— Convenience construction and publish ——
    async def send(
        self,
        sender_id: str,
        target: str,
        type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Envelope:
        env = Envelope(sender_id=sender_id, target=target, type=type, payload=payload or {})
        await self.publish(env)
        return env
