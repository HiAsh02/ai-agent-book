# Experiment 4-5: Asynchronous Agent with Parallel Execution and Interrupt Capability (★★★)

This directory contains the runnable code for Experiment 4-5 of *Deep Understanding of AI Agents*, implementing the core of the event-driven asynchronous Agent framework (Flux) described in the design document [`agent_framework_design.md`](./agent_framework_design.md).

Building on the simple event queue from 4-4, this experiment delves into the deep end of asynchronous Agents, focusing on four key areas:
**Asynchronous tool execution, event queue and batch processing, interrupt mechanism, cancellation and status querying of parallel tools**.
The Agent needs to manage multiple concurrent tasks simultaneously, handle interruptions and resumptions, and make dynamic decisions based on real-time state.

This directory provides two usage paths:

- **Offline Demo (Recommended to run first, zero dependencies, no API key required)**: Isolates the three core asynchronous capabilities and demonstrates them in a measurable way—**wall-clock time comparison of parallel vs. serial execution, recovery after interruption/cancellation, and state checkpoint persistence and restoration**.
  This path does not require network access, does not call an LLM, and does not even require installing `openai`. Simply run `python demo.py`.
- **LLM Scenario (Reproduces the four validation scenarios from the book)**: The Agent's decisions are made by a real LLM (default OpenAI `gpt-5.6-luna`, function calling), requiring an API key configuration.

Both paths share the same asynchronous runtime; long-running tasks are implemented using **simulated asynchronous "terminal commands"** (with progress output) and never execute real dangerous commands.

---

## 1. Architecture

Corresponding to the event processing loop in Section 5 of the design document, all implemented based on `asyncio` single-threaded:

```
                       ┌──────────────┐
   User Message / Interrupt ──▶ │    inbox     │  All incoming raw events
   Async Task Completion Notification ──▶ │  (asyncio.Q) │
                       └──────┬───────┘
                              │
                   ┌──────────▼───────────┐   Determine urgency classify_urgency()
                   │     _dispatcher      │──▶ Interrupt / Immediate / Queue
                   └──────────┬───────────┘
             ┌────────────────┼───────────────────┐
   INTERRUPT │        IMMEDIATE│           DEFERRED│
   Cancel current turn + async tools     Directly enter work         Enter pending buffer,
   and leave trace                                      batch append when async result arrives
                   ┌──────────▼───────────┐
                   │        work          │  Event batch to be processed
                   └──────────┬───────────┘
                   ┌──────────▼───────────┐
                   │       _worker        │  Process batch: append to trace -> run_llm_turn()
                   │   turn_task can be cancelled│  (cancel this subtask on interrupt)
                   └──────────────────────┘

  TaskManager: Manages simulated async terminal tasks (start / query / cancel / cancel_all)
               Task naturally completes -> injects into inbox as a "new event" (async.result)
```

Code Files:

| File | Purpose |
|------|---------|
| `events.py`  | Event model `Event` (with checkpoint serialization `to_dict`/`from_dict`), event types, **urgency determination** `classify_urgency()` |
| `tasks.py`   | Simulated asynchronous "terminal commands" and `TaskManager` (progress advancement, cancel/query by ID, state `snapshot`/`restore`) |
| `runtime.py` | `AgentRuntime`: Event loop, two processing mechanisms, LLM function calling, tool execution, checkpoint `save_checkpoint`/`load_checkpoint` |
| `async_demos.py` | Three **offline demos** (no API key required): Parallel wall-clock comparison, interrupt/resume, state checkpoint |
| `demo.py`    | Unified command-line entry point (argparse subcommands): Offline demos + four LLM validation scenarios |

### Two Event Processing Mechanisms (Design Document 5.1)

- **Cancellation-Based Processing**: When an urgent event (user "cancel/stop") arrives, immediately cancel the ongoing LLM turn and all background async tools, writing the interrupt event and cancellation receipt into the trace.
- **Queued Processing**: Non-urgent events (supplementary instructions) first enter the `pending` buffer without interrupting ongoing work; when an async tool completes and generates an `async.result` event, all events in `pending` are batch-appended to the trace, triggering another LLM call.

Urgency Determination Rules (simple and explainable):

1. Contains interrupt keywords (cancel/stop…) → `INTERRUPT` (cancellation-based processing)
2. Is a question (contains a question mark or interrogative word, e.g., "What time is it?") → `IMMEDIATE` (respond immediately, but **do not** interrupt background tasks)
3. Other supplementary instructions (e.g., "Reply in Japanese") → `DEFERRED` (queue, batch process)

### Asynchronous Tools

`run_terminal_command` is an **asynchronous** tool: returns a `task_id` placeholder immediately upon invocation (non-blocking), the command advances progress at a fixed rate in the background; when it actually completes, its result is injected into the conversation as a **new event** (`async.result`).
Additionally, `query_task` / `cancel_task` query progress and cancel by ID, and `get_current_time` is used for immediate questions.

**Time Scale Acceleration**: For reproducibility, 1 "simulated second" maps to `0.4` real seconds by default (`FLUX_TICK_REAL` is adjustable).
The speed differences of **3% / 2% / 1% per (simulated) second** and the **whether past 50%** determination logic are fully preserved.

---

## 2. Running

The command-line entry point is `demo.py`, organized using `argparse` subcommands. Run `python demo.py --help` to see all usage.

### Offline Demo (No API Key Required, Ready to Use)

```bash
cd chapter4/async-agent

python demo.py              # Default: runs the three offline demos below sequentially
python demo.py offline      # Same as above: explicitly runs the three offline demos sequentially
python demo.py parallel     # Capability 1: Wall-clock time comparison of parallel vs. serial tool calls (prints speedup ratio)
python demo.py interrupt    # Capability 2: Long-running task interrupted/cancelled, then system recovers
python demo.py state        # Capability 3: State checkpoint persistence + cross-session restoration and verification
```

These three demos do not require network access, do not call an LLM, and do not even require installing `openai`—they use pure `asyncio` to directly measure parallel speedup, state freezing after interruption, and checkpoint persistence and restoration.

### LLM Validation Scenarios (Reproduces the Four Scenarios from the Book, Requires API Key)

```bash
pip install -r requirements.txt
cp env.example .env         # Fill in OPENAI_API_KEY

python demo.py scenarios                # Runs all four scenarios sequentially
python demo.py scenarios --scenario 1   # Run only scenario 1 (async execution + immediate question)
python demo.py scenarios --scenario 3   # Run only scenario 3 (interrupt mechanism)
```

Default uses OpenAI `gpt-5.6-luna`. You can also switch service providers (OpenAI-compatible API):

```bash
# Moonshot (default model is the current reasoning model kimi-k3)
LLM_PROVIDER=moonshot python demo.py scenarios --scenario 1
# Volcano Engine ARK (LLM_MODEL fill in the reasoning access point ID)
LLM_PROVIDER=ark LLM_MODEL=ep-xxxx python demo.py scenarios --scenario 1
```

> **OpenRouter General Fallback**: When `OPENAI_API_KEY` is not configured (and moonshot/ark provider is not used), as long as `OPENROUTER_API_KEY` is set, `demo.py` will automatically switch to OpenRouter and map the model name to the `provider/model` format (`gpt-*` → `openai/…`, `claude-*` → `anthropic/claude-opus-4.8`, names containing `/` are passed through as-is). You can also explicitly use `LLM_PROVIDER=openrouter`. For example:
> `OPENROUTER_API_KEY=sk-or-xxx LLM_MODEL=openai/gpt-5.6-luna python demo.py scenarios --scenario 1`

> Moonshot defaults to the **reasoning model `kimi-k3`** (the older `kimi-k2-*-preview` and `moonshot-v1-*` models are deprecated/discontinued).
> Reasoning models require `temperature=1` and `max_tokens>=2048`; `demo.py` will automatically apply these sampling parameters based on the model, no manual configuration needed.

> Compatibility with old usage: `python demo.py --scenario N` will automatically be equivalent to `scenarios --scenario N`.

Different sources in the logs are distinguished by color: `USER` (user), `AGENT` (Agent reply), `TOOL` (tool call), `TASK` (background async task), `TRAJ` (trace recording), `STATE` (state checkpoint), `SYSTEM` (framework event).

---

## 3. Three Capabilities of the Offline Demo (Real Measurement Output)

The following three sections are excerpts from **actual runs** (no API key required), demonstrating what asynchrony actually brings.

### Capability 1: Parallel vs. Serial Tool Calls (`python demo.py parallel`)

Four independent read-only sensing tools (read file / search / query database / vector retrieval), comparing wall-clock time of serial `await` vs. parallel `asyncio.gather`:

```
  ── Result Comparison ─────────────────────────────────────────────
  Serial Total Time (Σ each tool)                  4.51s
  Parallel Total Time (gather)                 1.50s
  Parallel Theoretical Lower Bound (slowest single)                  1.50s
  Speedup = Serial / Parallel                 3.00x
  ─────────────────────────────────────────────────────────
```

Wall-clock time drops from "sum of all tools" to "maximum of the single slowest"—this is the quantitative manifestation of the book's statement that "read-only sensing tools are naturally suited for parallelism."

### Capability 2: Interrupt / Cancel / Resume (`python demo.py interrupt`)

While three parallel background tasks are running, the user first asks an immediate question (without blocking the tasks), then issues a "cancel" interrupt:

```
[  1.00s] USER   | (Immediate Question) What time is it?
[  1.00s] AGENT  | It is currently 00:14:26. The three background tasks are still progressing in parallel, not blocked by this question.
[  2.00s] USER   | (Interrupt) Cancel
[  2.00s] TASK   | T1 has been cancelled 🛑 (progress stopped at 39%)
[  2.00s] TASK   | T2 has been cancelled 🛑 (progress stopped at 26%)
[  2.00s] TASK   | T3 has been cancelled 🛑 (progress stopped at 13%)

  ── Task Status After Interrupt (Progress Frozen Midway) ───────────────────
  task_id Command                        Status              Progress
  T1      python analyze_fast.py    cancelled      39%
  T2      python analyze_mid.py     cancelled      26%
  T3      python analyze_slow.py    cancelled      13%
  ─────────────────────────────────────────────────────────
[  2.05s] SYSTEM | Interrupt processing complete, system returns to idle, ready to accept new tasks...
[  5.52s] TASK   | T4 completed ✅
```[  5.52s] AGENT  | Resumed from interruption, new task T4 completed normally: ...
```

Interruption only freezes the progress of the cancelled task; the runtime itself is unaffected and can immediately accept and complete a new task.

### Capability 3: State Checkpoint Persistence and Recovery (`python demo.py state`)

Session A generates a trajectory plus two running background tasks, saved to disk as `checkpoints/agent_state.json`;
Session B recovers from disk with a fresh runtime and verifies:

```
  ── Recovery Verification ─────────────────────────────────────────────
  Trajectory events     Before save 3  ->  After recovery 3  [Consistent ✓]
  Reconstructable LLM context messages 4 (system + trajectory replay)
  task_id  Command                              Progress before save  After recovery status   Progress
  T1      python analyze_fast.py           21%  suspended      21%
  T2      python analyze_slow.py            7%  suspended       7%
  ─────────────────────────────────────────────────────────────────────
```

The trajectory and task progress are fully persisted and restored across sessions; running tasks are marked as `suspended` upon recovery, retaining their last known progress,
allowing the upper layer to decide whether to "restart" or "resume from progress" — this is the state management of asynchronous tasks.

---

## IV. Four LLM Verification Scenarios

### Scenario 1: Asynchronous Tool Execution
The Agent executes a long terminal command, during which the user interjects with a question: "What time is it now?"
Because the long command is asynchronous and non-blocking, the Agent immediately responds with the time using `get_current_time`,
and presents the analysis conclusion after the background task completes.

### Scenario 2: Event Queue and Batch Processing
While the Agent is executing a long task, the user sends consecutive messages: "Remember to reply in Japanese" and "Format it as a web page."
These are non-urgent instructions that first enter a queue buffer; when the task completes, the framework **appends them all at once** to the trajectory,
and the Agent then synthesizes all instructions to output the result in Japanese HTML.

### Scenario 3: Interruption Mechanism
The Agent is executing a long task, and the user sends "Cancel." The framework immediately cancels the current execution flow and the background asynchronous tool,
recording the interruption event (`user.interrupt`) and the cancellation receipt (`system.note`, including the cancelled task_id) in the trajectory.

### Scenario 4: Parallel Tool Cancellation and Status Query
The user requests: "Run these three scripts simultaneously. Whichever finishes first, check the progress of the others. Cancel any that haven't passed 50%."
The three scripts progress at 3% / 2% / 1% per second respectively. The Agent starts all three asynchronous tasks simultaneously;
after the fastest one completes, the Agent queries the other two (approximately 66% and 33%), cancels the one below 50%,
and after the remaining one finishes, integrates the results into a report.

---

## V. Real Output from LLM Scenarios (Key Excerpts)

> The following are excerpts from actual calls to `gpt-5.6-luna` (OpenAI-compatible interface) (timestamps are real seconds; an API key is required to reproduce).

**Scenario 1 (Asynchronous Execution + Instant Question)**
```
[ 3.97s] AGENT | Task has been started in the background (task_id: T1). Once completed, I will provide conclusions based on the log analysis.
[ 4.96s] TASK  | T1 `python analyze_logs.py` progress 22%      ← Task still running in background
[ 5.19s] TOOL  | get_current_time -> 2026-07-18 13:43:30  ← Instant question answered first
[ 6.91s] AGENT | The current time is 2026-07-18 13:43:30.
[12.19s] TRAJ  | + async.result  Async completion T1               ← Real result injected as a new event
[16.67s] AGENT | Log analysis completed. Conclusion: Scanned 12,840 records…  ← Analysis presented afterwards
```

**Scenario 2 (Batch Processing)**
```
[ 1.50s] SYSTEM | Event entered queue buffer (1 pending)
[ 1.90s] SYSTEM | Event entered queue buffer (2 pending)
[12.05s] TASK   | T1 completed ✅
[12.05s] SYSTEM | Async result arrived, batch processing 2 pending non-urgent events
[12.06s] TRAJ   | + async.result   Async completion T1
[12.06s] TRAJ   | + user.input     Remember to reply in Japanese at the end
[12.06s] TRAJ   | + user.input     Format the result as a web page (HTML)
...
[22.38s] AGENT  | <!DOCTYPE html>…<h2>Analysis Conclusion</h2>… (Batch instructions satisfied at once: Japanese + HTML)
```

**Scenario 3 (Interruption)**
```
[ 2.40s] TASK   | Started async task T1: `python analyze_logs.py` (speed 4%/simulated second)
[ 4.00s] USER   | (interrupt) Cancel
[ 4.00s] TASK   | T1 has been cancelled 🛑 (progress stopped at 14%)
[ 4.00s] TRAJ   | + user.interrupt  User interruption: Cancel
[ 4.00s] TRAJ   | + system.note     Interruption receipt, cancelled task ['T1']
[ 5.04s] AGENT  | Background task T1 has been stopped.
```

**Scenario 4 (Parallel + Status Query + Cancellation at 50% Threshold + Integrated Report)**
```
[ 2.82s] TASK | Started async task T1: `python analyze_fast.py` (speed 3%/simulated second)
[ 2.82s] TASK | Started async task T2: `python analyze_mid.py`  (speed 2%/simulated second)
[ 2.82s] TASK | Started async task T3: `python analyze_slow.py` (speed 1%/simulated second)
[16.47s] TASK | T1 completed ✅                               ← Fastest script finishes first
[19.84s] TOOL | query_task(T2) -> running 84%           ← Query progress of the other two
[19.84s] TOOL | query_task(T3) -> running 42%
[21.93s] TOOL | cancel_task(T3) -> Cancelled (progress 47%)     ← Below 50%, cancelled
[22.89s] TASK | T2 completed ✅
[26.50s] AGENT | ## Summary Analysis Report … analyze_slow.py: Cancelled (did not exceed 50%)…
```

---

## VI. Notes

- **Offline demos (`parallel`/`interrupt`/`state`) require no API key and no installation of `openai`** — they run out of the box.
- **Only the `scenarios` subcommand requires a network connection and a valid API key** (`OPENAI_API_KEY`, or switch to
  `MOONSHOT_API_KEY` / `ARK_API_KEY`).
- LLM decisions are made by a real model, so the exact wording of the output may vary slightly each time; the **behavioral logic** of the four scenarios is stable and reproducible.
  If you encounter occasional high latency from OpenAI, simply re-run.
- The timeline has been accelerated; increasing `FLUX_TICK_REAL` makes the demo closer to the real-world pace of "tens of seconds" described in the book,
  while decreasing it makes it faster (setting it too low may prevent the "cancel below 50%" logic in Scenario 4 from triggering in time).
- All "terminal commands" are simulated and will not actually execute any commands on your machine.
