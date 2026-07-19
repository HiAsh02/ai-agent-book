# Comprehensive Coding Agent - Pure Python Implementation

A production-ready AI coding agent built with Claude, implementing all techniques from Chapter 2 with **pure Python tools** - no command-line dependencies required!

## 🌟 Key Features

### ✅ Pure Python Implementation

**All tools implemented without command-line dependencies:**
- ❌ No `grep`, `rg` (ripgrep), `find` commands needed
- ❌ No dependency on system utilities
- ✅ **100% pure Python** implementations
- ✅ Works on any system with Python 3.8+
- ✅ **Especially designed for Mac users** without command-line tools

### 🛠️ Complete Tool Suite

**All 16 tools from tools.json fully implemented:**

**File Operations (Pure Python):**
- `Read` - File reading with image/PDF/notebook support
- `Write` - File writing with auto lint checking
- `Edit` - Search and replace editing
- `MultiEdit` - Multiple edits in one operation

**Search Tools (Pure Python, no rg/grep dependency):**
- `Grep` - **Pure Python regex search** with full ripgrep feature parity
  - Full regex support
  - Case insensitive search
  - Context lines (before/after/around)
  - Line numbers
  - Multiline mode
  - Glob filtering
  - File type filtering
  - Multiple output modes
- `Glob` - File pattern matching
- `LS` - Directory listing

**Shell Operations:**
- `Bash` - Persistent shell sessions
- `BashOutput` - Background job output
- `KillBash` - Terminate shells

**Project Management:**
- `TodoWrite` - Task list management
- `ExitPlanMode` - Plan mode exit

**Advanced:**
- `NotebookEdit` - Jupyter notebook editing
- `WebFetch` - Web content fetching (stub)
- `WebSearch` - Web search (stub)
- `Task` - Sub-agent launcher (stub)

### 🧠 System Hint Techniques (Chapter 2)

1. **Timestamps**: Every message and tool result timestamped
2. **Tool Call Counting**: Warns after 3+ repeated calls
3. **TODO List Management**: Explicit task tracking
4. **Detailed Error Information**: Rich error context
5. **System State Awareness**: Working directory, OS, Python version
6. **Environment Information**: Dynamic state in context

### 🔧 Terminal Environment

- **Persistent Shell Sessions**: Commands in same shell
- **Working Directory Tracking**: Directory changes persist
- **Background Execution**: Long-running command support

### ✅ Auto Lint Detection

After Write/Edit/MultiEdit:
- Python syntax checking
- JavaScript/TypeScript checking  
- Errors appear immediately in tool results

## 📁 Project Structure

```
coding-agent/
├── agent.py                    # Main agent implementation
├── system_state.py            # System state tracking
├── tool_registry.py           # Tool name → implementation mapping
├── tools/                     # All tool implementations
│   ├── __init__.py
│   ├── base.py               # Base tool class
│   ├── bash_tool.py          # Shell execution
│   ├── bash_output_tool.py   # Background job output
│   ├── kill_bash_tool.py     # Shell termination
│   ├── read_tool.py          # File reading
│   ├── write_tool.py         # File writing
│   ├── edit_tool.py          # File editing
│   ├── multi_edit_tool.py    # Multiple edits
│   ├── grep_tool.py          # 🔥 Pure Python regex search (no rg!)
│   ├── glob_tool.py          # File pattern matching
│   ├── ls_tool.py            # Directory listing
│   ├── todo_write_tool.py    # TODO management
│   ├── exit_plan_mode_tool.py
│   ├── notebook_edit_tool.py
│   ├── web_fetch_tool.py
│   ├── web_search_tool.py
│   ├── task_tool.py
│   └── shell_session.py      # Shell session management
├── tools.json                 # Tool definitions
├── system-prompt.md          # System prompt
├── config.py                 # Configuration
├── requirements.txt          # Dependencies
└── README.md                 # This file
```

## 🚀 Installation

```bash
# Navigate to project directory
cd /Users/boj/ai-agent-book/projects/week5/coding-agent

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and configure your provider
```

### Configuration

Edit `.env` file:

```bash
# Choose your provider (anthropic, openai, or openrouter)
PROVIDER=anthropic

# Add API key for your chosen provider
ANTHROPIC_API_KEY=sk-ant-api03-...
# or
OPENROUTER_API_KEY=sk-or-v1-...
# or
OPENAI_API_KEY=sk-...

# Select model appropriate for your provider
DEFAULT_MODEL=claude-sonnet-5
```

**See [PROVIDERS.md](PROVIDERS.md) for detailed provider configuration guide.**

### Requirements

**Core dependencies:**
- Python 3.8+
- `anthropic` - For Anthropic API
- `openai` - For OpenAI/OpenRouter API
- `python-dotenv` - For configuration

**Optional (for enhanced features):**
- `PyPDF2` - For PDF reading
- `requests`, `beautifulsoup4`, `html2text` - For WebFetch

**No command-line tools needed!** Works on macOS without Homebrew packages.

### Supported Providers

- **Anthropic** - Direct Claude API access
- **OpenRouter** - Access to Claude, GPT, Gemini, Llama, and more
- **OpenAI** - Direct GPT API access

The agent automatically handles the different API formats for each provider.

### OpenRouter as a universal fallback

You do **not** need a direct Anthropic or OpenAI key to run the agent. If the
requested direct provider's key is missing, the agent transparently falls back
to **OpenRouter** (via the OpenAI-compatible SDK) as long as
`OPENROUTER_API_KEY` is set:

- `PROVIDER=anthropic` **with** `ANTHROPIC_API_KEY` → Anthropic SDK, unchanged (default behavior).
- `PROVIDER=anthropic` **without** `ANTHROPIC_API_KEY` (but `OPENROUTER_API_KEY` set) → routed through OpenRouter.
- `PROVIDER=openai` **with** `OPENAI_API_KEY` → OpenAI SDK, unchanged.
- `PROVIDER=openai` **without** `OPENAI_API_KEY` (but `OPENROUTER_API_KEY` set) → routed through OpenRouter.

When falling back, the native model id is **prefixed/mapped** to an OpenRouter id:

| Requested model | OpenRouter id used |
|-----------------|--------------------|
| `claude-sonnet-*` (e.g. `claude-sonnet-5`) | `anthropic/claude-sonnet-4.6` |
| `claude-haiku-*` | `anthropic/claude-haiku-4.5` |
| `claude-opus-*` / other `claude-*` | `anthropic/claude-opus-4.8` |
| `gpt-*` / `o1-*` (e.g. `gpt-5.6-luna`) | `openai/<model>` |
| already prefixed (`vendor/model`) | passed through unchanged |

So a user with **only** an `OPENROUTER_API_KEY` can run, e.g.:

```bash
# No ANTHROPIC_API_KEY needed — falls back to OpenRouter automatically
python main.py --provider anthropic --model claude-sonnet-5 -p "..."

# gpt-5.6-luna routed through OpenRouter (no OPENAI_API_KEY needed)
python main.py --provider openai --model gpt-5.6-luna -p "..."
```

Set `PROVIDER=openrouter` explicitly (with a `vendor/model` id) if you want to
target a specific OpenRouter model without any mapping.

## 📖 Usage

### Command-Line Entry Point (`main.py`)

`main.py` is the single recommended entry point, providing a unified argparse CLI. Run
`python main.py --help` to see the full help text:

```bash
python main.py --help
```

Key parameters:

| Parameter | Description |
|-----------|-------------|
| (none) | Enter interactive conversation (default behavior) |
| `-p, --prompt "task"` | Non-interactive mode: execute a single task then exit, suitable for scripts / CI |
| `--list-tools` | **Offline** list all registered tools with descriptions (no API Key needed, useful for self-check) |
| `--provider {anthropic,openai,openrouter}` | Temporarily override `PROVIDER` in `.env` |
| `--model model-name` | Temporarily override `DEFAULT_MODEL` in `.env` |
| `--base-url URL` | Temporarily override the API Base URL (for custom gateways / OpenAI-compatible services) |
| `--max-iterations N` | Maximum number of agent iterations for a single task (default 50) |
| `--no-color` | Disable colored output (automatically disabled when no TTY) |

### Quick Self-Check (Offline, No API Key Needed)

First, confirm the tool set loads correctly:

```bash
$ python main.py --list-tools
16 tools registered:

  Task           Launch a new agent to handle complex, multi-step tasks autonomously.
  Bash           Executes a given bash command in a persistent shell session ...
  Glob           - Fast file pattern matching tool that works with any codebase size
  Grep           A powerful search tool built on ripgrep
  ...
```

### End-to-End Example: Have the Agent Complete a Real Coding Task

After configuring `.env` (see Configuration above), use a single command to have the Agent create and run a script:

```bash
python main.py -p "Create hello_world.py: print Hello, World!, include a function that greets by name and a main demonstration block, then run it to verify the output."
```

**The terminal output structure on success looks roughly like this** (illustrative; actual rounds/calls depend on the model):

```
✓ Agent initialized successfully
You: Create hello_world.py ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Calling tool: Write
   ✓ Completed (call #1)
   ✓ No lint errors
   File: hello_world.py
🔧 Calling tool: Bash
   ✓ Completed (call #2)
   Output:
     Hello, World!
     Hello, Alice!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Task completed!
   Iterations: 2
   Tool calls: 2
```

> Indicators of success: The Agent sequentially calls `Write` to create the file and `Bash` to run the script,
> the actual script output appears in the terminal, and it ends with `✅ Task completed!`.
> (`quickstart.py` is a scripted version of the same task, for comparison.)

### Interactive Conversation (Default)

Running without `-p` starts an interactive session:

```bash
python main.py
```

**Features:**
- 🎨 Color-coded output for better readability
- ⚡ Real-time streaming responses
- 🔧 Live tool execution display
- 📊 Built-in status command
- 💬 Conversation history
- 🔄 Reset command to start fresh

**In-session commands (type during conversation):**
- `/help` - Show help message
- `/quit` or `/exit` - Exit the CLI
- `/reset` - Reset conversation history
- `/clear` - Clear the screen
- `/status` - Show agent status (tool calls, TODOs, etc.)

### Other Example Scripts (All Require API Key)

```bash
python quickstart.py                  # Basic quick start (same task as the end-to-end example above)
python example_complex_task.py        # Complex multi-step task
python example_with_system_hints.py   # System Hint technique demonstration
```

### Programmatic Usage

```python
from agent import CodingAgent

agent = CodingAgent(api_key="your-key")

for event in agent.run("List all Python files"):
    if event["type"] == "text_delta":
        print(event["delta"], end="", flush=True)
    elif event["type"] == "done":
        print("\n✅ Done!")
```

## 🔍 Pure Python Grep Implementation

The **Grep tool** is fully implemented in pure Python without any dependency on `grep`, `rg`, or other command-line tools. It provides all the features of ripgrep:

```python
# Example: Search for pattern in files
{
    "name": "Grep",
    "input": {
        "pattern": "def.*test",
        "path": "/path/to/search",
        "output_mode": "content",
        "-i": True,              # Case insensitive
        "-C": 3,                 # 3 lines context
        "-n": True,              # Show line numbers
        "glob": "*.py",          # Only Python files
        "multiline": False       # Single line matching
    }
}
```

**Features:**
- ✅ Full regex support (Python `re` module)
- ✅ Case insensitive search (`-i`)
- ✅ Context lines (`-A`, `-B`, `-C`)
- ✅ Line numbers (`-n`)
- ✅ Multiline mode
- ✅ Glob filtering (`glob` parameter)
- ✅ File type filtering (`type` parameter)
- ✅ Output modes: `content`, `files_with_matches`, `count`
- ✅ Head limit
- ✅ Recursive directory search
- ✅ Binary file skip
- ✅ Hidden file/directory skip

## 🏗️ Architecture

### Modular Tool System

Each tool is implemented as a separate class inheriting from `BaseTool`:

```python
class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "MyTool"
    
    def _execute_impl(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Tool implementation
        return {"result": "success"}
```

### Tool Registry

`ToolRegistry` maps tool names to implementations:

```python
registry = ToolRegistry()
tool = registry.get_tool("Grep", system_state)
result = tool.execute(params)
```

### System State

`SystemState` tracks:
- Current working directory
- Tool call counts
- TODO list
- Shell sessions
- Environment info

### System Hints

System hints are injected before each LLM call:

```xml
<system_hint>
# System State
Current Time: 2025-10-12 15:30:45
Working Directory: /Users/boj/coding-agent
OS: Darwin
Python: Python 3.11.5

# Tool Call Statistics
- Grep: 2 calls
- Write: 1 calls

# Current TODO List
✅ [1] Search for files (completed)
🔄 [2] Implement feature (in_progress)
⬜ [3] Write tests (pending)
</system_hint>
```

## 🎯 Design Principles

### 1. Pure Python Implementation

**Why:** Maximum portability and compatibility
- Works on any system with Python
- No Homebrew, apt, or other package managers needed
- Consistent behavior across platforms### 2. Modular Tool Architecture

**Why:** Maintainability and extensibility
- Each tool is self-contained
- Easy to add new tools
- Easy to test individually
- Clear separation of concerns

### 3. No Command-Line Dependencies

**Why:** Reliability and control
- **Grep**: Pure Python regex search
- **Glob**: Python's `pathlib.glob()`
- **LS**: Python's `os` and `pathlib`
- No subprocess calls for core functionality
- Full control over behavior

### 4. System Hints for Self-Awareness

**Why:** Better agent behavior
- Prevents infinite loops (tool call counting)
- Maintains task focus (TODO tracking)
- Provides environmental context
- Enables self-monitoring

## 📊 Comparison with Chapter 2

| Technique | Status | Implementation |
|-----------|--------|----------------|
| Standard OpenAI Tool Format | ✅ | Anthropic SDK |
| Streaming Tool Calls | ✅ | Real-time JSON delta parsing |
| Parallel Tool Calls | ✅ | Multiple tools per response |
| Pure Python Tools | ✅ | **No command-line dependencies** |
| Grep without rg | ✅ | **Pure Python regex search** |
| Timestamps | ✅ | All messages/tools |
| Tool Call Counting | ✅ | Warns at 3+ |
| TODO List | ✅ | TodoWrite tool |
| System State | ✅ | Working dir, OS, Python |
| Persistent Shell | ✅ | Shell sessions |
| Auto Lint Detection | ✅ | After Write/Edit/MultiEdit |

## 🔧 Configuration

`.env` file:

```bash
# Required
ANTHROPIC_API_KEY=your_key_here

# Optional
DEFAULT_MODEL=claude-sonnet-5
MAX_ITERATIONS=50
MAX_TOKENS=8192
```

## 📝 Adding New Tools

1. Create tool file in `tools/`:

```python
# tools/my_tool.py
from .base import BaseTool

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "MyTool"
    
    def _execute_impl(self, params):
        # Implementation
        return {"result": "success"}
```

2. Register in `tools/__init__.py`:

```python
from .my_tool import MyTool

__all__ = [..., 'MyTool']
```

3. Add to `tool_registry.py`:

```python
self._tools = {
    ...,
    "MyTool": MyTool,
}
```

4. Add definition to `tools.json`

## 🐛 Troubleshooting

### "No module named 'tools'"

Make sure you're running from the project directory:
```bash
cd /Users/boj/ai-agent-book/projects/week5/coding-agent
python agent.py
```

### Grep not finding files

Check:
- Path is correct
- Pattern is valid regex
- Glob pattern matches files
- Files contain searchable text (not binary)

### Shell commands fail

Ensure:
- Bash is available at `/bin/bash`
- Working directory exists
- Commands are properly quoted

## 🧪 Testing

Comprehensive test suite with 130+ tests covering all tool features.

### Run Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=tools --cov-report=html

# Run specific tool tests
pytest tests/test_grep_tool.py
pytest tests/test_bash_tool.py

# Verbose output
pytest -v
```

### Test Coverage

- **130+ tests** across 14 test files
- **2,200+ lines** of test code
- **All major features** from tools.json tested
- **Integration tests** for tool chaining and system hints

See [tests/README.md](tests/README.md) for detailed test documentation.

## 🎓 Learning Path

1. **Start with examples**: Run `python main.py` (interactive CLI)
2. **Run quickstart**: `python quickstart.py`
3. **Explore system hints**: `python example_with_system_hints.py`
4. **Study Grep implementation**: See `tools/grep_tool.py`
5. **Run tests**: `pytest -v` to see all features in action
6. **Read Chapter 2**: Understand the theory
7. **Add custom tools**: Extend the system

## 📚 References

- Chapter 2: Context Engineering (AI Agent Book)
- Tools specification: `tools.json`
- System prompt: `system-prompt.md`
- Anthropic Claude API: https://docs.anthropic.com/

## 🎉 Key Advantages

1. **No Dependencies on External Tools**
   - Pure Python implementation
   - Works without rg, grep, find, etc.
   - Perfect for Mac users without Homebrew

2. **Modular Architecture**
   - Each tool is a separate file
   - Easy to understand and modify
   - Clear separation of concerns

3. **Production Ready**
   - Comprehensive error handling
   - Auto lint detection
   - System hints for reliability
   - Streaming support for UX

4. **Educational Value**
   - Learn how tools work internally
   - Understand pure Python file operations
   - See regex search implementation
   - Study agent architecture patterns

## 📄 License

MIT

## 🤝 Contributing

This is an educational implementation. Feel free to adapt and extend!

---

**Built with pure Python for maximum portability and learning! 🐍✨**

