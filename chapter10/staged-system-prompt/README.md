# Experiment 10-1: Staged System Prompt Based on Execution Phase

*Hands-on code accompanying "Understanding AI Agents"*

## Experiment Objective

The same Coding Agent loads **different system prompts + different tool sets** at different **execution phases** of a task,
thereby playing different roles and exhibiting different behavior patterns within the same conversation; while ensuring **conversation history and task state are continuously shared across phases**.

This experiment uses a single "Coding Agent" to chain together three phases:

| Phase | Role | System Prompt Emphasis | Supporting Tool Set | Tool Triggering Next Phase |
| --- | --- | --- | --- | --- |
| 1 Requirements Clarification | Requirements Analyst | Only ask clarifying questions, **do not write code** | `ask_clarifying_question` / `save_requirement` / `complete_requirements_analysis` | `complete_requirements_analysis` → Phase 2 |
| 2 Code Implementation | Software Engineer | Write high-quality Python based on confirmed requirements | `write_file` / `read_file` / `execute_code` / `submit_for_review` | `submit_for_review` → Phase 3 |
| 3 Code Review | Code Reviewer | Critically evaluate quality | `run_linter` / `run_tests` / `analyze_complexity` / `request_revision` / `approve_code` | `request_revision` → **fallback to Phase 2**; `approve_code` → Complete |

## Architecture

```
demo.py                Entry point: run all three phases with one command (task = "write a Python script to organize the Downloads folder")
agent.py               StagedAgent: phase state machine + tool call loop + cross-phase shared context + execution log
tools.py               Schemas and real implementations for three tool sets (virtual workspace / real code execution / linter / complexity analysis)
simulated_user.py      Simulated user: automatically answers the Agent's questions during requirements clarification (predefined answers), enabling unattended operation
config.py              Read API Key / base_url / model from environment variables
```

Key design points:

- **Shared Context**: `StagedAgent.history` is a message list that persists throughout. When switching phases, **only the system prompt is replaced, only the tools passed to the model are swapped**; the history (requirements, code, review comments) is fully retained. Each request is `[system(current phase)] + history`.
- **Phase transitions triggered by tool calls**: The main loop detects when "signal tools" like `complete_requirements_analysis` / `submit_for_review` / `request_revision` / `approve_code` are called, injects a cross-phase "handover" message, and switches the phase.
- **Fallback mechanism**: When issues are found during the review phase, `request_revision(issues)` is called, sending the issue list back to the implementation phase; a `max_revisions` safety valve prevents infinite loops from burning tokens.
- **Real execution**: `execute_code` / `run_tests` write code to a temporary directory and run it in a real subprocess; `run_linter` / `analyze_complexity` perform real static analysis based on `ast`, not fake returns.

## How to Run

```bash
pip install -r requirements.txt

# Configuration (choose one)
export OPENAI_API_KEY=sk-...           # Option A: direct export
cp env.example .env && vi .env         # Option B: write to .env

python demo.py

# View offline three-phase configuration (roles / system prompts / tool sets / transition signals), no API Key required
python demo.py --list-stages

# View optional parameters (does not affect default behavior)
python demo.py --help
```

Optional command-line arguments (default values are identical to running without arguments):

| Argument | Default Value | Description |
| --- | --- | --- |
| `--task` | Organize Downloads folder task | Override the user task given to the Agent |
| `--start-stage` | `requirements` | Which phase to start from. Choosing `implementation` will pre-populate confirmed requirements equivalent to the output of the requirements clarification phase, starting directly from the implementation phase. Useful for debugging the latter two phases independently (`review` depends on code from the implementation phase and cannot be a starting point) |
| `--interactive` | Off | During the requirements clarification phase, a real person answers the Agent's questions from standard input (default uses the simulated user from `simulated_user.py` for automatic answers, enabling unattended full flow) |
| `--max-revisions` | `3` | Maximum number of fallbacks allowed during the review phase; exceeding this forces the demo to end |
| `--model` | Environment variable `OPENAI_MODEL` | Override the model name used |
| `--list-stages` | — | Print the three-phase configuration offline and exit, without calling any API (suitable for understanding the mechanism without a Key) |

Configurable environment variables (see `env.example`): `OPENAI_API_KEY`, `OPENAI_BASE_URL` (default is official),
`OPENAI_MODEL` (default `gpt-5.6-luna`, currently the affordable flagship), `OPENAI_TEMPERATURE` (default 0.3).
Can also switch to Kimi / Doubao compatible with the OpenAI protocol.

**Universal fallback**: Prefers using `OPENAI_API_KEY` to connect directly to OpenAI; if this variable is not set but `OPENROUTER_API_KEY` is, it automatically switches to OpenRouter and maps the model name to its namespace
(`gpt-5.6-luna` → `openai/gpt-5.6-luna`). Note: The `gpt-5.6` series requires organization verification for direct OpenAI connection. Simply setting `OPENROUTER_API_KEY` (without `OPENAI_API_KEY`) forces the use of OpenRouter, which is more convenient.

## What the Demo Illustrates

A real run (`gpt-5.6-luna`) will show:

1. **Requirements Clarification Phase**: The Agent behaves by "continuously asking questions" — proactively inquiring about which file types to process, whether to recurse, whether to keep original names, move or copy, how to determine the target directory, and saves each requirement with `save_requirement`. It **does not write any code**.
2. **Code Implementation Phase**: After the prompt switch, the same Agent behaves by "writing code" — producing a Python script with `write_file`, self-testing with `execute_code`, and then calling `submit_for_review`.
3. **Code Review Phase**: The Agent behaves as a "critical reviewer" — sequentially running `run_linter` / `run_tests` / `analyze_complexity`, discovering real issues (e.g., missing module docstring, smoke test `FileNotFoundError`), and then calling `request_revision` to **fall back to the implementation phase**.
4. The implementation phase **rewrites and fixes** the code based on the issue list, then submits again; after the review passes, `approve_code` is called, and the task is complete.

In other words: **The prompt + tool set change with the phase, and the behavior pattern changes noticeably accordingly**, while the task state (requirements, code, review comments) remains continuously shared across phases. At the end of the run, a "behavior distribution" statistic for each role is printed, visually comparing the behavioral differences across the three phases.

## Expected Output Example

The following is an excerpt from a real run (`python demo.py`, `gpt-5.6-luna`, routed via OpenRouter), fully demonstrating the behavior switch across three phases
(In this run, the requirements clarification phase repeatedly asked about case-sensitivity rules, triggered 1 review fallback, and ultimately hit the total step limit
safety valve to end — a common outcome in real runs, see "Limitations" below):

```
Model: openai/gpt-5.6-luna  | base_url: https://openrouter.ai/api/v1

======================================================================
Entering phase: requirements  |  Role: Requirements Analyst  |  Available tools: ['ask_clarifying_question', 'save_requirement', 'complete_requirements_analysis']
======================================================================
[Requirements Analyst] Question: What file types do you want the script to organize? For example, organize all common files by extension, or only handle specific types like images, documents, videos, etc.?
[Requirements Analyst] Simulated user answer: Categorize by file type: Images (jpg/png/gif), Documents (pdf/doc/txt), Audio (mp3/wav), Video (mp4/mov), Archives (zip/rar), and put the rest into Others.
[Requirements Analyst] Recorded requirement: file_categories = Categorize by file type: Images jpg/png/gif; Documents pdf/doc/txt; Audio mp3/wav; Video mp4/mov; Archives zip/rar; other extensions go into Others.
[Requirements Analyst] Question: Do you need to recursively process subdirectories within the Downloads folder, or only process files in the root of the Downloads folder?
[Requirements Analyst] Recorded requirement: recursive = Do not recursively process subdirectories, only organize files at the current level of the Downloads folder, ignoring existing subfolders.
[Requirements Analyst] Recorded requirement: operation = Move files (move), do not keep the original location.
[Requirements Analyst] Recorded requirement: name_conflicts = Keep original filenames; if a file with the same name exists in the target directory, add _1, _2, etc., before the extension to avoid overwriting.
... (The simulated user only gives a fallback answer to "whether extensions are case-sensitive," so the Agent repeatedly asks about the same point, asking a total of 19 questions)
[Requirements Analyst] Completed requirements analysis -> Handing over to implementation: Confirmed: Script categorizes by specified extensions and puts other files into Others; only processes the current level of the download directory; default path is ~/Downloads, can also be specified via command-line argument; moves files instead of copying; extensions are case-insensitive; keeps original filenames, appends _1, _2, etc., to avoid overwriting in case of conflicts.

======================================================================
Entering phase: implementation  |  Role: Software Engineer  |  Available tools: ['write_file', 'read_file', 'execute_code', 'submit_for_review']
======================================================================
[Software Engineer] Wrote file: Wrote file organize_downloads.py (4312 characters, 135 lines)
[Software Engineer] Executed code for self-test: from pathlib import Path from tempfile import TemporaryDirectory import organize ...
[Software Engineer] Submitted for review -> Handing over to review: organize_downloads.py

======================================================================
Entering phase: review  |  Role: Code Reviewer  |  Available tools: ['run_linter', 'run_tests', 'analyze_complexity', 'request_revision', 'approve_code']
======================================================================
[Code Reviewer] run_linter: [linter] Passed: No issues found.
[Code Reviewer] run_tests: [tests] Smoke test result: FAIL
[Code Reviewer] analyze_complexity: [complexity] Number of functions=6, Branch/loop statements=16, Max nesting depth=3
[Code Reviewer] Review not passed -> Falling back to implementation: Fallback #1: ['Smoke test failed: `from __future__ import annotations` not at the beginning of the file triggers SyntaxError. Please remove this future import or use a compatible approach.']

======================================================================
Entering phase: implementation  |  Role: Software Engineer  |  Available tools: ['write_file', 'read_file', 'execute_code', 'submit_for_review']
======================================================================
[Software Engineer] Wrote file: Wrote file organize_downloads.py (4218 characters, 133 lines)
[Software Engineer] Submitted for review -> Handing over to review: organize_downloads.py
```... (review phase repeats, looping until `approve_code` or reaching step/rollback limit)

======================================================================
Execution Summary
======================================================================
[Requirements Analyst] Behavior distribution: questions×19, simulated user responses×19, recorded requirements×7, completed requirements analysis -> handoff to implementation×1
[Software Engineer] Behavior distribution: wrote files×2, executed code self-tests×4, read files×1, submitted review -> handoff to review×2
[Code Reviewer] Behavior distribution: run_linter×1, run_tests×1, analyze_complexity×1, review failed -> rollback to implementation×1

Confirmed requirements count: 7
Output files: ['organize_downloads.py']
Review rollback count: 1
```

The three "behavior distribution" sections clearly show the different behavior patterns of the same Agent under three different prompts: the Requirements Analyst only asks and never writes, the Software Engineer only writes and never reviews, and the Code Reviewer only reviews and never writes.

## Will a stronger model make this "phase scaffolding" redundant?

A common intuition is that scaffolding (here, a state machine that switches system prompts and tool sets by phase) is just a crutch for weaker models. With a stronger model, it would naturally self-organize into "clarify first, then implement, then review," making the scaffolding obsolete. Using the same code, the same task, the same simulated user, and running `gpt-4o-mini` and `gpt-5.6-luna` locally for a real comparison, the conclusion is negative:

| Observation | `gpt-4o-mini` (weaker) | `gpt-5.6-luna` (stronger reasoning model) |
| --- | --- | --- |
| Number of requirements clarification questions | 5 (one question per point, then moves on) | **21** (repeatedly harping on the edge case of "how to classify uppercase extensions / files without extensions") |
| Completed all three phases and obtained `approve_code` | **Yes** (passed review after 1 rollback, task completed) | **No** (hit the 40-step total step safety valve and was forcibly terminated) |
| Review rollback count | 1 | 1 |

(Run commands: `MODEL=gpt-4o-mini python demo.py --model gpt-4o-mini`; `python demo.py --model gpt-5.6-luna`. The latter was routed via OpenRouter as `openai/gpt-5.6-luna`.)

Two key points:

1. **This scaffolding is not a "crutch that can be turned off," but a structural constraint.** Each phase only exposes the tools of that phase to the model (the requirements phase has no `write_file`, the implementation phase has no `approve_code`). Role separation is enforced by **tool gating**, applied equally to both strong and weak models—no model can "self-organize" to skip or merge phases. For this very reason, **there is no baseline** in this experiment where scaffolding is turned off and the strong model is allowed to freely improvise, for a strict comparison.
2. **Switching to a stronger model did not make the scaffolding redundant; instead, it became more dependent on its safety valves.** `gpt-5.6-luna` is more "persistent," insisting on asking about an edge case that the simulated user cannot answer, and cleverly rephrasing the question each time, thereby bypassing the `SimulatedUser`'s anti-repetition mechanism of "asking the same question twice prompts it to move to the next phase." As a result, it idled for over twenty steps in the requirements phase, burning through the 40-step budget—ultimately, the `max_total_steps` scaffolding safety valve had to catch it. The weaker `gpt-4o-mini`, on the other hand, because it "asked a few broad questions and then stopped," completed the entire process smoothly.

**Honest boundary**: The fact that `gpt-5.6-luna` did not finish this time is largely due to the `SimulatedUser` with preset answers (see "Limitations")—it couldn't answer the edge-case questions the strong model pursued, which triggered the idle loop. With a real human answering (`--interactive`) or a smarter simulated user, the strong model would likely converge much faster. Therefore, this data **cannot** be used to conclude that "a stronger model performs worse on this task." It only supports a narrower, but more useful, conclusion for the reader: **Phase-based prompts + tool gating is a structural scaffolding. The role separation and safety valves it provides work equally for both strong and weak models and will not automatically become ineffective or redundant as models become stronger.**

## Limitations

- **Dependence on the selected model's capabilities**: The default uses the inexpensive flagship `gpt-5.6-luna` to control demonstration costs. Note that "stronger model = faster convergence" is not always true: more persistent reasoning models are more likely to get stuck in the requirements clarification phase, asking edge-case questions that the preset `SimulatedUser` cannot answer, leading to idle loops (see the real comparison in the previous section). In such cases, the `max_total_steps` / `max_revisions` scaffolding safety valves are more critical for catching failures.
- **Single fixed task**: The built-in demo task is "organize the downloads folder." Although a `--task` parameter has been added to override it, the preset Q&A in `simulated_user.py` is designed around this specific task scenario. For tasks that are very different, the simulated user may not provide relevant answers.
- **Simulated user uses preset answers**: The `SimulatedUser` matches preset answers based on keywords; it does not truly understand semantics. When the Agent asks questions outside the preset script, it degrades to a fallback response or urges the Agent to move to the next phase.
- **Real LLMs have randomness**: Even with `temperature=0.3`, the order of questions, implementation details, whether the review passes, and the number of rollbacks can vary between runs. It is also possible, as in the example above, to hit the `max_revisions` safety valve and be forcibly terminated instead of obtaining `approve_code`.
