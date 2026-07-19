# Contextual Retrieval System - Educational Implementation

An educational implementation of Anthropic's Contextual Retrieval technique, demonstrating how contextualizing chunks before indexing dramatically improves retrieval accuracy in RAG systems.

## 🌟 Key Insight

**The Problem**: Traditional RAG systems lose context when chunking documents. A chunk saying "The company's revenue grew by 3%" loses meaning without knowing which company or time period.

**The Solution**: Contextual Retrieval prepends chunk-specific explanatory context to each chunk before embedding and indexing, preserving semantic meaning.

## 📊 Core Experiment: Offline Quantification of Retrieval Improvement (Experiment 3-11)

The Key Insight above is the core claim this project aims to validate. `compare_retrieval.py` uses a set of controlled comparative experiments to **fully offline** quantify it: it builds BM25 indexes for the same set of text chunks in two ways — without context (indexing only the raw text) and with context (indexing the LLM-generated prefix + raw text) — then compares `recall@k` (hit rate) on the evaluation set `evaluation/retrieval_eval.json` (15 queries + human-annotated gold text chunks). **No API or retrieval service required** (BM25 + jieba tokenization).

```bash
# Run the full comparison table (default corpus document_store.json, default evaluation set)
python compare_retrieval.py

# View hit ranking details for each query
python compare_retrieval.py --per-query

# Ad-hoc single query: side-by-side Top-K results without / with context
python compare_retrieval.py --query "What are the powers of the President?" --top-k 5

# View only the plain baseline / save machine-readable results
python compare_retrieval.py --mode plain
python compare_retrieval.py --output result.json

# Chinese --help
python compare_retrieval.py --help
```

Actual run output (22 text chunks from the Constitution and the Public Prosecutors Law, 15 queries, jieba tokenization):

```
Retrieval Recall Comparison: Plain Chunking  vs.  Context-Aware Retrieval (BM25)
====================================================================
Method                 recall@1    recall@3    recall@5
----------------------------------------------------
Plain (no context)          60.0%      86.7%      93.3%
Contextual (ctx)            86.7%      86.7%      93.3%
----------------------------------------------------
Improvement (Δpp)        +26.7pp      +0.0pp      +0.0pp
----------------------------------------------------
Failure rate reduction          67%          0%          0%
```

Conclusion consistent with the book: prepending a contextual prefix to text chunks significantly improves top-1 recall (60% → 86.7%, failure rate 1−recall@1 drops by 67%), as the prefix injects "identity tag"-like matchable keywords into BM25. This improvement is most pronounced at recall@1; the `--query` mode lets you intuitively see how the prefix re-ranks the text chunk belonging to the correct chapter to the top.

> `--method embedding` / `--method hybrid` (contextual vector embeddings + RRF fusion) require calling an embedding API and cannot run offline; the script will prompt and fall back to BM25 offline results.
> The full implementation of dense retrieval + reranking is in `contextual_tools.py`.

The same comparison logic is also built into `ContextualChunker.compare_retrieval_methods()` (the `compare_retrieval_methods` functionality in the book), allowing side-by-side retrieval comparison directly on any set of `ContextualChunk` objects.

## 📚 Educational Features

This implementation includes extensive logging and comparison capabilities to understand:

1. **How Context Generation Works**: Watch the LLM generate context for each chunk
2. **Dual Indexing Strategy**: See how both BM25 and embeddings benefit from context
3. **Comparison Mode**: Run with `use_contextual=False` to compare against standard chunking
4. **Performance Metrics**: Track improvements in retrieval accuracy
5. **Cost Analysis**: Understand the token usage and costs

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│           Document Input                │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│          Basic Chunking                 │
│   (Respects paragraph boundaries)       │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│     Context Generation (Optional)       │
│         Using LLM API                   │
│   (Enabled with use_contextual=True)   │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│      Enhanced Chunks                    │
│  • Contextual: Context + Original Text  │
│  • Standard: Original Text Only         │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│      Retrieval Pipeline Indexing        │
│   • Sparse Index (BM25)                 │
│   • Dense Index (Embeddings)            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│    Hybrid Search with Reranking         │
│   Combines BM25 + Embedding scores      │
│   Cross-encoder reranking for accuracy  │
└─────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Installation

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp env.example .env

# Edit .env and add your API keys:
# - MOONSHOT_API_KEY for Kimi
# - ARK_API_KEY for Doubao
# - OPENAI_API_KEY for OpenAI
# - etc.
```

### 3. Start the Retrieval Pipeline

```bash
# In a separate terminal, start the retrieval pipeline server
cd ../retrieval-pipeline
python main.py
# Server will run on http://localhost:4242
```

### 4. Index Documents

```bash
# Index Chinese law documents with contextual enhancement
python index_local_laws_contextual.py

# Or index without contextual enhancement for comparison
python index_local_laws_contextual.py --no-contextual
```

### 5. Run Queries

```bash
# Interactive mode with contextual retrieval
python main.py

# Query with specific mode
python main.py --query "What is Article 1 of the Constitution?" --mode agentic

# Compare agentic vs non-agentic modes
python main.py --query "What is Article 1 of the Constitution?" --mode compare
```

## Context Generation Process

The system generates context for each chunk by:

1. **Providing the full document** (or surrounding context) to the LLM
2. **Showing the specific chunk** to be contextualized
3. **Asking for concise context** (2-3 sentences) that situates the chunk

Example prompt template:
```
<document>
[Full document or surrounding context]
</document>

Here is the chunk we want to situate:
<chunk>
[Specific chunk text]
</chunk>

Please give a short, succinct context to situate this chunk within the overall document...
```

## 📚 References

- [Anthropic's Contextual Retrieval Blog Post](https://www.anthropic.com/engineering/contextual-retrieval)

## 🤝 Contributing

This is an educational implementation. Contributions welcome for:- Additional chunking strategies
- Alternative context generation prompts
- Performance optimizations
- Evaluation metrics
- Visualization tools

## 📝 License

Educational project for learning purposes.

## 🙏 Acknowledgments

Based on research by Anthropic's engineering team on improving RAG retrieval accuracy through contextual enhancement.

## OpenRouter Universal Fallback

This experiment now supports a **universal OpenRouter fallback** for its chat LLM.

- If the primary provider key (e.g. `MOONSHOT_API_KEY` / `KIMI_API_KEY` / `OPENAI_API_KEY` / `DOUBAO_API_KEY` …) is present, behavior is unchanged.
- Else if `OPENROUTER_API_KEY` is set, the chat LLM is automatically routed through OpenRouter (`https://openrouter.ai/api/v1`). Model names are mapped automatically: `gpt-*`/`o1-*` → `openai/…`, `claude-*` → `anthropic/claude-opus-4.8`, `kimi-*` → `moonshotai/kimi-k2.6`, ids already containing `/` are kept as-is, and other provider-native ids (e.g. `doubao-*`) fall back to `openai/gpt-5.6-luna`. Set `OPENROUTER_MODEL` to force a specific OpenRouter model id.
- Else a clear error lists the accepted keys.

Add `OPENROUTER_API_KEY=...` to your `.env` (see `env.example`) to enable it.
