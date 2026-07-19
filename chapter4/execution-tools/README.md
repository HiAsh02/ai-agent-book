# Execution Tools MCP Server

An MCP (Model Context Protocol) server that provides comprehensive execution tools with built-in safety mechanisms for AI agents.

## Features

### Safety Mechanisms

1. **LLM-Based Approval**: Irreversible operations require approval from a secondary LLM before execution
2. **Result Summarization**: Execution tool outputs larger than 10,000 characters are automatically summarized by an LLM for easier processing
3. **Automatic Verification**: Operations that can be verified (e.g., syntax checking) are automatically validated

### Tool Categories

#### File System Tools
- **file_write**: Write content to files with automatic syntax verification
- **file_edit**: Edit existing files with diff preview and verification

#### Generic Execution Tools
- **code_interpreter**: Execute Python code in a sandboxed environment with result analysis
- **virtual_terminal**: Execute shell commands with error summarization

#### External System Integration Tools
- **google_calendar_add**: Add events to Google Calendar
- **github_create_pr**: Create GitHub Pull Requests with validation

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

1. Copy `env.example` to `.env`:
```bash
cp env.example .env
```

2. Configure your environment variables:
```
# LLM Configuration (for safety checks and summarization)
PROVIDER=kimi

# API Keys (set the one for your provider)
KIMI_API_KEY=your_kimi_key
# SILICONFLOW_API_KEY=your_siliconflow_key
# DOUBAO_API_KEY=your_doubao_key
# OPENROUTER_API_KEY=your_openrouter_key

# Model (optional, defaults to provider's default)
# MODEL=kimi-k3

# Model parameters
TEMPERATURE=0.7
MAX_TOKENS=4096

# External Services (optional)
GOOGLE_CALENDAR_CREDENTIALS_FILE=credentials.json
GITHUB_TOKEN=your_github_token

# Safety Settings
REQUIRE_APPROVAL_FOR_DANGEROUS_OPS=true
AUTO_SUMMARIZE_COMPLEX_OUTPUT=true
AUTO_VERIFY_CODE=true
```

**Supported Providers:**
- `siliconflow`: Qwen/Qwen3-235B-A22B-Thinking-2507
- `doubao`: doubao-seed-1-6-thinking-250715  
- `kimi`/`moonshot`: kimi-k3
- `openrouter`: google/gemini-3.5-flash (or openai/gpt-5.6-luna, anthropic/claude-sonnet-4.6)

> **Universal OpenRouter fallback**: when the configured `PROVIDER`'s key is
> missing but `OPENROUTER_API_KEY` is set, the LLM steps (approval,
> summarization, error/syntax analysis) transparently switch to `openrouter`
> via `Config.effective_provider()`. Set `MODEL` to a `provider/model` id for
> OpenRouter, e.g. `MODEL=openai/gpt-5.6-luna`.

## Usage

### CLI Entry Point

`cli.py` is the unified CLI entry point for listing, individually invoking each execution tool, and running an end-to-end demo.
It reuses the same tool implementations as the MCP server, so behavior is identical.

```bash
# View top-level help and all subcommands
python cli.py --help

# List all execution tools
python cli.py list

# End-to-end offline demo (recommended to try first; runs without API key)
python cli.py demo

# Invoke a specific tool
python cli.py code --language python --code "print(2 ** 10)"
python cli.py shell "python3 --version"
python cli.py write --path notes.txt --content "hello" --overwrite
python cli.py edit --path notes.txt --search hello --replace world
```

Global flags (place before the subcommand):

| Flag | Effect |
|------|--------|
| `--provider` | Override LLM provider (`PROVIDER`) |
| `--workspace` | Override working directory (file operations are restricted to this directory) |
| `--no-approval` | Disable LLM pre-approval for dangerous operations |
| `--no-verify` | Disable automatic syntax verification for file writes/code |
| `--no-summarize` | Disable LLM summarization of long output (still truncates and persists) |

**Offline operation**: `list`, `demo`, and `code`/`shell`/`write`/`edit` with approval/summarization/non-Python verification disabled all run without an API key. Scenarios requiring an API key are: LLM pre-approval, LLM summarization of long output, and non-Python syntax verification. `calendar` and `pr` additionally require the corresponding external credentials.

> **Long output truncation and persistence**: When the output of `code_interpreter` / `virtual_terminal`
> exceeds the threshold (default 200 lines or 10,000 characters), the tool retains only the first and last 50 lines
> in the context, writes the full output to a temporary file, and provides the path in the `stdout_file` / `stderr_file`
> fields of the return value. This mechanism does not depend on the LLM and works offline.

### Running the MCP Server

```bash
python server.py
```

### Using with MCP Client

```python
from mcp import Client

# Connect to the MCP server
client = Client("stdio://python server.py")

# Use file write tool
result = await client.call_tool("file_write", {
    "path": "test.py",
    "content": "print('Hello, World!')"
})

# Use code interpreter
result = await client.call_tool("code_interpreter", {
    "code": "import math\nprint(math.sqrt(16))"
})

# Use virtual terminal
result = await client.call_tool("virtual_terminal", {
    "command": "ls -la"
})
```

### Testing Individual Tools

```bash
# Test file operations
python test_file_tools.py

# Test execution tools
python test_execution_tools.py

# Test external integrations
python test_external_tools.py
```

## Architecture

The server implements a layered architecture:

1. **Safety Layer**: Intercepts dangerous operations and validates them
2. **Tool Layer**: Implements individual tool logic
3. **Verification Layer**: Validates outputs and provides feedback
4. **Integration Layer**: Connects to external services

## Examples

See `examples.py` for comprehensive usage examples.

## Experiment 4-2: Execution Tools MCP Server

This project corresponds to Experiment 4-2 in Chapter 4 "Execution Tools" of the book, focusing on the safety mechanisms of execution tools:
layered security protection (input validation, permission control, LLM pre-approval), automatic syntax verification and feedback loops,
and truncation and persistence of long outputs. It is recommended to start with `python cli.py demo`.
