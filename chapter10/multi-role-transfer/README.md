# Experiment 10-2: Multi-Role Transfer / `transfer_to_agent` (★★)

Companion code for *Deep Understanding of AI Agents*. Demonstrates **chained handoff under shared context**:
a single conversation contains multiple specialized agent roles (each with its own system prompt and dedicated tool set),
and control is **autonomously handed off** between roles via a `transfer_to_agent(target_role, reason)` tool.

## What This Experiment Illustrates

- Unlike 10-1 (a **predefined stage pipeline** for a single software development task), 10-2 emphasizes **cross-domain**,
  **agent-driven judgment** about which specialized role to switch to — not a pre-planned linear flow,
  but dynamic switching based on task progress.
- Because **the same conversation history is shared**, the full history is naturally preserved upon handoff,
  and the new role automatically inherits all prior context (no explicit parameter passing required).
- The core mechanism is **autonomous role handoff**, not the sophistication of the tools themselves,
  so the tools use lightweight real implementations / controllable mocks.

## Architecture

```
                        Shared conversation history (user/assistant/tool messages, retained throughout)
                                       ▲   ▲
   On each LLM call:                    │   │
   [ current role's system prompt ] + history ┘   └ only [ current role's tool set + transfer_to_agent ] exposed

   Two model actions:
     ① Call its own dedicated tools (normal function calling)
     ② Call transfer_to_agent(target_role, reason)
        → Orchestrator swaps "system prompt + tool set", history stays unchanged
        → New role inherits all history (shared context)
```

5 roles (`roles.py`):

| Role | Description | Dedicated Tool Set |
|------|-------------|-------------------|
| `triage` | Front-desk triage / default entry point, decomposes requests and hands off sequentially, final wrap-up | Only `transfer_to_agent` |
| `research` | Information retrieval | `web_search` (built-in knowledge base mock) |
| `coding` | Programming | `execute_python` (real execution with output capture) |
| `data_analysis` | Data analysis / computation | `calculate`, `descriptive_stats` |
| `writing` | Polishing and writing | `count_characters` |

Each role additionally holds `transfer_to_agent`, enabling autonomous handoff of control to colleagues.

Code structure:

- `tools.py` — Implementation of each role's dedicated tools + OpenAI function-calling schema
- `roles.py` — 5 role definitions (system prompts + tool sets) + `transfer_to_agent` schema
- `orchestrator.py` — Handoff orchestrator (shared history + main loop for swapping system prompts/tool sets, with deadlock prevention and self-handoff rejection)
- `demo.py` — Single-command demo entry point

## How to Run

```bash
pip install -r requirements.txt

# Configure API key (choose one)
export OPENAI_API_KEY=sk-...        # Direct export
# or: cp env.example .env and fill in

python demo.py
```

Configurable environment variables (all have defaults):
`OPENAI_API_KEY`, `OPENAI_BASE_URL` (default `https://api.openai.com/v1`),
`OPENAI_MODEL` (default `gpt-5.6-luna`).

**General fallback**: Prefers direct OpenAI connection via `OPENAI_API_KEY`; if that variable is not set but
`OPENROUTER_API_KEY` is set, it automatically switches to OpenRouter and maps the model name to its namespace
(`gpt-5.6-luna` → `openai/gpt-5.6-luna`). Note: The `gpt-5.6` series requires organization verification for direct OpenAI access;
setting only `OPENROUTER_API_KEY` (without `OPENAI_API_KEY`) forces OpenRouter, which is simpler.

### Command-Line Arguments

All arguments are optional; if omitted, behavior is identical to the original version (runs the default `cagr` scenario). Run
`python demo.py --help` to see the full Chinese documentation.

| Argument | Effect |
|----------|--------|
| `--list-roles` | **Offline self-check**: Only prints the role roster + built-in scenarios and exits, **no API Key required** |
| `--scenario {cagr,solar,coding}` | Select a built-in scenario (default `cagr`); `coding` routes to the `coding` role to actually run code |
| `--task "..."` | Custom task text, overrides `--scenario` |
| `--role {triage,research,coding,data_analysis,writing}` | Specify the **starting role** (alias `--starting-role`, default `triage`) |
| `--interactive` | **Interactive multi-turn**: Reuses the same orchestrator, roles and shared history persist across turns |
| `--model gpt-5.6-luna` | Temporarily overrides `OPENAI_MODEL` |
| `--max-steps 30` | Hard upper limit on LLM rounds per message (default 20, prevents infinite loops) |

Examples:

```bash
python demo.py --list-roles            # Offline view of roles/scenarios, no API call
python demo.py --scenario coding       # Scenario routed to the coding role
python demo.py --task "Research and summarize…" # Custom task
python demo.py --role research         # Start from the research role
python demo.py --interactive           # Interactive multi-turn, type exit to quit
```

Three built-in scenarios (`SCENARIOS`): `cagr` (default, new energy vehicle sales → CAGR → investment summary),
`solar` (same chain with a different set of photovoltaic installation data), `coding` (routes to the `coding` role
to actually run a Fibonacci script via `execute_python`, then `writing`/`triage` wraps up).

## Demo Description

`demo.py` presents a composite task requiring **multiple cross-domain switches**:

> Look up China's new energy vehicle sales for 2021–2023 → Calculate the compound annual growth rate (CAGR) → Write a Chinese summary for investors

Expected autonomous handoff chain:

```
triage → research → data_analysis → writing
```

- `triage` determines the first step is to look up data, hands off to `research`;
- `research` uses `web_search` to find the three years of sales data, hands off to `data_analysis`;
- `data_analysis` uses `calculate` to compute CAGR ≈ 64.22%, hands off to `writing`;
- `writing` synthesizes the sales data and CAGR from **the prior history** and directly produces the final draft.

`writing` never retrieved or computed anything itself, yet it can reference accurate sales figures and growth rates —
this is evidence of **shared context**. After execution, the full handoff chain, each `from→to` and `reason`,
and a **role-by-role summary** (who called which dedicated tools, who produced the final reply) are printed,
making it clear at a glance how "different specialized roles take turns on the same history."

> Note: Real LLM output has randomness; specific wording or step counts in a given run may vary slightly, but the handoff mechanism is consistent.

### Expected Output Example (from a real run)

The following is a key excerpt from an actual `python demo.py` run (`model=gpt-5.6-luna`, routed via OpenRouter), unedited and unembellished:

```
=== Role Roster (5 specialized roles) ===
• triage — Front-desk triage (default entry)
    Tool set: ['transfer_to_agent']
    System prompt (first line): You are the 'front-desk triage' role of the general assistant system, and the default entry point.
• research — Information retrieval specialist
    Tool set: ['web_search', 'transfer_to_agent']
    ...(other roles omitted, see full list in the role table above)

┌── Current role: Information Retrieval Specialist (research)   Tools: ['web_search', 'transfer_to_agent']
└── 🔧 Calling tool web_search args={'query': 'China 2021 2022 2023 new energy vehicle sales CPCA CAAM'}
    → [Search Results · China Passenger Car Association / CAAM]…2021: 3.521 million units / 2022: 6.887 million units / 2023: 9.495 million units
┌── Current role: Data Analysis Specialist (data_analysis)   Tools: ['calculate', 'descriptive_stats', 'transfer_to_agent']
└── 🔧 Calling tool calculate args={'expression': '(9.495/3.521)**(1/2)-1'}
    → (9.495/3.521)**(1/2)-1 = 0.6421562289791105

================ Run Summary ================
Autonomous handoff chain: triage → research → data_analysis → writing → triage
Handoff count: 4
  1. triage → research  |  reason: Need to first retrieve China's 2021, 2022, 2023 new energy vehicle sales and reliable sources, to provide data for subsequent CAGR calculation and investor summary.
  2. research → data_analysis  |  reason: Retrieved 2021, 2022, 2023 NEV sales data; please calculate the two-year CAGR from 2021 to 2023 and provide the result for subsequent writing.
  3. data_analysis → writing  |  reason: Sales data and CAGR completed: 2021: 3.521M, 2022: 6.887M, 2023: 9.495M; 2021–2023 CAGR=(9.495/3.521)^(1/2)-1=64.22%. Please write a Chinese investor summary of no more than 120 characters based on this.
  4. writing → triage  |  reason: Completed investor summary and verified length (101 characters, within 120-char limit)… Please do final wrap-up confirmation.

Role-by-role breakdown (who used which tools, who produced the final reply):
  triage        : (routing/handoff only, no dedicated tools used)  ⇒ Produced final reply
  research      : web_search
  data_analysis : calculate
  writing       : count_characters

Final output:
According to public data from CAAM, China's new energy vehicle sales grew from 3.521 million units in 2021 to 6.887 million in 2022 and 9.495 million in 2023. The two-year CAGR from 2021 to 2023 reached 64.2%, indicating rapid market expansion with significant growth potential.
```

## Limitations

- The default model is `gpt-5.6-luna`; whether the handoff follows the expected chain depends heavily on the selected model's instruction-following ability. Switching models may yield different results.
- The `research` role's `web_search` is a **built-in knowledge base mock**, not a real web search; it only matches a small set of predefined keywords (new energy vehicle sales, photovoltaic installations, Python GIL). Changing the query may return no results.
- Real LLM output has randomness: the exact number of handoff steps, the wording of each `reason`, whether the `coding` role is visited, etc., may vary between runs, but the handoff mechanism itself is consistent.
- `orchestrator.py` has a hard `max_steps` limit (default 20) and a correction prompt for "same (role, tool, arguments) called ≥3 times consecutively" to prevent model infinite loops; this is a safety net, not an indication that every run will use all these steps.
