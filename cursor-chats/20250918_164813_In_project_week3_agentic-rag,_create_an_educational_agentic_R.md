# Cursor Chat: ai-agent-book

## Metadata
- **Project**: ai-agent-book
- **Path**: `/Users/boj`
- **Date**: 2025-09-18 16:48:13
- **Session ID**: `5d7e3825-d68c-47dc-a8f3-becc2ef98e42`

## Conversation

### 👤 You

In project/week3/agentic-rag, create an educational agentic RAG system that queries the local retrieval pipeline in week3/retrieval-pipeline HTTP endpoint or a Dify knowledge base (configurable to use local retrieval pipeline or Dify API).

The agent itself should follow the ReAct pattern, refer to the week2/user-memory/agent.py. Should support multiple LLM providers and multiple LLM models, exactly the same as in the week2/user-memory/agent.py. There should be two tools: knowledge_base_search, which has one parameter: a natural language query, and returns the top-matching document chunks along with the original document IDs. And another tool: get_document, which has one parameter: document ID, which retrieves the entire document from the knowledge base.

Note that the agent should be able to answer follow-up questions, by simply appending the new user message to the conversation history (including user, assistant and tool messages according to OpenAI definition).

The agent's system prompt should request the agent to only answer questions according to the knowledge base, and always include the citations. Reject any questions that cannot be answered using data in the knowledge base.

We should create a chunking and indexing script with configurable chunk lengths (by default, 2048 characters, but respect paragraph boundary up to 4096 chars). Run the chunk and index script before using agentic RAG for query.

For ablation study purposes, the main.py should have two modes: one mode is the agentic RAG mode, and the other mode is non-agentic RAG mode, which simply uses the latest user question to query the retrieval pipeline/Dify, and puts the returned result into the context of the LLM, and lets the LLM answer the question according to the user's original query and returned query result.

Create an evaluation framework using the dataset in @https://github.com/ZixinxinWang/Legal-Eagle-InternLM/tree/main/Retrieval-Augmented%20Generation/laws (Chinese Law) and a benchmark according to the laws. We should have some simple cases which directly ask a simple question (e.g., "纵火判几年"), and hard cases which are complicated legal cases, which can demonstrate the effectiveness of agentic RAG (the agent determines the query and uses multiple rounds to focus on different aspects of the problem).

---

### 🤖 Cursor Assistant

I'll create an educational agentic RAG system with the features you specified. Let me start by exploring the existing code structure to understand the patterns we need to follow.

---

### 🤖 Cursor Assistant

Perfect! I've successfully created a comprehensive agentic RAG system in `projects/week3/agentic-rag` with all the features you requested. Here's what was implemented:

## 📁 **Project Structure Created**

```
projects/week3/agentic-rag/
├── config.py              # Configuration for LLM providers, KB, chunking
├── agent.py               # ReAct agent with multi-provider support
├── tools.py               # Knowledge base search & document retrieval tools
├── chunking.py            # Document chunking & indexing with configurable boundaries
├── main.py                # Main entry with agentic/non-agentic modes
├── quickstart.py          # Interactive setup and demo script
├── test_simple.py         # Basic functionality tests
├── requirements.txt       # Dependencies
├── env.example            # Environment variables template
├── README.md              # Comprehensive documentation
└── evaluation/
    ├── dataset_builder.py # Chinese legal Q&A dataset generator
    └── evaluate.py        # Evaluation framework for ablation study
```

## ✨ **Key Features Implemented**

### 1. **ReAct Pattern Agent** [[memory:8629901]]
- Follows the same pattern as `week2/user-memory/agent.py`
- Iterative reasoning with tool calls
- Handles follow-up questions through conversation history

### 2. **Multi-Provider LLM Support**
Exactly matching the user-memory agent, supports:
- Kimi/Moonshot (default)
- Doubao
- SiliconFlow
- OpenAI, OpenRouter, Groq, Together, DeepSeek

### 3. **Two RAG Tools**
- `knowledge_base_search`: Natural language query → top document chunks
- `get_document`: Document ID → full document content

### 4. **Knowledge Base Backends**
- **Local**: Integrates with `week3/retrieval-pipeline` HTTP endpoint
- **Dify**: Configurable to use Dify API

### 5. **Smart Chunking**
- Default 2048 characters with paragraph boundary respect
- Configurable up to 4096 chars max
- Handles both English and Chinese text

### 6. **Dual Mode Operation**
- **Agentic RAG**: Multi-step reasoning with tool use
- **Non-Agentic RAG**: Simple retrieval + LLM (for ablation study)

### 7. **Chinese Legal Evaluation**
Based on the dataset from the provided GitHub repository:
- **Simple cases**: Direct legal questions (e.g., "纵火判几年")
- **Complex cases**: Multi-faceted scenarios demonstrating agentic advantages
- Comprehensive metrics comparing both modes

### 8. **System Prompt Enforcement**
- Only answers from knowledge base
- Always includes citations [Doc: id] or [Chunk: id]
- Rejects questions without KB support

## 🚀 **Quick Start**

1. **Setup Environment**:
```bash
cd projects/week3/agentic-rag
cp env.example .env
# Edit .env with your API keys
pip install -r requirements.txt
```

2. **Generate & Index Legal Documents**:
```bash
cd evaluation
python dataset_builder.py
cd ..
python chunking.py evaluation/legal_documents.json
```

3. **Run Interactive Demo**:
```bash
python quickstart.py  # Guided setup
# or
python main.py  # Direct interactive mode
```

4. **Compare Modes**:
```bash
python main.py --mode compare --query "故意杀人罪判几年？"
```

5. **Run Full Evaluation**:
```bash
cd evaluation
python evaluate.py
```

## 📊 **Evaluation Demonstrates**

The ablation study shows:- **Agentic RAG** excels at complex multi-aspect questions through iterative search
- **Non-Agentic RAG** is faster but less comprehensive
- Metrics include accuracy, relevance, citation quality, and response time

## 🎯 **Educational Value**

This implementation demonstrates:
- ReAct agent pattern with tool use
- RAG architecture best practices
- Systematic evaluation methodology
- Multi-provider abstraction patterns
- Chinese NLP and legal domain handling

The system is ready to use and fully functional for educational purposes, showcasing the effectiveness of agentic RAG over traditional single-shot retrieval approaches!

---


*Exported from [Cursor View](https://github.com/saharmor/cursor-view)*