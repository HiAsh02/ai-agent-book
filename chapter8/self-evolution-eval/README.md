# Experiment 8-6: Designing an Evaluation Dataset for Self-Evolving Agents (★★★)

Evaluating an agent's "self-evolution" capability—i.e., **discovering, creating, and reusing tools on its own** when no ready-made tool is available—
requires a specialized evaluation dataset and validation methodology. The challenge lies in: tasks must not hint at tool names (otherwise it degenerates into "memorizing fixed tool patterns"),
and "whether the result is correct" is only the most superficial signal; we also need to see **how it discovers, how well it creates, and whether it will reuse next time**.

This directory provides a runnable, complete implementation: **a dataset of 20 cross-domain tasks + a four-layer hierarchical validation harness + a controllable reference agent + a one-click demo**.

## Directory Structure

| File | Description |
| --- | --- |
| `dataset.json` | 20 tool-requiring tasks across different domains. Each entry contains a goal description (without hinting at tool names), a reference solution (recommended libraries + API examples), known pitfalls (deprecated libraries / paid or registration-required APIs), and correctness criteria. |
| `harness.py` | Four-layer validation harness: `FourLayerEvaluator.evaluate(task, trajectory, variant_trajectory)`. |
| `agent.py` | Reference agent under test (controllable mock version of a self-evolving agent) + `ToolRegistry`. |
| `demo.py` | One-click demo: `python demo.py`. |
| `config.py` | Reads API Key, constructs an OpenAI-compatible client. |
| `requirements.txt` / `env.example` | Dependencies and environment variable example. |

## Dataset Design Principles

1. **State only the goal, do not hint at tool names.** For example, "Get the subtitles of a YouTube video" instead of "Use `youtube-transcript-api`";
   "Query real-time cryptocurrency price trends" instead of "Use the CoinGecko API". This truly tests the agent's **discovery/creation** ability,
   rather than its memory of a specific library name.
2. **20 different domains**: Multimedia, Finance/Cryptocurrency, Scientific Computing, Geocoding, Social Media, IoT, Weather, NLP, Image,
   PDF, Astronomy, Chemistry, Bioinformatics, Audio, Exchange Rates, Stocks, Geospatial, RSS, QR Codes, Time Zones. The more diverse the domains, the better
   to prevent the model from applying fixed patterns.
3. Each task includes a **reference solution** (`reference_solution`: list of recommended open-source libraries + typical API examples) and
   **known pitfalls** (`known_pitfalls`: `deprecated_libraries`, `paid_or_registration_apis`),
   used as judgment criteria for layers 2 and 3.
4. `correctness_criteria` provides verifiable criteria for layer 1 (regex or keywords); `discovery_keywords` provides keywords for layer 2
   to determine if the search is relevant; `tool_name` + `variant_goal` support layer 4's "whether the second similar task reuses the tool".
5. `mock_answer` is only used to drive the **controllable reference agent** in this repository through the harness; the real agent under test does not depend on it.

## Four-Layer Hierarchical Validation

The harness takes the **execution trajectory** of an agent under test (`trajectory`: sequence of tool calls + created tool code + final answer;
schema is in the comments at the top of `agent.py`) and outputs scores for each of the four layers and an overall evaluation:

| Layer | Name | Method | Criteria Source |
| --- | --- | --- | --- |
| **L1** | Task Correctness | Rule/criteria check of the final answer | `correctness_criteria` |
| **L2** | Tool Discovery Effectiveness | Heuristic analysis of search keywords / whether web pages were accessed / which library was chosen | `discovery_keywords` + `reference_solution` + `known_pitfalls` |
| **L3** | Tool Creation Quality | **LLM-as-a-Judge scoring based on a Rubric** (Error Handling / Parameter Validation / Documentation / Robustness, each 0-3) | Tool code created by the agent under test |
| **L4** | Tool Reuse Capability | Analyze the trajectory of the "second similar task": whether it directly retrieves a registered tool instead of repeating the search and creation | Action sequence of `variant_trajectory` |

- **L2** is purely heuristic (no LLM needed): Selected recommended library (0.40) + Search is relevant (0.25) + Avoided pitfalls (0.25) + Accessed web page (0.10).
  Choosing a deprecated library or paid API results in a "failed to avoid pitfalls" judgment.
- **L3** is the only layer that must call an LLM: the tool function code is given to the judge, which returns JSON scores and a Chinese comment based on the 4-dimensional Rubric.
- **L4** distinguishes between `retrieve_tool` (reuse) and `search`+`create_tool` (redundant work) based on the action sequence of the second similar task (`variant_goal`).
- If a layer is not applicable (e.g., the reuse trajectory does not generate a new tool, so L2/L3 are marked N/A), the overall score is re-normalized by weight among the available layers.

## How to Evaluate Your Own Agent with the Harness

Have your agent under test produce a trajectory conforming to the schema in `agent.py` (`steps` / `created_tools` / `final_answer`),
and reuse the same `ToolRegistry` for the second similar task. Then:

```python
from harness import FourLayerEvaluator
evaluator = FourLayerEvaluator(judge_model="gpt-5.6-luna")          # Default: run all four layers
# Run only deterministic layers (no internet needed): evaluator = FourLayerEvaluator(layers=("L1","L2","L4"))
report = evaluator.evaluate(task, first_trajectory, variant_trajectory)
print(report["layers"], report["summary"]["overall"])
```

`layers=` is used to select which layers to actually run—only **L3** requires an internet connection to call the LLM; removing L3 allows for fully offline evaluation.
Unselected layers are recorded as `score=None` (N/A), and the overall score is re-normalized by weight among the available layers.

## Running

```bash
pip install -r requirements.txt
cp env.example .env      # Fill in OPENAI_API_KEY (default provider=openai, model gpt-5.6-luna)
python demo.py                       # Default: strong runs 3 tasks + weak runs 1 as control (online, includes L3)
python demo.py --quick               # Quick demo: strong / weak each run only 1 task, saves time and money
python demo.py --tasks task-01,task-07   # Specify which task IDs to evaluate
python demo.py --help                # View all parameters (Chinese description)
```

**Full Parameters** (`python demo.py --help`):

| Parameter | Effect |
| --- | --- |
| `--all` | Evaluate all 20 tasks (default: automatically switches to result table output, no per-task scrolling) |
| `--tasks IDS` | Comma-separated task IDs, specify which ones to evaluate |
| `--quick` | strong / weak each run only 1 task |
| `--layers L1,L2,L4` | Select which validation layers to run (only **L3** needs internet; remove it for offline) |
| `--profile {strong,weak,both}` | Select the reference profile under test; default retains the default (strong all + weak first) |
| `--offline` | Offline mode: does not call any LLM (strong uses offline tool templates), automatically skips L3 |
| `--provider {openai,moonshot,ark}` | Override the provider |
| `--agent-model` / `--judge-model` | Override the tool-creation model / L3 judge model |
| `--table` | Only print the "per task × per layer" result table, do not print per-task detailed reports |
| `--output PATH` | Write the complete scoring results (including per-layer details) to a JSON file |

`demo.py` will: print a dataset overview and a few task examples without hinting at tool names → run the four-layer validation with the **strong** reference agent → run the **weak** reference agent as a control → finally print a **per task × per layer result table**, comparing scores across tasks on the four layers horizontally.

### Offline Run Output (No API Key Needed, `python demo.py --all --offline --profile both`)

Runs only the three deterministic layers (L1/L2/L4, L3 is marked N/A), fully reproducible, used to demonstrate the "per task × per layer" result table and the strong/weak differentiation:

```
Per Task × Per Layer Result Table (N/A = Layer not applicable or not selected)
------------------------------------------------------------------------------
Task     Domain               Profile  L1     L2     L3   L4     Overall
task-01  Multimedia           strong   1.000  1.000  N/A  1.000  1.000
task-02  Financial Data / Crypto strong 1.000  1.000  N/A  1.000  1.000
...
task-10  Document Processing  strong   1.000  0.750  N/A  1.000  0.917
task-19  Encoding / QR Code   strong   1.000  0.750  N/A  1.000  0.917
...
task-01  Multimedia           weak     1.000  0.000  N/A  0.000  0.467
task-03  Scientific Computing weak     1.000  0.250  N/A  0.000  0.550
task-10  Document Processing  weak     1.000  0.400  N/A  0.000  0.600
...
```

Strong scores are generally perfect on L2 (Discovery)/L4 (Reuse); weak scores are significantly lower due to choosing deprecated/paid libraries and never reusing; both can have L1 = 1 (getting the answer right by chance)—which precisely demonstrates that "correct result" is insufficient for judging self-evolution capability. **L3 (Tool Creation Quality) requires an internet connection to call the LLM judge**; removing `--offline` and configuring an API Key will add it back (see the online output below).

### Online Run Output (Includes L3, Excerpt)

Strong (good discovery + high-quality tool generated by LLM + reuse):

```
■ Task task-01 (Multimedia) | Profile=strong
  L1 Task Correctness     : 1.000
  L2 Tool Discovery Effectiveness : 1.000  | Selected recommended library=True Avoided pitfalls=True (Selected library: ['youtube-transcript-api'])
  L3 Tool Creation Quality   : 1.000  | Rubric 4-dimension total 12/12
       Rubric: Error Handling=3 Parameter Validation=3 Documentation=3 Robustness=3
       LLM-Judge Comment: The code excels in error handling, parameter validation, documentation completeness, and robustness...
  L4 Tool Reuse Capability   : 1.000  | Directly retrieved and reused a registered tool (no repeated search/creation)
  >> Overall score   : 1.000
    [Reuse Probe] Action sequence for the second similar task: ['retrieve_tool', 'call_tool', 'final_answer']
```

Weak (bad discovery: chose deprecated library pytube + rough stub + never reuses):

```
■ Task task-01 (Multimedia) | Profile=weak
  L1 Task Correctness     : 1.000
  L2 Tool Discovery Effectiveness : 0.000  | Selected recommended library=False Avoided pitfalls=False (Selected library: ['pytube (subtitle/caption feature has been broken for a long time)'])
  L3 Tool Creation Quality   : 0.000  | Rubric 4-dimension total 0/12
       LLM-Judge Comment: The code lacks error handling, parameter validation, and documentation, and the implementation does not meet the task objective.
  L4 Tool Reuse Capability   : 0.000  | Did not reuse; repeated search and tool creation
  >> Overall score   : 0.350
    [Reuse Probe] Action sequence for the second similar task: ['search', 'select_library', 'create_tool', 'register_tool', 'call_tool', 'final_answer']
```

The two profiles are clearly differentiated on L2/L3/L4; note that weak's L1 can still be 1 (getting the answer right by chance), which precisely demonstrates that "correct result" is insufficient for judging self-evolution capability—discovery/creation/reuse must be examined hierarchically.

## Configuration / How to Adapt- **Switch Model**: `AGENT_MODEL` (the Agent under test that creates tools), `JUDGE_MODEL` (Layer 3 judge, default `gpt-5.6-luna`).
- **Switch Provider / Gateway**: Default `PROVIDER=openai`, reads `OPENAI_API_KEY`; also supports `PROVIDER=moonshot` (`MOONSHOT_API_KEY`)
  or `PROVIDER=ark` (`ARK_API_KEY`), automatically switches `base_url` and default model (see `config.py`).
- **Switch Task / Input**: Edit `dataset.json` to add new tasks (follow the principle of "state only the goal, do not hint at tool names"), or use `--tasks task-xx,...`
  to specify which tasks to evaluate; feed your own Agent's trajectory (following the schema at the top of `agent.py`) into `FourLayerEvaluator.evaluate` to evaluate a real Agent.
- **Unified Fallback**: If the selected provider's API key is missing but `OPENROUTER_API_KEY` is set, it will automatically switch to OpenRouter,
  and map the model name to `openai/gpt-5.6-luna` / `anthropic/claude-opus-4.8`, etc. (see `config.py`).

## Limitations

- The built-in `SelfEvolutionAgent` is a **controllable reference Agent** (mock version), used to run the four-layer harness and demonstrate the distinction between strong and weak,
  not a real networked strong Agent; L1's "accidental correct answer" is precisely used to illustrate that "correct results alone are insufficient to judge self-evolution capability."
- L3 relies on LLM-as-a-Judge, so scores may fluctuate slightly with the judge model and sampling; L2/L4 are interpretable heuristics with criteria hardcoded in the harness.
- In `--offline` mode, the strong profile uses **offline tool templates** (instead of actually calling an LLM to generate tools) to create tools, so **L3 cannot run offline** (recorded as N/A);
  it is used to deterministically reproduce L1, L2, and L4 along with the result table when no API key is available. To evaluate real tool creation quality, you still need to run L3 online.
- The dataset consists of 20 teaching-scale samples, covering a wide range but with only 1 sample per domain, emphasizing methodological demonstration rather than statistical significance.
