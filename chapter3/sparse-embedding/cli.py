#!/usr/bin/env python3
"""
Sparse retrieval command-line tool (Experiment 3-5)

Run BM25 sparse retrieval on a small example corpus, supporting:
  - Custom corpus / query / top-k / output file
  - --explain reproduces the "per-word IDF / TF / BM25 contribution" log from the book
  - --eval computes recall@k / precision@k / MRR on a small annotated evaluation set
  - --method splade learned sparse retrieval (requires model download; offline environment will show a hint)

When run without any arguments, it is equivalent to the default demo of Experiment 3-5 in the book (query "model distillation").
"""

import argparse
import json
import logging
import sys
from typing import Dict, List, Optional, Set, Tuple

from bm25_engine import SparseSearchEngine


# ---------------------------------------------------------------------------
#  Built-in example corpus and annotations (English, consistent with the engine's tokenizer, fully reproducible offline)
#  The corpus deliberately mixes: common words, proprietary code, technical abbreviations, and documents with only "synonymous expressions",
#  to simultaneously demonstrate BM25's strength in exact keyword matching and its weakness in synonyms.
# ---------------------------------------------------------------------------
DEFAULT_CORPUS: List[Dict] = [
    {"doc_id": "doc_1", "title": "Python Language",
     "text": "Python is a high-level programming language known for readability and a simple syntax."},
    {"doc_id": "doc_2", "title": "JavaScript Runtime",
     "text": "JavaScript runs in the browser and on servers via Node.js for full-stack web development."},
    {"doc_id": "doc_3", "title": "Model Distillation",
     "text": "Model distillation compresses a large teacher model into a smaller student model while preserving accuracy."},
    {"doc_id": "doc_4", "title": "Knowledge Distillation",
     "text": "Knowledge distillation transfers knowledge from a big neural network to a compact model for efficient inference."},
    {"doc_id": "doc_5", "title": "BM25 Ranking",
     "text": "BM25 is a probabilistic ranking function using term frequency and inverse document frequency."},
    {"doc_id": "doc_6", "title": "HTTP Errors",
     "text": "The HTTP 404 error code means the requested resource was not found on the web server."},
    {"doc_id": "doc_7", "title": "A Playful Kitten",
     "text": "A cute kitten chased a ball of yarn across the living room floor all afternoon."},
    {"doc_id": "doc_8", "title": "Silent Hunter",
     "text": "The feline predator stalked its prey silently through the tall grass at dusk."},
    {"doc_id": "doc_9", "title": "Hardware Fault",
     "text": "Error code XK9-2B4-7Q1 indicates a hardware fault in the storage controller board."},
    {"doc_id": "doc_10", "title": "Transformers",
     "text": "Transformer models use self-attention to process input sequences in parallel efficiently."},
]

# query -> set of relevant document doc_ids (human-annotated ground truth)
DEFAULT_LABELS: Dict[str, List[str]] = {
    "model distillation": ["doc_3", "doc_4"],
    "HTTP 404 error": ["doc_6"],
    "XK9-2B4-7Q1": ["doc_9"],
    "BM25 ranking function": ["doc_5"],
    #  Relevant documents use kitten / feline to express "cat", deliberately omitting the literal "cat",
    #  to demonstrate the weakness of sparse retrieval in understanding synonyms (BM25 will miss recall).
    "cat": ["doc_7", "doc_8"],
}

DEFAULT_QUERY = "model distillation"


def _quiet_logging(verbose: bool) -> None:
    """Default suppresses engine logs; --verbose / --explain raises to DEBUG to show computation."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.getLogger().setLevel(level)
    logging.getLogger("bm25_engine").setLevel(level)


def load_corpus(path: Optional[str]) -> List[Dict]:
    """Load corpus. Supports .json (document array) and .jsonl (one document per line)."""
    if not path:
        return DEFAULT_CORPUS
    docs: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".jsonl"):
            for line in f:
                line = line.strip()
                if line:
                    docs.append(json.loads(line))
        else:
            data = json.load(f)
            docs = data["documents"] if isinstance(data, dict) else data
    if not docs:
        raise ValueError(f"Corpus file is empty:{path}")
    return docs


def load_labels(path: Optional[str]) -> Dict[str, List[str]]:
    """Load evaluation annotations: {query: [relevant_doc_id, ...]}."""
    if not path:
        return DEFAULT_LABELS
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_engine(corpus: List[Dict], k1: float, b: float) -> SparseSearchEngine:
    """Feed corpus into engine; rebuild BM25 with given k1/b."""
    engine = SparseSearchEngine()
    engine.index_batch([
        {"text": d["text"],
         "doc_id": d.get("doc_id"),
         "metadata": {"title": d.get("title", "")}}
        for d in corpus
    ])
    # index_batch internally rebuilds BM25 for each document; here we explicitly fix it with target parameters once more
    from bm25_engine import BM25
    engine.bm25 = BM25(engine.index, k1=k1, b=b)
    return engine


def explain_result(engine: SparseSearchEngine, query: str, doc_id: str) -> List[Tuple[str, int, int, float, float]]:
    """Reproduce book log: for matched documents, give per-query-word TF / document length / IDF / BM25 contribution."""
    from bm25_engine import TextProcessor
    internal = engine.external_to_internal[doc_id]
    terms = TextProcessor().tokenize(query)
    rows = []
    for term in terms:
        tf = engine.index.term_frequency[internal].get(term, 0)
        if tf == 0:
            continue
        dl = engine.index.doc_lengths[internal]
        idf = engine.bm25.calculate_idf(term)
        contrib = engine.bm25.calculate_term_score(term, internal)
        rows.append((term, tf, dl, idf, contrib))
    return rows


def run_search(engine: SparseSearchEngine, query: str, top_k: int,
               explain: bool) -> List[Dict]:
    """Execute a single query and print results; return structured results for --output to disk."""
    results = engine.search(query, top_k=top_k)
    print(f"\nQuery: '{query}'  (BM25, top-{top_k})")
    print("-" * 60)
    if not results:
        print("  No documents matched (all query words are not in the inverted index).")
        return []
    out = []
    for rank, r in enumerate(results, 1):
        title = r["metadata"].get("title", "")
        print(f"  #{rank}  {r['doc_id']}  score={r['score']:.4f}  {title}")
        print(f"       Matched word: {r['debug']['matched_terms']}")
        print(f"       Preview: {r['text'][:80]}...")
        if explain:
            rows = explain_result(engine, query, r["doc_id"])
            for term, tf, dl, idf, contrib in rows:
                print(f"         └ '{term}': TF={tf}, document length={dl} words, "
                      f"IDF={idf:.4f}, BM25 contribution={contrib:.4f}")
        out.append({
            "rank": rank,
            "doc_id": r["doc_id"],
            "score": r["score"],
            "title": title,
            "matched_terms": r["debug"]["matched_terms"],
        })
    return out


def _metrics_for_query(retrieved: List[str], relevant: Set[str], k: int) -> Dict:
    """Single query recall@k / precision@k / hit rank (for MRR)."""
    topk = retrieved[:k]
    hits = [d for d in topk if d in relevant]
    recall = len(set(hits)) / len(relevant) if relevant else 0.0
    precision = len(hits) / len(topk) if topk else 0.0
    rr = 0.0
    for i, d in enumerate(retrieved, 1):
        if d in relevant:
            rr = 1.0 / i
            break
    return {"recall": recall, "precision": precision, "rr": rr,
            "hits": hits, "retrieved": topk}


def run_eval(engine: SparseSearchEngine, labels: Dict[str, List[str]],
             k: int) -> Dict:
    """Run retrieval evaluation on the annotation set, print per-query metrics + macro average."""
    print(f"\n{'='*60}")
    print(f"Retrieval quality evaluation (recall@{k} / precision@{k} / MRR)")
    print(f"{'='*60}")
    per_query = {}
    sum_recall = sum_prec = sum_rr = 0.0
    for query, rel_list in labels.items():
        relevant = set(rel_list)
        results = engine.search(query, top_k=max(k, 10))
        retrieved = [r["doc_id"] for r in results]
        m = _metrics_for_query(retrieved, relevant, k)
        per_query[query] = m
        sum_recall += m["recall"]
        sum_prec += m["precision"]
        sum_rr += m["rr"]
        flag = "" if m["recall"] > 0 else "   <- Missed recall (synonym weakness)" if query == "cat" else "   <- Missed recall"
        print(f"\nQuery '{query}'   Relevant documents={sorted(relevant)}")
        print(f"   Recall ranking: {retrieved[:k]}")
        print(f"  recall@{k}={m['recall']:.2f}  precision@{k}={m['precision']:.2f}  RR={m['rr']:.2f}{flag}")
    n = len(labels)
    macro = {
        "recall@k": sum_recall / n,
        "precision@k": sum_prec / n,
        "mrr": sum_rr / n,
        "miss_rate@k": 1.0 - sum_recall / n,
    }
    print(f"\n{'-'*60}")
    print(f"Macro-average recall@{k}={macro['recall@k']:.3f}  "
          f"precision@{k}={macro['precision@k']:.3f}  "
          f"MRR={macro['mrr']:.3f}   Miss rate (1-recall@{k})={macro['miss_rate@k']:.3f}")
    return {"k": k, "per_query": {q: {kk: vv for kk, vv in m.items() if kk != "retrieved"}
                                  for q, m in per_query.items()},
            "macro": macro}


def run_splade(query: str, corpus: List[Dict], top_k: int) -> Optional[List[Dict]]:
    """Learned sparse retrieval (SPLADE). Requires transformers + torch + pretrained model.

    When the model cannot be downloaded in an offline environment, a clear prompt is printed and None is returned (does not affect parameter parsing validation).
    """
    model_name = "naver/splade-cocondenser-ensembledistil"
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForMaskedLM, AutoTokenizer
    except Exception as e:
        print("\n[SPLADE] Requires dependencies transformers and torch, which are missing in the current environment:", e)
        print("        Install: pip install torch transformers")
        print("        (BM25 path requires no model and can run completely offline)")
        return None
    try:
        # Only load from local cache to avoid getting stuck in endless network downloads in an offline environment.
        print(f"\n[SPLADE] Attempting to load model from local cache {model_name} ...")
        tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
        model = AutoModelForMaskedLM.from_pretrained(model_name, local_files_only=True)
        model.eval()
    except Exception:
        print(f"\n[SPLADE] No model in local cache {model_name}, and cannot download weights in an offline environment.")
        print("        Please first run the following command once in an online environment to cache the model locally, then rerun this command:")
        print(f"          huggingface-cli download {model_name}")
        print("        (BM25 path does not depend on any model and can fully reproduce experiments 3-5 in the book offline)")
        return None

    import torch

    def encode(text: str) -> Dict[str, float]:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        with torch.no_grad():
            logits = model(**inputs).logits  # [1, seq, vocab]
        # SPLADE: log(1+ReLU(logits)) then max-pool along the sequence dimension to obtain vocabulary-dimension sparse weights
        weights = torch.max(
            torch.log1p(torch.relu(logits)) * inputs["attention_mask"].unsqueeze(-1),
            dim=1,
        ).values.squeeze(0)
        nz = torch.nonzero(weights).squeeze(-1)
        return {int(i): float(weights[i]) for i in nz}

    q_vec = encode(query)
    scored = []
    for d in corpus:
        d_vec = encode(d["text"])
        score = sum(w * d_vec.get(t, 0.0) for t, w in q_vec.items())
        scored.append((d.get("doc_id"), score, d.get("title", "")))
    scored.sort(key=lambda x: x[1], reverse=True)
    print(f"\nQuery: '{query}'  (SPLADE, top-{top_k})")
    print("-" * 60)
    out = []
    for rank, (doc_id, score, title) in enumerate(scored[:top_k], 1):
        print(f"  #{rank}  {doc_id}  score={score:.4f}  {title}")
        out.append({"rank": rank, "doc_id": doc_id, "score": score, "title": title})
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Sparse retrieval command-line tool (experiments 3-5): Run BM25 / SPLADE sparse retrieval on a small corpus and evaluate retrieval quality.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python cli.py                                  # Default demo (query "model distillation")
  python cli.py -q "HTTP 404 error" --explain    # Show per-word TF/IDF/BM25 contribution
  python cli.py --eval                           # Compute recall/precision/MRR on labeled set
  python cli.py -q "cat"                          # Observe BM25's synonym limitation
  python cli.py --corpus my.json -q "..." -o out.json
  python cli.py --method splade -q "model distillation"   # Learned sparse retrieval (requires model)
""",
    )
    parser.add_argument("-q", "--query", default=DEFAULT_QUERY,
                        help=f"Query string (default: '{DEFAULT_QUERY}'）")
    parser.add_argument("-c", "--corpus", default=None,
                        help="Corpus file path (.json document array or .jsonl one document per line); default uses built-in example corpus")
    parser.add_argument("-m", "--method", choices=["bm25", "splade"], default="bm25",
                        help="Retrieval method: bm25 (default, offline) or splade (learned sparse, requires model download)")
    parser.add_argument("-k", "--top-k", type=int, default=5,
                        help="Return top k results (default: 5)")
    parser.add_argument("-o", "--output", default=None,
                        help="Write results/evaluation metrics as JSON to this file")
    parser.add_argument("--eval", action="store_true",
                        help="Evaluate on labeled set with recall@k / precision@k / MRR, instead of running a single query")
    parser.add_argument("--labels", default=None,
                        help="Evaluation label file {query: [relevant doc_id,...]}; default uses built-in labels")
    parser.add_argument("--explain", action="store_true",
                        help="Show per-word TF/IDF/BM25 contribution for each hit document (reproduce book logs)")
    parser.add_argument("--k1", type=float, default=1.5,
                        help="BM25 term frequency saturation parameter k1 (default: 1.5)")
    parser.add_argument("-b", "--b", type=float, default=0.75,
                        help="BM25 document length normalization parameter b (default: 0.75)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable engine DEBUG logs (show tokenization, inverted index construction, scoring process)")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    _quiet_logging(args.verbose)

    corpus = load_corpus(args.corpus)
    print(f"Loaded corpus: {len(corpus)} documents"
          + ("(built-in example)" if not args.corpus else f"(from {args.corpus}）"))

    payload: Dict = {"method": args.method, "query": args.query, "top_k": args.top_k}

    if args.method == "splade":
        results = run_splade(args.query, corpus, args.top_k)
        if results is None:
            return 0  # Model missing prompt given, treated as normal exit
        payload["results"] = results
    else:
        engine = build_engine(corpus, k1=args.k1, b=args.b)
        print(f"BM25 parameters: k1={args.k1}, b={args.b}, avgdl={engine.bm25.avgdl:.2f}")
        if args.eval:
            labels = load_labels(args.labels)
            payload["eval"] = run_eval(engine, labels, args.top_k)
        else:
            payload["results"] = run_search(engine, args.query, args.top_k, args.explain)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\nResults written:{args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
