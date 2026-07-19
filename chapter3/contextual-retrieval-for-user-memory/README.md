# Experiment 3-12: Enhancing User Memory with Context-Aware Retrieval

Applying context-aware retrieval techniques to user memory construction addresses the core pain points of traditional dialogue history chunking and is key to advancing toward higher-level memory capabilities. This project implements a dual-layer memory system that combines:

1. **Contextual RAG**: Precise retrieval of dialogue history
2. **Advanced JSON Cards**: Structured storage of core facts

## 🆕 Latest Updates

### LLM-Based Memory Card Generation
- **Automatic Extraction**: Uses LLM to intelligently extract structured memory cards from conversations
- **Complete Structure**: Each card contains necessary fields such as backstory, person, relationship
- **Intelligent Fallback**: Automatically degrades to keyword extraction when LLM is unavailable

### LLM Judge Integration  
- **Automatic Evaluation**: Integrates LLM Judge to automatically score Agent responses
- **Dual Path Support**: Supports both module import and direct API calls
- **Detailed Feedback**: Provides 0-1 scores, pass/fail status, and evaluation reasoning

### Enhanced Debugging
- **Memory Card Visualization**: Automatically prints full JSON of all memory cards during evaluation
- **Test Case Ordering**: Displays test cases sorted alphabetically by name
- **Evaluation Transparency**: Clearly shows LLM Judge usage status

## Core Innovations

### 1. Context-Enhanced Dialogue Chunking

Traditional dialogue chunking loses contextual information. For example, an isolated dialogue fragment "Okay, book this one" is meaningless on its own. Only when we know the preceding context—discussing a "one-way ticket from Shanghai to Seattle priced at $500"—does this fragment become meaningful.

This system adds a critical "context generation" step before indexing dialogue history:
- Each dialogue chunk calls the LLM to generate a prefix summary containing key background information
- Context includes critical clues such as time, people, and intent
- Significantly improves retrieval accuracy and relevance

### 2. Dual-Layer Memory Structure

**Advanced JSON Cards (Persistent Memory)**
- Stores structured, summarized core facts
- Always fixed in the Agent's context
- Contains metadata such as backstory (information source) and relationship (related persons)
- Example: "User Jessica's passport will expire on February 18, 2025"

**Contextual RAG (On-Demand Retrieval)**
- Provides precise access to unstructured raw dialogue details
- Quickly finds complete context for specific discussions
- Serves as "evidence" to support decision-making

### 3. LLM-Based Memory Extraction

The system can now intelligently extract structured memory cards from conversations:

```python
# Automatically generate memory cards from conversations
cards = indexer._generate_summary_cards(chunks, conversation_id)

# Example of generated card:
{
    "category": "financial",
    "card_key": "bank_account_primary", 
    "backstory": "User provided bank information when opening the account",
    "date_created": "2024-01-15 10:30:00",
    "person": "John Smith (primary)",
    "relationship": "primary account holder",
    "bank_name": "Chase Bank",
    "account_type": "checking",
    "account_ending": "4567"
}
```

## Project Structure

```
contextual-retrieval-for-user-memory/
├── contextual_chunking.py      # Context-aware chunking
├── advanced_memory_manager.py  # Advanced JSON card management
├── contextual_indexer.py       # Dual-layer memory indexer (with LLM extraction)
├── contextual_agent.py         # Agent combining dual-layer memory
├── contextual_evaluator.py     # Evaluation framework (with LLM Judge)
├── contextual_compare.py       # 🆕 Offline comparison script: contextual vs plain chunk recall (no API needed)
├── memory_qa_eval.json         # 🆕 Controlled memory QA evaluation set for offline comparison
├── main.py                     # Main entry point (argparse, includes --mode compare for offline comparison)
├── config.py                   # Configuration management
├── chunker.py                  # Base chunker
├── tools.py                    # Agent tools
└── requirements.txt            # Dependencies
```

## Installation and Configuration

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file:

```bash
# LLM Provider Configuration
MOONSHOT_API_KEY=your_api_key_here
ARK_API_KEY=your_api_key_here
SILICONFLOW_API_KEY=your_api_key_here
OPENAI_API_KEY=your_api_key_here

# Default Provider
LLM_PROVIDER=kimi  # Options: kimi, doubao, siliconflow, openai

# Model Settings
LLM_MODEL=kimi-k3  # Or other models
```

### 3. Start the Retrieval Pipeline Service

```bash
cd ../retrieval-pipeline
python api_server.py
```

## Usage Examples

### Offline Comparison: Does Contextualization Help? (No API Needed, Recommended to Run First)

The core thesis of this experiment is: **Generating a 'context prefix' for each dialogue memory chunk before feeding it into embedding/indexing improves recall of isolated fragments (e.g., 'Okay, book this one') that lack context.** `--mode compare` provides a **fully offline, controlled comparison experiment that requires no API Key or retrieval service** to quantify this.

It uses the same context to measure recall for both 'plain' (no concatenation) and 'contextual' (concatenated before indexing) approaches, with the only variable being whether the indexed text includes the context prefix. Thus, the results directly reflect the contribution of contextualization itself. Retrieval uses deterministic BM25 lexical retrieval (pure Python, no third-party dependencies) as an offline proxy for neural embeddings; the comparison dataset is in [`memory_qa_eval.json`](memory_qa_eval.json) (a controlled teaching set, replaceable with `--dataset`).

```bash
# Print comparison metrics table (Recall@1 / Recall@3 / MRR)
python main.py --mode compare
# Equivalent to running the standalone script directly:
python contextual_compare.py

# Compare plain vs contextual Top-K retrieval for a single query
python main.py --mode compare --query 'Which flight was the ticket I finally confirmed?'

# Save full results (including per-query ranking details) to JSON
python main.py --mode compare --output results/compare.json
```

Example output (controlled set with 12 memory chunks and 8 queries):

```
Method                          Recall@1  Recall@3       MRR
--------------------------------------------------------------------
Plain (directly indexing raw chunks)      0.625     1.000     0.792
Contextual (indexing after contextualization)        0.750     1.000     0.875
--------------------------------------------------------------------
Improvement (Δ)                         +0.125    +0.000    +0.083
```

For queries like "Has my Seattle hotel booking been confirmed?", the gold memory chunk ("Okay, book it for me") ranked 3rd under Plain but rose to 1st under Contextual—the context prefix re-anchored the isolated confirmation fragment back to the "Seattle Hyatt Hotel" scenario.

> Note: This is an **offline lexical proxy** designed to clearly demonstrate the mechanism and directional benefits of contextualization in an API-free environment. In the production pipeline, context prefixes are generated per chunk by the LLM and indexed using neural embeddings + hybrid retrieval (see `--mode evaluate` below), requiring API Key configuration.

### End-to-End Evaluation (Requires API / Retrieval Service)

```bash
# Interactive interface (default)
python main.py

# Evaluate a specific category (requires LLM and retrieval pipeline service)
python main.py --mode evaluate --category layer1

# Disable contextualization for comparison, specify model and output
python main.py --mode evaluate --category layer1 --no-contextual --model gpt-5.6-luna --output results/plain_eval.json
```

See `python main.py --help` for full command-line arguments (with Chinese descriptions).

### Interactive Test Interface

Run `python main.py` to enter the interactive interface:

```
Main Menu:
1. 🚀 Demo Mode (Quick Start)
2. 📚 Load & Index Conversations
3. 🎴 Manage Memory Cards
4. 🔍 Test Query
5. 📊 Evaluate All Test Cases (by Category) [LLM Judge]
6. 🎯 Evaluate Specific Test Case [LLM Judge]
7. 📈 Show Statistics
8. ⚙️  Configure Settings
0. Exit
```

### Evaluation Output Example

```
============================================================
DEBUG: All Memory Cards in System
============================================================

[financial.bank_account_primary]
{
  "backstory": "Information provided by the user when opening a bank account",
  "date_created": "2024-06-12 14:30:00",
  "person": "Michael James Robertson (primary)",
  "relationship": "primary account holder",
  "bank_name": "First National Bank",
  "account_number": "4429853327",
  "routing_number": "123006800"
}

Total Memory Cards: 5
============================================================

LLM Judge Evaluation Results
============================================================
Reward: 1.000/1.000
Passed: Yes
Reasoning: The agent correctly provided the checking account number...
============================================================
```

## Workflow Example

When a user asks "What else should I prepare for my Tokyo trip in January?":

1. **Fact Review**: The Agent first examines the content in Advanced JSON Cards
   - Finds "Tokyo trip" information (departing January 25th)
   - Finds "passport information" (expiring February 18th)

2. **Association and Reasoning**: By comparing core facts
   - Identifies the risk of the flight date being close to the passport expiration date

3. **Detail Verification**: Initiates RAG retrieval
   - Searches for dialogue fragments related to "passport" and "Tokyo flight"
   - Retrieves all details from the original discussion

4. **Proactive Service**: Combines both types of memory
   - Provides a key recommendation: "Your passport is about to expire. We strongly recommend you expedite the renewal immediately."

5. **Automatic Evaluation**: LLM Judge evaluates the answer
   - Score: 0.95/1.0
   - Reasoning: Correctly identified the risk and provided appropriate recommendations

## References

- [Anthropic's Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)- [RAG Technology Survey](https://arxiv.org/abs/2005.11401)
- [Memory Systems in AI Agents](https://arxiv.org/abs/2203.14680)
- [LLM as Judge](https://arxiv.org/abs/2306.05685)

## License

MIT License

## OpenRouter Universal Fallback / Universal OpenRouter fallback

This experiment now supports a **universal OpenRouter fallback** for its chat LLM.

- If the primary provider key (e.g. `MOONSHOT_API_KEY` / `KIMI_API_KEY` / `OPENAI_API_KEY` / `DOUBAO_API_KEY` …) is present, behavior is unchanged.
- Else if `OPENROUTER_API_KEY` is set, the chat LLM is automatically routed through OpenRouter (`https://openrouter.ai/api/v1`). Model names are mapped automatically: `gpt-*`/`o1-*` → `openai/…`, `claude-*` → `anthropic/claude-opus-4.8`, `kimi-*` → `moonshotai/kimi-k2.6`, ids already containing `/` are kept as-is, and other provider-native ids (e.g. `doubao-*`) fall back to `openai/gpt-5.6-luna`. Set `OPENROUTER_MODEL` to force a specific OpenRouter model id.
- Else a clear error lists the accepted keys.

Add `OPENROUTER_API_KEY=...` to your `.env` (see `env.example`) to enable it.
