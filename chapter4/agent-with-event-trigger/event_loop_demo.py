"""
event_loop_demo.py —— End-to-end demonstration of an event-driven Agent (single process, can run offline)

The section "Event-Driven Asynchronous Agent" in this chapter points out that a true "proactive service" requires not only that the Agent can periodically check the world, but also that the world can actively notify the Agent. This script runs this concept with minimal code:

  1. Register several "event triggers" (trigger sources), each running in a background thread, pushing a structured Event into a unified event queue at the moment the event actually occurs:
       - OneShotTimer —— corresponds to the "one-shot timer" of set_timer in the book
       - RecurringTimer —— corresponds to the "recurring timer" of set_timer in the book
       - FileWatchTrigger —— corresponds to file change triggers in platforms like n8n
  2. The EventLoop takes events one by one from the queue and wakes up the Agent to process them — this is the complete closed loop of "Agent registration, external triggering": declare what events you care about at registration time, and be asynchronously awakened when triggered.

Unlike server.py / client.py which require starting an HTTP server, this script plays both the "external world" and the "Agent" in a single process, making it suitable for intuitively demonstrating event-driven behavior.

Offline mode (--mock): Does not call the LLM, uses a "mock action" to print the processing after the Agent is awakened, allowing observation of the complete trigger→wake→process closed loop in an environment without an API Key.
Real mode (default): Connects to EventTriggeredAgent, where the LLM actually processes each event.

Usage examples:
    python event_loop_demo.py --mock                       # Offline demonstration of all triggers
    python event_loop_demo.py --mock --trigger timer       # Demonstrate only one-shot timer
    python event_loop_demo.py --mock --trigger recurring --interval 3 --duration 12
    python event_loop_demo.py --trigger file --watch-dir ./watched   # Real Agent processes file events
"""

import os
import sys
import time
import queue
import logging
import argparse
import threading
from datetime import datetime
from typing import Optional, Callable

from event_types import Event, EventType

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("event_loop")


# ============================================================================
# Event trigger (trigger source)
# ============================================================================

class TriggerSource(threading.Thread):
    """Event trigger base class: runs in a background thread and pushes events into a shared event queue.

    Registration is embodied by instantiating and calling start(); firing is embodied in run()
    calling self.emit(event) when conditions are met. This corresponds to the two moments in the book:
    "registration is when the Agent actively calls the tool, firing is when an external event asynchronously calls back."
    """

    def __init__(self, name: str, event_queue: "queue.Queue[Event]"):
        super().__init__(name=name, daemon=True)
        self.event_queue = event_queue
        self._stop = threading.Event()

    def emit(self, event: Event):
        """Trigger: push the event into the event queue and wake up the event loop."""
        logger.info(f"⚡ [{self.name}] Trigger event -> {event.event_type.value}: {event.content}")
        self.event_queue.put(event)

    def stop(self):
        self._stop.set()


class OneShotTimer(TriggerSource):
    """One-shot timer: triggers the timer_trigger event once after a delay of `delay` seconds.

    Corresponds to tasks with a clear point in time, such as "the user asks to call the DMV, it is currently Saturday, and the Agent sets 'call the DMV at 10:00 AM next Monday'" as described in the book.
    """

    def __init__(self, event_queue, delay: float, content: str, timer_id: str = "oneshot"):
        super().__init__(name=f"OneShotTimer({timer_id})", event_queue=event_queue)
        self.delay = delay
        self.content = content
        self.timer_id = timer_id

    def run(self):
        logger.info(f"⏱️  [{self.name}] Registered:{self.delay:.0f} trigger after seconds")
        if self._stop.wait(self.delay):
            return
        self.emit(Event(
            event_type=EventType.TIMER_TRIGGER,
            content=self.content,
            metadata={"timer_id": self.timer_id, "kind": "one_shot",
                      "scheduled_delay_seconds": self.delay},
        ))


class RecurringTimer(TriggerSource):
    """Cycle timer: triggers the timer_trigger event every interval seconds.

    Corresponds to "check server health every hour" and "send progress report every Friday" in the book, as well as
    OpenClaw Heartbeat-style periodic polling.
    """

    def __init__(self, event_queue, interval: float, content: str, timer_id: str = "recurring"):
        super().__init__(name=f"RecurringTimer({timer_id})", event_queue=event_queue)
        self.interval = interval
        self.content = content
        self.timer_id = timer_id

    def run(self):
        logger.info(f"🔁 [{self.name}] Registered: every {self.interval:.0f} triggered once per second")
        tick = 0
        while not self._stop.wait(self.interval):
            tick += 1
            self.emit(Event(
                event_type=EventType.TIMER_TRIGGER,
                content=f"{self.content}(No. {tick} times)",
                metadata={"timer_id": self.timer_id, "kind": "recurring",
                          "interval_seconds": self.interval, "tick": tick},
            ))


class FileWatchTrigger(TriggerSource):
    """File monitoring: Poll the directory and trigger the file_change event when new or modified files are detected.

    Corresponds to the "Trigger ecosystem of workflow platforms like n8n: Webhooks, timers, emails, database
    changes, file monitoring" in the book. Here, polling is used for implementation, without relying on third-party libraries, making it easy to run offline across platforms.
    """

    def __init__(self, event_queue, watch_dir: str, poll_interval: float = 1.0):
        super().__init__(name=f"FileWatch({watch_dir})", event_queue=event_queue)
        self.watch_dir = watch_dir
        self.poll_interval = poll_interval
        self._snapshot = {}

    def _scan(self):
        snapshot = {}
        try:
            for entry in os.scandir(self.watch_dir):
                if entry.is_file():
                    snapshot[entry.name] = entry.stat().st_mtime
        except FileNotFoundError:
            pass
        return snapshot

    def run(self):
        os.makedirs(self.watch_dir, exist_ok=True)
        self._snapshot = self._scan()
        logger.info(f"👀 [{self.name}] Registered: polling interval {self.poll_interval:.0f} seconds"
                    f"(currently has {len(self._snapshot)} files)")
        while not self._stop.wait(self.poll_interval):
            current = self._scan()
            for name, mtime in current.items():
                if name not in self._snapshot:
                    change = "created"
                elif mtime != self._snapshot[name]:
                    change = "modified"
                else:
                    continue
                self.emit(Event(
                    event_type=EventType.FILE_CHANGE,
                    content=f"File detected{'New' if change == 'created' else 'Modify'}, please review its content and provide brief handling suggestions.",
                    metadata={"path": os.path.join(self.watch_dir, name), "change": change},
                ))
            self._snapshot = current


# ============================================================================
# event loop
# ============================================================================

class EventLoop:
    """Unified event queue + single-threaded dispatch.

    All triggers push heterogeneous events into the same queue; the event loop
    dequeues them in arrival order, each event waking the Agent once for
    processing. This is the minimal implementation of the book's principle:
    "Model all inputs uniformly as an event stream, driving the Agent's
    thinking and actions through an event loop."
    """

    def __init__(self, dispatch: Callable[[Event], None]):
        self.event_queue: "queue.Queue[Event]" = queue.Queue()
        self.dispatch = dispatch
        self.triggers = []
        self.processed = 0

    def add_trigger(self, trigger: TriggerSource):
        self.triggers.append(trigger)

    def run(self, duration: float):
        """Start all triggers, stop after running for duration seconds."""
        deadline = time.monotonic() + duration
        for t in self.triggers:
            t.start()

        logger.info(f"🟢 Event loop started, will run {duration:.0f} seconds, waiting for event to wake up Agent...\n")
        while time.monotonic() < deadline:
            try:
                event = self.event_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self.processed += 1
            logger.info(f"\n{'='*80}\n📥 Event loop fetches the {self.processed} event"
                        f" -> Wake up Agent\n{'='*80}")
            try:
                self.dispatch(event)
            except Exception as e:  # noqa: BLE001 - do not want a single event exception to terminate the loop in the demo
                logger.error(f"❌ Error processing event: {e}")

        for t in self.triggers:
            t.stop()
        logger.info(f"\n🔴 Event loop ended, processed {self.processed} events.")


# ============================================================================
# Dispatch handler: simulated action or real Agent
# ============================================================================

def make_mock_dispatch() -> Callable[[Event], None]:
    """Offline simulation handler: does not call the LLM, prints the processing flow after the Agent is awakened."""

    def dispatch(event: Event):
        logger.info(f"🤖 Agent awakened, received message: {event.to_user_message()}")
        # Replace LLM + tool call with a deterministic "simulated action"
        if event.event_type == EventType.TIMER_TRIGGER:
            action = "Read scheduled task context -> perform routine check -> report result"
        elif event.event_type == EventType.FILE_CHANGE:
            path = event.metadata.get("path", "")
            preview = ""
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    preview = f.read(120).replace("\n", " ")
            except OSError:
                preview = "(Unable to read file content)"
            action = f"Read file {os.path.basename(path)} -> content preview: {preview!r} -> generate processing suggestion"
        else:
            action = "Parse event -> call relevant tools -> generate processing result"
        logger.info(f"🛠️  [Simulated action] {action}")
        logger.info(f"✅ Agent processing complete: responded to {event.event_type.value} events")

    return dispatch


def make_agent_dispatch(provider: str, model: Optional[str],
                        max_iterations: int) -> Callable[[Event], None]:
    """Real handler: connects to EventTriggeredAgent, each event is processed by the LLM."""
    from agent import EventTriggeredAgent, SystemHintConfig, resolve_provider_and_key

    # General fallback: when the key for the direct provider is missing, if OPENROUTER_API_KEY is set, automatically switch to openrouter.
    resolved_provider, api_key = resolve_provider_and_key(provider)
    if not api_key:
        print(f"❌ No API Key detected for provider '{provider}' (nor OPENROUTER_API_KEY fallback configured).")
        print(f"   Please set the environment variable first, or switch to offline demo: python event_loop_demo.py --mock")
        sys.exit(1)
    if resolved_provider != provider:
        print(f"ℹ️  provider '{provider}' has no available key, automatically switched to OpenRouter fallback (openrouter).")
        provider = resolved_provider
        # Keep explicit models already in provider/model form; otherwise let openrouter use its default model.
        model = model if (model and "/" in model) else None

    config = SystemHintConfig(
        enable_timestamps=True,
        enable_tool_counter=True,
        enable_todo_list=True,
        enable_detailed_errors=True,
        enable_system_state=True,
        save_trajectory=True,
        trajectory_file="event_loop_trajectory.json",
        temperature=0.7,
        max_tokens=4096,
        use_mcp_servers=False,  # This demo only uses built-in tools to avoid extra MCP dependencies
    )
    agent = EventTriggeredAgent(api_key=api_key, provider=provider,
                               model=model, config=config, verbose=True)
    logger.info(f"✅ Real Agent initialized (provider={provider}, model={agent.model}）")

    def dispatch(event: Event):
        result = agent.handle_event(event, max_iterations=max_iterations)
        logger.info(f"✅ Agent processing complete: success={result['success']}, "
                    f"iterations={result['iterations']}, "
                    f"tool_calls={len(result['tool_calls'])}")

    return dispatch


# ============================================================================
# CLI
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Event-driven Agent end-to-end demo: register triggers, asynchronously wake the Agent by external events.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python event_loop_demo.py --mock
      Offline demo of all triggers (one-shot timer + recurring timer + file watcher), no API Key required
  python event_loop_demo.py --mock --trigger timer
      Demo only one-shot timer
  python event_loop_demo.py --mock --trigger recurring --interval 3 --duration 12
      Trigger recurring timer every 3 seconds, run for 12 seconds total
  python event_loop_demo.py --mock --trigger file --watch-dir ./watched
      Watch the ./watched directory, writing a file there triggers an event
  python event_loop_demo.py --trigger timer --provider kimi
      Use a real LLM to process one-shot timer event (requires setting the corresponding API Key)
""",
    )
    parser.add_argument(
        "--trigger", choices=["timer", "recurring", "file", "all"], default="all",
        help="Trigger types to demo: timer=one-shot timer, recurring=recurring timer,"
             "file=file watch, all=all (default: all)",
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Offline mode: does not call the LLM, uses simulated actions to demonstrate the trigger→wake→process loop (no API Key required)",
    )
    parser.add_argument(
        "--duration", type=float, default=12.0,
        help="Total event loop runtime in seconds, after which all triggers are stopped (default: 12)",
    )
    parser.add_argument(
        "--delay", type=float, default=3.0,
        help="Delay trigger time for one-shot timer in seconds (default: 3)",
    )
    parser.add_argument(
        "--interval", type=float, default=4.0,
        help="Trigger interval for periodic timer in seconds (default: 4)",
    )
    parser.add_argument(
        "--watch-dir", default="watched_dir",
        help="Directory monitored by the file watch trigger; created automatically if it does not exist (default: watched_dir)",
    )
    parser.add_argument(
        "--provider", default=os.getenv("LLM_PROVIDER", "kimi"),
        choices=["siliconflow", "doubao", "kimi", "moonshot", "openrouter"],
        help="LLM provider used in real mode (default: environment variable LLM_PROVIDER or kimi)",
    )
    parser.add_argument(
        "--model", default=os.getenv("LLM_MODEL"),
        help="Model name override in real mode (default: use provider's default model)",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=10,
        help="Maximum number of tool call rounds per event in real mode (default: 10)",
    )
    return parser


def main():
    args = build_parser().parse_args()

    print("\n" + "=" * 80)
    print("🚀 Event-Driven Agent Demo")
    print("=" * 80)
    print(f"Trigger: {args.trigger} | Mode: {'Offline Simulation' if args.mock else 'Real Agent'} | "
          f"Duration: {args.duration:.0f}s")
    print("=" * 80 + "\n")
    sys.stdout.flush()

    if args.mock:
        dispatch = make_mock_dispatch()
    else:
        dispatch = make_agent_dispatch(args.provider, args.model, args.max_iterations)

    loop = EventLoop(dispatch)

    if args.trigger in ("timer", "all"):
        loop.add_trigger(OneShotTimer(
            loop.event_queue, delay=args.delay, timer_id="daily_backup_check",
            content="One-shot timer expired: please check if the daily backup has been completed.",
        ))
    if args.trigger in ("recurring", "all"):
        loop.add_trigger(RecurringTimer(
            loop.event_queue, interval=args.interval, timer_id="health_check",
            content="Periodic timer expired: please check server health.",
        ))
    if args.trigger in ("file", "all"):
        loop.add_trigger(FileWatchTrigger(loop.event_queue, watch_dir=args.watch_dir))
        print(f"💡 Hint: Write or modify a file in directory {args.watch_dir}/ to trigger a file_change event.")
        print(f"   For example, in another terminal run: echo hello > {args.watch_dir}/note.txt\n")
    sys.stdout.flush()

    if not loop.triggers:
        print("❌ No runnable triggers.")
        sys.exit(1)

    try:
        loop.run(duration=args.duration)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupt signal received, stopping...")
        for t in loop.triggers:
            t.stop()

    print("\n" + "=" * 80)
    print(f"📊 Demo ended: processed {loop.processed} events.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
