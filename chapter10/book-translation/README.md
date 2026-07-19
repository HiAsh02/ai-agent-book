# Experiment 10-3: Book Translation Agent — Orchestration Pattern

Accompanying code demonstrating how to use the **Orchestration Pattern** to delegate long-document translation to multiple specialized agents. The core principles are
**context isolation** and **controlling Manager context growth**: the Manager only stores tasks, plans, agent call records, and file indexes; **complete translations are all written to the file system**, so no matter how long the book is, the Manager's context remains essentially constant.

## Objective

Compare the "single agent translating an entire book in one conversation" approach with the "orchestration pattern multi-agent collaboration" approach, using
**real token counts** to show how the latter controls main/Manager context growth, and using a **shared glossary** to ensure terminology consistency throughout the book.

## Architecture: Four Agents

| Agent | Input (Independent Context) | Output | Context Characteristics |
| --- | --- | --- | --- |
| **Glossary Agent** | Full book content | Structured glossary `glossary.json` | Reads the entire book, context released after output |
| **Translation Agent** | Current chapter + glossary + translation guide | `chapterN_zh.md` | One independent instance per chapter, only sees its own chapter |
| **Proofreading Agent** | All translations + glossary | Proofreading report `proofreading_report.json` | Performs consistency/fluency checks |
| **Manager Agent** | Task + file index + report summary | Scheduling decisions (whether to send back for revision) | **Stores only meta-information, not the full text** |

Data flow: Manager schedules Glossary → chapter-by-chapter Translation (all sharing the same glossary file) → Proofreading → Manager decides based on the report whether to send individual chapters back to Translation for revision. Translations and the glossary are passed through the **file system**; the Manager only saves file paths in its context.

Key design: The Manager forces "house style" terms (e.g., token→词元, prompt→提示词, latency→时延) into the shared glossary, which is then distributed to each Translation Agent, thereby enforcing the specified translations throughout the entire book. A single agent cannot see the glossary and can only use its own default translations.
## Directory

```
book-translation/
├── agents.py          # Four Agents + two execution modes + token tracking
├── consistency.py     # Terminology consistency / glossary adherence rate (deterministic string matching)
├── demo.py            # One-click demo: runs orchestration mode + single agent comparison, prints comparison table
├── sample_book/       # Bundled short English technical book (4 short chapters, includes terminology and code)
│   ├── chapter1.md ... chapter4.md
├── output/            # Generated at runtime: glossary / chapter translations / proofreading report (gitignored)
├── requirements.txt
└── env.example
```

## Running

```bash
pip install -r requirements.txt
cp env.example .env      # Fill in OPENAI_API_KEY
python demo.py
```

`python demo.py` will first print the **real-time trace of the four-agent collaboration** (Manager creates plan → schedules Glossary → chapter-by-chapter Translation → Proofreading → decides on revisions based on report), then print each agent's token consumption and the core comparison table between orchestration mode and single agent.

- The default model is `gpt-5.6-luna` (currently the cheap flagship), can be overridden with `OPENAI_MODEL`; if you need a custom/proxy endpoint, set `OPENAI_BASE_URL`.
- **Key and universal fallback**: It first tries `OPENAI_API_KEY` to connect directly to OpenAI; if this variable is not set but `OPENROUTER_API_KEY` is, it automatically switches to OpenRouter and maps the model name to its namespace (`gpt-5.6-luna` → `openai/gpt-5.6-luna`). Tip: The `gpt-5.6` series requires organization verification for direct OpenAI access; just setting `OPENROUTER_API_KEY` (without `OPENAI_API_KEY`) will force the use of OpenRouter, which is simpler.
- The task scale is intentionally small (4 short chapters), costing roughly a few hundredths of a US dollar per run.
- Running without any arguments behaves exactly like the old version.

### Command Line Arguments (`python demo.py --help`)

| Argument | Effect | Default |
| --- | --- | --- |
| `--dry-run` | **Offline rehearsal**: Only draws the four-agent collaboration diagram, Manager plan, house style terms, and token budget for each agent; **does not call any API, no Key required** | Off |
| `--sample-dir DIR` | Directory of the book to translate (reads `*.md` files, sorted by filename) | `sample_book/` |
| `--out-dir DIR` | Root directory for output (subdirectories `orchestration/`, `single_agent/` are created within) | `output/` |
| `--source-lang LANG` / `--target-lang LANG` | Source / target language (only affects prompt wording) | `English` / `Chinese` || `--no-glossary` | Disable the Glossary Agent (only keeps house style terms) | Enabled |
| `--no-proofreading` | Disable the Proofreading Agent and Manager revision loop | Enabled |
| `--model MODEL` | Temporarily override the model (equivalent to setting `OPENAI_MODEL`) | `gpt-5.6-luna` |
| `--skip-single` | Run only orchestration mode, skip the single agent control group | Off |

> Note: The built-in terminology consistency / adherence rate statistics (`consistency.py`) are calibrated for **English→Chinese**; changing the translation direction will still translate correctly, but the statistics table will be of limited significance.

**No Key / Offline Quick Architecture View**:

```bash
python demo.py --dry-run     # Prints four-agent collaboration diagram + Manager plan + token budget, no network required
```

This mode uses `tiktoken` to estimate the context size each agent will read offline, intuitively confirming that the "Manager context only grows by a few lines of records per chapter, independent of each chapter's text length," while the single agent's cumulative context grows linearly with the book's length.

## Token Statistics Definitions

- Input and output tokens for sub-agents / single agent are taken from the **real usage** returned by OpenAI.
- "Context peak" = the maximum single-input context (prompt tokens) across all calls for a given agent, used to measure context growth.
- Manager context peak: the peak token count, calculated by `tiktoken`, of the serialized Manager state (task/plan/call records/file index) — it never contains the complete translation text.

## Results (Real Run, gpt-5.6-luna, 4 Chapters)

| Metric | Orchestration Mode | Single Agent |
| --- | --- | --- |
| Main/Manager Context Peak (tokens) | **697** | **2320** |
| Manager LLM Decision Call Context (tokens) | 783 | — |
| Total Pipeline Tokens | 11849 | 6886 |
| Internal Terminology Consistency Rate | 100% | 89% |
| Specified Term Adherence Rate | **100%** | **53%** |
| Number of Agent Types Involved | 4 | 1 |

1. **Controlling Context Growth**: The single agent's main context accumulates with each chapter, peaking at 2320 tokens; in orchestration mode, the Manager's context peaks at only 697 tokens (approximately a 3.3x difference). More importantly, the Manager's context is **essentially independent** of the book's length (it only adds one line of call record/file index), while the single agent's cumulative context grows linearly with the number of chapters — the longer the book, the larger the gap. Sub-agents' contexts are isolated from each other, preventing cross-contamination (each Translation instance peaks at only about 547 tokens).
2. **Terminology Consistency**: The orchestration mode writes house style terms into the shared glossary and enforces them, achieving **100%** adherence for the 4 specified terms across the entire book; the single agent, unable to see the glossary, achieves only **53%** adherence. After switching to the more powerful gpt-5.6-luna, the single agent **spontaneously** adopts some "common sense translations" (token→词元, prompt→提示词 both matched the specified translations), but still acts independently for terms without a single standard (latency was translated as "延迟" throughout the book instead of the specified "时延", embedding as "嵌入" instead of "嵌入向量", with 0/4 and 0/3 adherence respectively). More critically, even the same term **drifts across chapters** for the single agent — token is translated as "词元" in some chapters and left as "token" in others, causing the internal consistency rate to drop to 89%; the orchestration mode, using the shared glossary, eliminates both types of issues (internal consistency 100%, adherence 100%).3. **Cost**: The orchestration mode uses significantly more tokens (11849 vs 6886, due to additional glossary extraction, proofreading, scheduling calls, and longer outputs from the reasoning model), in exchange for **controllable main context** and **enforceable terminology uniformity** — precisely the properties needed for long-document translation.

> Note: Terminology consistency is measured using deterministic string matching (see `consistency.py`), not model self-evaluation. Specific numbers may fluctuate slightly with each run, but the magnitude and conclusions are stable and reproducible.

## Limitations

- The table above was validated on `gpt-5.6-luna`; switching to a stronger/weaker model will change the gap between the two modes — a stronger single agent is more likely to spontaneously hit some common sense translations (adherence rate rising from nearly 0% for weaker models to 53% in this run), but it still cannot cover terms without a single standard, and cross-chapter drift still occurs; the orchestration mode's shared glossary consistently achieves 100%.
- The sample book is intentionally very small (4 short chapters) to clearly expose the mechanism; it does not represent the absolute token values for a large-scale real book.
- Glossary adherence rate and terminology consistency are both measured using deterministic string matching (`consistency.py`), not model self-evaluation, which may miss more flexible translation variants.
- Specific numbers for each run may fluctuate slightly due to the randomness of model output (the table above is from the most recent real run), but the magnitude and conclusions are stable and reproducible.
