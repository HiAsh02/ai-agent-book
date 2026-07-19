"""Offline comparison: Impact of contextualized memory chunks vs. raw memory chunks on 'user fact recall' (Experiment 3-12).

This module is a **fully offline, no API/external service required** controlled experiment to quantify the core argument of this chapter:
Before feeding dialogue memory chunks into indexing/embedding, first generating a 'context prefix' (situational anchor) for each chunk
can significantly improve the recall probability of out-of-context isolated fragments (e.g., 'Okay, let's go with this one').

Method description (honesty boundary):
- In production pipeline, LLM generates context for each chunk, and neural embedding + retrieval service is used for dense/hybrid retrieval (requires API Key).
- Here, **deterministic BM25 lexical retrieval** is used as a proxy that requires no API: for the same context,
  measure recall for two methods: 'plain (no concatenation)' vs. 'contextual (concatenated before indexing)'.
  The only variable is whether the indexed text contains the context prefix, so the result directly reflects the contribution of contextualization itself.
- Metrics: Recall@1, Recall@3, MRR (same definition as recall@k in the book: hit if any of the top k results is a recall).

Dataset is in the same directory: memory_qa_eval.json (controlled teaching set, can be replaced with --dataset).
"""

import argparse
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_DATASET = str(Path(__file__).parent / "memory_qa_eval.json")

_CJK = r"一-鿿"


def tokenize(text: str) -> List[str]:
    """CJK-aware lightweight tokenization: English/numbers by word, Chinese by 'single character + adjacent bigram'.

    Preserve positional adjacency for adjacent bigrams to avoid spurious bigrams across segments.
    """
    text = text.lower()
    tokens: List[str] = []
    tokens.extend(re.findall(r"[a-z0-9]+", text))
    for run in re.findall(f"[{_CJK}]+", text):
        chars = list(run)
        tokens.extend(chars)
        for i in range(len(chars) - 1):
            tokens.append(chars[i] + chars[i + 1])
    return tokens


class BM25:
    """Standard BM25, pure Python implementation, no third-party dependencies."""

    def __init__(self, corpus_tokens: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus_tokens
        self.N = len(corpus_tokens)
        self.doc_len = [len(d) for d in corpus_tokens]
        self.avgdl = sum(self.doc_len) / self.N if self.N else 0.0
        self.tf: List[Dict[str, int]] = []
        df: Dict[str, int] = {}
        for doc in corpus_tokens:
            counts: Dict[str, int] = {}
            for t in doc:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts:
                df[t] = df.get(t, 0) + 1
        self.idf = {
            t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()
        }

    def score(self, query_tokens: List[str], idx: int) -> float:
        counts = self.tf[idx]
        dl = self.doc_len[idx]
        s = 0.0
        for t in query_tokens:
            if t not in counts:
                continue
            idf = self.idf.get(t, 0.0)
            freq = counts[t]
            denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            s += idf * (freq * (self.k1 + 1)) / denom
        return s

    def rank(self, query_tokens: List[str]) -> List[int]:
        scored = [(self.score(query_tokens, i), i) for i in range(self.N)]
        #  Stable sort: descending by score, ascending by original index for ties
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [i for _, i in scored]


def _gold_rank(ranked_ids: List[str], gold_id: str) -> int:
    """Returns the rank of gold in the sorted results (1-based); returns 0 if not found."""
    for pos, cid in enumerate(ranked_ids, start=1):
        if cid == gold_id:
            return pos
    return 0


def evaluate(chunks: List[dict], queries: List[dict], mode: str) -> Tuple[dict, List[dict]]:
    """Index and retrieve according to the specified mode, returning aggregated metrics and per-item details.

    mode='plain'      index text = chunk['text']
    mode='contextual' index text = chunk['context'] + '\n' + chunk['text']
    """
    ids = [c["id"] for c in chunks]
    if mode == "plain":
        docs = [c["text"] for c in chunks]
    elif mode == "contextual":
        docs = [f"{c.get('context','')}\n{c['text']}" for c in chunks]
    else:
        raise ValueError(f"unknown mode: {mode}")

    bm25 = BM25([tokenize(d) for d in docs])

    r1 = r3 = 0
    mrr = 0.0
    details = []
    for q in queries:
        ranked = [ids[i] for i in bm25.rank(tokenize(q["q"]))]
        rank = _gold_rank(ranked, q["gold"])
        hit1 = 1 if rank == 1 else 0
        hit3 = 1 if 1 <= rank <= 3 else 0
        r1 += hit1
        r3 += hit3
        mrr += (1.0 / rank) if rank else 0.0
        details.append({"q": q["q"], "gold": q["gold"], "rank": rank,
                        "hit@1": hit1, "hit@3": hit3, "top": ranked[:3]})

    n = len(queries)
    metrics = {
        "recall@1": r1 / n,
        "recall@3": r3 / n,
        "mrr": mrr / n,
        "n_queries": n,
    }
    return metrics, details


def run_comparison(dataset_path: str, output_path: str = None, verbose: bool = True) -> dict:
    data = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    chunks, queries = data["chunks"], data["queries"]

    plain_m, plain_d = evaluate(chunks, queries, "plain")
    ctx_m, ctx_d = evaluate(chunks, queries, "contextual")

    if verbose:
        print("=" * 68)
        print("Experiment 3-12 · Impact of Contextualized Memory Blocks on User Fact Recall (Offline BM25 Agent)")
        print(f"Dataset: {dataset_path}")
        print(f"Memory block: {len(chunks)}  Query: {len(queries)}")
        print("=" * 68)
        print(f"{'Method':<28}{'Recall@1':>10}{'Recall@3':>10}{'MRR':>10}")
        print("-" * 68)
        print(f"{'Plain (directly index original block)':<24}{plain_m['recall@1']:>10.3f}"
              f"{plain_m['recall@3']:>10.3f}{plain_m['mrr']:>10.3f}")
        print(f"{'Contextual (contextualized index)':<22}{ctx_m['recall@1']:>10.3f}"
              f"{ctx_m['recall@3']:>10.3f}{ctx_m['mrr']:>10.3f}")
        print("-" * 68)
        d1 = ctx_m["recall@1"] - plain_m["recall@1"]
        d3 = ctx_m["recall@3"] - plain_m["recall@3"]
        dm = ctx_m["mrr"] - plain_m["mrr"]
        print(f"{'Boost (Δ)':<26}{d1:>+10.3f}{d3:>+10.3f}{dm:>+10.3f}")
        print("=" * 68)
        print("\nQuery ranking (position of gold in retrieval results, smaller is better; 0 means not recalled):")
        print(f"{'Query':<38}{'Plain':>8}{'Ctx':>8}")
        print("-" * 68)
        pd = {x["q"]: x["rank"] for x in plain_d}
        for x in ctx_d:
            q = x["q"][:36]
            print(f"{q:<38}{pd[x['q']]:>8}{x['rank']:>8}")
        print("=" * 68)
        print("Note: Isolated fragments (e.g., \"Okay, let's book this one\") lack retrievable signals under Plain.")
        print("After being contextualized and 'anchored' back to its context, the recall ranking is significantly improved.")

    result = {
        "dataset": dataset_path,
        "n_chunks": len(chunks),
        "plain": plain_m,
        "contextual": ctx_m,
        "delta": {
            "recall@1": ctx_m["recall@1"] - plain_m["recall@1"],
            "recall@3": ctx_m["recall@3"] - plain_m["recall@3"],
            "mrr": ctx_m["mrr"] - plain_m["mrr"],
        },
        "plain_details": plain_d,
        "contextual_details": ctx_d,
    }

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        if verbose:
            print(f"\nResult saved to: {output_path}")

    return result


def single_query(dataset_path: str, query: str, top_k: int = 3, verbose: bool = True) -> dict:
    """For a single query, offline compare the Top-K retrieval results under plain and contextual indexes."""
    data = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    chunks = data["chunks"]
    ids = [c["id"] for c in chunks]
    qt = tokenize(query)

    out = {"query": query}
    for mode in ("plain", "contextual"):
        if mode == "plain":
            docs = [c["text"] for c in chunks]
        else:
            docs = [f"{c.get('context','')}\n{c['text']}" for c in chunks]
        bm25 = BM25([tokenize(d) for d in docs])
        ranked = bm25.rank(qt)
        out[mode] = [{"id": ids[i], "score": round(bm25.score(qt, i), 4)}
                     for i in ranked[:top_k]]

    if verbose:
        print("=" * 60)
        print(f"Query: {query}")
        print("=" * 60)
        for mode in ("plain", "contextual"):
            label = "Plain (raw block)" if mode == "plain" else "Contextual"
            print(f"\n[{label}] Top-{top_k}:")
            for rank, item in enumerate(out[mode], 1):
                print(f"  {rank}. {item['id']:<18} score={item['score']}")
        print("=" * 60)
    return out


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Offline Comparison of Contextualized Memory Chunks vs. Raw Memory Chunks for User Fact Recall (Experiment 3-12, No API Required)",
    )
    p.add_argument("--dataset", default=DEFAULT_DATASET,
                   help="Memory QA comparison set JSON path (default: memory_qa_eval.json)")
    p.add_argument("--output", default=None,
                   help="Path to save the comparison results (including per-query details) as JSON (not saved by default)")
    p.add_argument("--quiet", action="store_true", help="Output only the result JSON, do not print the table")
    return p


def main():
    args = build_arg_parser().parse_args()
    run_comparison(args.dataset, output_path=args.output, verbose=not args.quiet)


if __name__ == "__main__":
    main()
