"""Hybrid retrieval pipeline offline evaluation CLI.

This script runs the entire retrieval pipeline—chunk → embed → retrieve →
fuse → rerank—completely in a **single-process, offline** environment, and on a small
evaluation set with annotated answers, compares the retrieval quality of each method stage by stage. It does not depend on dense/sparse microservices
(ports 4240/4241/4242), so you can reproduce the core conclusion of "how metrics improve with each added stage" offline using local models.

Local components used in each stage:
  - Sparse retrieval: BM25 (pure Python, rank_bm25, no model download required)
  - Dense retrieval: Local sentence embedding model (default Qwen3-Embedding-0.6B, multilingual,
                    loaded via transformers; can also be replaced with BGE-M3, etc.)
  - Fusion: see fusion.py, two strategies: RRF and weighted normalization
  - Rerank: Cross-encoder (default cross-encoder/ms-marco-MiniLM-L-6-v2)

Default behavior (without any arguments): Evaluate on the built-in evaluation set
  BM25 / Dense / Hybrid-RRF / Hybrid-Weighted / Hybrid-RRF+Rerank five configurations,
  print Recall@k, MRR, nDCG@k comparison table.

Examples:
  python evaluate.py                         # Built-in evaluation set, full comparison table
  python evaluate.py --top-k 10 --rerank-top-k 5
  python evaluate.py --no-rerank             # Skip rerank stage
  python evaluate.py --embed-model BAAI/bge-m3 --pooling cls
  python evaluate.py --query "怎样提升检索精度"  # Single query, per-stage ranking trace
  python evaluate.py --corpus my_corpus.json --queries my_queries.json --output result.json
"""

import argparse
import json
import math
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fusion import fuse

# ---------------------------------------------------------------------------
#  Built-in evaluation set: directly reuses the educational test cases from test_client.py (four categories: semantic similarity / exact name /
#  multilingual / technical code), whose expected field is the manually annotated relevant documents, serving as the evaluation gold standard.
#  Additionally, two longer documents are included to demonstrate the chunk stage.
# ---------------------------------------------------------------------------
DEFAULT_CORPUS: List[Dict[str, Any]] = [
    # --- Near-duplicate code cluster (sparse dominates, dense fails) ---
    #  Each text is almost identical, differing only in model code; dense vectors can hardly distinguish members within the same cluster,
    #  while sparse retrieval hits precisely via exact term matching. The larger the cluster, the higher the probability of dense selection errors.
    {"doc_id": "xr_7001", "text": "Product model XR-7001 is a smartphone available now."},
    {"doc_id": "xr_7002", "text": "Product model XR-7002 is a smartphone available now."},
    {"doc_id": "xr_7003", "text": "Product model XR-7003 is a smartphone available now."},
    {"doc_id": "xr_7004", "text": "Product model XR-7004 is a smartphone available now."},
    {"doc_id": "xr_7005", "text": "Product model XR-7005 is a smartphone available now."},
    {"doc_id": "xr_7006", "text": "Product model XR-7006 is a smartphone available now."},
    #  Near-duplicate HTTP error code cluster (sparse dominates, dense fails)
    {"doc_id": "http_400", "text": "The HTTP-400 response is a client error status code."},
    {"doc_id": "http_401", "text": "The HTTP-401 response is a client error status code."},
    {"doc_id": "http_403", "text": "The HTTP-403 response is a client error status code."},
    {"doc_id": "http_404", "text": "The HTTP-404 response is a client error status code."},
    {"doc_id": "http_500", "text": "The HTTP-500 response is a server error status code."},
    # --- Semantic paraphrase cluster (dense dominates, sparse fails) ---
    #  Query and documents share almost no common words; sparse BM25 cannot match, dense hits via semantics.
    {"doc_id": "sem_readable", "text": "The language emphasizes clean, readable code that newcomers can pick up quickly."},
    {"doc_id": "sem_gc", "text": "Automatic memory management frees developers from manually releasing objects."},
    {"doc_id": "sem_photo", "text": "Green plants convert sunlight into chemical energy stored as sugars."},
    {"doc_id": "sem_crypto", "text": "Encryption scrambles a message so that only the intended recipient can read it."},
    #  Longer documents: topics independent of each other, used to demonstrate the chunk stage (will be split into multiple chunks before retrieval)
    {"doc_id": "doc_watercycle", "text": (
        "The water cycle describes how water moves continuously between the ocean, the atmosphere and the land. "
        "Heat from the sun evaporates water from the sea surface into vapor that rises high into the sky. "
        "As the vapor cools it condenses into tiny droplets that gather to form clouds. "
        "When the droplets grow heavy enough they fall back to the ground as rain or snow, "
        "and rivers eventually carry that water back to the ocean, closing the loop."
    )},
    {"doc_id": "doc_volcano", "text": (
        "A volcano forms where molten rock called magma rises from deep inside the planet toward the surface. "
        "Magma collects in a chamber beneath the crust, and mounting pressure forces it upward through cracks. "
        "During an eruption the magma bursts out as lava, ash and gas, which pile up around the vent. "
        "Layer after layer of cooled lava slowly builds the cone-shaped mountain we recognize as a volcano."
    )},
]

DEFAULT_QUERIES: List[Dict[str, Any]] = [
    #  Exact code query: sparse hits precisely, dense struggles to distinguish similar models (expected is the only correct answer)
    {"query": "XR-7003", "expected": ["xr_7003"]},
    {"query": "XR-7005", "expected": ["xr_7005"]},
    {"query": "HTTP-403", "expected": ["http_403"]},
    {"query": "HTTP-400", "expected": ["http_400"]},
    #  Semantic paraphrase query: almost no common words with documents, dense hits via semantics, sparse cannot match
    {"query": "a beginner friendly language with tidy syntax", "expected": ["sem_readable"]},
    {"query": "reclaiming unused heap space without programmer effort", "expected": ["sem_gc"]},
    {"query": "how vegetation turns light into food", "expected": ["sem_photo"]},
    {"query": "hiding a note so eavesdroppers cannot understand it", "expected": ["sem_crypto"]},
    #  Long document semantic query: the hit long document is first chunked, then recalled and reranked by a chunk
    {"query": "how does water move between the ocean and the sky", "expected": ["doc_watercycle"]},
    {"query": "how are volcanoes formed from molten rock", "expected": ["doc_volcano"]},
]


# ---------------------------------------------------------------------------
#  Chunk
# ---------------------------------------------------------------------------
def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Splits a document into overlapping chunks by character window.

    Short documents (length <= chunk_size) return a single chunk as-is. In real scenarios, chunks are the smallest
    retrieval unit; here we use a character-level sliding window to keep implementation simple and language-agnostic.

    Args:
        text: Original document text.
        chunk_size: Maximum number of characters per chunk.
        overlap: Number of overlapping characters between adjacent chunks.

    Returns:
        List of chunk texts (at least one).
    """
    text = text.strip()
    if chunk_size <= 0 or len(text) <= chunk_size:
        return [text]

    step = max(1, chunk_size - overlap)
    chunks = []
    for start in range(0, len(text), step):
        piece = text[start:start + chunk_size].strip()
        if piece:
            chunks.append(piece)
        if start + chunk_size >= len(text):
            break
    return chunks or [text]


# ---------------------------------------------------------------------------
#  Tokenization (for BM25): keep English words/numbers/codes with hyphens or underscores, CJK uses jieba + single characters
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*|[一-鿿]+")


def tokenize(text: str) -> List[str]:
    """Tokenizes text into BM25 terms.

    - English words, pure numbers, and technical codes like ``http-403`` / ``max_buffer_size`` / ``xr-7000``
      are kept intact (hyphens and underscores not split), ensuring exact matching.
    - Consecutive CJK segments produce both jieba segmentation results and single characters, enhancing Chinese recall robustness.
    """
    tokens: List[str] = []
    for match in _TOKEN_RE.finditer(text.lower()):
        span = match.group()
        if "一" <= span[0] <= "鿿":
            try:
                import jieba
                tokens.extend(w for w in jieba.cut(span) if w.strip())
            except Exception:
                pass
            tokens.extend(list(span))
        else:
            tokens.append(span)
    return tokens


# ---------------------------------------------------------------------------
#  Sparse retrieval: BM25
# ---------------------------------------------------------------------------
class BM25Retriever:
    """BM25 retriever based on rank_bm25 (chunk level)."""

    def __init__(self, chunk_ids: List[str], chunk_texts: List[str]):
        from rank_bm25 import BM25Okapi

        self.chunk_ids = chunk_ids
        self.tokenized = [tokenize(t) for t in chunk_texts]
        self.bm25 = BM25Okapi(self.tokenized)

    def search(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        """Returns a list of (chunk_id, score) sorted by score descending, keeping only positive scores."""
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self.chunk_ids, scores), key=lambda kv: kv[1], reverse=True)
        return [(cid, float(s)) for cid, s in ranked[:top_k] if s > 0]


# ---------------------------------------------------------------------------
#  Dense retrieval: local sentence embedding model (transformers)
# ---------------------------------------------------------------------------
class DenseEncoder:
    """Loads a local sentence embedding model via transformers for dense retrieval."""

    def __init__(self, model_name: str, pooling: str, device: str,
                 query_instruct: str = "", max_length: int = 256):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.device = device
        self.max_length = max_length
        self.pooling = self._resolve_pooling(pooling, model_name)
        #  Instruction-based retrieval models (e.g., Qwen3-Embedding, last-token pooling) require a task instruction on the query side;
        #  mean/cls pooling models (MiniLM / BGE-M3) do not, so it is automatically disabled.
        self.query_instruct = query_instruct if (query_instruct and self.pooling == "last") else ""
        #  last-token pooling requires left padding so that the last position aligns with the actual last token
        padding_side = "left" if self.pooling == "last" else "right"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side=padding_side)
        self.model = AutoModel.from_pretrained(model_name).to(device).eval()

    @staticmethod
    def _resolve_pooling(pooling: str, model_name: str) -> str:
        if pooling != "auto":
            return pooling
        name = model_name.lower()
        if "qwen" in name:
            return "last"
        if "bge-m3" in name or "bge-large" in name or "bge-base" in name:
            return "cls"
        return "mean"

    def _pool(self, last_hidden, attention_mask):
        torch = self.torch
        if self.pooling == "cls":
            return last_hidden[:, 0]
        if self.pooling == "last":
            return last_hidden[:, -1]
        # mean pooling
        mask = attention_mask.unsqueeze(-1).float()
        return (last_hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)

    def encode(self, texts: Sequence[str], is_query: bool = False, batch_size: int = 16):
        torch = self.torch
        if is_query and self.query_instruct:
            texts = [f"Instruct: {self.query_instruct}\nQuery:{t}" for t in texts]
        vectors = []
        for start in range(0, len(texts), batch_size):
            batch = list(texts[start:start + batch_size])
            pooled = self._forward(batch)
            #  Some models produce NaN on mps during forward pass (transformers 5.x + certain weights);
            #  After detection, permanently fall back to CPU recomputation to ensure finite vectors and reproducible results.
            if self.device != "cpu" and torch.isnan(pooled).any():
                self.device = "cpu"
                self.model = self.model.to("cpu")
                pooled = self._forward(batch)
            pooled = torch.nn.functional.normalize(pooled.float(), p=2, dim=1)
            vectors.append(pooled.cpu())
        return torch.cat(vectors, dim=0)

    def _forward(self, batch: List[str]):
        torch = self.torch
        enc = self.tokenizer(
            batch, padding=True, truncation=True,
            max_length=self.max_length, return_tensors="pt",
        ).to(self.device)
        with torch.no_grad():
            out = self.model(**enc)
        return self._pool(out.last_hidden_state, enc["attention_mask"])


class DenseRetriever:
    """  Chunk-level retriever based on dense vector cosine similarity."""

    def __init__(self, encoder: DenseEncoder, chunk_ids: List[str], chunk_texts: List[str]):
        self.encoder = encoder
        self.chunk_ids = chunk_ids
        self.matrix = encoder.encode(chunk_texts)  #  [N, D], normalized

    def search(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        q = self.encoder.encode([query], is_query=True)[0]
        sims = (self.matrix @ q).tolist()
        ranked = sorted(zip(self.chunk_ids, sims), key=lambda kv: kv[1], reverse=True)
        return [(cid, float(s)) for cid, s in ranked[:top_k]]


# ---------------------------------------------------------------------------
#  Reranking: cross-encoder
# ---------------------------------------------------------------------------
class CrossEncoderReranker:
    """  Fine-rank candidates with a cross-encoder.

    In transformers 5.x + some BERT weights, fp32 forward may produce NaN; this class detects NaN and
    automatically falls back to CPU + float64 recomputation to ensure finite and reproducible output.
    """

    def __init__(self, model_name: str, device: str, max_length: int = 512):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.device = device
        self.max_length = max_length
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(device).eval()

    def score(self, query: str, docs: Sequence[str]) -> List[float]:
        torch = self.torch
        if not docs:
            return []
        enc = self.tokenizer(
            [query] * len(docs), list(docs),
            padding=True, truncation=True, max_length=self.max_length, return_tensors="pt",
        ).to(self.device)
        with torch.no_grad():
            logits = self.model(**enc).logits.squeeze(-1).float()
        if torch.isnan(logits).any():
            #  Fallback: CPU + float64 recomputation
            enc_cpu = {k: v.to("cpu") for k, v in enc.items()}
            model64 = self.model.to("cpu").double()
            with torch.no_grad():
                logits = model64(**enc_cpu).logits.squeeze(-1)
            self.model = self.model.to(self.device).float()
        return [float(x) for x in logits.reshape(-1).tolist()]

    def rerank(self, query: str, candidates: List[Tuple[str, str]], top_k: int) -> List[Tuple[str, float]]:
        """  candidates: [(doc_id, text)] -> [(doc_id, rerank_score)] descending, take top_k."""
        scores = self.score(query, [text for _, text in candidates])
        ranked = sorted(
            ((doc_id, s) for (doc_id, _), s in zip(candidates, scores)),
            key=lambda kv: kv[1], reverse=True,
        )
        return ranked[:top_k]


# ---------------------------------------------------------------------------
#  chunk-level results -> doc-level results (take the highest-scoring chunk per document)
# ---------------------------------------------------------------------------
def chunks_to_docs(ranked_chunks: List[Tuple[str, float]], chunk_to_doc: Dict[str, str]) -> List[Tuple[str, float]]:
    best: Dict[str, float] = {}
    for chunk_id, score in ranked_chunks:
        doc_id = chunk_to_doc[chunk_id]
        if doc_id not in best or score > best[doc_id]:
            best[doc_id] = score
    return sorted(best.items(), key=lambda kv: kv[1], reverse=True)


# ---------------------------------------------------------------------------
#  Evaluation metrics
# ---------------------------------------------------------------------------
def recall_at_k(ranked_ids: List[str], gold: Sequence[str], k: int) -> float:
    if not gold:
        return 0.0
    topk = set(ranked_ids[:k])
    return len(topk & set(gold)) / len(gold)


def reciprocal_rank(ranked_ids: List[str], gold: Sequence[str]) -> float:
    gold_set = set(gold)
    for idx, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in gold_set:
            return 1.0 / idx
    return 0.0


def ndcg_at_k(ranked_ids: List[str], gold: Sequence[str], k: int) -> float:
    gold_set = set(gold)
    dcg = 0.0
    for idx, doc_id in enumerate(ranked_ids[:k], start=1):
        if doc_id in gold_set:
            dcg += 1.0 / math.log2(idx + 1)
    ideal_hits = min(len(gold_set), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def aggregate_metrics(per_query_ranked: List[Tuple[List[str], Sequence[str]]], k: int) -> Dict[str, float]:
    n = len(per_query_ranked)
    if n == 0:
        return {"recall@k": 0.0, "mrr": 0.0, "ndcg@k": 0.0}
    recall = sum(recall_at_k(r, g, k) for r, g in per_query_ranked) / n
    mrr = sum(reciprocal_rank(r, g) for r, g in per_query_ranked) / n
    ndcg = sum(ndcg_at_k(r, g, k) for r, g in per_query_ranked) / n
    return {"recall@k": recall, "mrr": mrr, "ndcg@k": ndcg}


# ---------------------------------------------------------------------------
#  Pipeline: produce doc-level rankings for each method for a single query
# ---------------------------------------------------------------------------
class Pipeline:
    def __init__(self, corpus, args):
        self.args = args
        self.chunk_ids: List[str] = []
        self.chunk_texts: List[str] = []
        self.chunk_to_doc: Dict[str, str] = {}
        self.doc_text: Dict[str, str] = {}

        #  Chunking
        for doc in corpus:
            self.doc_text[doc["doc_id"]] = doc["text"]
            chunks = chunk_text(doc["text"], args.chunk_size, args.chunk_overlap)
            for i, chunk in enumerate(chunks):
                cid = f"{doc['doc_id']}::c{i}" if len(chunks) > 1 else doc["doc_id"]
                self.chunk_ids.append(cid)
                self.chunk_texts.append(chunk)
                self.chunk_to_doc[cid] = doc["doc_id"]

        self.n_docs = len(corpus)
        self.n_chunks = len(self.chunk_ids)

        #  Sparse index
        self.bm25 = BM25Retriever(self.chunk_ids, self.chunk_texts)

        #  Dense index (optional)
        self.dense: Optional[DenseRetriever] = None
        if args.use_dense:
            encoder = DenseEncoder(args.embed_model, args.pooling, args.device,
                                   query_instruct=args.query_instruct)
            self.dense = DenseRetriever(encoder, self.chunk_ids, self.chunk_texts)

        #  Reranker (optional)
        self.reranker: Optional[CrossEncoderReranker] = None
        if args.use_rerank:
            self.reranker = CrossEncoderReranker(args.reranker_model, args.device)

    def run_query(self, query: str) -> Dict[str, List[Tuple[str, float]]]:
        """  Return doc-level rankings for each method {method: [(doc_id, score)]}."""
        top_k = self.args.top_k
        sparse_chunks = self.bm25.search(query, top_k)
        sparse_docs = chunks_to_docs(sparse_chunks, self.chunk_to_doc)

        out: Dict[str, List[Tuple[str, float]]] = {"sparse": sparse_docs}

        if self.dense is not None:
            dense_chunks = self.dense.search(query, top_k)
            dense_docs = chunks_to_docs(dense_chunks, self.chunk_to_doc)
            out["dense"] = dense_docs

            ranked_lists = {"dense": dense_docs, "sparse": sparse_docs}
            weights = {"dense": self.args.dense_weight, "sparse": self.args.sparse_weight}
            rrf = fuse(ranked_lists, method="rrf", k=self.args.k_rrf, weights=weights)
            weighted = fuse(ranked_lists, method="weighted", weights=weights)
            out["rrf"] = rrf
            out["weighted"] = weighted

            if self.reranker is not None:
                #  Fine-rank top-N candidate pool from RRF fusion
                pool = [doc_id for doc_id, _ in rrf[: self.args.rerank_pool]]
                candidates = [(doc_id, self.doc_text[doc_id]) for doc_id in pool]
                reranked = self.reranker.rerank(query, candidates, self.args.rerank_top_k)
                out["rerank"] = reranked

        return out


# ---------------------------------------------------------------------------
#  Output: comparison table / single query trace
# ---------------------------------------------------------------------------
METHOD_LABELS = [
    ("sparse", "BM25 (sparse)"),
    ("dense", "Dense"),
    ("rrf", "Hybrid-RRF"),
    ("weighted", "Hybrid-Weighted"),
    ("rerank", "Hybrid-RRF+Rerank"),
]


def run_evaluation(pipeline: Pipeline, queries, args) -> Dict[str, Any]:
    k = args.eval_k
    per_method: Dict[str, List[Tuple[List[str], Sequence[str]]]] = {m: [] for m, _ in METHOD_LABELS}
    per_query_records = []

    t0 = time.time()
    for spec in queries:
        query = spec["query"]
        gold = spec.get("expected", [])
        results = pipeline.run_query(query)
        record = {"query": query, "expected": gold, "methods": {}}
        for method, _ in METHOD_LABELS:
            if method not in results:
                continue
            ranked_ids = [doc_id for doc_id, _ in results[method]]
            per_method[method].append((ranked_ids, gold))
            record["methods"][method] = {
                "top": [{"doc_id": d, "score": round(s, 4)} for d, s in results[method][:5]],
                "recall@k": round(recall_at_k(ranked_ids, gold, k), 4),
                "mrr": round(reciprocal_rank(ranked_ids, gold), 4),
                "ndcg@k": round(ndcg_at_k(ranked_ids, gold, k), 4),
            }
        per_query_records.append(record)
    elapsed = time.time() - t0

    summary = {}
    for method, _ in METHOD_LABELS:
        if per_method[method]:
            summary[method] = aggregate_metrics(per_method[method], k)

    return {
        "summary": summary,
        "per_query": per_query_records,
        "elapsed_sec": round(elapsed, 2),
        "eval_k": k,
    }


def print_table(report: Dict[str, Any], pipeline: Pipeline, args) -> None:
    k = report["eval_k"]
    print("=" * 78)
    print("Hybrid retrieval pipeline · stage-by-stage evaluation comparison")
    print("=" * 78)
    print(f"Corpus: {pipeline.n_docs}  documents → {pipeline.n_chunks}  chunks "
          f"(chunk_size={args.chunk_size}, overlap={args.chunk_overlap})")
    print(f"Queries: {len(report['per_query'])}  "
          f"Dense model: {args.embed_model if args.use_dense else '(disabled)'}   "
          f"Rerank model: {args.reranker_model if args.use_rerank else '(disabled)'}")
    print(f"Retrieval top_k={args.top_k}  Fusion k(RRF)={args.k_rrf}  "
          f"Rerank candidate pool={args.rerank_pool}  Evaluation truncation k={k}  device={args.device}")
    print(f"Time: {report['elapsed_sec']}s")
    print("-" * 78)
    header = f"{'Stage / Method':<22}{'Recall@'+str(k):>12}{'MRR':>12}{'nDCG@'+str(k):>12}"
    print(header)
    print("-" * 78)
    for method, label in METHOD_LABELS:
        if method not in report["summary"]:
            continue
        m = report["summary"][method]
        print(f"{label:<22}{m['recall@k']:>12.4f}{m['mrr']:>12.4f}{m['ndcg@k']:>12.4f}")
    print("-" * 78)
    print("Read the table: gradually add the dense retrieval / fusion / reranking stages from top to bottom and observe the changes in metrics.")
    print("=" * 78)


def print_per_query(report: Dict[str, Any]) -> None:
    """Print the MRR of each method for each query, intuitively showing that 'a single path may fail, fusion provides a safety net'."""
    methods = [m for m, _ in METHOD_LABELS]
    short = {"sparse": "BM25", "dense": "Dense", "rrf": "RRF",
             "weighted": "Wgt", "rerank": "Rerank"}
    print("\nMRR details for each query (1.00 = correct document ranked 1st; roughly see which path fails on which type of query)")
    print("-" * 78)
    header = f"{'Query':<42}" + "".join(f"{short[m]:>7}" for m in methods)
    print(header)
    print("-" * 78)
    for rec in report["per_query"]:
        cells = ""
        for m in methods:
            if m in rec["methods"]:
                cells += f"{rec['methods'][m]['mrr']:>7.2f}"
            else:
                cells += f"{'-':>7}"
        q = rec["query"]
        q = q if len(q) <= 41 else q[:38] + "..."
        print(f"{q:<42}{cells}")
    print("=" * 78)


def print_query_trace(pipeline: Pipeline, query: str, args) -> None:
    results = pipeline.run_query(query)
    print("=" * 78)
    print(f"Per-query per-stage ranking tracking   query = {query!r}")
    print(f"corpus {pipeline.n_docs} docs → {pipeline.n_chunks} chunk   device={args.device}")
    print("=" * 78)
    for method, label in METHOD_LABELS:
        if method not in results:
            continue
        print(f"\n[{label}]")
        for rank, (doc_id, score) in enumerate(results[method][:5], start=1):
            snippet = pipeline.doc_text.get(doc_id, "")[:60].replace("\n", " ")
            print(f"  {rank}. {doc_id:<14} score={score:8.4f}  {snippet}")
    print("=" * 78)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def detect_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI for offline evaluation of hybrid retrieval pipeline (chunk→embed→retrieve→fuse→rerank, compare per stage).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python evaluate.py                       # Built-in evaluation set, full comparison table\n"
            "  python evaluate.py --no-rerank           # Skip reranking stage\n"
            "  python evaluate.py --no-dense            # BM25 only (fully offline, no model needed)\n"
            "  python evaluate.py --query 'how to improve retrieval accuracy'  # Per-query per-stage ranking\n"
            "  python evaluate.py --embed-model BAAI/bge-m3 --pooling cls\n"
            "  python evaluate.py --output result.json  # Write results to JSON as well\n"
        ),
    )
    data = parser.add_argument_group("Data")
    data.add_argument("--corpus", help="Corpus JSON file, format [{'doc_id','text'}...]; default uses built-in corpus")
    data.add_argument("--queries", help="Query JSON file, format [{'query','expected':[...]}...]; default uses built-in queries")
    data.add_argument("--query", help="Single query mode: only run per-stage ranking tracking for that query, no evaluation")
    data.add_argument("--limit-queries", type=int, default=0, help="Only evaluate the first N queries (0 = all)")

    stages = parser.add_argument_group("Pipeline stages")
    stages.add_argument("--no-dense", dest="use_dense", action="store_false",
                        help="Disable dense retrieval (also disables fusion and reranking; falls back to pure BM25, fully offline, no model needed)")
    stages.add_argument("--no-rerank", dest="use_rerank", action="store_false",
                        help="Disable neural reranking stage")
    stages.set_defaults(use_dense=True, use_rerank=True)

    chunk = parser.add_argument_group("Chunking")
    chunk.add_argument("--chunk-size", type=int, default=280, help="Maximum characters per chunk (default 280)")
    chunk.add_argument("--chunk-overlap", type=int, default=40, help="Overlap characters between adjacent chunks (default 40)")

    retr = parser.add_argument_group("Retrieval and Fusion")
    retr.add_argument("--top-k", type=int, default=10, help="Number of candidates retrieved per path (default 10)")
    retr.add_argument("--k-rrf", type=int, default=60, help="RRF smoothing constant k (default 60)")
    retr.add_argument("--dense-weight", type=float, default=1.0, help="Dense path weight during fusion (default 1.0)")
    retr.add_argument("--sparse-weight", type=float, default=1.0, help="Sparse path weight during fusion (default 1.0)")

    rer = parser.add_argument_group("Reranking")
    rer.add_argument("--rerank-pool", type=int, default=10, help="Candidate pool size for reranking (top-N from RRF fusion, default 10)")
    rer.add_argument("--rerank-top-k", type=int, default=10, help="Number of results returned after reranking (default 10)")

    model = parser.add_argument_group("Model")
    model.add_argument("--embed-model", default="sentence-transformers/all-MiniLM-L6-v2",
                       help="Dense sentence embedding model (default sentence-transformers/all-MiniLM-L6-v2, ~90MB, English-oriented;"
                            "For multilingual corpora, switch to Qwen/Qwen3-Embedding-0.6B or BAAI/bge-m3)")
    model.add_argument("--pooling", default="auto", choices=["auto", "mean", "cls", "last"],
                       help="Sentence embedding pooling method (auto selects based on model name: qwen→last, bge-m3→cls, others→mean)")
    model.add_argument("--query-instruct",
                       default="Given a search query, retrieve relevant passages that answer the query",
                       help="Query-side task instruction for instruction-aware retrieval models (only effective for last-token pooling models like Qwen3-Embedding)")
    model.add_argument("--reranker-model", default="BAAI/bge-reranker-base",
                       help="Cross-encoder reranking model (default BAAI/bge-reranker-base, multilingual, ~1.1GB on first run;"
                            "For production, switch to stronger BAAI/bge-reranker-v2-m3; for lightweight, use cross-encoder/ms-marco-MiniLM-L-6-v2)")
    model.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"],
                       help="Inference device (default auto)")

    out = parser.add_argument_group("Evaluation and Output")
    out.add_argument("--eval-k", type=int, default=3, help="Metric truncation position k (Recall@k / nDCG@k, default 3)")
    out.add_argument("--no-per-query", dest="show_per_query", action="store_false",
                     help="Do not print per-query MRR detail matrix")
    out.set_defaults(show_per_query=True)
    out.add_argument("--output", help="Write full results (including per-query details) to this JSON file")
    out.add_argument("--offline", action="store_true", help="Set HF_HUB_OFFLINE=1 to force using only local cached models")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

    args.device = detect_device(args.device)
    #Single query tracing mode does not affect use_dense/use_rerank semantics, but reranking depends on dense fusion pool
    if not args.use_dense:
        args.use_rerank = False

    corpus = load_json(args.corpus) if args.corpus else DEFAULT_CORPUS
    queries = load_json(args.queries) if args.queries else DEFAULT_QUERIES

    try:
        pipeline = Pipeline(corpus, args)
    except Exception as exc:  # noqa: BLE001
        print(f"[Error] Pipeline initialization failed: {exc}", file=sys.stderr)
        print("Hint: Dense/reranking stages require local sentence embedding and cross-encoder models;"
              "Use --no-dense to fall back to pure BM25 (fully offline), or specify a cached model with --embed-model.",
              file=sys.stderr)
        return 1

    if args.query:
        print_query_trace(pipeline, args.query, args)
        return 0

    if args.limit_queries > 0:
        queries = queries[: args.limit_queries]

    report = run_evaluation(pipeline, queries, args)
    print_table(report, pipeline, args)
    if args.show_per_query:
        print_per_query(report)

    if args.output:
        payload = {
            "config": {
                "embed_model": args.embed_model if args.use_dense else None,
                "reranker_model": args.reranker_model if args.use_rerank else None,
                "top_k": args.top_k, "k_rrf": args.k_rrf, "eval_k": args.eval_k,
                "chunk_size": args.chunk_size, "chunk_overlap": args.chunk_overlap,
                "device": args.device,
            },
            **report,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\nResults written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
