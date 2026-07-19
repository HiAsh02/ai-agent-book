# Experiment 5-8: Intelligent Diagnostic System for Production Logs

Companion to Chapter 5 of "Deep Understanding of AI Agents" – "Code as Generative Capability: Automatic Analysis and Problem Diagnosis of Agent Execution Logs".

## Objective

Production environments generate a large volume of **trajectory logs** from agents. Identifying issues, locating root causes, and building regression tests from these logs is costly.
This experiment lets a diagnostic agent automate this pipeline:

**Read trajectory collection + Architecture docs + PRD → Locate issues, generate structured reports → Generate regression test cases → Replay framework for actual execution verification → (mock) Create GitHub Issues via MCP integration.**

## Diagnostic Pipeline

```
data/trajectories.jsonl  (production trajectories with known issues)
data/architecture.md     (system architecture)          ┐
data/PRD.md              (product requirements)         ├─► [LLM] diagnose()      Structured issue report (priority/module/description/suggestion)
                                                         ┘        │
                                                                   ▼
                                                         [LLM] gen_test_cases()   Regression test cases (reference trajectory ID + interaction turns)
                                                                   │
                                                                   ▼
                                                         replay.py replay framework ── Replay the system under test with the same input and assert
                                                           (A) Unfixed system → FAIL (bug reproduced)
                                                           (B) Fixed system → PASS (fix verified)
                                                                   │
                                                                   ▼
                                                         github_mcp.py (mock) Render and print/save GitHub Issue
```

- `diagnoser.py`: Diagnostic agent, makes two real calls to OpenAI (default gpt-5.6-luna, JSON mode).
- `sut.py`: **Deterministic simulator** of the system under test. `fixed=False` reproduces the online bug, `fixed=True` simulates the fixed behavior.
- `replay.py`: Regression test replay framework. Takes trajectory input → replays `sut` → evaluates assertions on the new trajectory (built-in 4 assertion DSLs).
- `github_mcp.py`: GitHub Issue creation, default mock (prints + writes to `output/github_issues.json`).

## Predefined Known Issues (Agent should identify)

| Trajectory | Issue | Violates PRD | Module |
|------------|-------|--------------|--------|
| T-1001 / T-1002 | **Skips** mandatory `verify_refund_eligibility` check before refund | R1 (P0) | order_service |
| T-1002 | `process_refund` **repeatedly fails**, no backoff, and falsely reports success | R2 (P0) | payment_service |
| T-1003 | `check_stock` latency 8300ms **timeout without degradation** | R3 (P1) | inventory_service |
| T-1004 | Normal trajectory (control group, no issues) | — | — |

## Running

```bash
pip install -r requirements.txt
cp env.example .env      # Fill in OPENAI_API_KEY (model defaults to gpt-5.6-luna); if not configured, set OPENROUTER_API_KEY to automatically switch to OpenRouter
python demo.py           # Full pipeline (two real LLM calls)
```

`demo.py` runs everything in one go: read trajectories → diagnostic report → regression test cases → replay execution (pass/fail) → (mock) GitHub Issue.

Common parameters (see `python demo.py -h` for all):

- `--smoke`: **Quick self-check without API**, skips LLM, uses built-in diagnostic results to run only the replay framework + GitHub mock, verifying the pipeline is end-to-end connected (all green, exit code 0). Suitable for environments without a key or CI.
- `--model gpt-5.6`: Temporarily override the model (equivalent to setting `OPENAI_MODEL`).
- `--data-dir DIR`: Use your own input directory (must contain `trajectories.jsonl` + `architecture.md` + `PRD.md`, defaults to `data/`).
- `--output FILE`: Path to save mock GitHub Issues (defaults to `output/github_issues.json`).
- `--create-issue`: **Create Issues in a real repository via MCP** (requires `GITHUB_TOKEN` + `GITHUB_REPO`, see next section; falls back to mock if missing).
- `--no-github`: Skip step 4, do not generate GitHub Issues.

## Real Run Output (Excerpt)

During the diagnosis phase, the agent identifies all 3 predefined issues:

```
[Issue 1] Refund eligibility check not performed
  Priority : P0     Module: order_service    PRD: R1
  Trajectories   : ['T-1001', 'T-1002']  Key turns: [3]
[Issue 2] Payment retry mechanism not correctly implemented
  Priority : P0     Module: payment_service    PRD: R2
[Issue 3] Inventory query latency not degraded
  Priority : P1     Module: inventory_service    PRD: R3
```

Regression test cases are **actually executed** by the replay framework (first reproducing the bug, then verifying the fix):

```
(A) Replaying against the 'unfixed online' system — expecting bug reproduction (FAIL)
    [FAIL] RT-001 (T-1001)  Tool verify_refund_eligibility missing
    [FAIL] RT-002 (T-1002)  process_refund called 3 times, failed 3 times, last call failed
    [FAIL] RT-003 (T-1003)  check_stock max latency 8300ms, threshold 5000ms
(B) Replaying against the 'fixed' system — expecting fix verification (PASS)
    [PASS] RT-001 (T-1001)  Tool verify_refund_eligibility present
    [PASS] RT-002 (T-1002)  process_refund called 2 times, failed 1 time, last call succeeded
    [PASS] RT-003 (T-1003)  check_stock max latency 400ms, threshold 5000ms
  Summary: Bug reproduced 3/3 cases; fix verified 3/3 cases.
```

Mock GitHub Issues are printed and written to `output/github_issues.json`, example:

```
title  : [P0][order_service] Refund eligibility check not performed
labels : ['module:order_service', 'priority:critical', 'auto-diagnosis']
body   : ## Problem Description ... ## Related Regression Test Cases - RT-001 (Trajectory T-1001 Turn 3) ...
```

## Regression Test Assertion DSL (built into replay framework)

Agent-generated test cases must use one of the following assertions, which the framework can automatically evaluate:

- `step_present` `{tool}`: A specific tool must appear (e.g., mandatory pre-check).
- `tool_succeeds` `{tool}`: A specific tool ultimately succeeds, and there is no "false success after multiple failures".
- `latency_under` `{tool, threshold_ms}`: The single-call latency of a specific tool is below the threshold.
- `final_status_is` `{value}`: The final status of the task equals a given value.

## How to Adapt/Extend

- **Change model**: Set `OPENAI_MODEL` (or `python demo.py --model <name>`). `diagnoser.py` defaults to `gpt-5.6-luna`, both use JSON mode; stronger models are more stable for complex/implicit issues.
- **Change provider**: This project uses the official `openai` SDK. Simply set `OPENAI_BASE_URL` to point to a service compatible with the OpenAI API (e.g., Moonshot / Volcano Ark / local vLLM), along with that provider's `OPENAI_API_KEY` and `OPENAI_MODEL`. No code changes needed. For example:
  ```bash
  export OPENAI_BASE_URL=https://api.moonshot.cn/v1
  export OPENAI_API_KEY=sk-...          # The provider's Key
  export OPENAI_MODEL=kimi-k3
  python demo.py
  ```
- **Change logs**: Replace your own production trajectories following the structure of `data/trajectories.jsonl` (`trajectory_id / task / task_input / turns[] / final_status`, with `turns` containing `module/tool/input/output/status/latency_ms`). Also update `data/architecture.md` and `data/PRD.md` as diagnostic references. If the trajectory fields differ, adjust `sut.py` (replay stub) and `replay.py` (assertion evaluation) accordingly.
- **Connect to real GitHub MCP**: See the next section. Use `GITHUB_TOKEN` + `GITHUB_REPO` + `--create-issue` to set `mock=False`.

## Connecting to Real GitHub MCP (requires token, default mock)

This experiment defaults to mock; only `--create-issue` will actually connect to the network. The real creation implementation is built into
`github_mcp._create_issues_via_mcp()`: It connects to the official
GitHub MCP Server via an MCP client (`mcp` SDK, stdio), and calls its `create_issue` tool for each issue, passing the `title / body / labels / assignees` generated by `build_issue()`. Steps to enable:

1. Prepare a GitHub Personal Access Token (`repo` scope), write it to `GITHUB_TOKEN` in `.env`;
   and set the target repository `GITHUB_REPO=owner/repo`.
2. Ensure the official GitHub MCP Server can be started locally. The default start command uses the official Docker image
   `ghcr.io/github/github-mcp-server`; you can override it with `GITHUB_MCP_COMMAND` to use any MCP Server that exposes the `create_issue` tool (the token is injected into its environment via `GITHUB_PERSONAL_ACCESS_TOKEN`).
3. `pip install mcp` (only needed for this path; mock/self-check do not require it).
4. Run `python demo.py --create-issue`. If `GITHUB_TOKEN` / `GITHUB_REPO` are missing, a prompt will be printed and it will automatically fall back to mock to avoid unintended network connections.

## Limitations

- The system under test `sut.py` is a **deterministic simulation**, designed to allow the regression tests to be truly replayed and produce stable pass/fail results; in real-world scenarios, replaying requires connecting to the actual system or using recorded/replayed dependency stubs.- Diagnostic quality depends on the LLM; gpt-5.6-luna can consistently identify all 3 preset issues (R1 missing validation / R2 retry false positive / R3 delay not downgraded) in this dataset, with stable diagnostics in step 1. However, it tends to report R1 "missing validation" as two separate items under T-1001 and T-1002, often outputting 4 issues (rather than the 3 merged items shown in the example above). In step 2, when generating assertions, it consistently selects `final_status_is:failed` for the "payment retry" issue (observed in both runs) instead of the `tool_succeeds` used in the example—because the fixed system under test will succeed on retry (final_status=success), this assertion fails during post-fix replay, reducing the post-fix pass count to 3/4 instead of all green. Additionally, it occasionally adds module prefixes to tool names in `step_present`/`latency_under` (e.g., `order_service.verify_refund_eligibility`), which does not match the replay framework's bare tool name matching, further reducing the post-fix pass count (observed as 3/4 and 0/4 in two runs). The built-in `--smoke` test cases deterministically yield 3/3.
- GitHub creates a default mock without network access; only `--create-issue` connects via a real MCP Server to create issues online (requires token + repo + an available GitHub MCP Server).
- The trace format shown is simplified; production traces contain richer fields (token usage, sub-agent call trees, etc.).
