# Experiment 10-6 · Agent Collecting Information from Multiple Websites Simultaneously (★★)

A companion experiment for *Deep Understanding of AI Agents*. Demonstrates **parallel search with multiple homogeneous agents + central coordination**:
The main coordinator simultaneously launches N child agents, each accessing one "website/source" to find an answer;
once any child agent hits the target, the rest gracefully stop.

The prototype in the book is "10 parallel Computer Use Agents accessing different websites simultaneously to find information." For ease of
automated verification, this experiment **does not launch a real browser** but instead uses a set of **controllable simulated information sources**;
the focus is entirely on the coordination mechanism — **message bus, parallel dispatch, real-time monitoring, cascading termination, and race condition handling are all real implementations**.

## Directory Structure

| File | Role |
| --- | --- |
| `message_bus.py` | In-process asynchronous message bus (Redis Pub/Sub style), with `Envelope` envelope and subscription mechanism |
| `sources.py` | Simulated 10 "websites/sources", each with different delays; controllable keyword hit determination; `build_sources(n)` supports arbitrary parallelism |
| `llm.py` | Optional LLM judgment layer (default offline keyword judgment, uses real LLM if key is configured) |
| `agents.py` | Main coordinator `Coordinator` and child agent `WorkerAgent` (core coordination logic); `run_sequential` serial baseline |
| `demo.py` | Single-command demo entry point, with argparse CLI and assertion-based self-check at the end |

## Architecture and Mechanism

```
                         ┌────────────────────────────┐
                         │   Coordinator (Main Coordinator)  │
                         │  · Parallel dispatch task_assigned  │
                         │  · Maintain task state table (state machine)  │
                         │  · First hit → lock settlement (idempotent)  │
                         │  · Broadcast one round of terminate  │
                         └───────────┬────────────────┘
                                     │
                    ┌────────────────┴─────── MessageBus (Async Message Bus) ───────┐
                    │  Envelope{ sender_id, target, type, payload, seq, ts }    │
                    │  type: task_assigned/status_update/result/terminate/ack   │
                    └──┬─────────┬─────────┬─────────┬──────────────┬──────────┘
                       │         │         │         │              │
                    ┌──▼──┐  ┌──▼──┐  ┌──▼──┐  ┌──▼──┐   ...   ┌──▼──┐
                    │W-00 │  │W-01 │  │W-02 │  │W-03 │         │W-09 │  Child Agents
                    │Site A│  │Site B│  │Site C│  │Site D│         │Site J│  (Homogeneous · Parallel)
                    └─────┘  └─────┘  └─────┘  └─────┘         └─────┘
```

Corresponds to the five mechanisms emphasized in the book:

1. **Message Bus**: All communication is **enveloped messages** published to the bus, subscribed by `type`.
   Each `BUS ...` line in the log represents one publish/delivery (in-process implementation of Redis Pub/Sub semantics).
2. **Parallel Dispatch**: The `Coordinator` simultaneously sends `task_assigned` to 10 child agents and executes them concurrently via `asyncio.create_task`.
3. **Real-time Monitoring (push paradigm)**: Child agents proactively report progress via `status_update` during execution;
   the main agent maintains a **task state table** and refreshes the printout in real-time upon state machine transitions.
   State machine: `Submitted → Executing → (Input Required) → Completed / Failed / Terminated`.
4. **Cascading Termination**: Once a child agent hits the target, the main agent **broadcasts `terminate`**; other child agents,
   upon detecting the signal at their **safety checkpoints** in the loop, reply with `ack` and exit gracefully (state set to "Terminated").
5. **Race Condition Handling**: Multiple child agents may hit the target almost simultaneously; the main agent uses `asyncio.Lock` +
   an idempotent flag `_settled` to ensure **only one settlement and only one round of termination broadcast**; late hits are recorded and ignored.

> To make "race conditions" and "cascading termination" reproducible, each source is assigned a different simulated delay, where the two correct sources,
> `geo-journal` and `forum-qa`, are set to **the same delay**, thus reliably hitting the target at the same time and triggering a race condition.

## Running

```bash
cd chapter10/parallel-web-research
pip install -r requirements.txt   # Can be skipped for offline demo; pure standard library is sufficient
python demo.py
```

Default uses **offline keyword judgment** (no internet required, results reproducible). To have child agents use a real LLM for judgment:

```bash
cp env.example .env
# Fill in OPENAI_API_KEY in .env (also supports Moonshot / Volcano Ark ARK's OpenAI-compatible gateway)
python demo.py
# Or without modifying .env, use command-line switches directly (still requires key configuration to take effect):
python demo.py --use-llm --model gpt-5.6-luna
```

Available keys: `OPENAI_API_KEY` (default model `gpt-5.6-luna`) / `MOONSHOT_API_KEY` / `ARK_API_KEY`
(fill into `OPENAI_API_KEY` and set `OPENAI_BASE_URL` and `OPENAI_MODEL` as needed).

**General fallback**: If `OPENAI_API_KEY` is not set but `OPENROUTER_API_KEY` is, the real LLM judgment
automatically switches to OpenRouter and maps the model name to its namespace (`gpt-5.6-luna` → `openai/gpt-5.6-luna`).
This does not affect the coordination mechanism, only the "hit or miss" judgment.

### Command-Line Arguments

`python demo.py --help` shows the full help. All parameters **do not change the default behavior** — passing no arguments gives the original
"10 Agents + built-in question + offline reproducible + detailed BUS log" demo.

| Parameter | Role | Default |
| --- | --- | --- |
| `-q, --query QUESTION` | Research question (offline keyword judgment is tuned for built-in sources; custom questions generally require `--use-llm`) | Built-in question |
| `-n, --agents N` | Number of parallel child agents (when N≥2, always includes two sources with answers to reliably demonstrate race conditions/cascading termination) | `10` |
| `--model MODEL` | LLM model name (equivalent to setting `OPENAI_MODEL`, only effective with `--use-llm` and configured key) | Environment variable |
| `-o, --output PATH` | Write the conclusion (including parallel/serial wall-clock time, winner, race condition statistics) to a JSON file | Not written |
| `--compare` | After parallel run, **actually measure** the serial baseline and print wall-clock time comparison | Off |
| `--use-llm` | Force real LLM judgment (still requires `OPENAI_API_KEY` or `OPENROUTER_API_KEY`, otherwise automatically falls back to offline judgment) | Off |
| `--quiet` | Reduce per-message BUS logs (state table/conclusion/self-check unaffected) | Off |

```bash
python demo.py --agents 6 --compare       # 6 parallel agents, compare with serial wall-clock time
python demo.py --output result.json        # Write conclusion to JSON file
```

### Parallel vs Serial Wall-Clock Benefit (`--compare`)

Corresponds to the experiment requirement in the book "Record and compare parallel/serial time differences." `--compare` runs the **serial baseline**
(fetch one by one via `await source.fetch()` + judgment, stop on hit) with the **exact same source set** after the parallel demo; the time is **actually measured**, not estimated. Example output (default 10 sources, offline judgment):

```
5) Parallel execution wall-clock time: 1.57s (including convergence quiet period)
------------------------------------------------------------------------------
Parallel vs Serial Wall-Clock Comparison (--compare, serial baseline is actual measurement)
------------------------------------------------------------------------------
   Serial: Fetched 3/10 sources sequentially before hit, wall-clock time 2.60s, winner=geo-journal
   Parallel: Wall-clock time 1.57s, winner=worker-02
   Speedup ≈ 1.66×, saving approximately 1.03s (parallelism lets the fastest source end the global search immediately).
```

Serial must sequentially fetch baike-wiki→news-portal before reaching the fastest hit, geo-journal (cumulative 2.6s); parallel starts all sources simultaneously, and the fastest source triggers cascading termination upon hit, immediately ending the global search. The parallel wall-clock time includes the convergence overhead of cascading termination, so it is not the ideal "first source latency," but it is still significantly faster than serial — this is the value of parallelism + cascading termination.

## What the Demo Illustrates (Key Output Snippets from Actual Run)

**(a) Message bus publish/subscribe is working** — each enveloped message is printed:

```
BUS [t=  0.00s #3  ] coordinator -> worker-02   | task_assigned  | {"question": "...", "source": "geo-journal"}
BUS [t=  0.00s #13 ]   worker-02 -> coordinator | status_update  | {"state": "Executing", ...}
```

**(b) N child agents execute in parallel + main agent refreshes state table in real-time**:

```
── Task State Table (worker-02 -> Executing) ──
   worker-00  source=baike-wiki   state=Executing   | Starting source fetch
   worker-02  source=geo-journal  state=Executing   | Starting source fetch
   ...
```

**(c) Cascading termination** — after hit, broadcast terminate, other child agents ack and exit gracefully:

```
BUS [t=0.60s #41 ] coordinator -> ALL         | terminate | {"reason":"answer_found","winner":"worker-02"}
BUS [t=0.67s #43 ]   worker-09 -> coordinator | ack       | {"acked":"terminate","source":"map-service"}
[ack] worker-09 confirmed termination (1 acked)
...All 8 non-hitting Workers final state=Terminated
```

**(d) Race condition: even if hits occur almost simultaneously, only one settlement and one round of termination broadcast**:

```
BUS [t=0.60s #37 ]   worker-02 -> coordinator | result | {"found":true, "answer":"...Mount Everest...8848 meters..."}
BUS [t=0.60s #38 ]   worker-04 -> coordinator | result | {"found":true, "answer":"...Mount Everest...8848.86 meters..."}
[Settlement] First hit from worker-02 — lock settlement, broadcast one round of terminate.
[Race] worker-04 also hit, but already settled by worker-02 — ignoring this hit, no repeated termination broadcast.
```

`demo.py` has an **assertion-based self-check** at the end: `terminate broadcast rounds == 1`, `only one settlement == True`,
`winner is not empty`. Passing proves the mechanism is correct:

```
4) Terminate broadcast rounds: 1 (should be 1, proving only one round broadcast)
   Late/concurrent duplicate hits ignored: ['worker-04']
[Self-check passed] Single settlement + single round termination broadcast + cascading ack all meet expectations.
```

## Limitations and NotesThis experiment focuses on the **coordination mechanism** (message bus / parallel dispatch / cascading termination / race-condition handling), all of which are real implementations. However, to enable offline execution and automated verification, the following three aspects have been simplified, which are known limitations:

- **Limitation · Simulated source is not a real browser**: No real browser is launched; the source is controllable simulated data plus delays. To connect to a real Computer Use, simply replace the "fetch one step + judge" logic inside `WorkerAgent.run()` with real browser operations—the coordination layer requires no changes.
- **Limitation · Race conditions rely on identical delays for stable reproduction**: The two correct sources, `geo-journal` and `forum-qa`, are artificially set to the same delay to reliably trigger "simultaneous hits." In real environments, race conditions are sporadic, but the locking + idempotent settlement logic works equally well for sporadic races and does not depend on this artificial setting.
- **Limitation · In-process bus is not real Redis**: `MessageBus` uses an **in-process async queue** to simulate Redis Pub/Sub, eliminating the need for an actual Redis installation. The semantics (envelope, subscription by type, point-to-point/broadcast delivery) are consistent, but it lacks cross-process/cross-machine capability, making it convenient for single-machine reproduction and automated verification.
- Sub-agents **periodically check the termination signal** in their loop (before and after each fetch step), so termination is a "safe-point response" rather than a forced kill, ensuring resources are properly cleaned up.
