# GPT-5 Native Tools Agent

An advanced AI agent leveraging GPT-5's native `web_search` and `code_interpreter` tools through the OpenRouter API, matching the exact implementation pattern from production Go code. This agent can search the internet for real-time information and run code for deep analysis using GPT-5's built-in capabilities, realizing the "search → read → analyze → search again" Deep Research loop.

## 🌟 Features

- **Native Tool Support**: Utilizes GPT-5's built-in `web_search` and `code_interpreter` tools with OpenRouter-specific format
- **OpenRouter Integration**: Exact API format matching production Go implementation
- **Web Search Capability**: 
  - Real-time internet search for current information
  - Configurable search context size and user location
- **Reasoning Levels**: Support for low, medium, and high reasoning effort
- **Interactive CLI**: User-friendly command-line interface with reasoning controls
- **Agent Chaining**: Chain multiple requests for complex workflows
- **Comprehensive Testing**: Test suite demonstrating various use cases

## 📋 Prerequisites

- Python 3.8 or higher
- OpenRouter API key (get one at [https://openrouter.ai/keys](https://openrouter.ai/keys))
- Internet connection for web search functionality

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or navigate to the project directory
cd projects/week1/search-codegen

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp env.example .env

# Edit .env and add your OpenRouter API key
# OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

### 2. Configuration

Edit `.env` file with your settings:

```env
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
MODEL_NAME=openai/gpt-5.6-sol
DEFAULT_TEMPERATURE=0.3
DEFAULT_MAX_TOKENS=4000
```

> This experiment uses OpenRouter as its **primary** backend, so no fallback is
> needed. The same `OPENROUTER_API_KEY` doubles as the **universal fallback** for
> the other chapter1 experiments (`context`, `learning-from-experience`,
> `web-search-agent`) when their direct provider key is missing.

### 3. Run the Agent

#### Interactive Mode (Recommended)
```bash
python main.py
```

#### Single Request Mode
```bash
python main.py --mode single --request "Search for latest AI news and analyze the trends"
```

#### Run Tests
```bash
python main.py --mode test
```

### CLI Arguments

This experiment corresponds to **Experiment 1.3 ★: GPT-5.6 Native Deep Research Capability** in the book, demonstrating how the model autonomously combines the two native tools `web_search` and `code_interpreter` to complete the iterative research loop of "search → read → analyze → search again." Run `python main.py --help` to view Chinese help.

| Argument | Description | Default |
|----------|-------------|---------|
| `--mode` | Run mode: `interactive` / `single` / `test` | `interactive` |
| `--request` | Task or query content for `single` / `--dry-run` mode | — |
| `--model` | Override model name | `MODEL_NAME` from config |
| `--reasoning` | Reasoning Effort (`low`/`medium`/`high`) | `low` |
| `--verbosity` | Verbosity level (`low`/`medium`/`high`) | Follows model |
| `--no-tools` | Disable native tools | Enabled |
| `--output` | Save full results (including trace/request body) as JSON | — |
| `--dry-run` | Assemble and print request body offline, no network or API Key required | Disabled |
| `--test` | Run specific test case in `test` mode | Run all |

> **Reasoning Effort** and **Verbosity** are two GPT-5 native parameters emphasized in the book: the former adjusts thinking depth, the latter controls response detail. Both are exposed via CLI and injected as-is into the request body sent to the model.

Examples:

```bash
# Book example task: Closest pair among ASEAN-10 capitals (search coordinates + code to compute great-circle distance)
python main.py --mode single --request "Among the capitals of the 10 ASEAN countries, which two are closest to each other? Provide a detailed analysis and reasoning process." --reasoning high

# Book example task: Bitcoin technical analysis (multi-source real-time data + indicator calculation)
python main.py --mode single --request "Search for Bitcoin's price trend over the past month and calculate technical indicators such as MA, RSI, and MACD." --verbosity high --output btc.json
```

### View Request Body Offline (dry-run)

No API Key required to see the actual request sent to the model under the "model-as-agent" paradigm—including the definitions of the two native tools, `reasoning` and `verbosity` parameters. This provides an intuitive view of the native tool call structure and is also useful for debugging:

```bash
python main.py --dry-run --request "Among the capitals of the 10 ASEAN countries, which two are closest to each other?" --reasoning high --verbosity high
```

In the output request body, the `tools` array contains both `web_search` and `code_interpreter`, while `reasoning.effort` and `verbosity` reflect the selected levels—exactly the combination of native tools + reasoning/verbosity parameters described in the book.

## 🛠️ Usage Examples

### Example 1: Web Search Only
```python
from agent import GPT5NativeAgent
from config import Config

agent = GPT5NativeAgent(
    api_key=Config.OPENROUTER_API_KEY,
    base_url=Config.OPENROUTER_BASE_URL
)

result = agent.process_request(
    "What are the latest developments in quantum computing?",
    use_tools=True
)
print(result["response"])
```

### Example 2: Web Search with High Reasoning
```python
result = agent.process_request(
    "Analyze the implications of quantum computing on encryption",
    use_tools=True,
    reasoning_effort="high"
)
```

### Example 3: Web Search with Analysis
```python
result = agent.process_request(
    """Search for current Bitcoin price and market data, 
    then analyze the volatility and predict trends""",
    use_tools=True,
    reasoning_effort="medium"
)
```

### Example 4: Search and Analyze Method
```python
analysis_code = """
import statistics
# Process search results
prices = [45000, 46000, 45500, 47000, 46500]
volatility = statistics.stdev(prices)
print(f"Volatility: ${volatility:.2f}")
"""

result = agent.search_and_analyze(
    topic="Current cryptocurrency market conditions",
    analysis_code=analysis_code
)
```

## 📁 Project Structure

```
search-codegen/
├── agent.py          # Core GPT-5 agent implementation
├── config.py         # Configuration management
├── main.py           # Interactive CLI and entry point
├── test_agent.py     # Comprehensive test suite
├── env.example       # Environment variables template
├── requirements.txt  # Python dependencies
└── README.md        # This file
```

## 🔧 OpenRouter Tool Format

### web_search Tool Structure
The web_search tool uses OpenRouter's specific format:
```python
{
    "type": "web_search",
    "search_context_size": "medium",
    "user_location": {
        "type": "approximate",
        "country": "US"
    }
}
```

### Reasoning Configuration
Supports configurable reasoning effort:
- **low**: Fast responses with basic reasoning
- **medium**: Balanced reasoning and response time
- **high**: Deep reasoning for complex queries

## 🧪 Testing

The test suite includes comprehensive test cases:1. **Basic Web Search**: Test internet search capabilities
2. **Web Search with Analysis**: Search with analytical insights
3. **Complex Research**: Deep research with high reasoning
4. **Search and Code**: Search with code generation
5. **Reasoning Comparison**: Compare different reasoning levels
6. **Search and Analyze Method**: Convenience method testing
7. **Agent Chain**: Multi-step workflow

Run specific tests:
```bash
# Run all tests
python test_agent.py

# Run specific test
python main.py --mode test --test basic
```

Available test names: `basic`, `analysis`, `complex`, `code`, `reasoning`, `search_analyze`, `chain`

## 🎯 Interactive CLI Commands

When running in interactive mode, the following commands are available:

- `/help` - Show help message
- `/clear` - Clear conversation history
- `/history` - Show conversation history
- `/tools` - Toggle tools on/off
- `/search` - Enter web search mode
- `/code` - Enter code generation mode
- `/analyze` - Combined search + analysis mode
- `/config` - Show current configuration
- `/reasoning` - Set reasoning effort level
- `/exit` - Exit the application

## ⚙️ Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | Required |
| `MODEL_NAME` | GPT-5 model identifier | `openai/gpt-5.6-sol` |
| `DEFAULT_TEMPERATURE` | Response randomness (0-1) | `0.3` |
| `DEFAULT_MAX_TOKENS` | Maximum response length | `4000` |
| `DEFAULT_TOOL_CHOICE` | Tool selection strategy | `auto` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

## 🤝 API Integration

This agent uses the OpenRouter API to access GPT-5. OpenRouter provides:
- Unified API for multiple models
- Automatic fallbacks for reliability
- Usage tracking and analytics
- Competitive pricing

Learn more at [OpenRouter Documentation](https://openrouter.ai/docs)

## 📊 Token Usage

The agent tracks token usage for each request:
- Prompt tokens: Input token count
- Completion tokens: Output token count
- Total tokens: Combined usage

Monitor costs based on OpenRouter's pricing:
- Input: $1.25 per million tokens
- Output: $10 per million tokens

## 🐛 Troubleshooting

### API Key Issues
```bash
# Verify your API key starts with 'sk-or-'
echo $OPENROUTER_API_KEY
```

### Rate Limiting
Adjust `RATE_LIMIT_RPM` in `.env` if encountering rate limits

### Tool Errors
- Ensure `use_tools=True` when calling `process_request`
- Set `tool_choice="required"` to force tool usage

## 📝 License

This project is part of the AI Agent Hands-on Training Camp curriculum.
## 🔗 Resources

- [OpenRouter GPT-5 API](https://openrouter.ai/openai/gpt-5.6-sol)
- [OpenAI Native Tools Documentation](https://platform.openai.com/docs/guides/tools)
- [OpenRouter Documentation](https://openrouter.ai/docs)
- [API Keys](https://openrouter.ai/keys)

## 👥 Support

For issues or questions:
1. Check the troubleshooting section
2. Review test cases for usage examples
3. Consult the OpenRouter documentation

---

Built with GPT-5's native capabilities via OpenRouter API 🚀
