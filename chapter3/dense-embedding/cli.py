#!/usr/bin/env python3
"""
Dense Retrieval CLI Tool (Experiment 3-4)

Run dense embedding retrieval on a small sample corpus, supporting:
  - Custom corpus / query / top-k / output file
  - --eval: Compute recall@k / precision@k / MRR on a small annotated evaluation set,
            intuitively demonstrating the core selling point that "dense embeddings understand synonymous expressions"
  - --compare-ann: Reproduce the key point of Experiment 3-4 in the book—compare ANNOY vs. HNSW two ANN backends
            in terms of recall relative to exact brute-force retrieval, index building time, and query latency (reusing server-side indexing.py)
  - --embedding-model: Switchable embedding model; default BAAI/bge-m3, offline-available cached
            sentence-transformers/all-MiniLM-L6-v2

When run without any arguments, it is equivalent to the default demo of Experiment 3-4 in the book (query "a cat playing").
--compare-ann uses synthetic vectors, requires no model, and can reproduce the ANN comparison in a fully offline environment.
"""

import argparse
import json
import sys
import time
from typing import Dict, List, Optional, Set

import numpy as np

from indexing import AnnoyIndex, HNSWIndex


# ---------------------------------------------------------------------------
# Built-in example corpus and annotations (English, consistent with common sentence embedding model capabilities, fully reproducible offline)
# The corpus deliberately includes "synonymous expression" documents (kitten / feline for cat, two spellings of distillation), 
# Used to demonstrate the strengths of dense retrieval in semantic matching—these are exactly the scenarios where sparse BM25 (Experiment 3-5) would miss recall.
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
    {"doc_id": "doc_11", "title": "Deep Learning",
     "text": "Deep learning stacks many layers of neurons to extract hierarchical features from raw data."},
    {"doc_id": "doc_12", "title": "Gradient Descent",
     "text": "Gradient descent minimizes a loss function by iteratively updating the model parameters."},
]

# query -> set of relevant document doc_ids (manually annotated ground truth)
# Most of these queries do not share literal keywords with relevant documents, only semantic relevance—this tests the semantic capability of dense retrieval.
DEFAULT_LABELS: Dict[str, List[str]] = {
    #Neither kitten nor feline contains the literal "cat"; dense retrieval should recall by semantics, while sparse BM25 will miss it.
    "a cat playing": ["doc_7", "doc_8"],
    # Two spellings of "distillation", semantically the same topic
    "model distillation": ["doc_3", "doc_4"],
    #  Semantically related, but the literal text does not contain "neural network training"
    "training neural networks": ["doc_11", "doc_12"],
    "self attention in sequence models": ["doc_10"],
    "web server resource not found": ["doc_6"],
}

DEFAULT_QUERY = "a cat playing"

DEFAULT_MODEL = "BAAI/bge-m3"
OFFLINE_HINT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
#  Dense embedding encoder: compute sentence vectors directly with transformers' AutoModel (mean / cls pooling + L2 normalization)
# This allows loading both the default BAAI/bge-m3 from the book (bge series uses cls pooling) and the offline cached version.
# sentence-transformers/all-MiniLM-L6-v2 (mean pooling), no dependency on FlagEmbedding.
# ---------------------------------------------------------------------------
class DenseEncoder:
    def __init__(self, model_name: str, pooling: str = "auto",
                 device: str = "cpu", max_length: int = 512):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval().to(device)
        self.device = device
        self.max_length = max_length
        if pooling == "auto":
            # For bge / bge-m3, the dense vector takes [CLS]; most sentence-transformers models use mean pooling
            pooling = "cls" if "bge" in model_name.lower() else "mean"
        self.pooling = pooling

    def encode(self, texts: List[str], batch_size: int = 16) -> np.ndarray:
        vecs: List[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            enc = self.tokenizer(batch, padding=True, truncation=True,
                                 max_length=self.max_length, return_tensors="pt").to(self.device)
            with self.torch.no_grad():
                out = self.model(**enc)
            if self.pooling == "cls":
                emb = out.last_hidden_state[:, 0]
            else:
                mask = enc["attention_mask"].unsqueeze(-1).float()
                emb = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            emb = self.torch.nn.functional.normalize(emb, p=2, dim=1)
            vecs.append(emb.cpu().numpy().astype("float32"))
        return np.vstack(vecs)


def load_encoder(model_name: str, pooling: str, device: str) -> Optional["DenseEncoder"]:
    """Load dense encoder. Give a clear prompt when offline and model not cached, and return None (does not affect parameter parsing validation)."""
    try:
        import torch  # noqa: F401
        from transformers import AutoModel  # noqa: F401
    except Exception as e:
        print("\n[Dense Encoding] requires transformers and torch, which are missing in the current environment:", e)
        print("        Installation: pip install torch transformers")
        print("        (--compare-ann uses synthetic vectors, no model required, can run completely offline)")
        return None
    try:
        print(f"Loading embedding model {model_name}（pooling={pooling}, device={device}）...")
        t0 = time.time()
        encoder = DenseEncoder(model_name, pooling=pooling, device=device)
        print(f"模型加载完成，耗时 {time.time() - t0:.1f}s, pooling method ={encoder.pooling}")
        return encoder
    except Exception as e:
        print(f"\n[Dense Encoding] Unable to load model {model_name}：{e}")
        print(f"        Cannot download in offline environment {model_name} Weight (BGE-M3 about 2.3GB).")
        print(f"        Can switch to a cached small model: --embedding-model {OFFLINE_HINT_MODEL}")
        print("        Or pre-cache the target model in an online environment first; --compare-ann requires no model at all.")
        return None


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
        raise ValueError(f"The corpus file is empty: {path}")
    return docs


def load_labels(path: Optional[str]) -> Dict[str, List[str]]:
    """Load evaluation annotations: {query: [relevant_doc_id, ...]}."""
    if not path:
        return DEFAULT_LABELS
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Dense retrieval (exact brute-force, used for single query and retrieval quality evaluation)
# ---------------------------------------------------------------------------
def dense_rank(query_vec: np.ndarray, doc_matrix: np.ndarray) -> List[int]:
    """The vectors are L2 normalized, so cosine similarity equals dot product; returns document indices sorted by similarity in descending order."""
    sims = doc_matrix @ query_vec
    return list(np.argsort(-sims)), sims


def run_search(encoder: "DenseEncoder", corpus: List[Dict], doc_matrix: np.ndarray,
               query: str, top_k: int) -> List[Dict]:
    """Execute a single dense query and print the result, returning a structured result for --output to persist."""
    q = encoder.encode([query])[0]
    order, sims = dense_rank(q, doc_matrix)
    print(f"\nQuery: '{query}'  (dense retrieval, top-{top_k})")
    print("-" * 60)
    out = []
    for rank, idx in enumerate(order[:top_k], 1):
        d = corpus[idx]
        title = d.get("title", "")
        print(f"  #{rank}  {d.get('doc_id')}  cos={float(sims[idx]):.4f}  {title}")
        print(f"        Preview: {d['text'][:80]}...")
        out.append({
            "rank": rank,
            "doc_id": d.get("doc_id"),
            "score": float(sims[idx]),
            "title": title,
        })
    return out


def _metrics_for_query(retrieved: List[str], relevant: Set[str], k: int) -> Dict:
    """Recall@k / precision@k / hit rank (for MRR) of a single query."""
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


def run_eval(encoder: "DenseEncoder", corpus: List[Dict], doc_matrix: np.ndarray,
             labels: Dict[str, List[str]], k: int) -> Dict:
    """Evaluate dense retrieval on the labeled set, printing per-query metrics + macro average."""
    doc_ids = [d.get("doc_id") for d in corpus]
    print(f"\n{'=' * 60}")
    print(f"Dense retrieval quality evaluation (recall@{k} / precision@{k} / MRR)")
    print(f"{'=' * 60}")
    per_query = {}
    sum_recall = sum_prec = sum_rr = 0.0
    q_vecs = encoder.encode(list(labels.keys()))
    for (query, rel_list), qv in zip(labels.items(), q_vecs):
        relevant = set(rel_list)
        order, _ = dense_rank(qv, doc_matrix)
        retrieved = [doc_ids[i] for i in order]
        m = _metrics_for_query(retrieved, relevant, k)
        per_query[query] = m
        sum_recall += m["recall"]
        sum_prec += m["precision"]
        sum_rr += m["rr"]
        flag = "" if m["recall"] > 0 else "   <- Missed recall"
        print(f"\nQuery '{query}'  relevant docs={sorted(relevant)}")
        print(f"   Recall ranking: {retrieved[:k]}")
        print(f"  recall@{k}={m['recall']:.2f}  precision@{k}={m['precision']:.2f}  RR={m['rr']:.2f}{flag}")
    n = len(labels)
    macro = {
        "recall@k": sum_recall / n,
        "precision@k": sum_prec / n,
        "mrr": sum_rr / n,
        "miss_rate@k": 1.0 - sum_recall / n,
    }
    print(f"\n{'-' * 60}")
    print(f"Macro average recall@{k}={macro['recall@k']:.3f}  "
          f"precision@{k}={macro['precision@k']:.3f}  "
          f"MRR={macro['mrr']:.3f}   Missed recall rate (1-recall@{k})={macro['miss_rate@k']:.3f}")
    return {"k": k, "per_query": {q: {kk: vv for kk, vv in m.items() if kk != "retrieved"}
                                  for q, m in per_query.items()},
            "macro": macro}


# ---------------------------------------------------------------------------
# ANN backend comparison (focus of experiments 3-4): reuse the ANNOY / HNSW implementation in server-side indexing.py,
#  compare their recall relative to "exact brute-force retrieval", indexing time, and query latency on a batch of synthetic unit vectors.
#  Using synthetic vectors instead of real text embeddings is to (a) be fully offline without downloading models; (b) when the corpus is large enough,
#  the "approximation" of ANN will show a gap from exact retrieval, thus revealing the trade-offs between the two algorithms.
# ---------------------------------------------------------------------------
def _exact_topk(queries: np.ndarray, base: np.ndarray, k: int) -> List[Set[int]]:
    """Exact brute-force nearest neighbor (cosine), as ground truth for ANN recall."""
    sims = queries @ base.T
    idx = np.argsort(-sims, axis=1)[:, :k]
    return [set(row.tolist()) for row in idx]


def _sanity_ok(index, base: np.ndarray) -> bool:
    """Self-check: query with an existing vector in the library should recall itself. Used to identify a corrupted index backend in the environment."""
    probe = min(5, len(base))
    for i in range(probe):
        ids, _ = index.search(base[i], min(10, len(base)))
        if f"v{i}" not in set(ids):
            return False
    return True


def compare_ann(base: np.ndarray, queries: np.ndarray, top_k: int, backends: List[str],
                annoy_n_trees: int, hnsw_M: int, hnsw_ef_search: int,
                hnsw_ef_construction: int) -> Dict:
    dim = base.shape[1]
    n = len(base)
    exact_sets = _exact_topk(queries, base, top_k)

    print(f"\n{'=' * 60}")
    print(f"ANN backend comparison:{n}  vectors of dimension {dim}, {len(queries)} queries, top-{top_k}")
    print(f"Metrics: recall@{top_k}  relative to exact brute-force retrieval / indexing time / average query latency")
    print(f"{'=' * 60}")

    report: Dict[str, Dict] = {}
    for backend in backends:
        if backend == "annoy":
            index = AnnoyIndex(dimension=dim, n_trees=annoy_n_trees,
                               metric="angular", logger=None)
        else:
            index = HNSWIndex(dimension=dim, max_elements=n + 16,
                              ef_construction=hnsw_ef_construction, M=hnsw_M,
                              ef_search=hnsw_ef_search, space="cosine", logger=None)

        t0 = time.time()
        for i, v in enumerate(base):
            index.add_item(f"v{i}", v)
        if backend == "annoy":
            index.rebuild_index()
        build_time = time.time() - t0

        healthy = _sanity_ok(index, base)

        recalls: List[float] = []
        qtimes: List[float] = []
        for qi, q in enumerate(queries):
            ts = time.time()
            ids, _ = index.search(q, top_k)
            qtimes.append(time.time() - ts)
            got = {int(d[1:]) for d in ids}
            recalls.append(len(got & exact_sets[qi]) / top_k)

        mean_recall = float(np.mean(recalls))
        mean_qms = float(np.mean(qtimes) * 1000)
        params = (f"n_trees={annoy_n_trees}" if backend == "annoy"
                  else f"M={hnsw_M}, ef_search={hnsw_ef_search}, ef_construction={hnsw_ef_construction}")
        report[backend] = {
            "recall@k": mean_recall,
            "build_time_s": build_time,
            "mean_query_ms": mean_qms,
            "params": params,
            "healthy": healthy,
        }
        warn = "" if healthy else "  [Warning] This backend cannot even recall its own vector, likely corrupted in the current environment; the following numbers are unreliable"
        print(f"\n[{backend.upper()}]  {params}{warn}")
        print(f"  recall@{top_k} = {mean_recall:.3f}")
        print(f"  Indexing time   = {build_time * 1000:.1f} ms")
        print(f"  Average query latency = {mean_qms:.3f} ms")

    if "annoy" in report and "hnsw" in report:
        print(f"\n{'-' * 60}")
        print("Summary: HNSW graph structure usually has higher recall and supports incremental insertion, at the cost of higher memory and indexing overhead;")
        print("      ANNOY tree structure indexes faster and uses less memory, but deletion requires rebuilding, and recall is tuned by n_trees.")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Dense retrieval CLI tool (Experiment 3-4): Run dense embedding retrieval on a small corpus and evaluate retrieval quality,"
                    "and compare two ANN index backends: ANNOY / HNSW.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python cli.py                                       # Default demo (query "a cat playing", requires embedding model)
  python cli.py -q "model distillation" -k 3          # Single dense query
  python cli.py --eval                                # Compute recall/precision/MRR on labeled set
  python cli.py --embedding-model sentence-transformers/all-MiniLM-L6-v2 --eval   # Offline small model
  python cli.py --compare-ann                         # ANNOY vs HNSW recall comparison (synthetic vectors, no model needed)
  python cli.py --compare-ann --ann-base 5000 --annoy-n-trees 5 -k 10 -o ann.json
""",
    )
    parser.add_argument("-q", "--query", default=DEFAULT_QUERY,
                        help=f"Query string (default: '{DEFAULT_QUERY}'）")
    parser.add_argument("-c", "--corpus", default=None,
                        help="Corpus file path (.json document array or .jsonl one doc per line); defaults to built-in example corpus")
    parser.add_argument("-k", "--top-k", type=int, default=5,
                        help="Return top k results (default: 5)")
    parser.add_argument("-o", "--output", default=None,
                        help="Write results/evaluation metrics as JSON to this file")
    parser.add_argument("--embedding-model", default=DEFAULT_MODEL,
                        help=f"Dense embedding model name (default: {DEFAULT_MODEL}）；"
                             f"Offline cached {OFFLINE_HINT_MODEL}")
    parser.add_argument("--pooling", choices=["auto", "mean", "cls"], default="auto",
                        help="Sentence vector pooling method: auto(bge* uses cls, others use mean) / mean / cls")
    parser.add_argument("--device", default="cpu",
                        help="Inference device (cpu / cuda / mps, default: cpu)")
    parser.add_argument("--eval", action="store_true",
                        help="Evaluate recall@k / precision@k / MRR on labeled set instead of running a single query")
    parser.add_argument("--labels", default=None,
                        help="Evaluation label file {query: [relevant_doc_id,...]}; defaults to built-in labels")

    ann = parser.add_argument_group("ANN backend comparison (--compare-ann)")
    ann.add_argument("--compare-ann", action="store_true",
                     help="Compare recall/time of ANNOY vs HNSW (reuses indexing.py, uses synthetic vectors, no model needed)")
    ann.add_argument("--backend", choices=["annoy", "hnsw", "both"], default="both",
                     help="ANN backends to compare (default: both)")
    ann.add_argument("--ann-base", type=int, default=3000,
                     help="Number of synthetic base vectors (default: 3000; larger values make ANN approximation error more noticeable)")
    ann.add_argument("--ann-queries", type=int, default=100,
                     help="Number of synthetic query vectors (default: 100)")
    ann.add_argument("--ann-dim", type=int, default=128,
                     help="Synthetic vector dimension (default: 128)")
    ann.add_argument("--annoy-n-trees", type=int, default=10,
                     help="Number of ANNOY trees (default: 10; more trees = more accurate but slower)")
    ann.add_argument("--hnsw-M", type=int, default=16,
                     help="HNSW node connection count M (default: 16; larger = higher recall but more memory)")
    ann.add_argument("--hnsw-ef-search", type=int, default=20,
                     help="HNSW query-time dynamic candidate list size ef_search (default: 20)")
    ann.add_argument("--hnsw-ef-construction", type=int, default=100,
                     help="HNSW index-time dynamic candidate list size ef_construction (default: 100)")
    ann.add_argument("--seed", type=int, default=42,
                     help="Synthetic vector random seed (default: 42)")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    payload: Dict = {"top_k": args.top_k}

    # --- ANN backend comparison: synthetic vectors, no embedding model needed, fully offline ---
    if args.compare_ann:
        rng = np.random.default_rng(args.seed)
        base = rng.standard_normal((args.ann_base, args.ann_dim)).astype("float32")
        base /= np.linalg.norm(base, axis=1, keepdims=True)
        queries = rng.standard_normal((args.ann_queries, args.ann_dim)).astype("float32")
        queries /= np.linalg.norm(queries, axis=1, keepdims=True)
        backends = ["annoy", "hnsw"] if args.backend == "both" else [args.backend]
        payload["compare_ann"] = compare_ann(
            base, queries, args.top_k, backends,
            annoy_n_trees=args.annoy_n_trees, hnsw_M=args.hnsw_M,
            hnsw_ef_search=args.hnsw_ef_search, hnsw_ef_construction=args.hnsw_ef_construction)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"\nResults written to: {args.output}")
        return 0

    # --- Dense retrieval / evaluation: requires embedding model ---
    corpus = load_corpus(args.corpus)
    print(f"Loaded corpus: {len(corpus)} documents"
          + (" (built-in example)" if not args.corpus else f"(from {args.corpus}）"))

    encoder = load_encoder(args.embedding_model, args.pooling, args.device)
    if encoder is None:
        return 0  # The model missing prompt has been given, considered as normal exit (parameter parsing has been verified)

    doc_matrix = encoder.encode([d["text"] for d in corpus])
    payload["embedding_model"] = args.embedding_model
    payload["query"] = args.query

    if args.eval:
        labels = load_labels(args.labels)
        payload["eval"] = run_eval(encoder, corpus, doc_matrix, labels, args.top_k)
    else:
        payload["results"] = run_search(encoder, corpus, doc_matrix, args.query, args.top_k)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\nResults written to: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
