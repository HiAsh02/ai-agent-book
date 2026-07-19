# Log Sanitization
This experiment demonstrates how to detect and sanitize sensitive information from Agent logs and tool outputs. It provides **two complementary sanitization engines**:

1. **Offline Rule Engine (regex, default)** — Pure regular expressions + validation algorithms (Luhn, ID checksum),  
   **no Ollama, no network, no external frameworks required**, deterministic results, fast, suitable as the first line of defense before logs are persisted.  
   It covers both the **key/secret** sensitive information most commonly leaked in Agent scenarios (API Key, cloud vendor tokens, private keys, connection string passwords)  
   and traditional **PII** (ID numbers, phone numbers, credit cards, emails, etc.).
2. **Local LLM Engine (llm)** — Uses Ollama to call a local small model (default `qwen3:0.6b`) for semantic recognition of  
   Level 3 PII. This echoes the chapter's argument that "small models can also handle structured tasks," while also exposing the limitations of small models  
   (e.g., they may return values with descriptive prefixes instead of the original string, causing backfill failures).

> To quickly see the effect, just run `python main.py --demo` (offline, no dependencies required) to see before/after comparisons and sanitization category summaries for multiple representative samples.

## Sensitive Information Categories Covered by the Offline Rule Engine

`regex_sanitizer.py` processes the following categories by priority (higher priority rules win when overlapping), replacing each with a tagged placeholder:

| Category | Placeholder | Description |
| --- | --- | --- |
| Private Key / Certificate | `[REDACTED_PRIVATE_KEY]` | PEM private key blocks |
| JWT | `[REDACTED_JWT]` | `eyJ...` three-part tokens |
| Connection String Credentials | `[REDACTED_URL_CRED]` | `scheme://user:PASSWORD@host` |
| AWS Access Key | `[REDACTED_AWS_KEY]` | `AKIA...` |
| GitHub / Slack / Google / OpenAI Keys | `[REDACTED_*_TOKEN]` / `[REDACTED_API_KEY]` | `ghp_`, `xoxb-`, `AIza`, `sk-` |
| Bearer Token | `[REDACTED_BEARER_TOKEN]` | `Authorization: Bearer ...` |
| Password / Secret Assignment | `[REDACTED_SECRET]` | `password=...`, `token: ...`, etc. |
| Email | `[REDACTED_EMAIL]` | |
| Credit Card Number | `[REDACTED_CREDIT_CARD]` | Passes Luhn check to reduce false positives |
| IBAN | `[REDACTED_IBAN]` | International Bank Account Number |
| US Social Security Number | `[REDACTED_SSN]` | |
| ID Card Number | `[REDACTED_ID_CARD]` | Mainland China 18-digit, includes checksum validation |
| Phone Number | `[REDACTED_PHONE]` | Mainland China |
| IP Address | `[REDACTED_IP]` | IPv4 |

## Level 3 PII Categories (LLM Engine)

Based on the privacy protection architecture, Level 3 PII includes highly sensitive information:
- Social Security Numbers (SSN)
- Credit Card Numbers
- Bank Account Numbers
- Medical Record Numbers
- Medical Diagnoses and Treatment Information
- Prescription Information
- Driver's License Numbers
- Passport Numbers
- Financial PINs
- Tax ID Numbers
- Health Insurance IDs
- Biometric Data

## Features

- **Offline Rule Engine**: Regex + Luhn/ID-checksum based sanitizer that needs no model, no network, and covers API keys/secrets in addition to PII
- **Local LLM Processing**: Uses Ollama with a local small model (default `qwen3:0.6b`) for privacy-preserving PII detection
- **Internal Reasoning**: Shows the model's thinking process using `<think>` tags for transparency
- **Streaming Output**: Real-time display of thinking and PII detection progress
- **Performance Metrics**: Measures TTFT (Time to First Token), token counts, and processing speeds
- **Batch Processing**: Can process multiple test cases from user-memory-evaluation framework
- **Detailed Metrics**: Tracks prefill time, output time, tokens per second for both phases

## Installation

### 1. Install Ollama

> **General Fallback (OpenRouter)**: This experiment uses a local Ollama small model by default. If Ollama is unavailable  
> (not running / unreachable) and `OPENROUTER_API_KEY` is set, the Agent will automatically switch to OpenRouter  
> (default hosted model `openai/gpt-5.6-luna`). To force fallback for verification, point Ollama to an  
> unreachable port: `export OLLAMA_HOST=http://127.0.0.1:1`.

#### macOS:
```bash
brew install ollama
ollama serve  # Run in separate terminal
```

#### Linux:
```bash
curl -fsSL https://ollama.com/install.sh | sh
systemctl start ollama
```

#### Windows:
Download from [ollama.com](https://ollama.com/download/windows)

> Note: The following Ollama-related steps are only needed when using `--mode llm` (local LLM engine) or running the LLM batch evaluation path.  
> The offline rule engine (`--demo`, `--input`) only depends on the Python standard library and does not require Ollama.

### 2. Pull the Qwen3 Model
```bash
ollama pull qwen3:0.6b
```

Note: The 0.6B model requires approximately 500MB of disk space (you can replace it with `qwen3:1.7b` or `qwen3:4b` as needed to improve accuracy).

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

## Usage

See `python main.py --help` for complete parameter descriptions (in Chinese).

### Offline Rule Demo (Recommended, No Ollama Required)
Displays before/after comparisons and sanitization category summaries for multiple built-in representative samples:
```bash
python main.py --demo
```

### Sanitize Any Log File (Offline)
```bash
python main.py --input app.log                 # Results written to app.log.sanitized
python main.py --input app.log -o cleaned.log  # Specify output file
```

You can also run the rule engine module directly to demo only the built-in samples:
```bash
python regex_sanitizer.py
```

### Using the Local LLM Engine
Add `--mode llm` to the above demo/file sanitization commands to switch to the local Ollama model:
```bash
python main.py --demo --mode llm
python main.py --input app.log --mode llm --model qwen3:1.7b
```

### Process All Layer 3 Test Cases (LLM Batch Evaluation Path)
Process all complex test cases from user-memory-evaluation (this path always uses LLM and requires Ollama and the chapter3 evaluation framework):
```bash
python main.py
```

### Process Specific Test Case
```bash
python main.py --test-id layer3_13_emergency_medical_cascade
```

### Limit Number of Test Cases
Process only the first N test cases:
```bash
python main.py --limit 3
```

### Select Model
```bash
python main.py --demo --mode llm --model qwen3:4b   # Default is qwen3:0.6b
```

## Output Structure

The sanitized logs and metrics are saved in the `output/` directory:

```
output/
├── <test_id>_sanitized.txt    # Sanitized conversation text
├── <test_id>_summary.json     # Summary of PII found and replaced
├── performance_metrics.json   # Detailed performance metrics
└── performance_summary.json   # Aggregated performance statistics
```

## Performance Metrics

The system tracks the following metrics for each conversation:

### Timing Metrics
- **Prefill Time (TTFT)**: Time to first token in milliseconds
- **Output Time**: Time to generate all output tokens
- **Total Time**: End-to-end processing time

### Token Metrics
- **Input Tokens**: Number of tokens in the prompt
- **Output Tokens**: Number of tokens generated
- **Prefill Speed**: Tokens per second during prefill phase
- **Output Speed**: Tokens per second during generation

### Sanitization Metrics
- **PII Items Found**: Number of Level 3 PII values detected
- **Replacements Made**: Number of replacements with [REDACTED]

## Example Output

```
🚀 Starting Log Sanitization with Local LLM
============================================================
📦 Loading test cases from user-memory-evaluation...
🤖 Initializing Ollama agent...
✅ Using model: qwen3:0.6b

[1/1] Test Case: layer3_13_emergency_medical_cascade
   Title: Emergency Medical Crisis - Multi-System Coordination Response
   Conversations: 8

🔍 Processing conversation: emergency_room_001
   Found 3 PII items
   - 123-45-6789
   - 4532 1234 5678 9012
   - MRN-789456
```============================================================
PERFORMANCE SUMMARY
============================================================

📊 Total Conversations Processed: 8

⏱️  Timing Metrics (milliseconds):
   Prefill (TTFT): 125.34 ms (median: 118.50)
   Output Time:    234.67 ms (median: 220.00)
   Total Time:     360.01 ms (median: 338.50)

📝 Token Metrics:
   Average Input Tokens:  450.5
   Average Output Tokens: 25.3
   Total Tokens Processed: 4206

⚡ Speed Metrics (tokens/second):
   Prefill Speed: 3592.8 tok/s
   Output Speed:  107.8 tok/s

🔒 Sanitization Results:
   Total PII Items Found:     24
   Total Replacements Made:   48
   Average PII per Conversation: 3.0
```

## Architecture

The project consists of several modules:

1. **regex_sanitizer.py**: Offline rule-based sanitizer (regex + Luhn/ID checksums), covers keys/secrets and PII
2. **samples.py**: Representative agent-log samples used by the offline demo
3. **config.py**: Configuration for Ollama model and PII categories
4. **test_loader.py**: Loads test cases from user-memory-evaluation framework
5. **agent.py**: Core LLM sanitization logic using Ollama
6. **metrics.py**: Performance metrics collection and reporting
7. **main.py**: Main entry point and orchestration

## How It Works

1. **Test Case Loading**: The system loads conversation histories from the user-memory-evaluation framework
2. **PII Detection**: Each conversation is sent to the local Qwen3 0.6B model with a specialized prompt to detect Level 3 PII
3. **Sanitization**: Detected PII values are replaced with [REDACTED] in the original text
4. **Metrics Collection**: Performance metrics are collected for each operation
5. **Output Generation**: Sanitized logs and performance summaries are saved to the output directory

## Privacy Considerations

- All processing happens locally using Ollama - no data is sent to external APIs
- The Qwen3 0.6B model runs entirely on your local machine
- Sanitized logs replace sensitive information with [REDACTED] placeholders
- Original PII values are logged for verification but should be handled securely

## Troubleshooting

### "Ollama not found"
Make sure Ollama is installed and running:
```bash
ollama serve
```

### "Model qwen3:0.6b not found"
Pull the model:
```bash
ollama pull qwen3:0.6b
```

### "Evaluation framework not found"
Ensure the user-memory-evaluation project exists at:
```
../user-memory-evaluation/
```
