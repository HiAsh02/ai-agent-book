"""Offline comparison experiment: Agentic RAG (multi-turn/decomposed retrieval) vs. Non-agentic RAG (single-shot retrieval).

This script runs **completely offline**—it only performs retrieval, does not call any LLM, and does not rely on external retrieval services,
so it can be reproduced without an API key. It uses a small Chinese judicial QA dataset (evaluation/offline_qa.json)
to quantitatively compare the 'evidence recall' of two retrieval paradigms:

  - Non-agentic: Use the user's original question as the only query for a single retrieval (single-shot);
  - Agentic: Simulate an agent decomposing/rewriting the question to perform multiple retrievals, then take the union of results.

The gold standard (gold_articles) is the set of legal article numbers required to answer each question; an article is considered 'hit'
if and only if there exists a chunk in the retrieval results that starts with that article number. Evidence recall = number of hit gold articles
/ total number of gold articles. This retrieval-level metric is the upper bound of answer quality: if evidence is not retrieved, generation cannot begin.
End-to-end evaluation at the generation stage (requires LLM API) is in evaluation/evaluate.py.
"""

import os
import re
import sys
import json
import time
import argparse
from typing import List, Dict, Any

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from offline_retriever import OfflineRetriever, _ARTICLE_RE


def _leading_article(text: str) -> str:
    """Extract the legal article number at the beginning of the chunk (e.g., 'Article 235'), return empty string if none."""
    m = _ARTICLE_RE.match(text.strip())
    return m.group(0) if m else ""


def _covered(retrieved: List[Dict[str, Any]], gold_articles: List[str]) -> List[str]:
    """Return the list of gold standard articles hit by the retrieval results."""
    hit_markers = {_leading_article(r["text"]) for r in retrieved}
    hit_markers.discard("")
    return [g for g in gold_articles if g in hit_markers]


def run_case(retriever: OfflineRetriever, case: Dict[str, Any], top_k: int) -> Dict[str, Any]:
    gold = case["gold_articles"]

    #  Non-agentic: Single retrieval, query is the user's original question.
    naive_query = case.get("naive_query", case["question"])
    naive_hits = retriever.search(naive_query, top_k)
    naive_covered = _covered(naive_hits, gold)

    #  Agentic: Decompose into multiple sub-queries, retrieve each, then take the union.
    subqueries = case.get("subqueries") or [case["question"]]
    agentic_hits: List[Dict[str, Any]] = []
    seen = set()
    for sq in subqueries:
        for r in retriever.search(sq, top_k):
            if r["chunk_id"] not in seen:
                seen.add(r["chunk_id"])
                agentic_hits.append(r)
    agentic_covered = _covered(agentic_hits, gold)

    return {
        "id": case["id"],
        "question": case["question"],
        "difficulty": case.get("difficulty", "unknown"),
        "gold_articles": gold,
        "naive": {
            "num_searches": 1,
            "covered": naive_covered,
            "recall": len(naive_covered) / len(gold) if gold else 0.0,
        },
        "agentic": {
            "num_searches": len(subqueries),
            "covered": agentic_covered,
            "recall": len(agentic_covered) / len(gold) if gold else 0.0,
        },
    }


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _pad(text: str, width: int) -> str:
    """Left-aligned by display width (one Chinese character counts as two widths)."""
    display = sum(2 if ord(c) > 127 else 1 for c in text)
    return text + " " * max(0, width - display)


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    def agg(subset):
        return {
            "count": len(subset),
            "naive_recall": _mean([r["naive"]["recall"] for r in subset]),
            "agentic_recall": _mean([r["agentic"]["recall"] for r in subset]),
            "naive_searches": _mean([r["naive"]["num_searches"] for r in subset]),
            "agentic_searches": _mean([r["agentic"]["num_searches"] for r in subset]),
        }

    summary = {"overall": agg(results)}
    for diff in ("easy", "hard"):
        subset = [r for r in results if r["difficulty"] == diff]
        if subset:
            summary[diff] = agg(subset)
    return summary


def print_table(results: List[Dict[str, Any]], summary: Dict[str, Any]):
    print("\n" + "=" * 78)
    print("Offline Retrieval Comparison: Evidence Recall")
    print("=" * 78)
    print(_pad("Question", 30) + _pad("Difficulty", 8) + _pad("Single-shot Retrieval", 12)
          + _pad("Decomposed Retrieval", 12) + "Retrieval Count")
    print("-" * 78)
    for r in results:
        q = (r["question"][:13] + "…") if len(r["question"]) > 13 else r["question"]
        naive = f"{r['naive']['recall']:.0%}"
        agentic = f"{r['agentic']['recall']:.0%}"
        searches = f"1 → {r['agentic']['num_searches']}"
        print(_pad(q, 30) + _pad(r["difficulty"], 8) + _pad(naive, 12)
              + _pad(agentic, 12) + searches)
    print("-" * 78)

    def row(name, s):
        print(_pad(name, 30) + _pad("", 8) + _pad(f"{s['naive_recall']:.0%}", 12)
              + _pad(f"{s['agentic_recall']:.0%}", 12)
              + f"{s['naive_searches']:.1f} → {s['agentic_searches']:.1f}")

    print("Aggregate Metrics (Average Evidence Recall):")
    row("  All", summary["overall"])
    if "easy" in summary:
        row("  Easy", summary["easy"])
    if "hard" in summary:
        row("  Hard", summary["hard"])
    print("=" * 78)
    ov = summary["overall"]
    lift = ov["agentic_recall"] - ov["naive_recall"]
    print(f"Conclusion: Decomposed multi-turn retrieval improves overall evidence recall from {ov['naive_recall']:.0%} "
          f" to {ov['agentic_recall']:.0%}（+{lift:.0%}），"
          f"at the cost of increasing the average retrieval count from {ov['naive_searches']:.1f} to {ov['agentic_searches']:.1f}。")
    if "hard" in summary:
        hv = summary["hard"]
        print(f"      The gap is most significant on hard questions:{hv['naive_recall']:.0%} → {hv['agentic_recall']:.0%}。")
    print("=" * 78)


def main():
    parser = argparse.ArgumentParser(
        description="Offline comparison of evidence recall between agentic RAG (multi-turn decomposed retrieval) and non-agentic RAG (single-shot retrieval); pure retrieval, no LLM or external services required.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--dataset", type=str, default="evaluation/offline_qa.json",
                        help="Offline QA dataset path (default: evaluation/offline_qa.json)")
    parser.add_argument("--corpus", type=str, default="laws",
                        help="Legal corpus directory for building offline BM25 index (default: laws)")
    parser.add_argument("--top-k", type=int, default=5,
                        help="Number of chunks returned per retrieval, i.e., retrieval depth (default: 5)")
    parser.add_argument("--output", type=str, default=None,
                        help="JSON file path to write detailed results (default: do not write to disk, only print)")
    args = parser.parse_args()

    print(f"[Offline Comparison] Building BM25 index, corpus directory: {args.corpus} …")
    t0 = time.time()
    retriever = OfflineRetriever(args.corpus)
    print(f"[Offline Comparison] Indexing complete: {len(retriever.chunks)} legal article chunks / "
          f"{len(retriever.documents)} documents, elapsed time {time.time() - t0:.1f}s")

    with open(args.dataset, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    cases = dataset["cases"]

    results = [run_case(retriever, c, args.top_k) for c in cases]
    summary = summarize(results)
    print_table(results, summary)

    if args.output:
        payload = {
            "dataset": args.dataset,
            "corpus": args.corpus,
            "top_k": args.top_k,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results,
            "summary": summary,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\nDetailed results saved to: {args.output}")


if __name__ == "__main__":
    main()
