# Experiment 8-4: Active Tool Discovery

> Companion code for *Deep Understanding of AI Agents* · ★★★
>
> On a tool library of **126 cross-domain tools**, run a single comparison of three "tool discovery" strategies—**full injection**,
> **retrieval pre-filtering** (one-shot semantic pre-selection of top-n), **active discovery** (on-demand `discover_tools` during execution)—
> and output a unified comparison table (accuracy / injection tokens / latency). Quantify the token waste of full injection, demonstrate how active discovery
> uses **embedding vector similarity** to converge hundreds of tools into a few precise candidates, while revealing the inherent limitation of "one-shot pre-filtering"
> on multi-step cross-domain tasks. **No API key required**: `python demo.py --offline` uses local embeddings + a mock model self-check mechanism.

## Purpose

When an Agent has hundreds of tools, the common practice is to inject the JSON schemas of all tools into the system prompt at once.
This introduces two problems:

1. **Token waste**: The full schema of 126 tools is approximately **11,600 tokens**, and each inference step incurs repeated costs.
2. **Instruction-following degradation**: Under vaguely worded tasks, the model will "cast a wide net" by invoking both generic fallback tools (`web_search` /
   `google_search` / `universal_search`) and specialized tools together, or even replace specialized tools with generic search
   — i.e., the book's example of "choosing a generic web_search to look up a stock price."

**Active discovery** keeps only a small set of basic tools in the system prompt plus a `discover_tools(need)` meta-tool. When the model encounters a capability gap,
it describes the need in natural language, and the system retrieves 3-5 most relevant specialized tools from the tool library using embedding similarity, appending their schemas as
**user messages** into the conversation (preserving the KV Cache of the system prefix), and updates the status bar's available tool list.

## Mechanism

```
tools_library.py   126 cross-domain tools (finance/web/arxiv/github/geo/weather/media/... 17 domains total)
                   Each tool has a real name/description/parameters; execution is lightweight mock (focus is on "selecting the right tool")
                   8 "generic/synonymous" tools (web_search, etc.) are deliberately mixed in, with descriptions exaggerating their omnipotence
                   select_tools(size): Subset by --tool-set-size, demonstrating "the larger the tool set, the more costly full injection"
discovery.py       Pluggable embedding backend + tool vector index; OpenAIEmbedder generates vectors with text-embedding-3-small
                   and caches them in .cache/; search(need) = vectorize need, compute cosine similarity with tool vectors, return top-k
agent.py           ReAct loop for three strategies (text protocol: model outputs a JSON tool call per step)
                   - run_full_injection: All 126 tool schemas written into the system prompt
                   - run_retrieval_prefilter: One-shot retrieval of top-n tools based on the initial query (the book's "retrieval pre-filtering")
                   - run_active_discovery: Basic tools + discover_tools, on-demand retrieval and loading during execution
offline_backend.py Offline backend: LocalEmbedder (local hash bag-of-words embedding) + MockChatClient (scripted mock model),
                   enabling --offline to run the full pipeline without any API key (token/latency are real, accuracy only reflects heuristic routing)
demo.py            Run selected strategies on the same set of tasks, print token/latency/call trace/whether precisely correct, and output a summary comparison table
```

**Why use "text injection + text parsing" instead of OpenAI's native function calling?**
The native function-calling interface imposes strong optimization constraints on tool selection, making it rare to mis-select even with hundreds of tools, thus failing to demonstrate the
"instruction-following degradation under long context" described in the book. Treating schemas as plain text injected into the prompt and having the model output tool calls as JSON
is the real mechanism of the control group, and only then can degradation be observed. This is exactly the approach of "injecting schemas into the system prompt (tens of thousands of tokens)" in the book.

**Why can embedding retrieval avoid mis-selection?** The description of the generic tool `web_search` ("can do anything") dilutes its semantics; whereas specialized tools
(e.g., `search_news`) have focused descriptions. For a focused `need` ("get the latest news about Tesla"), the focused specialized tool has a higher cosine similarity
and ranks higher, while the generic tool often fails to make it into the top-k and thus is never loaded — the retrieval layer naturally acts as a "precision filter."

**Why is retrieval pre-filtering insufficient?** Retrieval pre-filtering (`run_retrieval_prefilter`) performs only a single semantic match based on the **initial query**,
injecting the top-n tools all at once. For multi-step cross-domain tasks like "look up a stock price + search for news," the vector of the initial query often leans toward the first domain,
and the specialized tool needed for the second sub-task may not make it into the top-n. The model then discovers halfway through that "the tool I want to call isn't even in the list" —
this is the inherent limitation of one-shot matching pointed out in the book. Active discovery postpones "discovery" to execution time, retrieving separately for each real `need` that emerges,
thereby filling this gap (in the offline self-check, it can be directly observed that retrieval pre-filtering misses the second tool in half of the multi-step tasks, see table below).

## Running

```bash
pip install -r requirements.txt

# Method A: Offline mechanism self-check (no key required; token/latency are real, accuracy only reflects heuristic routing)
python demo.py --offline

# Method B: Real model (demonstrating "instruction-following degradation" in small models requires a real LLM)
cp env.example .env    # Fill in OPENAI_API_KEY (both chat and embeddings use OpenAI)
# Fallback: If no OPENAI_API_KEY but OPENROUTER_API_KEY is set, chat will automatically switch to OpenRouter
# (model mapped to openai/gpt-5.6-luna, etc.), tool retrieval falls back to local hash embeddings (OpenRouter has no embeddings API).
python demo.py                                   # All 8 tasks × three strategies
python demo.py --strategies full,discovery       # Run only two strategies for comparison
python demo.py --tasks finance+news,crypto+news  # Run only specified tasks (comma-separated)
python demo.py --tasks 'opinion(诱导)'            # Task IDs with parentheses, remember to quotepython demo.py --tool-set-size 20                # Reduce tool set size to see how full injection's disadvantage scales
python demo.py --query 'Check Nvidia's stock price and search for related news' --offline   # Temporary single natural language taskpython demo.py --offline --output results/offline.json         # Export structured results
```

Default model `gpt-5.6-luna`, can be overridden with `--model` or env: `python demo.py --model gpt-5.6-luna`.
First run generates embedding vectors for tools and caches them in `.cache/`, subsequent runs reuse them. `python demo.py --help` for all parameters
(`--query / --tasks / --strategies / --tool-set-size / --top-k / --prefilter-n / --model / --embed-model / --max-steps / --offline / --output`).

## How to Adapt / Extend

- **Change model**: `MODEL=gpt-4.1-mini python demo.py` (chat model); `EMBED_MODEL=text-embedding-3-large` to change embedding model
  (changing the embedding model will automatically rebuild the `.cache/` index due to signature changes).
- **Change provider / gateway**: Both chat and embeddings use the OpenAI SDK; `OpenAI()` automatically reads the environment variable `OPENAI_BASE_URL`,
  so pointing to any **OpenAI-compatible** gateway/proxy only requires `OPENAI_BASE_URL=https://your-gateway/v1` (this endpoint must provide both chat and embeddings).
- **Change tasks / input**: Edit `TASKS` in `tools_library.py` (each entry contains a `prompt` and capability slots for scoring), or use
  `--tasks` to run only a few, or use `--query` to pass a temporary requirement; to expand the tool library, add or remove entries in `ALL_TOOLS` in `tools_library.py`.
- **Offline self-check**: `--offline` uses the local hash embedding from `offline_backend.py` + a scripted mock model, requiring no key,
  suitable for CI, offline environments, or quick pipeline validation; it reproduces the token/latency structure and the mechanism of "retrieval pre-filtering missing tools in one shot,"
  but does not reproduce the real model's selection behavior under a long-context tool wall (see the real gpt-5.6-luna results below).

## Offline Mechanism Self-Check (Local Embeddings + Mock Model, `python demo.py --offline`)

The table below is from a real `--offline` run (8 tasks × three strategies). **Token/latency are real measurements from tiktoken/wall-clock**;
**accuracy only reflects the scripted heuristic routing, not the real model's capability**—the mock model is a "strong router" that does not degrade, so full injection also scores perfectly.

| Strategy | Precisely Correct | Task Completion | Avg Injection Tokens | Total Injection Tokens | Avg Latency (s) |
|---|---|---|---|---|---|
| Full Injection | 8/8 | 8/8 | 11630 | 93040 | 0.008 |
| Retrieval Pre-filtering | 4/8 | 4/8 | 1030 | 8236 | 0.006 |
| Active Discovery | 8/8 | 8/8 | 974 | 7796 | 0.010 |

**Two real, reproducible structural conclusions** from the offline self-check:

1. **Token differentiation scales with tool set size**: Full injection is a fixed 11,630 tokens/task; retrieval pre-filtering and active discovery inject only
   about 1,000 tokens on demand (**~11.9× reduction**). Using `--tool-set-size 20` to shrink the tool set narrows the gap to ~1.8×—confirming "the more tools,
   the more costly full injection."
2. **Retrieval pre-filtering structurally misses tools on multi-step cross-domain tasks**: One-shot top-10 retrieval missed the specialized tool needed for the second sub-task
   in 4 out of 8 tasks (e.g., `academic(诱导)`'s top-10 had no `arxiv_search` at all); the model reaches the middle of execution and cannot call the tool → sub-task fails;   active discovery retrieves separately for each real `need` that emerges, completing 8/8.

## Conclusion (Based on a Real Run, gpt-5.6-luna, 2026-07)

> Note: The table below is from a real LLM run (`python demo.py --model gpt-5.6-luna`, 8 tasks × three strategies, OpenAI direct connection
> chat + `text-embedding-3-small` retrieval). gpt-5.6-luna is a reasoning model that only supports the default `temperature=1`
> (does not support `temperature=0`; the code automatically falls back to the default temperature upon encountering this error), so this is a **single, non-deterministic** run;
> token/latency are real measurements, and per-task selection results may vary with sampling. Judgment: ✅=Precisely correct (covers all capability slots and did not mis-select
> a generic fallback tool); ⚠️=Completed but incidentally mis-selected a generic tool; ❌=Error (missed specialized tool or gave up midway, 0 tool calls).

| Task | Full Injection | Retrieval Pre-filtering | Active Discovery | Full Tokens | Discovery Tokens |
|---|---|---|---|---|---|
| finance+news | ✅ | ❌ | ✅ | 11630 | 883 |
| arxiv+download | ✅ | ❌ | ✅ | 11630 | 927 |
| github+viz | ❌ | ❌ | ❌ | 11630 | 295 |
| weather+calendar | ❌ | ✅ | ✅ | 11630 | 1055 |
| forex+weather | ✅ | ✅ | ❌ | 11630 | 295 |
| crypto+news | ❌ | ⚠️ | ❌ | 11630 | 295 |
| opinion(induction) | ⚠️ | ❌ | ✅ | 11630 | 688 |
| academic(induction) | ⚠️ | ⚠️ | ❌ | 11630 | 295 || **Precisely Correct** | **3/8** | **2/8** | **4/8** | | || **Task Completion** | **5/8** | **4/8** | **4/8** | | |
| **Total Injected Tokens** | | | | **93040** | **4733** |

(Retrieval pre-filtering averages 971 tokens/task, total 7768; average latency for the three strategies is approximately 11.5 / 9.6 / 10.7 s, all measured in this run.)

1.  **Token savings remain robust (and even more pronounced)**: Full injection injects a fixed **11,630 tokens** per task; active discovery, with on-demand loading, uses only **295~1,055 tokens**, totaling 93,040 → 4,733 (**~19.7×**). It must be honestly noted: this ratio is larger partly because gpt-5.6-luna directly gave up on several tasks without triggering `discover_tools` (injecting only 3 basic tools = 295 tokens). Even so, the structural benefit of "full injection fixedly billing tens of thousands of tokens repeatedly, while on-demand discovery only injects thousands of tokens" remains unaffected.

2.  **Core phenomena from the book are faithfully reproduced on the two "inducement tasks"**: When wording is vague, full injection tends to grab general-purpose fallback tools:
    -   `opinion(inducement)` ("Tesla's recent news and public opinion trends"): Full injection called `search_news, search_news, web_search, search_tweets`, also using the general-purpose **`web_search`** (⚠️ wrong selection); active discovery retrieved `search_news / get_news_by_source / ...` (**no** `web_search`), calling only specialized news tools, **clean and correct (✅)**.
    -   `academic(inducement)` ("Latest scientific research progress in quantum computing"): Full injection called 8 tools at once, including **`google_search / universal_search / ask_knowledge_base`**, all general-purpose fallbacks (⚠️); retrieval pre-filtering also incorrectly selected `google_search / universal_search`. This is exactly the portrayal from the book of "a tool wall of hundreds of tools + vague wording → casting a wide net and grabbing general-purpose tools".

3.  **Another type of real behavior exposed in this run (different from the earlier gpt-4o-mini run, must be faithfully recorded)**: gpt-5.6-luna is a conservative reasoning model. On several tasks, it **finished early without calling (mock) tools**, often citing "inability to access real-time data/tools" (e.g., `github+viz`, `weather+calendar` for full injection, and `forex+weather`, `crypto+news`, `academic` for active discovery, all showed 0 tool calls). This lowered the absolute accuracy for all three strategies and also means that **this run cannot conclude** that "the model always selects correctly when facing a tool wall on clear tasks" – on the contrary, giving up/missing steps became the main source of errors, and this type of error exists in both full injection and active discovery.

4.  **Honest explanation of boundaries**:
    -   This experiment uses a control group mechanism of "injecting schemas as plain text + the model self-outputting JSON tool calls" to observe long-context selection behavior; mock tools return placeholder data, and conservative reasoning models sometimes see through this and refuse to answer, which is a major source of the low accuracy in this run.
    -   Because gpt-5.6-luna only supports the default `temperature=1`, per-task results are stochastic; which tasks "give up" and which "incorrectly select general-purpose tools" will fluctuate in repeated runs, but the two structural conclusions (token savings, full injection misusing general-purpose tools on inducement tasks) are directionally stable.
    -   For a cleaner, reproducible mechanism self-check (token/latency structure + retrieval pre-filtering one-shot tool omission), see the `--offline` table above.

> In a nutshell: **On gpt-5.6-luna, the most stable benefit of active tool discovery remains tokens (~19.7× in this run); on "inducement tasks" with vague wording where general-purpose tools are easily misused, embedding retrieval indeed blocks exaggerated general-purpose tools like `web_search / google_search / universal_search` from the candidate set. However, this version of the real run also reminds us: the conservative "give up" behavior of strong reasoning models simultaneously lowers the absolute accuracy of all strategies, and single-run results must be interpreted faithfully according to the table above.**

## Model ↔ Scaffolding Trade-off (Weak Model gpt-4o-mini vs Strong Model gpt-5.6-luna, Both Real Runs)

> This section answers a direct question: **As models become stronger, does this "active tool discovery" scaffolding become useless?**
> We compare the gpt-5.6-luna (strong) results above with a real run of **gpt-4o-mini (weak)** under the same 8 tasks × 3 strategies, using OpenAI direct chat + `text-embedding-3-small` retrieval
> (`python demo.py --model gpt-4o-mini`, July 2026, same judgment criteria). The conclusion is: the scaffolding has two types of value, one that **fades** as models become stronger, and another that is **independent of model strength and always exists**.

**Weak model gpt-4o-mini real summary:**

| Strategy | Precise Correct | Task Completion | Total Injected Tokens | Avg Latency(s) |
|---|---|---|---|---|
| Full Injection | 5/8 | **8/8** | 93040 | 8.38 |
| Retrieval Pre-filtering | 7/8 | 7/8 | 7768 | 4.90 |
| Active Discovery | **8/8** | **8/8** | 7266 | 7.65 |

(Tokens 93040 → 7266, **~12.8×** reduction.)

### Value 1: Avoiding "Incorrect Selection of General-Purpose Tools" – **Fades** as Models Become Stronger

-   **Weak model gpt-4o-mini: Scaffolding value is huge and clean.** Under full injection, gpt-4o-mini never gives up (task completion 8/8), but on 3 tasks it "cast a wide net" and grabbed general-purpose fallback tools – `crypto+news` used `web_search`, and the two inducement tasks `opinion` / `academic` each called `web_search / google_search / universal_search` together – so full injection achieved only **5/8 precise**. Active discovery allowed embedding retrieval to **block these exaggerated general-purpose tools from the candidate set**, making it impossible for gpt-4o-mini to misuse them: **8/8 precise, 0 general-purpose tool misuses, and task completion did not decrease (still 8/8)**. This is exactly the weak model ailment of "a tool wall of hundreds of tools + vague wording → casting a wide net and grabbing general-purpose tools" described in the book, and the scaffolding cures it in one go.
-   **Strong model gpt-5.6-luna: The same value is significantly diminished.** Its "general-purpose tool misuse" under full injection is limited to only 2 tasks (`opinion` / `academic`), fewer than gpt-4o-mini's 3; active discovery cleans up these two instances, but the precise rate only increases from **3/8 to 4/8 (+1)**, and **task completion actually decreases from 5/8 to 4/8**. The reason is that the strong reasoning model's main source of error is **not "selecting the wrong tool," but "directly giving up"**: on several tasks, it called 0 tools and `finished` (often citing "inability to access real-time data"). The retrieval layer cannot fix this type of error, and with fewer tools visible, it might even be slightly exacerbated. **In other words, the weakness that the scaffolding specifically treats – "incorrectly selecting general-purpose tools" – is already thin in strong models, and the benefit fades accordingly.**

### Value 2: Saving Injected Tokens – **Independent of Model Strength, Always Exists** (Persisting)

Full injection, regardless of model strength, is fixed at **11,630 tokens/task** (stuffing all 126 tool schemas into the system). On-demand discovery injects only a few hundred to over a thousand tokens:

-   Weak model gpt-4o-mini: 93,040 → 7,266, **~12.8×**;
-   Strong model gpt-5.6-luna: 93,040 → 4,733, **~19.7×** (the ratio is larger, partly because it often gave up and never triggered `discover_tools`, injecting only 3 basic tools).

Token savings are solidly established for both models and scale up with a larger tool set – **this benefit does not disappear as models become stronger** and is a hard reason for the scaffolding to remain valuable in the "era of strong models."

### One-Sentence Summary

> **The stronger the model, the more the scaffolding's value of "helping it avoid selecting the wrong tool" fades (gpt-4o-mini full 5/8 → discovery 8/8 precise, zero completion loss; gpt-5.6-luna only 3/8 → 4/8 with completion even decreasing, because its errors are "giving up" rather than "wrong selection"); but the value of "saving tokens" is independent of model strength and always exists (weak model ~12.8×, strong model ~19.7×, full injection constant at 11,630 tokens/task). Therefore, on strong models, the primary reason for active tool discovery shifts from "correcting instruction-following degradation" to "controlling context cost."**

## Files

-   `tools_library.py` — 126 tool definitions + `select_tools` subset extraction + mock execution + 8 evaluation tasks and scoring criteria
-   `discovery.py` — Pluggable embedding backend (`OpenAIEmbedder`) + tool vector index and similarity retrieval (`discover_tools`/pre-filtering backend)
-   `agent.py` — ReAct loop and token statistics for three strategies (full injection / retrieval pre-filtering / active discovery)
-   `offline_backend.py` — Offline backend: `LocalEmbedder` + `MockChatClient`, supporting `--offline` keyless self-check
-   `demo.py` — One-click multi-strategy comparison demo (includes CLI: `--query/--tasks/--strategies/--tool-set-size/--offline/--output`, etc.)
-   `requirements.txt` / `env.example`
