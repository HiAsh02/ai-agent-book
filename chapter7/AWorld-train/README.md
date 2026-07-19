<div align="center">

# AWorld Train

*A "Learning from Practice" Training Framework for Agentic AI*

[![License: MIT][license-image]][license-url]
[![Paper](https://img.shields.io/badge/arXiv-2508.20404-b31b1b.svg)](https://arxiv.org/abs/2508.20404)

</div>

---

## Table of Contents

- [Introduction](#introduction)
  - [Important Note on This Educational Experiment](#important-note-on-this-educational-experiment)
  - [Core Features](#core-features)
- [GAIA Environment Tool Ecosystem](#gaia-environment-tool-ecosystem)
  - [Web Interaction Tools](#-web-interaction-tools-3-servers-9-tools)
  - [Document Processing Tools](#-document-processing-tools-5-servers-12-tools)
  - [Multimedia Processing Tools](#-multimedia-processing-tools-3-servers-12-tools)
  - [Intelligent Reasoning Tools](#-intelligent-reasoning-tools-3-servers-6-tools)
  - [Code Execution Tools](#-code-execution-tools-3-servers-24-tools)
  - [File System Tools](#-file-system-tools-1-server-14-tools)
  - [Excel Processing Tools](#-excel-processing-tools-1-server-29-tools)
  - [Knowledge Retrieval Tools](#-knowledge-retrieval-tools-3-servers-11-tools)
  - [Tool Statistics Summary](#tool-statistics-summary)
- [Core Architecture](#core-architecture)
- [Quick Start](#quick-start)
  - [Install the Training Framework](#install-the-training-framework)
  - [Configure the GAIA Environment](#configure-the-gaia-environment)
- [Build a Custom Agent](#build-a-custom-agent)
- [Prepare for Training](#prepare-for-training)
- [Start Training](#start-training)
- [Latest Optimizations](#latest-optimizations)
- [Troubleshooting](#troubleshooting)
- [Performance Benchmarks](#performance-benchmarks)
- [Advanced Topics](#advanced-topics)
- [Citation](#citation)
- [Community & Support](#community--support)

---

## Introduction

AWorld Train is an open-source training framework implementing the **"Learning from Practice"** paradigm, specifically designed for Agentic AI. According to the [AWorld paper](https://arxiv.org/abs/2508.20404), building high-performance Agent systems requires three core elements:

1. **Algorithm**: Learning mechanisms that enable the Agent to adapt and improve from environment interactions
2. **Environment**: Complex interaction scenarios providing rich feedback and diverse challenges
3. **Priors**: The foundational capabilities of current LLMs in areas like reasoning, mathematics, and vision

AWorld Train addresses the core bottleneck of traditional methods—**inefficient experience generation**—through a distributed architecture. On the GAIA benchmark, we achieved a **14.6x** speedup in data collection, making large-scale reinforcement learning training feasible.

### ⚠️ Important Note on This Educational Experiment

**GAIA (General AI Assistants Benchmark)** is one of the most challenging benchmarks for evaluating Agent capabilities and a competitive arena for SOTA (State-of-the-Art) Agent systems. According to the [paper](https://arxiv.org/abs/2508.20404):

- **Data Scarcity**: The GAIA validation set contains only **165 questions**, and the test set has approximately **300 questions**, far fewer than the data volume typically required for RL training
- **Computational Resource Requirements**: The Qwen3-32B-AWorld model from the paper required training on **2 clusters of 8x A100 GPUs** for several days to achieve 32.23% performance, which is still far from SOTA performance (over 80%)
- **Task Complexity**: GAIA questions involve multi-modal understanding, multi-step reasoning, tool chain calls, etc., requiring an average of 10-20 interaction rounds to complete

Therefore, this project adopts an education-friendly configuration, using Qwen3-4B-Thinking-2507 as the base model for faster training.

**The goals of this project are:**
- ✅ Demonstrate the complete "Learning from Practice" training pipeline
- ✅ Understand the Agent-Environment interaction mechanism
- ✅ Practice applying RL algorithms (PPO/GRPO) in Agent training

### Core Features

- ⚡ **Efficient Concurrency**: Distributed task execution, 14.6x data collection acceleration
- 🔌 **Framework Agnostic**: Supports mainstream RL frameworks like VeRL, OpenRLHF, AReaL, SWIFT
- 🛠️ **Tool Ecosystem**: Built-in 26 MCP servers providing **126 tool functions**, covering search, browser, code execution, multi-modal processing, etc.
- 📊 **Long Context**: Supports 131K token contexts for handling complex multi-turn interactions
- 🎯 **SOTA Performance**: Qwen3-32B-AWorld achieves 32.23% pass@1 on the GAIA test set

---

## GAIA Environment Tool Ecosystem

According to the [paper](https://arxiv.org/abs/2508.20404) and MCP Server implementation, AWorld provides comprehensive tool support for GAIA tasks, totaling **26 MCP servers** and **126 tool functions**. Below is the complete list of tools by category:

### 🌐 Web Interaction Tools (3 Servers, 9 Tools)

#### 1. Google Search Server (`googlesearch-server`)
- `search_google`: Perform web searches using the Google Custom Search API
- `get_search_capabilities`: Retrieve search service capability information

**Typical Applications**: Querying real-time information, fact-checking, starting point for multi-hop reasoning

#### 2. Browser Use Server (`browser-server`)
- `browser_use`: LLM-based intelligent browser automation (using the browser-use library)
- `get_browser_capabilities`: Retrieve browser automation capabilities

**Features**:
- Automatic handling of bot detection and CAPTCHAs
- Supports form filling, file downloads, content extraction
- Integrates visual understanding and memory functions

#### 3. Playwright Server (`ms-playwright`)
Provides **23 fine-grained browser control tools**:
- **Navigation**: `browser_navigate`, `browser_navigate_back`
- **Interaction**: `browser_click`, `browser_type`, `browser_hover`, `browser_drag`, `browser_select_option`
- **Forms**: `browser_fill_form`, `browser_file_upload`
- **Debugging**: `browser_console_messages`, `browser_network_requests`, `browser_take_screenshot`
- **Management**: `browser_close`, `browser_resize`, `browser_tabs`, `browser_handle_dialog`
- **Execution**: `browser_evaluate`, `browser_press_key`, `browser_wait_for`
- **Snapshots**: `browser_snapshot`, `browser_install`

**Comparison**: `browser-server` offers high-level automation, while `ms-playwright` provides fine-grained control

---

### 📄 Document Processing Tools (5 Servers, 12 Tools)

#### 4. Documents CSV Server (`documents-csv-server`)
- `extract_csv_content`: Extract and analyze CSV file content (supports Markdown/JSON output formats)
- `list_supported_formats`: List supported CSV formats

#### 5. Documents DOCX Server (`documents-docx-server`)
- `extract_docx_content`: Extract Word document content (including text, tables, images)
- `list_supported_formats`: List supported DOCX formats

#### 6. Documents PPTX Server (`documents-pptx-server`)
- `extract_pptx_content`: Extract PowerPoint content (slide text, notes, layout)
- `list_supported_formats`: List supported PPTX formats

#### 7. Documents PDF Server (`documents-pdf-server`)
- `convert_document_to_markdown`: Convert PDF to Markdown (preserving structure and formatting)

#### 8. Documents TXT Server (`documents-txt-server`)
- `extract_text_content`: Extract plain text file content
- `list_supported_formats`: List supported text encodings

**GAIA Application Scenario**: Processing attached files (70% of GAIA dataset questions include document attachments)

---

### 🎥 Multimedia Processing Tools (3 Servers, 12 Tools)

#### 9. Media Audio Server (`media-audio-server`)
- `transcribe_audio`: Speech-to-text (supports Whisper API)
- `extract_audio_metadata`: Extract audio metadata (duration, bitrate, sample rate)
- `trim_audio`: Trim audio segments
- `list_supported_formats`: List supported audio formats (MP3, WAV, M4A, etc.)

#### 10. Media Image Server (`media-image-server`)
- `extract_text_ocr`: OCR text recognition (based on Tesseract/Cloud Vision API)
- `analyze_image_ai`: AI image analysis (scene recognition, object detection, description generation)
- `get_image_metadata`: Extract image metadata (dimensions, EXIF, capture time)

#### 11. Media Video Server (`media-video-server`)
- `analyze_video`: Video content analysis (scene segmentation, keyframe extraction)
- `summarize_video`: Video summary generation
- `extract_keyframes`: Extract keyframe images

#### Supplementary: Standalone Multimedia Tools
- **Audio Server** (`audio-server`): `mcp_transcribe_audio` - Advanced speech transcription
- **Image Server** (`image-server`): `mcp_image_recognition` - Image recognition and classification

**GAIA Application**: Approximately 40% of GAIA questions involve image, audio, or video analysis

---

### 💡 Intelligent Reasoning Tools (3 Servers, 6 Tools)

#### 12. Intelligence Code Server (`intelligence-code-server`)
- `generate_python_code`: Generate and validate Python code (for mathematical calculations, data processing)
- `get_reasoning_capabilities`: Retrieve code generation capability information

#### 13. Intelligence Think Server (`intelligence-think-server`)
- `complex_problem_reasoning`: Complex problem reasoning (mathematical proofs, algorithm design, logic puzzles)
- `get_reasoning_capabilities`: Retrieve reasoning capability information

**Features**: Invokes more powerful reasoning models (e.g., GPT-4o, Claude 3.7 Sonnet) for deep thinking

#### 14. Intelligence Guard Server (`intelligence-guard-server`)
- `guarding_reasoning_process`: Reasoning process protection and validation (prevents hallucinations, checks logical consistency)
- `get_guarding_capabilities`: Retrieve guarding capability information

**Paper Highlight**: These "thinking tools" enable smaller models to leverage the reasoning capabilities of larger models, allowing them to "stand on the shoulders of giants"

---

### 💻 Code Execution Tools (3 Servers, 24 Tools)

#### 15. Terminal Server (`terminal-server`)
- `execute_command`: Execute terminal commands (Python, bash, system commands)
- `get_command_history`: Retrieve command execution history
- `get_terminal_capabilities`: Retrieve terminal capability information

**Security Features**: Command whitelist, timeout control, output truncation

#### 16. E2B Code Server (`e2b-code-server`)
- `e2b_upload_file`: Upload files to the sandbox
- `e2b_run_code`: Execute code in an isolated sandbox (supports Python, JavaScript, multiple languages)

**Advantage**: Completely isolated execution environment, preventing malicious code from affecting the main system

#### 17. Terminal Controller (`terminal-controller`)
Provides **10 advanced terminal management tools**:- `execute_command`, `get_command_history`, `get_current_directory`, `change_directory`
- `list_directory`, `write_file`, `read_file`
- `insert_file_content`, `delete_file_content`, `update_file_content`

**Difference**: `terminal-server` focuses on command execution, while `terminal-controller` provides file system management.

---

### 📂 File System Tools (1 Server, 14 Tools)

#### 18. Filesystem Server (`filesystem-server`)
Complete file operation capabilities:
- **Reading**: `read_file`, `read_text_file`, `read_media_file`, `read_multiple_files`
- **Writing**: `write_file`, `edit_file`
- **Management**: `create_directory`, `move_file`, `get_file_info`
- **Search**: `search_files`, `list_directory`, `list_directory_with_sizes`, `directory_tree`
- **Permissions**: `list_allowed_directories` - Lists allowed directories for access

**GAIA Application**: Access dataset attachments (in the `/root/workspace/gaia_dataset/` directory)

---

### 📊 Excel Processing Tools (1 Server, 29 Tools)

#### 19. Excel Server (`excel`)
Provides enterprise-grade Excel operations:

**Data Operations (9)**:
- `read_data_from_excel`, `write_data_to_excel`
- `insert_rows`, `insert_columns`, `delete_sheet_rows`, `delete_sheet_columns`
- `copy_range`, `delete_range`, `validate_excel_range`

**Workbook/Sheet Management (7)**:
- `create_workbook`, `create_worksheet`, `copy_worksheet`
- `delete_worksheet`, `rename_worksheet`, `get_workbook_metadata`

**Advanced Features (13)**:
- `apply_formula`, `validate_formula_syntax`
- `format_range`, `create_chart`, `create_pivot_table`, `create_table`
- `merge_cells`, `unmerge_cells`, `get_merged_cells`
- `get_data_validation_info`

**GAIA Typical Tasks**: Analyze complex Excel data tables, compute statistical metrics, generate charts

---

### 🔍 Knowledge Retrieval Tools (3 Servers, 11 Tools)

#### 20. Wikipedia Server (`wiki-server`)
- `search_wikipedia`: Search Wikipedia entries
- `get_article_content`: Get full article content
- `get_article_summary`: Get article summary
- `get_article_categories`: Get article categories
- `get_article_links`: Get article links
- `get_article_history`: Get article history (for time-sensitive questions)
- `get_wikipedia_capabilities`: Get Wikipedia service capabilities

**Special Features**: Supports multiple languages, historical version queries (GAIA has questions like "population data for a certain month and year")

#### 21. ArXiv Server (`parxiv-server`)
- `search_papers`: Search arXiv papers
- `get_paper_details`: Get detailed paper information (abstract, authors, citations)
- `download_paper`: Download paper PDF
- `get_arxiv_capabilities`: Get arXiv service capabilities
- `get_categories`: Get arXiv category list

#### 22. Wayback Machine Server (`wayback-server`)
- `list_archived_versions`: List archived versions of a webpage
- `get_archived_content`: Get webpage content at a specific point in time
- `get_wayback_capabilities`: Get Wayback Machine capabilities

**GAIA Application**: Answer historical queries like "information on a certain website in 2015"

---

### 📥 Other Utility Tools (3 Servers, 3 Tools)

#### 23. Download Server (`download-server`)
- `download_file`: Download a network file to local storage
- `get_download_capabilities`: Get download service capabilities

#### 24. Read Web Server (`readweb-server`)
- Provides webpage content reading capabilities (specific tools defined by MCP configuration)

#### 25. Google Search Alternative (`google-search`)
- `search`: Simplified search interface
- `read_webpage`: Read webpage content

---

### Tool Statistics Summary

| Category | Servers | Tools | Key Capabilities |
|----------|---------|-------|------------------|
| **Web Interaction** | 3 | 32 | Search, intelligent browsing, fine-grained control |
| **Document Processing** | 5 | 12 | CSV, Word, PPT, PDF, TXT |
| **Multimedia** | 5 | 14 | Audio transcription, OCR, image/video analysis |
| **Intelligent Reasoning** | 3 | 6 | Code generation, complex reasoning, verification |
| **Code Execution** | 3 | 36 | Terminal commands, sandbox execution, file management |
| **File System** | 1 | 14 | Complete file operation capabilities |
| **Excel** | 1 | 29 | Enterprise-grade spreadsheet processing |
| **Knowledge Retrieval** | 3 | 11 | Wikipedia, ArXiv, historical web pages |
| **Other** | 2 | 3 | File download, webpage reading |
| **Total** | **26** | **126** | **Covers all capabilities required by GAIA** |

### Tool Call Examples (from Training Logs)

```python
# Google Search Example
Tool call: aworld-mcp__search_google
Tool args: {"query": "Wyoming population 2020", "num_results": 5}
Result: {"success": true, "results": [{"title": "Wyoming - Census Bureau", "snippet": "576,851..."}]}

# File System Example
Tool call: aworld-mcp__list_directory
Tool args: {"path": "/root/workspace/gaia_dataset/2023/test"}
Result: ["[FILE] 021a5339-...-bd9b-9368b3efda7a.pdf", "[FILE] 03c577c9-...-f8f598de14c1.mp3", ...]

# CSV Processing Example (will error if tabulate dependency is missing)
Tool call: aworld-mcp__extract_csv_content
Tool args: {"file_path": "/root/workspace/gaia_dataset/2023/test/52e8ce1c-...-67d1648779b9.csv"}
Error: "CSV extraction failed: Missing optional dependency 'tabulate'"

# Wikipedia History Query Example
Tool call: aworld-mcp__get_article_history
Tool args: {"title": "Cat", "date": "20191231", "language": "en"}
Result: {...historical Wikipedia content...}
```

---

## Core Architecture

AWorld Train uses a four-stage training pipeline:

![Architecture](../docs/imgs/train_env_agent_architecture.png)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Environment │───▶│    Agent    │───▶│   Adapter   │───▶│   Training  │
│   Setup     │    │Construction │    │   Layer     │    │  Framework  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     (MCP)           (AWorld)            (VeRL)           (PPO/GRPO)
```

1. **Environment Setup**: Deploy GAIA MCP Server, providing 20+ tool capabilities
2. **Agent Construction**: Implement a custom AgentLoop, define decision logic
3. **Adapter Integration**: Unify interfaces, connect to the RL training framework
4. **Training Execution**: Configure reward functions and hyperparameters, start the training task

---

## Quick Start

### System Requirements

| Component | Requirement |
|-----------|-------------|
| **Operating System** | Linux (recommended) / macOS / Windows |
| **Hardware** | Minimum 4 CPU cores + 8GB RAM<br>Training recommended: 8x A100/H100 GPU |
| **Software** | Docker, NVIDIA Driver, CUDA 12.1+ |

### Install Training Framework

Using VeRL as an example, the installation steps are as follows:

```bash
# 1. Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y build-essential git wget

# 2. Install CUDA Toolkit (matching your GPU Driver)
# Reference: https://developer.nvidia.com/cuda-downloads

# 3. Install PyTorch (matching CUDA version)
pip install torch==2.4.0 torchvision==0.19.0 --index-url https://download.pytorch.org/whl/cu121

# 4. Clone the AWorld repository
git clone https://github.com/inclusionAI/AWorld.git ~/AWorld
cd ~/AWorld

# 5. Install VeRL and dependencies (will automatically install transformers, vllm, deepspeed, etc.)
cd /path/to/verl
pip install -e .
```

**Important Note**: Some dependencies of VeRL need to be compiled in a CUDA environment. Please ensure steps 1-2 are completed first.

---

### Configure GAIA Environment

The GAIA environment is deployed via Docker and provides MCP (Model Context Protocol) services.

#### 1. Download the Dataset

```bash
# Download the GAIA dataset from Hugging Face
cd ~/AWorld/env/gaia-mcp-server/docker
mkdir -p gaia_dataset

# Use Hugging Face CLI to download (requires pip install huggingface_hub first)
huggingface-cli download gaia-benchmark/GAIA --repo-type dataset --local-dir gaia_dataset
```

#### 2. Configure Environment Variables

```bash
cd ~/AWorld/env/gaia-mcp-server/mcp_servers
cp .env_template .env

# Edit the .env file to configure necessary API keys
vim .env
```

Example `.env` file (partial fields):

```bash
# OpenAI API (for intelligence-code-server, etc.)
OPENAI_API_KEY=sk-your-openai-key

# Google Search API (for googlesearch-server)
GOOGLE_API_KEY=your-google-api-key
```GOOGLE_CSE_ID=your-search-engine-id

# E2B API (for code execution sandbox)
E2B_API_KEY=your-e2b-api-key
```

#### 3. Start the MCP Server

```bash
cd ~/AWorld/env
bash run-local.sh
```

Once started successfully, you will see output similar to:

```
Starting services...
DISPLAY=:0
2025-10-06 05:20:42,368 - __main__ - INFO - Starting MCP Server Proxy...
2025-10-06 05:20:42,373 - mcp_server_proxy.mcp_server_proxy - INFO - Added MCP server executor: googlesearch-server
...
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

The MCP Server provides two services:
- **MCP Interface**: `http://localhost:8080/mcp` (Agent tool calls)
- **VNC Interface**: `http://localhost:5901/vnc.html?autoconnect=true` (visual debugging)

#### 4. Verify the Environment

```bash
# Set environment variables
export MCP_SERVER_URL=http://localhost:8080/mcp

# Test connection (Python)
python3 << EOF
from train.adapter.verl.common import get_agent_tool_env_and_servers

config, servers = get_agent_tool_env_and_servers()
print(f"Available servers: {len(servers)}")
print(f"Sample servers: {servers[:5]}")
EOF
```

Expected output:

```
Available servers: 20
Sample servers: ['readweb-server', 'browser-server', 'documents-csv-server', ...]
```

---

## Building a Custom Agent

### Implementing AgentLoop

The core of creating a custom Agent is to inherit `AworldAgentLoop` and implement the `build_agents()` method. Below is a complete example of a GAIA Agent:

```python
# train/examples/train_gaia_with_aworld_verl/custom_agent_loop.py

from aworld.agents.llm_agent import Agent
from aworld.config import AgentConfig
from train.adapter.verl.aworld_agent_loop import AworldAgentLoop
from train.adapter.verl.common import get_agent_tool_env_and_servers

class GaiaAgentLoop(AworldAgentLoop):
    """Custom Agent Loop for GAIA tasks"""
    
    def build_agents(self):
        # Get MCP environment configuration and list of available servers
        gaia_env_config, gaia_env_servers = get_agent_tool_env_and_servers()
        
        # Build Agent instance
        return Agent(
            conf=AgentConfig(
                # LLM server address is dynamically managed by VeRL
                llm_base_url=self.get_llm_server_address(),
                llm_model_name=self.get_llm_server_model_name(),
                llm_api_key="dummy",  # No real API key needed for VeRL internal communication
            ),
            name="gaia_super_agent",
            
            # System prompt (defines Agent role and capabilities)
            system_prompt="""You are a helpful AI assistant specialized in solving complex tasks.
You have access to various tools including web search, code execution, and file analysis.
When given a task, break it down into steps and use available tools systematically.
Always provide your final answer in <answer>...</answer> tags.""",
            
            # MCP tool configuration
            mcp_config=gaia_env_config,
            mcp_servers=gaia_env_servers,
        )
```

### Configuring agent.yaml

Register your AgentLoop in `train/examples/train_gaia_with_aworld_verl/agent.yaml`:

```yaml
- name: gaia_agent
  _target_: train.examples.train_gaia_with_aworld_verl.custom_agent_loop.GaiaAgentLoop
```

### Advanced Scenarios

#### Multi-Agent System

```python
from aworld.swarms.swarm import Swarm

class MultiAgentLoop(AworldAgentLoop):
    def build_agents(self):
        config, servers = get_agent_tool_env_and_servers()
        
        # Create specialized Agents
        researcher = Agent(
            conf=AgentConfig(...),
            name="researcher",
            system_prompt="You are a research specialist...",
            mcp_servers=["googlesearch-server", "wiki-server"]
        )
        
        coder = Agent(
            conf=AgentConfig(...),
            name="coder",
            system_prompt="You are a coding expert...",
            mcp_servers=["e2b-code-server", "terminal-server"]
        )
        
        # Build Swarm
        return Swarm(
            agents=[researcher, coder],
            coordinator=researcher  # Main coordinating Agent
        )
```

---

## Preparing for Training

### 1. Prepare the Dataset

Run the dataset generation script to convert GAIA data into training format:

```bash
cd ~/AWorld/train/examples/train_gaia_with_aworld_verl/gaia_datasets

python create_dataset.py \
  --dataset_path ~/AWorld/env/gaia-mcp-server/docker/gaia_dataset \
  --output_dir ~/datasets \
  --train_size 300 \
  --test_size 100
```

This will generate:
- `~/datasets/train.parquet`: 300 training samples
- `~/datasets/test.parquet`: 100 test samples

Data format (Parquet):

| Field | Type | Description |
|------|------|------|
| `prompt` | List[Dict] | Formatted chat messages `[{"role": "user", "content": "..."}]` |
| `data_source` | str | Data source identifier `"gaia"` |
| `ability` | str | Ability category `"agi"` |
| `reward_model` | Dict | Reward configuration `{"style": "GAIA", "ground_truth": "..."}` |
| `extra_info` | Dict | Additional metadata (task_id, level, etc.) |
| `agent_name` | str | Target Agent name |

### 2. Configure the Reward Function

Define the reward logic in `train/examples/train_gaia_with_aworld_verl/metrics/gaia_reward_function.py`:

```python
import re
from aworld.logs.util import logger

def gaia_reward_func(data_source, solution_str, ground_truth, extra_info=None):
    """
    Reward function for GAIA tasks
    
    Args:
        data_source: Data source identifier
        solution_str: Complete solution generated by the Agent
        ground_truth: Ground truth answer
        extra_info: Additional information (e.g., task_id, level)
    
    Returns:
        float: Reward value (0.0 or 1.0)
    """
    # Extract content from <answer>...</answer> tags in solution_str
    pattern = r'<answer>(.*?)</answer>'
    match = re.search(pattern, solution_str, re.DOTALL | re.MULTILINE)
    
    if not match:
        logger.warning("No answer tag found in solution")
        return 0.0
    
    answer = match.group(1).strip()
    logger.info(f"Extracted answer: {answer}, Ground truth: {ground_truth}")
    
    # Use GAIA standard scorer (supports numbers, lists, strings)
    if question_scorer(answer, ground_truth):
        return 1.0
    else:
        return 0.0

def question_scorer(model_answer: str, ground_truth: str) -> bool:
    """GAIA standard scoring logic (detailed implementation omitted)"""
    # Supports number comparison, list comparison, string normalization comparison
    # See full code for details
    ...
```

### 3. Configure the Training Script

Edit `run.sh` to configure key parameters:

```bash
#!/usr/bin/env bash
set -xeuo pipefail

# ============ Cluster Topology ============
export GPUS_PER_NODE=${GPUS_PER_NODE:-8}
export NNODES=${NNODES:-1}

# ============ Model and Data ============
model_path=${model_path:-Qwen/Qwen3-4B-Thinking-2507}
train_files=$DATA_ROOT/datasets/train.parquet
test_files=$DATA_ROOT/datasets/test.parquet

# ============ Custom Configuration ============
path_to_train="/root/AWorld/train"agent_loop_config_path=${path_to_train}/examples/train_gaia_with_aworld_verl/agent.yaml
reward_fn_file_path=${path_to_train}/examples/train_gaia_with_aworld_verl/metrics/gaia_reward_function.py
reward_fn_name=gaia_reward_func

# ============ Training Hyperparameters ============
# PPO Algorithm Configuration
adv_estimator=grpo              # Use Group Relative Policy Optimization
clip_ratio_low=0.2              # PPO clip lower bound
clip_ratio_high=0.28            # PPO clip upper bound
actor_lr=1e-6                   # Actor learning rate

# Long Context Configuration (AWorld Latest Optimization)
max_turns=32                    # Maximum number of interaction turns (increased from 8 to 32)
max_prompt_length=4096          # Maximum prompt length (increased from 1024 to 4096)
max_response_length=4096        # Maximum response length (increased from 2048 to 4096)

# Batch Configuration
train_batch_size=32             # Training batch size (increased from 1 to 32)
ppo_mini_batch_size=8           # PPO mini-batch size (4 gradient updates)
n_resp_per_prompt=16            # Sample 16 responses per prompt (increased from 1)
n_resp_per_prompt_val=16        # Number of samples for validation

# ============ MCP Server ============
export MCP_SERVER_URL=${MCP_SERVER_URL:-http://localhost:8080/mcp}

# ============ Performance Optimization ============
export VLLM_USE_V1=1                      # Use vLLM v1 engine
export VLLM_ATTENTION_BACKEND=FLASH_ATTN  # FlashAttention-2
infer_tp=1                                # Tensor Parallel size
train_sp=1                                # Sequence Parallel size
offload=true                              # Offload parameters to CPU

# ============ VeRL Training Command ============
python3 -m verl.trainer.main_ppo \
    algorithm.adv_estimator=$adv_estimator \
    data.train_files="['$train_files']" \
    data.val_files="['$test_files']" \
    data.return_raw_chat=true \
    data.train_batch_size=$train_batch_size \
    data.max_prompt_length=$max_prompt_length \
    data.max_response_length=$max_response_length \
    actor_rollout_ref.model.path="$model_path" \
    actor_rollout_ref.rollout.multi_turn.max_user_turns=$max_turns \
    actor_rollout_ref.rollout.multi_turn.max_assistant_turns=$max_turns \
    actor_rollout_ref.rollout.max_model_len=131072 \
    actor_rollout_ref.rollout.max_num_batched_tokens=131072 \
    actor_rollout_ref.rollout.gpu_memory_utilization=0.9 \
    actor_rollout_ref.rollout.agent.agent_loop_config_path=$agent_loop_config_path \
    custom_reward_function.path="${reward_fn_file_path}" \
    custom_reward_function.name="${reward_fn_name}" \
    trainer.logger=['console','wandb'] \
    trainer.experiment_name=aworld_train_qwen3_4b \
    trainer.save_freq=5 \
    trainer.test_freq=5 \
    +trainer.num_steps=300
```

---

## Launching Training

### Single-Node Training

```bash
cd ~/AWorld/train/examples/train_gaia_with_aworld_verl

# Launch training (8 GPUs)
export DATA_ROOT=~/datasets
export GPUS_PER_NODE=8
bash run.sh
```

### Multi-Node Training (Slurm)

```bash
# Submit Slurm job (2 nodes, 8 GPUs per node)
sbatch <<EOF
#!/bin/bash
#SBATCH --job-name=aworld-train
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=8
#SBATCH --time=48:00:00

export DATA_ROOT=/path/to/datasets
export NNODES=2
export GPUS_PER_NODE=8

srun bash run.sh
EOF
```

### Training Monitoring

The training process supports multiple logging backends:

```bash
# 1. Console Output
# View training metrics in real-time (loss, reward, KL divergence, etc.)

# 2. WandB Visualization (Recommended)
# Visit https://wandb.ai/<your-project>/aworld_train_qwen3_4b

# 3. TensorBoard
tensorboard --logdir ~/datasets/checkpoint/aworld_train_qwen3_4b
```

Key Monitoring Metrics:

| Metric | Description | Target Value |
|--------|-------------|--------------|
| `reward/mean` | Average reward | Gradually increase to 0.3+ |
| `reward/max` | Maximum reward | Reach 1.0 |
| `actor/loss` | Actor loss | Steadily decrease |
| `rollout/response_length` | Response length | Adjust based on task |
| `rollout/num_turns` | Average number of turns | Efficient tool use (5-15 turns) |

---

## Latest Optimizations

Based on the latest code changes (commit `a52d61d6`), we have implemented the following key optimizations:

### 1. Long Context Support (verl_provider.py)

```python
# New dynamic max_model_len parameter configuration
self.max_model_len = params.get("max_model_len", 24576)
```

**Impact**: Supports context windows of up to 131K tokens, enabling complex multi-turn dialogues and large-scale tool call histories.

### 2. Data Format Optimization (create_dataset.py)

```python
# Prompt formatted as a list of chat messages (adapting to VeRL return_raw_chat mode)
rl_dataset["prompt"].append([{"role": "user", "content": data["Question"]}])
```

**Impact**: Seamlessly integrates with VeRL's chat template system, avoiding format conversion overhead.

### 3. Hyperparameter Tuning (run.sh)

| Parameter | Old Value | New Value | Improvement |
|-----------|-----------|-----------|-------------|
| `max_turns` | 8 | 32 | 4x interaction depth |
| `max_prompt_length` | 1024 | 4096 | 4x input capacity |
| `max_response_length` | 2048 | 4096 | 2x output capacity |
| `train_batch_size` | 1 | 32 | 32x training efficiency |
| `n_resp_per_prompt` | 1 | 16 | 16x sample diversity |

**Impact**:
- **Deeper Reasoning**: Allows the agent to perform longer tool chains and reasoning
- **More Efficient Training**: Larger batches accelerate convergence, diverse sampling improves generalization
- **More Stable Optimization**: `ppo_mini_batch_size=8` enables 4 gradient updates, balancing training stability and efficiency

### 4. Memory Optimization

```bash
# vLLM Configuration
actor_rollout_ref.rollout.max_model_len=131072           # Model context length
actor_rollout_ref.rollout.max_num_batched_tokens=131072  # Batched token count
actor_rollout_ref.rollout.gpu_memory_utilization=0.9     # GPU memory utilization
```

**Impact**: Supports concurrent inference of 32K+ tokens on A100 80GB, fully utilizing GPU resources.

### 5. New Qwen3-30B-A3B Training Script

```bash
# run_qwen3_30b_a3b.sh
infer_tp=4   # Tensor Parallel (Inference)
train_sp=8   # Sequence Parallel (Training)
```

**Impact**: Supports training larger models, leveraging model parallelism to overcome single-GPU limitations.

---

## Troubleshooting

### Agent Training Process Output Examples

#### ✅ Normal Inference Flow

```
(AgentLoopWorker pid=448354)   [agent] Content: Okay, let's see. So the user is asking about the population difference between the two states that have both Carl's Jr. and Hardee's fast food restaurants...
(AgentLoopWorker pid=448354)   [agent] Tool call: aworld-mcp__search_google - ID: chatcmpl-tool-94b30baa
(AgentLoopWorker pid=448354)   [agent] Tool args: {"query": "Wyoming population 2020", "num_results": 5}
(AgentLoopWorker pid=448354)   [agent] Content: ["{\"success\": true, \"message\": {\"query\": \"Wyoming population 2020\", \"results\": [{\"title\": \"Wyoming - Census Bureau Profile\", \"snippet\": \"576,851. The Total Population for Wyoming is 576,851...\"...}
```

**Explanation**: The agent correctly calls the tool and receives results; the inference chain is complete.

#### ✅ Successful File Listing

```
(AgentLoopWorker pid=448358)   [agent] Content: ["[FILE] 021a5339-744f-42b7-bd9b-9368b3efda7a.pdf\n[FILE] 03c577c9-4227-48a9-9b75-f8f598de14c1.mp3\n[FILE] 063800f6-8832-4856-972b-17b877612533.png\n..."]
(AgentLoopWorker pid=448358)   [agent] Content: Okay, let's try to figure out how many horror titles are overdue based on the inventory file...
```

**Explanation**: The file system tool works correctly; the agent can access dataset files.

---

### GAIA MCP Server Output Example#### ✅ Normal Startup Output

```bash
$ docker logs gaia-mcp-server-gaia-mcp-server-1 -f

Starting services...
DISPLAY=:0
2025-10-06 05:20:42,368 - __main__ - INFO - Starting MCP Server Proxy...
2025-10-06 05:20:42,370 - mcp_server_proxy.mcp_server_proxy - INFO - Loaded MCP tool schema: mcp_tool_schema=
  readweb-server:
  browser-server:
    - get_browser_capabilities
    - browser_use
  documents-csv-server:
    - extract_csv_content
    - list_supported_formats
  googlesearch-server:
    - search_google
    - get_search_capabilities
  ...
2025-10-06 05:20:42,373 - mcp_server_proxy.mcp_server_proxy - INFO - Added MCP server executor: googlesearch-server
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

**Checkpoints**:
- ✅ `Starting MCP Server Proxy` appears
- ✅ 20+ tool servers loaded (`Added MCP server executor`)
- ✅ Uvicorn listening on port 8080

#### ✅ Normal Request During Training

```
INFO:     208.64.254.164:36416 - "POST /mcp HTTP/1.1" 200 OK
2025-10-06 05:09:23,880 - mcp.server.lowlevel.server - INFO - Processing request of type CallToolRequest
2025-10-06 05:09:27,006 - mcp.server.lowlevel.server - INFO - Processing request of type CallToolRequest
[10/06/25 05:09:27] INFO     🔍 Searching Google for: 'Speaker of the House that passed act...'
                    INFO     ✅ Found 5 results in 0.42s
```

**Explanation**: The agent is calling the Google search tool normally, with fast request-response times (< 1s).

---

### ❌ Common Errors and Solutions

#### 1. CSV Extraction Failed (Missing Dependency)

```
ERROR    CSV extraction failed: Missing optional dependency 'tabulate'.
         Use pip or conda to install tabulate.
```

**Cause**: The `to_markdown()` function in pandas requires the `tabulate` library.

**Solution**:

```bash
# Enter the MCP Server Docker container
docker exec -it gaia-mcp-server-gaia-mcp-server-1 bash

# Install the missing dependency
cd /app/mcp_servers/documents_server
source .venv/bin/activate
pip install tabulate

# Restart the container
exit
docker restart gaia-mcp-server-gaia-mcp-server-1
```

#### 2. OpenAI API Key Error

```
WARNING  coding failed: Error code: 401 - {'error': {'message': 'Incorrect API key provided: sk-or-v1***...', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}}
```

**Cause**: Tools like `intelligence-code-server` require an OpenAI API key to generate code.

**Solution**:

```bash
# Method 1: Configure a real OpenAI API Key
vim ~/AWorld/env/gaia-mcp-server/mcp_servers/.env
# Add: OPENAI_API_KEY=sk-your-real-key

# Method 2: Use a compatible service like OpenRouter
# Configure in .env:
LLM_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-your-openrouter-key

# Restart the service
cd ~/AWorld/env
bash run-local.sh
```

#### 3. Wikipedia API 429 Rate Limiting

```
ERROR    Wikipedia summary retrieval error:
         requests.exceptions.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Cause**: The Wikipedia API is rate-limiting (429 Too Many Requests), but the Python library does not handle it gracefully.

**Solution**:

```bash
# Method 1: Reduce concurrent requests (adjust training parameters)
train_batch_size=16  # Reduce from 32 to 16
n_resp_per_prompt=8  # Reduce from 16 to 8

# Method 2: Use a proxy or switch Wikipedia mirror
# Configure in wiki_server/.env:
WIKIPEDIA_BASE_URL=https://en.wikipedia.org/w/api.php

# Method 3: Add request retry logic (requires code modification)
# Add exponential backoff in wiki_server/src/wiki.py
```

#### 4. Tool Execution Timeout

```
2025-10-06 05:21:08,548 - mcp_server_proxy.mcp_server_executor - INFO - Starting tool server browser-server...
[No response after 10 seconds]
```

**Cause**: The browser tool (Playwright) is slow to start or has insufficient resources.

**Solution**:

```bash
# Increase timeout configuration
vim ~/AWorld/env/gaia-mcp-server/mcp_servers/.env
# Add:
TOOL_EXECUTION_TIMEOUT=120  # Increase from default 60s to 120s

# Warm up the browser environment
docker exec -it gaia-mcp-server-gaia-mcp-server-1 bash
cd /app/mcp_servers/browser_server
uv run python -c "from playwright.sync_api import sync_playwright; sync_playwright().start()"
```

#### 5. vLLM OOM (Out of Memory)

```
RuntimeError: CUDA out of memory. Tried to allocate 20.00 GiB (GPU 0; 79.35 GiB total capacity; 75.12 GiB already allocated; 2.31 GiB free; 78.90 GiB reserved in total by PyTorch)
```

**Solution**:

```bash
# Method 1: Reduce batch size
train_batch_size=16             # Reduce from 32
ppo_mini_batch_size=4          # Reduce from 8

# Method 2: Reduce GPU memory utilization
actor_rollout_ref.rollout.gpu_memory_utilization=0.75  # Reduce from 0.9

# Method 3: Enable CPU offload
actor_rollout_ref.actor.fsdp_config.param_offload=true
actor_rollout_ref.actor.fsdp_config.optimizer_offload=true

# Method 4: Use larger Tensor Parallel
infer_tp=4  # Increase from 1 to 4 (requires 4 GPUs)
```

---

### Debugging Tips

#### 1. Enable Verbose Logging

```bash
# VeRL training logs
export RAY_LOGGING_LEVEL=DEBUG
export HYDRA_FULL_ERROR=1

# MCP Server logs
docker logs -f gaia-mcp-server-gaia-mcp-server-1 --tail 100

# vLLM inference logs
export VLLM_LOGGING_LEVEL=DEBUG
```

#### 2. Step-by-Step Agent Debugging

```python
# test_agent_debug.py
from train.examples.train_gaia_with_aworld_verl.custom_agent_loop import GaiaAgentLoop

# Create AgentLoop (without starting training)
loop = GaiaAgentLoop()
agent = loop.build_agents()

# Test a single question
response = agent.chat("What is the capital of France?")
print(response)
```

#### 3. Check Tool Availability

```bash
# Test MCP Server health status
curl http://localhost:8080/health

# List all tools
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}'
```

---

## Performance Benchmarks

### GAIA Test Set Results (Based on Paper)

| Model | Pass@1 | Data Collection Speedup | Training Time |
|-------|--------|------------------------|---------------|
| GPT-4o (Baseline) | 27.91% | - | - |
| DeepSeek-V3 | 31.89% | - | - |
| **Qwen3-32B-AWorld** | **32.23%** | **14.6x** | 48h (8x A100) |

**Key Findings**:
- Through the "learning from practice" paradigm, a 32B parameter model surpasses GPT-4o and DeepSeek-V3
- Distributed experience generation reduces data collection time from 7 days to 12 hours
- End-to-end training (SFT + PPO) improves performance on the GAIA validation set by over 15 percentage points

### Hardware Performance

| Configuration | Throughput | GPU Utilization | Memory Usage |
|---------------|------------|-----------------|--------------|
| 1x A100 80GB (TP=1) | 120 tokens/s | 85% | 72GB |
| 4x A100 80GB (TP=4) | 450 tokens/s | 92% | 68GB/GPU |
| 8x A100 80GB (FSDP+TP) | 850 tokens/s | 95% | 70GB/GPU |

**Optimization Recommendations**:
- **Small models (< 8B)**: Single GPU training, `infer_tp=1`, `train_sp=1`
- **Medium models (8-30B)**: Use TP=4 for faster inference, `infer_tp=4`
- **Large models (> 30B)**: Combine TP and SP, `infer_tp=4, train_sp=8`

---

## Advanced Topics

### Custom Reward Functions

Beyond GAIA's binary reward, you can implement more complex reward shaping:

```python
def dense_reward_func(data_source, solution_str, ground_truth, extra_info=None):
    """Dense reward function (considering intermediate steps)"""
    reward = 0.0
    
    # 1. Tool usage reward (encourages exploration)
    num_tool_calls = solution_str.count("Tool call:")
    reward += min(num_tool_calls * 0.1, 0.5)  # Max 0.5 points
    
    # 2. Reasoning quality reward (based on CoT)    if "<think>" in solution_str and "</think>" in solution_str:
        reward += 0.2  # Reward for having a reasoning process
    
    # 3. Final answer reward (main score)
    if question_scorer(extract_answer(solution_str), ground_truth):
        reward += 1.0
    
    # 4. Efficiency penalty (avoid excessive tool calls)
    if num_tool_calls > 15:
        reward -= 0.2
    
    return reward
```

### Multi-task Training

```python
# gaia_datasets/create_multitask_dataset.py
def create_multitask_dataset():
    datasets = []
    
    # Task 1: GAIA
    gaia_ds = load_gaia_dataset(...)
    gaia_ds['task_type'] = 'gaia'
    datasets.append(gaia_ds)
    
    # Task 2: Code Execution
    code_ds = load_code_dataset(...)
    code_ds['task_type'] = 'code'
    datasets.append(code_ds)
    
    # Task 3: Web Navigation
    web_ds = load_webarena_dataset(...)
    web_ds['task_type'] = 'web'
    datasets.append(web_ds)
    
    # Mixed sampling
    return pd.concat(datasets).sample(frac=1.0)
```

---

## Citation

If you use AWorld Train in your research, please cite our paper:

```bibtex
@article{yu2025aworld,
  title={AWorld: Orchestrating the Training Recipe for Agentic AI},
  author={Yu, Chengyue and Lu, Siyuan and Zhuang, Chenyi and Wang, Dong and others},
  journal={arXiv preprint arXiv:2508.20404},
  year={2025}
}
```

---

## Community & Support

- **GitHub Issues**: [https://github.com/inclusionAI/AWorld/issues](https://github.com/inclusionAI/AWorld/issues)
- **Discord**: [https://discord.gg/aworld](https://discord.gg/aworld)
- **Paper**: [https://arxiv.org/abs/2508.20404](https://arxiv.org/abs/2508.20404)
- **Official Documentation**: [https://inclusionai.github.io/AWorld/](https://inclusionai.github.io/AWorld/)

---

<div align="center">

**AWorld Train** — Let Your Agent Learn from Practice

Made with ❤️ by [Inclusion AI](https://github.com/inclusionAI)

</div>

[license-image]: https://img.shields.io/badge/License-MIT-yellow.svg
[license-url]: https://opensource.org/licenses/MIT