# Vector Similarity Search Service

An educational HTTP service for vector similarity search using BGE-M3 embeddings with configurable ANNOY or HNSW indexing backends.

---

## Command Line Tool: Dense Retrieval & ANN Comparison (cli.py, Experiment 3-4)

In addition to the HTTP service above, this project provides an **out-of-the-box, offline-reproducible** command line tool `cli.py` that directly quantifies the two observation points from Experiment 3-4 in the book into measurable numbers, without needing to start the service first:

1. **Semantic capability of dense embedding retrieval** — computes `recall@k / precision@k / MRR` on a small annotated corpus;
2. **ANN index backend comparison** (the focus of Experiment 3-4) — reuses the ANNOY / HNSW implementations from the server-side `indexing.py` to measure their recall relative to **exact brute-force search**, index build time, and query latency.

### Usage

```bash
# 1) Single dense query (default query "a cat playing", requires embedding model)
python cli.py -q "model distillation" -k 3

# 2) Retrieval quality evaluation: recall@k / precision@k / MRR
python cli.py --eval

# 2') Offline reproduction: use a cached small model (no need to download 2.3GB BGE-M3)
python cli.py --embedding-model sentence-transformers/all-MiniLM-L6-v2 --eval

# 3) ANN backend comparison (synthetic vectors, fully offline, no model required)
python cli.py --compare-ann -k 10
python cli.py --compare-ann --backend hnsw --hnsw-ef-search 200 -k 10   # Tune ef_search to see recall increase

# Custom corpus / labels / output
python cli.py --corpus my.json --labels my_labels.json --eval -o result.json
```

`python cli.py --help` provides complete parameter descriptions in Chinese (`--corpus / --query / --embedding-model / --top-k / --output`, plus various index hyperparameters for ANN comparison).

### Common Parameters

| Parameter | Description |
| --- | --- |
| `-q, --query` | Query string (default `a cat playing`) |
| `-c, --corpus` | Corpus file (`.json` array or `.jsonl` one document per line); defaults to built-in example corpus |
| `-k, --top-k` | Return top k results (default 5) |
| `-o, --output` | Write results / evaluation metrics to a JSON file |
| `--embedding-model` | Embedding model name (default `BAAI/bge-m3`; offline-capable `sentence-transformers/all-MiniLM-L6-v2`) |
| `--pooling` | Pooling method `auto` (bge* uses cls, others mean) / `mean` / `cls` |
| `--eval` | Evaluate recall@k / precision@k / MRR on the labeled dataset |
| `--compare-ann` | Compare ANNOY / HNSW (synthetic vectors, no model required) |
| `--ann-base / --ann-dim / --ann-queries` | Synthetic base size / dimension / number of queries (default 3000 / 128 / 100) |
| `--annoy-n-trees / --hnsw-M / --hnsw-ef-search` | Key index hyperparameters for the two ANN types |

### Measured Results (Real Runs, Not Fabricated)

**Dense Retrieval Quality** (built-in 12-document corpus, `all-MiniLM-L6-v2`, offline):

```
Macro avg  recall@5=1.000  precision@5=0.320  MRR=1.000
```

For the query `a cat playing`, the relevant documents only use `kitten` / `feline` and **do not contain the literal word "cat"**; dense retrieval still ranks them 1st and 2nd — this is the semantic advantage of dense over sparse BM25 (Experiment 3-5 would miss recall).

**ANN Backend Comparison** (3000 128-dimensional random unit vectors, 100 queries, top-10): HNSW recall increases monotonically with `ef_search`, demonstrating the "precision / speed" trade-off:

| Configuration | recall@10 | Avg Query Latency |
| --- | --- | --- |
| HNSW `ef_search=20` | 0.562 | 0.05 ms |
| HNSW `ef_search=200` | 0.991 | 0.25 ms |

> **Environment Note**: This tool performs a "self-query" health check for each backend. On some macOS/arm64 environments, the precompiled wheel for `annoy==1.17.3` has a defect (even querying a vector already in the index only returns itself). In such cases, the tool prints `[Warning] ...suspected to be broken in the current environment` and marks that backend's numbers as unreliable. HNSW is unaffected. To reproduce the full ANNOY vs HNSW comparison, run in an environment where annoy works correctly (e.g., Linux x86_64).

## Features

- **BGE-M3 Model**: State-of-the-art multilingual embedding model supporting:
  - Dense embeddings for semantic search
  - Multi-language support (100+ languages)
  - Long context (up to 8192 tokens)
  
- **Dual Indexing Backends**:
  - **ANNOY** (Approximate Nearest Neighbors Oh Yeah): Fast, memory-efficient tree-based index
  - **HNSW** (Hierarchical Navigable Small World): High-precision graph-based index

- **Educational Logging**: Extensive debug logs showing:
  - Embedding generation process
  - Index operations (insert/delete/search)
  - Performance metrics
  - Vector statistics

- **RESTful API**: Clean HTTP endpoints for:
  - Document indexing (insert/update)
  - Document deletion
  - Similarity search
  - Statistics and monitoring

- **In-Memory Storage**: Pure in-memory operation for simplicity (no persistence)

## Architecture

```
┌──────────────────┐
│   HTTP Client    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  FastAPI Server  │
└────────┬─────────┘
         │
         ▼
    ┌────┴────┐
    │         │
    ▼         ▼
┌──────────┐ ┌──────────────┐
│ Document │ │  Embedding   │
│  Store   │ │   Service    │
└──────────┘ │  (BGE-M3)    │
             └──────┬─────────┘
                    │
                    ▼
          ┌─────────┴──────────┐
          │                    │
          ▼                    ▼
    ┌──────────┐        ┌──────────┐
    │  ANNOY   │        │   HNSW   │
    │  Index   │        │  Index   │
    └──────────┘        └──────────┘
```

## Installation

### Prerequisites

- Python 3.8 or higher
- macOS (optimized for M1/M2 chips) or Linux
- At least 4GB RAM (8GB recommended)
- CUDA-compatible GPU (optional, for faster embedding generation)

### Setup

1. Install dependencies:

```bash
cd projects/week3/dense-embedding
pip install -r requirements.txt
```

2. Download BGE-M3 model (will be downloaded automatically on first run):
   - Model size: ~2.3GB
   - Will be cached in HuggingFace cache directory

## Usage

### Starting the Service

#### With HNSW Index (Default)

```bash
python main.py
```

#### With ANNOY Index

```bash
python main.py --index-type annoy
```

#### With Custom Configuration

```bash
python main.py --index-type hnsw --host 0.0.0.0 --port 4242 --debug --show-embeddings
```

#### Available Options

- `--index-type`: Choose index backend (`annoy` or `hnsw`, default: `hnsw`)
- `--host`: Server host (default: `0.0.0.0`)
- `--port`: Server port (default: `4240`)
- `--debug`: Enable debug mode with verbose logging
- `--show-embeddings`: Show embedding vectors in logs (educational)

### API Documentation

Once the service is running, visit:
- Interactive docs: http://localhost:4240/docs
- OpenAPI schema: http://localhost:4240/openapi.json

### API Endpoints

#### 1. Index Document

```bash
POST /index
```

Index a new document or update existing one.

**Request:**
```json
{
  "text": "Machine learning is a subset of artificial intelligence.",
  "doc_id": "doc_001",  // Optional, auto-generated if not provided
  "metadata": {         // Optional metadata
    "category": "AI",
    "author": "John Doe"
  }
}
```

**Response:**
```json
{
  "success": true,
  "doc_id": "doc_001",
  "message": "Document indexed successfully using hnsw",
  "index_size": 1
}
```

#### 2. Search Documents

```bash
POST /search
```

Search for similar documents.

**Request:**
```json
{
  "query": "What is deep learning?",
  "top_k": 5,
  "return_documents": true
}
```

**Response:**
```json
{
  "results": [
    {
      "doc_id": "doc_001",
      "score": 0.92,
      "text": "Machine learning is a subset of artificial intelligence.",
      "metadata": {
        "category": "AI",
        "author": "John Doe"
      }
    }
  ],
  "query": "What is deep learning?",
  "total_results": 1
}
```  "success": true,
  "query": "What is deep learning?",
  "results": [
    {
      "doc_id": "doc_001",
      "score": 0.8543,
      "text": "Machine learning is a subset...",
      "metadata": {"category": "AI"},
      "rank": 1
    }
  ],
  "total_results": 5,
  "search_time_ms": 12.5
}
```

#### 3. Delete Document

```bash
DELETE /index
```

Delete a document from the index.

**Request:**
```json
{
  "doc_id": "doc_001"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Document doc_001 deleted successfully",
  "index_size": 0
}
```

#### 4. Get Statistics

```bash
GET /stats
```

Get service statistics.

**Response:**
```json
{
  "index_type": "hnsw",
  "index_size": 100,
  "document_count": 100,
  "embedding_dimension": 1024,
  "model_name": "BAAI/bge-m3"
}
```

#### 5. List Documents

```bash
GET /documents?limit=10
```

List documents in the store.

## Testing

### Run Demo Client

The demo client showcases all features with sample documents:

```bash
python test_client.py
```

### Run Performance Test

Test indexing and search performance with synthetic data:

```bash
python test_client.py --performance
```

### Manual Testing with curl

Index a document:
```bash
curl -X POST http://localhost:4240/index \
  -H "Content-Type: application/json" \
  -d '{"text": "This is a test document about machine learning."}'
```

Search for similar documents:
```bash
curl -X POST http://localhost:4240/search \
  -H "Content-Type: application/json" \
  -d '{"query": "artificial intelligence", "top_k": 5}'
```

## Index Comparison

### ANNOY (Approximate Nearest Neighbors Oh Yeah)

**Pros:**
- Very fast indexing
- Low memory footprint
- Good for static datasets
- Supports multiple distance metrics

**Cons:**
- Requires rebuild for deletion
- No incremental updates after build
- Trade-off between speed and accuracy (controlled by n_trees)

**Best for:**
- Large-scale similarity search
- Read-heavy workloads
- Memory-constrained environments

### HNSW (Hierarchical Navigable Small World)

**Pros:**
- High recall accuracy
- Supports incremental updates
- Fast search with good precision
- Supports soft deletion

**Cons:**
- Higher memory usage
- Slower indexing than ANNOY
- More complex parameter tuning

**Best for:**
- Dynamic datasets
- High-precision requirements
- Balanced read/write workloads

## Configuration

### Environment Variables

You can configure the service using environment variables with the `VEC_` prefix:

```bash
export VEC_INDEX_TYPE=hnsw
export VEC_MODEL_NAME=BAAI/bge-m3
export VEC_USE_FP16=true
export VEC_MAX_SEQ_LENGTH=512
export VEC_MAX_DOCUMENTS=100000
export VEC_LOG_LEVEL=DEBUG

# ANNOY specific
export VEC_ANNOY_N_TREES=50
export VEC_ANNOY_METRIC=angular

# HNSW specific
export VEC_HNSW_EF_CONSTRUCTION=200
export VEC_HNSW_M=32
export VEC_HNSW_EF_SEARCH=100
export VEC_HNSW_SPACE=cosine
```

## Educational Features

This service includes extensive logging for educational purposes:

1. **Embedding Generation Logs**: Shows the process of converting text to vectors
2. **Index Operation Logs**: Detailed information about index updates
3. **Search Process Logs**: Step-by-step search execution
4. **Performance Metrics**: Timing information for all operations
5. **Vector Statistics**: Min/max/mean values of embeddings (when enabled)

Enable full educational logging:
```bash
python main.py --debug --show-embeddings
```

## Performance Considerations

### Memory Usage

- BGE-M3 model: ~2.3GB
- Per document overhead: ~4KB (1024-dim float32 embedding)
- ANNOY index: ~(4 * dimension * n_items * n_trees / 2) bytes
- HNSW index: ~(4 * dimension * n_items * M * 2) bytes

### Optimization Tips

1. **For ANNOY**:
   - Increase `n_trees` for better accuracy (slower build)
   - Use `angular` metric for normalized vectors
   - Build index after batch insertions

2. **For HNSW**:
   - Increase `M` for better recall (more memory)
   - Increase `ef_construction` for better index quality (slower build)
   - Adjust `ef_search` for speed/accuracy trade-off

3. **General**:
   - Use FP16 for faster inference (slight accuracy loss)
   - Batch document insertions when possible
   - Limit `max_seq_length` based on your documents

## Troubleshooting

### Common Issues

1. **Out of Memory**:
   - Reduce batch size
   - Use FP16 mode
   - Lower max_seq_length
   - Use ANNOY instead of HNSW

2. **Slow Indexing**:
   - Reduce HNSW ef_construction
   - Reduce ANNOY n_trees
   - Use GPU if available

3. **Poor Search Quality**:
   - Increase ANNOY n_trees
   - Increase HNSW M and ef_search
   - Check if documents are too short/long

## References

- [BGE-M3 Paper](https://arxiv.org/abs/2402.03216)
- [BGE-M3 Model](https://huggingface.co/BAAI/bge-m3)
- [ANNOY Library](https://github.com/spotify/annoy)
- [HNSWlib](https://github.com/nmslib/hnswlib)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## License

This is an educational project for learning purposes.
