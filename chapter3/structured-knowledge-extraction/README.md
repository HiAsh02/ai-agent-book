# Experiment 3-13: Extracting Tacit Knowledge from Structured Data – A Case Study on Judicial Precedent Analysis

Accompanying Chapter 3 of *Understanding AI Agents*. Demonstrates how to make an Agent treat a knowledge base not as a "static warehouse for retrieval only," but rather to **first read and understand the data, inductively derive structured decision logic from the data itself, and then answer questions based on that logic**.

Using precedents for three types of crimes (theft / intentional injury / fraud) as examples, the complete four-stage pipeline is demonstrated:

```
Precedent Text ──① Bottom-up Factor Discovery──▶ Modular Schema (Core + Per-Crime Extensions)
                                                        │
                                            ② Structured Extraction (extract factors using discovered schema)
                                                        │
                                            ③ Intra-Crime Clustering ──▶ Case Archetypes + Hierarchical Factor Importance
                                                        │
        New Case ──④ Conversational Agent (match nearest archetype, ask follow-ups by importance, give advice) ◀──┘
```

Contrary to the "predefined rigid schema + regression black box" approach, the two key innovations of this experiment are:
**Factors are not predefined; they are freely induced by the LLM from the data**; **Sentencing experience is not modeled by regression fitting sentence length, but by clustering into interpretable case archetypes**.

## Four-Stage Pipeline

**① Bottom-up Factor Discovery (`discovery.py`)**
No fields are predefined. Precedent texts are fed to the LLM in batches, allowing it to **freely list** all factors that might influence the judgment in each batch of cases; then, a single LLM call is used to **merge, deduplicate, and normalize** the raw factors discovered from each batch into a modular schema:
`core` (general factors applicable to all crimes: voluntary surrender, compensation, guilty plea, prior record/recidivism…) + `extensions`
(crime-specific extension factors: theft → amount stolen/home invasion/gang, intentional injury → injury level/weapon use/premeditation, fraud → amount/number of victims).
Outputs `data/schema.json` (with caching).

**② Structured Extraction (`extractor.py`)**
Using the discovered schema, factors are extracted from each precedent as "core + crime-specific extensions" (LLM structured output,
`response_format=json_object`). Factors not mentioned in the text return `null`. Extraction results are cached to
`data/extracted.jsonl`; re-running after a one-time extraction is nearly free.

**③ Clustering into Case Archetypes + Hierarchical Factor Importance (`archetypes.py`)**
Factors are translated into numerical vectors: crime/categorical factors (e.g., injury level) use one-hot flags (not 1/2/3,
to avoid implying ordinal relationships); amounts / counts take `ln` to compress scale; binary circumstances take 0/1. **Within each crime type**, KMeans
clustering is applied (k automatically selected by silhouette score) to yield several "case archetypes"—for example, intentional injury will automatically cluster into
"minor injury," "light injury," "severe injury with weapon and premeditation," and other typical patterns. Two levels of importance are then calculated:
- **Global Factor Importance**: The discriminative power of each factor across all archetypes (between-cluster variance ratio) → global ranking;
- **Archetype-Defining Factors**: The factors most prominent in each archetype relative to the global average + the typical sentence distribution for that archetype (median / range).

Outputs a readable, self-consistent `data/archetypes.json` (including normalization parameters and cluster centers).

**④ Conversational Sentencing Advice Agent (`advisor_agent.py`)**
Uses "case archetypes + hierarchical factor importance" as decision logic: extracts known factors from the user's colloquial description → cross-references **global factor importance** to ask about still-missing key factors → **matches the case to the nearest case archetype** (first narrows candidates by crime type, then measures distance only on known dimensions) → has the LLM provide an interpretable recommendation based on the archetype's statistical data (typical sentence range, defining factors), supported by precedent and accompanied by a legal disclaimer. All sentence numbers come from archetype statistics; the LLM is only responsible for explaining them clearly.

## Running

```bash
pip install -r requirements.txt
cp env.example .env        # Fill in OPENAI_API_KEY (default model gpt-5.6-luna)
python generate_data.py    # Optional: regenerate synthetic precedent dataset (data/cases.jsonl included)
python demo.py             # Run full pipeline: factor discovery → extraction → clustering → conversational advice
```

The first run will call the LLM for factor discovery (approx. 7 calls) and per-case extraction (approx. 66 calls), writing results to
`data/schema.json` and `data/extracted.jsonl` respectively; subsequent runs hit the cache directly and are nearly free.

## Sample Real Output (Excerpt)

```
Stage 1 Bottom-up discovered schema:
  Core general factors: prior_record / self_surrender / compensation /
               guilty_plea / victim_reconciliation ...
  Extension·Theft:  amount_stolen / gang_involvement / use_of_weapon
  Extension·Intentional Injury: injury_level[minor injury/grade 2 light injury/grade 2 severe injury] / premeditation ...
  Extension·Fraud:  amount_defrauded / victim_count / group_crime

Stage 3 Intra-crime clustering (k auto-selected by silhouette score) → 12 case archetypes total; global factor importance ranking:
  1. Crime type  2. Injury level=severe  3. Amount defrauded  4. Amount stolen  5. Gang crime  6. Premeditation ...
  ▸ Archetype#0 [Intentional Injury] median 2 months: injury level=minor injury(z=+2.5)
  ▸ Archetype#1 [Intentional Injury] median 42 months: injury level=severe injury grade 2(z=+3.9), premeditation(z=+1.8) —— "Severe injury with weapon and premeditation" type
  ▸ Archetype#5 [Theft]     median 51 months: high amount stolen, prior record/recidivism 100% ...

Stage 4 Conversation: identified theft case missing amount → asked about amount/guilty plea/reconciliation by importance → after completion, matched to Archetype#6
         (typical sentence median 40 months, range 24~50 months), and cited the archetype's key factors for advice.
```

## Data Description

`data/cases.jsonl` is a **bundled small-sample synthetic dataset** (66 cases, covering 3 crime types), generated by `generate_data.py`
using known sentencing formulas with added noise: each entry contains natural language `fact`, structured ground truth `gold`, and sentence length `label_months`.
The key point is that **factors are "written into" the case text during generation, and then "read back" from the text during the discovery phase**—factor discovery relies entirely
on the text, not on the field list used during generation, so the learned patterns come from the data itself.

**The real target dataset is CAIL2018** (Chinese criminal judgments, millions of entries). Synthetic small samples are used only because the full dataset is too large to conveniently distribute with the repository; to use real data, simply replace `generate_data.py` with code that reads CAIL's `data_*.json`
(each line containing `fact`, `meta.accusation`, `meta.term_of_imprisonment`), producing a `cases.jsonl` of the same structure. The discovery / extraction / clustering / conversation code requires no modification.

## Files

| File | Purpose |
|------|---------|
| `generate_data.py` | Generate synthetic multi-crime small-sample precedent dataset |
| `discovery.py` | Stage ①: Bottom-up factor discovery → modular schema |
| `extractor.py` | Stage ②: Structured extraction using discovered schema (with caching) |
| `archetypes.py` | Stage ③: Intra-crime clustering into case archetypes + hierarchical factor importance |
| `advisor_agent.py` | Stage ④: Conversational sentencing advice Agent (match nearest archetype) |
| `demo.py` | Full pipeline demonstration entry point |
| `config.py` | OpenAI client and model configuration |

## Limitations and Disclaimer

- This project is **for educational purposes only**, demonstrating the technical paradigm of "extracting tacit knowledge from structured data."
- The data is synthetic, the factor set is simplified, and clustering cannot capture the full complexity and non-linearity of real judicial sentencing.
- **No output from this project constitutes legal advice.** Real case sentencing is influenced by legal provisions, judicial interpretations,
  regional policies, and a large number of specific circumstances. Please consult a professional lawyer and do not make any legal decisions based on this.

## OpenRouter Universal Fallback

This experiment now supports a **universal OpenRouter fallback** for its chat LLM.

- If the primary provider key (e.g. `MOONSHOT_API_KEY` / `KIMI_API_KEY` / `OPENAI_API_KEY` / `DOUBAO_API_KEY` …) is present, behavior is unchanged.
- Else if `OPENROUTER_API_KEY` is set, the chat LLM is automatically routed through OpenRouter (`https://openrouter.ai/api/v1`). Model names are mapped automatically: `gpt-*`/`o1-*` → `openai/…`, `claude-*` → `anthropic/claude-opus-4.8`, `kimi-*` → `moonshotai/kimi-k2.6`, ids already containing `/` are kept as-is, and other provider-native ids (e.g. `doubao-*`) fall back to `openai/gpt-5.6-luna`. Set `OPENROUTER_MODEL` to force a specific OpenRouter model id.
- Else a clear error lists the accepted keys.

Add `OPENROUTER_API_KEY=...` to your `.env` (see `env.example`) to enable it.
