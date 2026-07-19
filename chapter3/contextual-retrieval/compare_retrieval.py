#!/usr/bin/env python3
"""Context-Aware Retrieval Benchmark (Experiment 3-11)

This script uses controlled comparative experiments to quantify the recall improvement of "context-aware retrieval" over traditional chunking:
The same set of text chunks is indexed with BM25 in two ways:

  * Without context (plain): index only the original text chunk metadata.original_text
  * With context (contextual): index LLM-generated prefix + original text chunk (content field)

Then compare recall@k (hit rate: whether the relevant chunk appears in the top k results) on the same evaluation set.
This is the core claim of Anthropic's "Contextual Retrieval": adding a context prefix to text chunks
can enhance recall for both BM25 (sparse) and vector (dense) retrieval.

BM25 retrieval is fully offline, requiring no API or retrieval service; embedding/hybrid methods require
calling an embedding API (see --method description).

Usage examples:
  python compare_retrieval.py                       # Run comparison table with default eval set
  python compare_retrieval.py --query "What are the powers of the President?"   # Single query side-by-side comparison
  python compare_retrieval.py --mode plain          # Only baseline without context
  python compare_retrieval.py --output result.json  # Save machine-readable results
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from rank_bm25 import BM25Okapi

try:
    import jieba
    if hasattr(jieba, "setLogLevel"):
        jieba.setLogLevel(60)  #Suppress jieba loading logs
    _HAS_JIEBA = True
except Exception:  # pragma: no cover - jieba is usually installed via requirements
    _HAS_JIEBA = False


# ---------------------------------------------------------------------------
# Tokenization: Chinese has no spaces, so .split() treats the whole segment as one token, making BM25 completely ineffective.
# Default uses jieba tokenization; with --no-jieba, falls back to character bigrams, also runnable offline.
# ---------------------------------------------------------------------------
def tokenize(text: str, use_jieba: bool = True) -> List[str]:
    """Split text into token list for BM25."""
    text = (text or "").lower()
    if use_jieba and _HAS_JIEBA:
        return [t for t in jieba.cut(text) if t.strip()]
    # Fallback scheme: Chinese character bigrams + contiguous ASCII words
    tokens: List[str] = []
    buf = ""
    chars = list(text)
    for ch in chars:
        if ch.isascii() and (ch.isalnum()):
            buf += ch
            continue
        if buf:
            tokens.append(buf)
            buf = ""
        if not ch.isspace():
            tokens.append(ch)
    if buf:
        tokens.append(buf)
    # Append Chinese bigrams to improve matching granularity
    cjk = [c for c in text if "一" <= c <= "鿿"]
    tokens.extend(cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1))
    return tokens


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------
def load_corpus(path: str) -> List[Dict]:
    """Load chunks from document_store.json, return [{chunk_id, contextual, plain, context}].

    Each chunk's content field is "context prefix + original text", metadata.original_text
    is the original text without context, used for comparison between the two indexing methods.
    """
    with open(path, "r", encoding="utf-8") as f:
        store = json.load(f)

    chunks: List[Dict] = []
    for chunk_id, entry in store.items():
        if "_chunk_" not in chunk_id:
            continue  #Skip whole-document entries
        if not isinstance(entry, dict):
            continue
        meta = entry.get("metadata", {}) or {}
        contextual_text = entry.get("content", "") or ""
        plain_text = meta.get("original_text") or contextual_text
        #Context prefix = contextual minus trailing original_text
        context = contextual_text
        if plain_text and contextual_text.endswith(plain_text):
            context = contextual_text[: len(contextual_text) - len(plain_text)].strip()
        chunks.append({
            "chunk_id": chunk_id,
            "contextual": contextual_text,
            "plain": plain_text,
            "context": context,
        })
    return chunks


def load_eval(path: str) -> List[Dict]:
    """Load evaluation set, return [{id, query, gold_chunk_id, ...}]."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("queries", data if isinstance(data, list) else [])


# ---------------------------------------------------------------------------
# BM25 Retriever
# ---------------------------------------------------------------------------
class BM25Retriever:
    """Simple retriever that builds a BM25 index over a given text field."""

    def __init__(self, chunks: List[Dict], field: str, use_jieba: bool = True):
        self.chunk_ids = [c["chunk_id"] for c in chunks]
        self.use_jieba = use_jieba
        corpus_tokens = [tokenize(c[field], use_jieba) for c in chunks]
        self.index = BM25Okapi(corpus_tokens)

    def rank(self, query: str) -> List[str]:
        """Return chunk_id list sorted by relevance descending."""
        scores = self.index.get_scores(tokenize(query, self.use_jieba))
        order = np.argsort(scores)[::-1]
        return [self.chunk_ids[i] for i in order]

    def scored(self, query: str, top_k: int) -> List[Dict]:
        """Return top_k results with scores."""
        scores = self.index.get_scores(tokenize(query, self.use_jieba))
        order = np.argsort(scores)[::-1][:top_k]
        return [{"chunk_id": self.chunk_ids[i], "score": float(scores[i])} for i in order]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def recall_at_k(retriever: BM25Retriever, queries: List[Dict], ks: List[int]) -> Dict:
    """Compute recall@k (hit rate) for a batch of queries at various k values."""
    per_query = []
    hits = {k: 0 for k in ks}
    for q in queries:
        ranking = retriever.rank(q["query"])
        gold = q["gold_chunk_id"]
        rank_pos = ranking.index(gold) + 1 if gold in ranking else None
        row = {"id": q.get("id"), "query": q["query"], "gold": gold, "rank": rank_pos}
        for k in ks:
            hit = rank_pos is not None and rank_pos <= k
            row[f"hit@{k}"] = hit
            if hit:
                hits[k] += 1
        per_query.append(row)
    n = len(queries)
    recall = {k: (hits[k] / n if n else 0.0) for k in ks}
    return {"recall": recall, "per_query": per_query, "n": n}


def print_comparison_table(plain: Optional[Dict], contextual: Optional[Dict], ks: List[int]):
    """Print recall@k comparison table."""
    print("\n" + "=" * 68)
    print("Retrieval Recall Comparison: Non-contextual Chunks vs. Context-Aware Retrieval (BM25)")
    print("=" * 68)
    header = "  k  | " + " | ".join(f"{'No Context':>10}" if False else f"recall@{k:<3}" for k in ks)
    #Print each method line by line
    col_w = 12
    line = f"{'Method':<16}" + "".join(f"recall@{k}".rjust(col_w) for k in ks)
    print(line)
    print("-" * len(line))
    if plain:
        print(f"{'No Context (plain)':<16}" + "".join(f"{plain['recall'][k]*100:>10.1f}%" for k in ks))
    if contextual:
        print(f"{'With Context (ctx)':<16}" + "".join(f"{contextual['recall'][k]*100:>10.1f}%" for k in ks))
    if plain and contextual:
        print("-" * len(line))
        deltas = []
        for k in ks:
            d = (contextual["recall"][k] - plain["recall"][k]) * 100
            deltas.append(f"{d:>+9.1f}pp")
        print(f"{'Improvement (Δpp)':<16}" + "".join(s.rjust(col_w) for s in deltas))
        # Retrieval failure rate decrease (corresponding to "1 - recall@k" metric in the book)
        print("-" * len(line))
        fails = []
        for k in ks:
            p_fail = 1 - plain["recall"][k]
            c_fail = 1 - contextual["recall"][k]
            if p_fail > 0:
                red = (p_fail - c_fail) / p_fail * 100
                fails.append(f"{red:>9.0f}%")
            else:
                fails.append(f"{'-':>10}")
        print(f"{'Failure rate decreased':<16}" + "".join(s.rjust(col_w) for s in fails))
    print("=" * 68)


def print_per_query(result: Dict, label: str):
    print(f"\n[{label}] Rank of gold chunk in results for each query (— indicates not recalled)")
    for row in result["per_query"]:
        print(f"  {row['id']}  rank={str(row['rank']):>3}  gold={row['gold']:<28} {row['query'][:32]}")


# ---------------------------------------------------------------------------
# Side-by-side comparison for a single query
# ---------------------------------------------------------------------------
def single_query_compare(chunks: List[Dict], query: str, top_k: int, use_jieba: bool,
                         mode: str):
    id2chunk = {c["chunk_id"]: c for c in chunks}

    def show(field_label, field):
        retr = BM25Retriever(chunks, field, use_jieba)
        print(f"\n[{field_label}] Top-{top_k}")
        print("-" * 60)
        for i, r in enumerate(retr.scored(query, top_k), 1):
            c = id2chunk[r["chunk_id"]]
            snippet = c["plain"].replace("<!-- FORCE BREAK -->", "").replace("\n", " ").strip()[:48]
            ctx = c["context"].replace("\n", " ").strip()[:40]
            print(f"  {i}. score={r['score']:6.2f}  {r['chunk_id']}")
            if field == "contextual" and ctx:
                print(f"       Context prefix: {ctx}")
            print(f"       Original text: {snippet}")

    print("\n" + "=" * 60)
    print(f"Query: {query}")
    print("=" * 60)
    if mode in ("plain", "both"):
        show("No Context (plain)", "plain")
    if mode in ("contextual", "both"):
        show("With context (contextual)", "contextual")


# ---------------------------------------------------------------------------
# Optional: embedding / hybrid (requires API)
# ---------------------------------------------------------------------------
def embedding_unavailable_notice(method: str):
    print(f"\n[Prompt] --method {method} Requires embedding API (dense vectors), cannot run offline.")
    print("       Please configure OPENAI_API_KEY / SILICONFLOW_API_KEY etc. in .env,")
    print("       and use contextual_tools.ContextualKnowledgeBaseTools for embedding/hybrid retrieval.")
    print("       The default --method bm25 in this script can fully reproduce the recall improvement conclusion of \"context-augmented BM25\" in the book.")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Context-aware retrieval comparison evaluation: quantify the improvement of context prefix on retrieval recall@k (Experiment 3-11)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n"
               "  python compare_retrieval.py\n"
               "  python compare_retrieval.py --query \"What are the powers of the President?\" --top-k 5\n"
               "  python compare_retrieval.py --mode both --k 1 3 5 --output result.json",
    )
    p.add_argument("--corpus", default="document_store.json",
                   help="Corpus file (chunked storage with content and metadata.original_text), default document_store.json")
    p.add_argument("--eval", dest="eval_path", default="evaluation/retrieval_eval.json",
                   help="Evaluation set (query + gold_chunk_id), default evaluation/retrieval_eval.json")
    p.add_argument("--query", default=None,
                   help="Temporary single query: side-by-side display of Top-K retrieval results with/without context (does not run full evaluation set)")
    p.add_argument("--mode", choices=["plain", "contextual", "both"], default="both",
                   help="Which index to compare: plain=only without context, contextual=only with context, both=compare both (default)")
    p.add_argument("--method", choices=["bm25", "embedding", "hybrid"], default="bm25",
                   help="Retrieval method: bm25 (offline, default); embedding/hybrid requires embedding API")
    p.add_argument("--k", nargs="+", type=int, default=[1, 3, 5],
                   help="List of k values for evaluation (recall@k), default 1 3 5")
    p.add_argument("--top-k", type=int, default=5,
                   help="--query Number of results to display per method in single query mode, default 5")
    p.add_argument("--model", default=None,
                   help="Embedding model name (only effective when --method embedding/hybrid)")
    p.add_argument("--no-jieba", action="store_true",
                   help="Disable jieba tokenization, use character bigram tokenization (no jieba dependency)")
    p.add_argument("--output", default=None,
                   help="Write machine-readable evaluation results to this JSON file")
    p.add_argument("--per-query", action="store_true",
                   help="Print hit rank details for each query")
    return p


def main():
    args = build_arg_parser().parse_args()
    use_jieba = not args.no_jieba

    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        print(f"[Error] Cannot find corpus file: {corpus_path}", file=sys.stderr)
        sys.exit(1)

    chunks = load_corpus(str(corpus_path))
    if not chunks:
        print(f"[Error] No available chunks in corpus (missing *_chunk_* entries): {corpus_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(chunks)} text block | tokenization: {'jieba' if (use_jieba and _HAS_JIEBA) else 'character bigram'} "
          f"| retrieval method: {args.method}")

    if args.method in ("embedding", "hybrid"):
        embedding_unavailable_notice(args.method)
        # still use BM25 to provide runnable offline results
        print("       below, switch to BM25 to provide offline baseline results.\n")

    # single query mode
    if args.query:
        single_query_compare(chunks, args.query, args.top_k, use_jieba, args.mode)
        return

    # evaluation set mode
    eval_path = Path(args.eval_path)
    if not eval_path.exists():
        print(f"[error] evaluation set not found: {eval_path}", file=sys.stderr)
        sys.exit(1)
    queries = load_eval(str(eval_path))
    ks = sorted(set(args.k))

    plain_res = contextual_res = None
    if args.mode in ("plain", "both"):
        plain_res = recall_at_k(BM25Retriever(chunks, "plain", use_jieba), queries, ks)
    if args.mode in ("contextual", "both"):
        contextual_res = recall_at_k(BM25Retriever(chunks, "contextual", use_jieba), queries, ks)

    print(f"evaluation set: {eval_path}  total {len(queries)} queries")
    print_comparison_table(plain_res, contextual_res, ks)

    if args.per_query:
        if plain_res:
            print_per_query(plain_res, "no context plain")
        if contextual_res:
            print_per_query(contextual_res, "with context contextual")

    if args.output:
        out = {
            "corpus": str(corpus_path),
            "eval": str(eval_path),
            "num_chunks": len(chunks),
            "num_queries": len(queries),
            "tokenizer": "jieba" if (use_jieba and _HAS_JIEBA) else "char-bigram",
            "k": ks,
            "plain": plain_res,
            "contextual": contextual_res,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\nresults written to {args.output}")


if __name__ == "__main__":
    main()
