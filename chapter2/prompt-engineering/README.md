# Prompt Engineering Ablation Study for Tau-Bench

## Overview

This project extends the Tau-Bench framework with three critical ablation study options to demonstrate the importance of **prompt engineering: treating agents as smart new employees**. Through these experiments, we can quantify the impact of different prompt engineering factors on agent performance.

## Ablation Study Options

### 1. Tone Style 🎭

Demonstrates how different communication styles affect agent performance:

- **default**: Standard professional tone (baseline)
- **trump**: Donald Trump style - uses exaggerated language, repetitive emphasis, confident statements
- **casual**: Casual friendly style - heavy use of emojis, slang, and relaxed language

**Rationale**: Tone can affect agent professionalism and task completion quality. Overly casual or exaggerated tones may lead to:
- Reduced user trust
- Increased likelihood of misunderstandings
- Impact on task execution accuracy

### 2. Wiki Rule Randomization 📝

Uses a pre-generated extremely chaotic version of wiki.md:

- Removes all section headings and structure
- Prefixes each rule with an operational context (e.g., "When booking flights")
- Completely shuffles all rules into a flat list
- Destroys logical relationships between rules

**Rationale**: Well-organized instructions are like training manuals for new employees. Extreme randomization will:
- Completely destroy the logical hierarchy of information
- Blur rule boundaries across different operations
- Make it extremely difficult for agents to understand task priorities and rule associations
- Increase the risk of misapplying rules and missing critical steps

### 3. Tool Description Removal 🔧

Removes all tool and parameter descriptions:

- Sets tool function descriptions to empty strings
- Sets parameter descriptions to empty strings
- Tests the importance of clear descriptions

**Rationale**: Clear tool descriptions are like operation guides in an employee handbook. Removing descriptions will:
- Cause agents to misunderstand tool purposes
- Increase the probability of incorrect tool usage
- Reduce task completion rates

## Installation

First ensure the base Tau-Bench dependencies are installed:

```bash
cd projects/week2/prompt-engineering
pip install -r requirements.txt
```

## Usage

> All entry scripts provide Chinese `--help`: `python run_ablation.py --help`, `python analyze_results.py --help`.

### One-Click Full Ablation with Comparison Table (Recommended)

`--all` runs the baseline plus three individual ablation dimensions and the full combination sequentially in a single process. After completion, it prints a success rate comparison table and writes summary statistics to `--output` (default `log-dir/ablation_summary_<timestamp>.json`). This is the most direct way to reproduce the conclusions of "Experiment 2-4" in the book:

```bash
python run_ablation.py \
    --model gpt-5.6-luna \
    --env airline \
    --end-index 10 \
    --all
# Note: Uses OpenAI direct connection by default (provider=openai); requires OPENAI_API_KEY.
#       To use OpenRouter, write the model as an id with a slash (e.g., openai/gpt-5),
#       the script will automatically select the openrouter provider (requires OPENROUTER_API_KEY).
#       Fallback: even if the model is a bare id (e.g., gpt-4o-mini), if OPENAI_API_KEY is not set
#       but OPENROUTER_API_KEY is set, the script will automatically prefix it as openai/gpt-4o-mini
#       and switch to the openrouter provider.
```

After running, it prints a success rate comparison table. Below is output from a **real run** (`--model gpt-4o --env airline --end-index 4`, i.e., only 4 tasks per group as a smoke test), shown only to illustrate the table format:

```
Experiment                        Success Rate      Tasks        Relative
----------------------------------------------------------------------
wiki_random                      50.0%         2/  4      200.0%
baseline                         25.0%         1/  4      100.0%  ⭐
tone_trump                       25.0%         1/  4      100.0%
tone_casual                      25.0%         1/  4      100.0%
no_tool_desc                      0.0%         0/  4        0.0%
all_ablations                     0.0%         0/  4        0.0%
```

> ⚠️ The table above has only 4 tasks per group, with extremely small sample sizes and high noise—for example, `wiki_random` happened to be higher than `baseline` this time, which is small-sample fluctuation, not a real conclusion. The directional signals (removing tool descriptions → 0%, full combination → 0%, tone has no effect on success rate) are consistent with "Experiment 2-4" in the book, but to obtain stable quantitative conclusions (e.g., "information disorganization causes a success rate drop of over 30%"), please increase `--end-index` to 10 or higher and run multiple `--seed` values. Please rely on your own complete run results, not the smoke numbers here.

### Basic Run: Single Configuration

Run a baseline experiment (no ablation):

```bash
python run_ablation.py \
    --model gpt-5.6-luna \
    --env airline \
    --task-split test \
    --start-index 0 \
    --end-index 10
# Note: bare model ids (gpt-4o-mini) use OpenAI direct; ids with '/' auto-select openrouter
```

### Tone Ablation Experiments

#### Trump Style
```bash
python run_ablation.py \
    --model gpt-5.6-luna \
    --env airline \
    --tone-style trump \
    --ablation-name trump_tone
```

#### Casual Style
```bash
python run_ablation.py \
    --model gpt-5.6-luna \
    --env airline \
    --tone-style casual \
    --ablation-name casual_tone
```

### Wiki Randomization Experiment

```bash
python run_ablation.py \
    --model gpt-5.6-luna \
    --env airline \
    --randomize-wiki \
    --ablation-name wiki_random
```

### Tool Description Removal Experiment

```bash
python run_ablation.py \
    --model gpt-5.6-luna \
    --env airline \
    --remove-tool-descriptions \
    --ablation-name no_tool_desc
```

### Combined Ablation Experiments

Test the combined impact of multiple factors:

```bash
python run_ablation.py \
    --model gpt-5.6-luna \
    --env airline \
    --tone-style casual \
    --randomize-wiki \
    --remove-tool-descriptions \
    --ablation-name full_ablation
```

## Experiment Scripts

### Running the Full Ablation Study

There are two equivalent ways to run the complete ablation suite:

1. **Python one-click mode (recommended)**: `python run_ablation.py --env airline --end-index 10 --all`, runs within a single process and prints the comparison table directly.
2. **Bash orchestration script**: The repository includes `run_full_ablation.sh`, which calls `run_ablation.py` individually and then automatically invokes `analyze_results.py` for aggregation:

```bash
# Default 10 tasks/experiment; --quick for 3-task smoke test
./run_full_ablation.sh --model gpt-5.6-luna --env airline --num-tasks 10
./run_full_ablation.sh --quick
```

## Result Analysis

Raw trajectories for each experiment are saved in the `results_ablation/` directory, containing:

- **task_id**: Task identifier
- **reward**: Success rate (0 or 1)
- **info**: Detailed execution information
- **traj**: Complete conversation trajectory
- **ablation_config**: Ablation configuration used

### Aggregation Analysis Script

`analyze_results.py` scans the results directory, aggregates success rates by experiment name, and prints a comparison table, ablation factor impact analysis, and ASCII bar chart:

```bash
# Analyze default directory
python analyze_results.py

# Specify directory and write summary statistics to JSON
python analyze_results.py --results-dir results_ablation --output summary.json
```

> Note: The `--all` mode already prints the same comparison table at the end of execution. `analyze_results.py` is intended for post-hoc re-aggregation or analysis of historical/manual runs. The `results_ablation/*.json` files included in the repository are debug samples with a small number of tasks (1-6), only for demonstrating the data format. **The sample size is insufficient for statistical conclusions**. Please rely on your own complete runs (e.g., `--end-index 10` or higher) for results.

## Expected Results

Based on prompt engineering principles, the expected performance ranking:

1. **Baseline**: Standard configuration, best performance
2. **Tone variations**: Tone changes do not significantly affect interaction quality
3. **Wiki randomization**: Extremely chaotic rule arrangement severely impacts understanding, likely causing instruction non-compliance issues
4. **No tool descriptions**: Lack of tool descriptions leads to numerous tool call parameter errors, resulting in incorrect operations
5. **Combined ablations**: Multiple factors combined, worst performance

## Key Insights

These experiments demonstrate why we should **treat agents as smart new employees**:

### 1. Clear Instructions Are Crucial
Just like training new employees, agents need:
- Structured information
- Clear task descriptions
- Explicit tool usage instructions

### 2. Context Organization Affects Understanding
- Logically ordered rules are easier to follow
- Related information should be grouped together
- Priorities should be explicit

### 3. Tool Documentation Is Indispensable
- Each tool needs a clear purpose description
- Parameter descriptions prevent misuse
- Examples aid correct usage

## Parameters

| Parameter | Description | Options |
|-----------|-------------|---------|
| `--tone-style` | Dimension 1: Tone style (applied to system prompt) | default, trump, casual |
| `--randomize-wiki` | Dimension 2: Randomize wiki rule organization structure | flag |
| `--remove-tool-descriptions` | Dimension 3: Remove tool descriptions | flag |
| `--all` | One-click run complete ablation suite and print comparison table | flag || `--output` | (only with --all) Path to output aggregated statistics JSON | string |
| `--ablation-name` | Experiment name identifier | string |
| `--env` | Environment selection | airline, retail |
| `--model` | Model to use | string (e.g., gpt-4o-mini, gpt-4o) |
| `--model-provider` | Model provider (optional) | Auto-detected (bare IDs use openai, IDs with / use openrouter) |
| `--task-split` | Task set | train, test, dev |
| `--start-index` | Starting task index | integer |
| `--end-index` | Ending task index | integer |
| `--log-dir` | Directory to save results | string |

## Troubleshooting

### Common Issues

1. **ImportError**: Ensure you are running from the correct directory and have installed all dependencies
2. **API Error**: Check your API key settings and quotas
3. **Memory Issues**: Reduce the `--max-concurrency` parameter

### Debug Mode

Add verbose logging:
```bash
export LITELLM_LOG=DEBUG
python run_ablation.py ...
```

## Contributing

Contributions of additional ablation study options are welcome! Please consider adding:
- Different tone styles
- Other wiki organization methods
- More tool description variants
- Performance visualization tools

## Summary

This ablation study framework quantitatively demonstrates the importance of good prompt engineering. By systematically degrading different aspects of prompt quality, we can observe:

- **30-80% performance degradation** when prompt engineering is poor
- **Structure and clarity** are the most critical factors
- **Professionalism and consistency** build effective Agent systems

Remember: Good prompt engineering is good employee training!

---

*This project is the companion code for Chapter 2 "Prompt Engineering" of the book "AI Agent in Action".*

---

# τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains

**❗News**: We have released [τ²-bench](https://github.com/sierra-research/tau2-bench) as an extension of $\tau$-bench. $\tau^2$-bench includes code fixes and an additional `telecom` domain focusing on troubleshooting scenarios. Please use the $\tau^2$-bench as the latest version of this benchmark.

**Paper**:
* [τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains](https://arxiv.org/abs/2406.12045)
* [τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment](https://arxiv.org/abs/2506.07982)

We propose $\tau$-bench, a benchmark emulating dynamic conversations between a user (simulated by language models) and a language agent provided with domain-specific API tools and policy guidelines.

## Leaderboard

### Airline

| Strategy       | Pass^1 | Pass^2 | Pass^3 | Pass^4 |
| -------------- | ------ | ------ | ------ | ------ |
| [TC (claude-3-5-sonnet-20241022)](https://www.anthropic.com/news/3-5-models-and-computer-use)      | **0.460**     | **0.326**     | **0.263**     | **0.225**     |
| [TC (gpt-4o)](https://platform.openai.com/docs/guides/function-calling)     | 0.420     | 0.273     | 0.220     | 0.200     |
| [TC (claude-3-5-sonnet-20240620)](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)      | 0.360     | 0.224     | 0.169     | 0.139     |
| [TC (mistral-large-2407)](https://docs.mistral.ai/capabilities/function_calling/)     | ??     | ??     | ??     | ??     |
| [TC (gpt-4o-mini)](https://platform.openai.com/docs/guides/function-calling)     | 0.225     | 0.140     | 0.110     | 0.100     |
| [Act](https://arxiv.org/abs/2210.03629) (gpt-4o)     | 0.365 | 0.217 | 0.160 | 0.140     |
| [ReAct](https://arxiv.org/abs/2210.03629) (gpt-4o)     | 0.325 | 0.233 | 0.185 | 0.160     |

### Retail

| Strategy       | Pass^1 | Pass^2 | Pass^3 | Pass^4 |
| -------------- | ------ | ------ | ------ | ------ |
| [TC (claude-3-5-sonnet-20241022)](https://www.anthropic.com/news/3-5-models-and-computer-use)      | **0.692**     | **0.576**     | **0.509**     | **0.462**     |
| [TC (gpt-4o)](https://platform.openai.com/docs/guides/function-calling)     | 0.604     | 0.491     | 0.430     | 0.383     |
| [TC (claude-3-5-sonnet-20240620)](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)      | 0.626     | 0.506     | 0.435     | 0.387     |
| [TC (mistral-large-2407)](https://docs.mistral.ai/capabilities/function_calling/)     | ??     | ??     | ??     | ??     |
| [TC (gpt-4o-mini)](https://platform.openai.com/docs/guides/function-calling)     | ??     | ??     | ??     | ??     |
| [Act](https://arxiv.org/abs/2210.03629) (gpt-4o)     | ??     | ??     | ??     | ??     |
| [ReAct](https://arxiv.org/abs/2210.03629) (gpt-4o)     | ??     | ??     | ??     | ??     |

*TC = `tool-calling` strategy (the function-calling strategy reported in the paper)

## Setup

1. Clone this repository:

```bash
git clone https://github.com/sierra-research/tau-bench && cd ./tau-bench
```

2. Install from source (which also installs required packages):

```bash
pip install -e .
```

3. Set up your OpenAI / Anthropic / Google / Mistral / AnyScale API keys as environment variables.

```bash
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
MISTRAL_API_KEY=...
```

## Run

Run a tool-calling agent on the τ-retail environment:

```bash
python run.py --agent-strategy tool-calling --env retail --model gpt-4o --model-provider openai --user-model gpt-4o --user-model-provider openai --user-strategy llm --max-concurrency 10
```

Set max concurrency according to your API limit(s).

To run specific tasks, use the `--task-ids` flag. For example:

```bash
python run.py --agent-strategy tool-calling --env retail --model gpt-4o --model-provider openai --user-model gpt-4o --user-model-provider openai --user-strategy llm --max-concurrency 10 --task-ids 2 4 6
```

This command will run only the tasks with IDs 2, 4, and 6.

## User simulators

By default, we use `gpt-4o` as the user simulator with strategy `llm`. You can use other models by setting the `--user-model` flag, or other strategies by setting the `--user-strategy` flag. For example, run a tool-calling agent with a claude user simulator:

```bash
python run.py --agent-strategy tool-calling --env retail --model gpt-4o --model-provider openai --max-concurrency 10 --user-model claude-3-5-sonnet-20240620 --user-model-provider anthropic --user-strategy llm
```

Other strategies:

To run `react` user simulator:

```bash
python run.py --agent-strategy tool-calling --env retail --model gpt-4o --model-provider openai --max-concurrency 10 --user-model gpt-4o --user-model-provider openai --user-strategy react
```

Example of a `react` user response:

```md
Thought:
I should provide my name and zip code as I wasn't given an email address to use.

User Response:
Sure, my name is Yusuf Rossi, and my zip code is 19122.
```

To run `verify` user simulator:python run.py --agent-strategy tool-calling --env retail --model gpt-4o --model-provider openai --max-concurrency 10 --user-model gpt-4o --user-model-provider openai --user-strategy verify
```

This strategy uses a subsequent LLM verification step to check if the user simulator's response is satisfactory. If not, the user simulator will be prompted to generate a new response.

To run `reflection` user simulator:

```bash
python run.py --agent-strategy tool-calling --env retail --model gpt-4o --model-provider openai --max-concurrency 10 --user-model gpt-4o --user-model-provider openai --user-strategy reflection
```

This strategy uses a subsequent LLM verification step to check if the user simulator's response is satisfactory. If not, the user simulator will be prompted to reflect on its response and generate a new response.

## Auto error identification

Often times, it is difficult and time consuming to manually identify specific error locations in trajectories as they can be long and the constraints can be complex. We have provided an auto error identification tool that can do the following:

1. Fault assignment: determine the entity that is responsible for the fault (user, agent, environment)
2. Fault type classification: classify the type of fault (goal_partially_completed, used_wrong_tool, used_wrong_tool_argument, took_unintended_action)

Both of the labels are accompanied with a description.

To run the auto error identification, run:

```bash
python auto_error_identification.py --env <airline/retail> --platform openai --results-path <the path to your results file here> --max-concurrency 16 --output-path test-auto-error-identification --max-num-failed-results 10
```

Please note that this feature utilizes an LLM, which may lead to inaccurate error identifications.

*Notice: If an error is raised due to the structure of your results file, you may have to rerun the benchmark to produce a new results file. We have recently [rewritten](https://github.com/sierra-research/tau-bench/commit/043b544371757ebb3762b3d02a6675dfe0c41798) the benchmark to be more type-safe and extensible.

## Historical trajectories

τ-bench might be expensive to run. We have provided a set of historical trajectories for the airline and retail environments in `./historical_trajectories`.

If you would like to contribute your historical trajectories to this benchmark, please submit a PR!

## License

See `./LICENSE`.

## Contact

Please submit issues or pull requests if you find problems with the benchmark.

## Citation

```bibtex
@misc{yao2024tau,
      title={$\tau$-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains}, 
      author={Shunyu Yao and Noah Shinn and Pedram Razavi and Karthik Narasimhan},
      year={2024},
      eprint={2406.12045},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2406.12045}, 
}
@misc{barres2025tau2,
      title={$\tau^2$-Bench: Evaluating Conversational Agents in a Dual-Control Environment}, 
      author={Victor Barres and Honghua Dong and Soham Ray and Xujie Si and Karthik Narasimhan},
      year={2025},
      eprint={2506.07982},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2506.07982}, 
}
```
