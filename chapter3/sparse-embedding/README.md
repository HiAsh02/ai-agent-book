# Educational Sparse Vector Search Engine

An educational implementation of a sparse vector search engine using inverted index and BM25 algorithm. This project demonstrates the fundamental concepts of information retrieval with extensive logging and visualization features for learning purposes.

## Features

- **Full BM25 Implementation**: Complete implementation of the BM25 ranking algorithm
- **Advanced Tokenization**: Comprehensive tokenizer handling numbers, codes, technical terms, and mixed case
- **Inverted Index**: Efficient inverted index data structure for term lookup
- **HTTP API**: RESTful API built with FastAPI
- **Interactive Web UI**: Browser-based interface for indexing and searching
- **Extensive Logging**: Detailed educational logging throughout indexing and search operations
- **Index Visualization**: APIs to inspect the internal structure of the index
- **In-Memory Storage**: Simple in-memory storage for educational purposes

### Tokenization Capabilities

The TextProcessor now provides comprehensive tokenization for real-world text:

- **Numbers**: `404`, `3.14`, `2.0.1`
- **Codes**: `XK9-2B4-7Q1`, `API_KEY_123`
- **Technical Terms**: `C++`, `.NET`, `Node.js`
- **Mixed Case**: `JavaScript`, `PyTorch`, `iPhone`
- **Email**: `user@example.com`
- **Hex Codes**: `#FF5733`, `0x1234`
- **Acronyms**: `API`, `HTTP`, `NASA`
- **Alphanumeric**: `Python3`, `ES6`, `HTML5`

## Architecture

### Core Components

1. **TextProcessor**: Advanced tokenizer handling words, numbers, codes, technical terms, and mixed case
2. **InvertedIndex**: Maintains the inverted index structure with term frequencies and document frequencies
3. **BM25**: Implements the BM25 ranking algorithm for relevance scoring
4. **SparseSearchEngine**: Main engine coordinating all components
5. **HTTP Server**: FastAPI-based server exposing the search engine functionality

### BM25 Algorithm

BM25 (Best Matching 25) is a probabilistic ranking function that scores documents based on query terms. The algorithm uses:

- **Term Frequency (TF)**: How often a term appears in a document
- **Inverse Document Frequency (IDF)**: How rare or common a term is across all documents
- **Document Length Normalization**: Adjusts scores based on document length

Key parameters:
- `k1` (default 1.5): Controls term frequency saturation
- `b` (default 0.75): Controls length normalization

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

`cli.py` (the command-line tool in the next section) only depends on the Python standard library and can run offline without installing any third-party packages; `server.py` / `demo.py` require the FastAPI and other dependencies listed above.

## Command-Line Tool cli.py (Experiments 3-5, Recommended Entry Point)

`cli.py` provides a fully offline command-line entry point: it runs BM25 sparse retrieval on a built-in corpus of 10 small documents, reproduces the per-word IDF/TF/BM25 contribution logs from the book, and computes recall/precision/MRR on an annotated evaluation set. All parameters have Chinese `--help` text.

```bash
python cli.py --help                          # View all parameters (in Chinese)
python cli.py                                 # Default demo: query "model distillation"
python cli.py -q "model distillation" --explain   # Show per-word TF/IDF/BM25 contributions (matching the book's logs)
python cli.py --eval                          # Compute recall@k / precision@k / MRR on the annotated set
python cli.py -q "cat"                        # Observe BM25's inability to handle synonyms (kitten/feline are missed)
python cli.py --corpus my.json -q "query" -o out.json   # Custom corpus + save results to file
python cli.py --k1 2.0 -b 0.5 -q "..."        # Tune BM25 parameters k1 / b
python cli.py --method splade -q "..."        # Learned sparse retrieval SPLADE (requires pre-downloading the model)
```

Main parameters:

| Parameter | Description |
| --- | --- |
| `-q, --query` | Query string (default `model distillation`) |
| `-c, --corpus` | Corpus file (`.json` array of documents or `.jsonl` one document per line); if omitted, uses the built-in example corpus |
| `-m, --method` | `bm25` (default, offline) or `splade` (learned sparse, requires downloading the model) |
| `-k, --top-k` | Return top k results (default 5) |
| `-o, --output` | Write results / evaluation metrics to a JSON file |
| `--eval` | Evaluate recall@k / precision@k / MRR on the annotated set |
| `--labels` | Custom evaluation labels `{query: [relevant_doc_id,...]}` |
| `--explain` | Show per-word TF / IDF / BM25 contributions for matched documents |
| `--k1` / `-b` | BM25 term frequency saturation parameter k1, document length normalization parameter b |
| `-v, --verbose` | Enable engine DEBUG logs (tokenization, inverted index construction, scoring process) |

### Retrieval Quality Evaluation (--eval)

The built-in annotated set covers exact keyword queries, error codes, proper names, and queries with only synonymous expressions. Actual output of `python cli.py --eval` (k=5):

```
Query 'model distillation'  recall@5=1.00  precision@5=1.00  RR=1.00
Query 'HTTP 404 error'       recall@5=1.00  precision@5=0.50  RR=1.00
Query 'XK9-2B4-7Q1'          recall@5=1.00  precision@5=1.00  RR=1.00
Query 'BM25 ranking function' recall@5=1.00  precision@5=1.00  RR=1.00
Query 'cat'                  recall@5=0.00  precision@5=0.00  RR=0.00   <- Missed recall (synonym weakness)
Macro average  recall@5=0.800  precision@5=0.700  MRR=0.800  Missed recall rate (1-recall@5)=0.200
```

The results intuitively confirm the book's conclusion: BM25 performs excellently on exact keywords, error codes, and proper names (recall=1.0), but cannot handle synonyms — the query `cat` fails to match documents that only contain `kitten` / `feline` (recall=0). This strength and weakness together motivate the introduction of hybrid retrieval (see Experiment 3-6 `retrieval-pipeline`).

### Learned Sparse Retrieval (--method splade)

`--method splade` corresponds to the learned sparse retrieval (SPLADE) mentioned in the book: it uses a masked language model to assign weights to each term and can also assign weights to semantically related terms not present in the original text (term expansion). It requires downloading the pre-trained model `naver/splade-cocondenser-ensembledistil` (depends on `torch`, `transformers`). In an offline environment where the weights cannot be downloaded, the command will quickly give a clear prompt (and explain that the BM25 path can run offline without any model), without getting stuck on network downloads. In a networked environment, you can first run `huggingface-cli download naver/splade-cocondenser-ensembledistil` to cache the model before running.

## Usage

### Starting the Server

```bash
python server.py
```

The server will start on `http://localhost:4241`

### Web Interface

Open your browser and navigate to `http://localhost:4241` to access the interactive web UI.

### API Endpoints

#### Index a Document
```bash
POST /index
{
  "text": "Your document text here",
  "metadata": {"title": "Document Title", "category": "Category"}
}
```

#### Search Documents
```bash
POST /search
{
  "query": "your search query",
  "top_k": 10
}
```

#### Get Statistics
```bash
GET /stats
```

#### Get Index Structure
```bash
GET /index/structure
```

#### Retrieve Document by ID
```bash
GET /document/{doc_id}
```

#### Clear Index
```bash
DELETE /index
```

### Running the Demo

```bash
python demo.py
```

The demo script will:
1. Clear any existing index
2. Index sample documents about programming and computer science
3. Display index statistics
4. Show the internal index structure
5. Perform various search queries
6. Demonstrate document retrieval

## Educational Features

### Extensive Logging

The system provides detailed logging at every step:- Document tokenization process
- Term frequency calculations
- IDF score computations
- BM25 scoring for each term
- Query processing steps
- Candidate document identification

### Index Visualization

The `/index/structure` endpoint returns:
- Inverted index mapping (terms to documents)
- Document statistics (length, unique terms, top terms)
- BM25 parameters
- Global term frequency distribution

### Debug Information in Search Results

Each search result includes debug information:
- Matched query terms
- Document length
- Term frequencies for query terms
- Individual term contributions to the final score

## Example Output

### Indexing Log
```
2024-01-15 10:30:45 - Indexing document with ID 0
2024-01-15 10:30:45 - Document text: Python is a high-level programming...
2024-01-15 10:30:45 - Tokenizing text of length 142
2024-01-15 10:30:45 - Found 23 raw tokens
2024-01-15 10:30:45 - After removing stop words: 15 tokens
2024-01-15 10:30:45 - Document 0: 15 tokens, 12 unique terms
2024-01-15 10:30:45 - Document 0 indexed successfully
```

### Search Log
```
2024-01-15 10:31:20 - Searching for: 'machine learning algorithms'
2024-01-15 10:31:20 - Query terms after processing: ['machine', 'learning', 'algorithms']
2024-01-15 10:31:20 - Term 'machine' appears in 2 documents
2024-01-15 10:31:20 - Term 'learning' appears in 3 documents
2024-01-15 10:31:20 - Term 'algorithms' appears in 1 document
2024-01-15 10:31:20 - Found 4 candidate documents
2024-01-15 10:31:20 - IDF for 'machine': N=10, df=2, idf=1.7918
2024-01-15 10:31:20 - Term 'machine' in doc 1: tf=2, dl=35, score=3.2451
2024-01-15 10:31:20 - Document 1 total score: 7.8923
2024-01-15 10:31:20 - Returning top 3 results
```

## API Documentation

Interactive API documentation is available at `http://localhost:4241/docs` when the server is running.

## Project Structure

```
sparse-embedding/
├── bm25_engine.py     # Core search engine implementation
├── cli.py             # Offline argparse CLI: BM25/SPLADE search + recall/precision eval
├── server.py          # FastAPI HTTP server
├── demo.py            # Demonstration script
├── requirements.txt   # Python dependencies
└── README.md         # This file
```

## Learning Resources

This implementation demonstrates:
- How inverted indices work in search engines
- The mathematics behind BM25 ranking
- Term frequency and document frequency concepts
- The importance of text preprocessing
- How sparse vectors represent documents
- RESTful API design for search systems

## Limitations

This is an educational implementation with some limitations:
- In-memory storage (not persistent)
- Basic tokenization (could be improved with lemmatization)
- English-only stop words
- No support for phrase queries
- No query expansion or synonyms
- Single-threaded processing

## Further Improvements

Potential enhancements for learning:
- Add persistence with a database
- Implement more advanced text processing (stemming, lemmatization)
- Add support for phrase queries
- Implement query expansion
- Add multi-language support
- Implement index compression techniques
- Add support for field-specific searching
- Implement more ranking algorithms (TF-IDF, Okapi BM25+)
