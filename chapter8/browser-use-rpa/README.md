# Browser-Use RPA with Learning Capability

An Agent that can operate a computer and improve with practice.

## Project Overview

This project implements a browser automation Agent with learning capabilities. The Agent can:

1. **Learning Phase**: Complete new tasks using multimodal LLMs (GPT-4o, Claude, Gemini, etc.) and capture successful operation workflows.
2. **Application Phase**: Recognize similar tasks and directly replay learned workflows without invoking the LLM again.
3. **Continuous Improvement**: Record execution metrics and continuously optimize the knowledge base.

## Architecture Design

```
browser-use-rpa/
├── browser-use/          # Browser-use core library (unmodified)
├── learning_agent/       # Learning Agent wrapper layer
│   ├── agent.py         # Main Agent class, wrapping browser-use
│   ├── workflow.py      # Workflow data structure
│   ├── knowledge_base.py # Knowledge base management
│   └── replay.py        # Workflow replayer
├── demo_weather.py      # Weather query demo
├── demo_email.py        # Email sending demo
└── knowledge_base/      # Stores learned workflows
```

### Core Components

#### 1. LearningAgent (agent.py)
- Wraps the browser-use Agent class
- Intercepts and records each operation step
- Extracts stable XPath selectors
- Manages learning and replay modes

#### 2. Workflow (workflow.py)
- Defines the workflow data structure
- Supports parameterization (e.g., different recipients, subjects, etc.)
- Records element selectors and operation parameters

#### 3. KnowledgeBase (knowledge_base.py)
- Persistently stores workflows
- Intent matching algorithm
- Performance metric tracking

#### 4. WorkflowReplayer (replay.py)
- Uses Playwright to directly control the browser
- Intelligently waits for element loading
- Error recovery mechanism

## Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright browsers
playwright install chromium

# 3. Configure environment variables
cp env.example .env
# Edit the .env file and add your API keys
```

## Usage Examples

### Basic Usage

```python
from learning_agent import LearningAgent
from llm_factory import make_llm  # Wrapper LLM factory: direct OpenAI, falls back to OpenRouter if key is missing

# Create a learning Agent
agent = LearningAgent(
    task="Send an email to test@example.com with subject 'Test' and body 'This is a test email'",
    llm=make_llm(),  # Default: gpt-5.6-luna; falls back to OpenRouter if OPENAI_API_KEY is not set
    knowledge_base_path="./knowledge_base",
    headless=False  # Show the browser window
)

# Execute the task
result = agent.run_sync(max_steps=20)

print(f"Task completed: {'Success' if result['success'] else 'Failed'}")
print(f"Execution time: {result['execution_time']:.2f} seconds")
print(f"Learned workflow used: {result['replay_used']}")
```

### Running Demos

`demo_email.py` is the main entry point for this experiment, demonstrating the core idea of "learn a workflow once → replay it at high speed with different parameters."
It provides a complete Chinese command-line interface. Run `python demo_email.py --help` to view all parameters:

```bash
# Run the full "learn → replay" comparison demo (default behavior, opens a browser)
python demo_email.py

# Quick smoke test: run a single simple task without learn/replay comparison
python demo_email.py --quick

# Headless mode + use Gemini model
python demo_email.py --model gemini-2.0-flash-exp --headless

# Customize tasks for both phases and write metric comparison to a JSON file
python demo_email.py \
    --task 'Send an email to a@b.com with subject "Report"' \
    --replay-task 'Send an email to c@d.com with subject "Weekly Report"' \
    --output results.json

# Weather query demo (another lighter example)
python demo_weather.py
```

**Command-line argument description (`demo_email.py`):**

| Argument | Description | Default Value |
|-----|------|-------|
| `--task` | Task description for the learning phase | Send a test email to test@example.com |
| `--replay-task` | Task description for the replay phase (different parameters, same workflow) | Send an email to another@example.com |
| `--model` | LLM; `gpt-*` uses OpenAI (falls back to OpenRouter if key is missing), `gemini-*` uses Google | `gpt-5.6-luna` |
| `--headless` | Run the browser in headless mode | Show window |
| `--knowledge-base` | Storage directory for the workflow knowledge base | `./email_knowledge` |
| `--max-steps` | Maximum number of operation steps for the learning phase | `20` |
| `--output` | Write learn/replay metrics and knowledge base statistics to a JSON file | Do not write |
| `--quick` | Quick smoke test mode | Off |

**Expected results:** On the first run, the Agent is in the learning phase. It will gradually explore and record the "send email" workflow using the multimodal LLM. This takes longer and generates multiple LLM calls. Subsequently, the replay phase reuses the same workflow with new recipient/subject parameters, almost never invoking the LLM again, resulting in significantly reduced time. At the end of the demo, the duration, number of LLM calls, and knowledge base statistics for both phases are printed. If `--output` is specified, this comparison is saved as structured JSON, facilitating a review of the cost-benefit of "learn once, reuse many times."

> Note: A complete run requires a valid model API Key (see `.env`) and a locally available browser (`playwright install chromium`).
> `--help` and argument parsing do not require these dependencies.

## Acceptance Criteria Tests

### 1. First Task Execution (Learning Phase)

Run `demo_email.py` and observe the first phase:

- The Agent completes the task through an "observe-think-act" loop
- Each step requires an LLM call
- Upon success, the workflow is automatically saved to the knowledge base
- Execution time and step count are displayed

**Example output:**
```
📚 PHASE 1: LEARNING - First Email Task
Task: Send email to test@example.com
🚀 Starting learning phase...
✅ Learning phase completed!
   - Success: ✓
   - Execution time: 35.2 seconds
   - LLM calls made: 12
   - Workflow captured: Yes
```

### 2. Repeated Task Execution (Application Phase)

Continue observing the second phase:

- The Agent recognizes a similar task and matches a learned workflow
- Directly replays the operation steps without invoking the LLM
- Automatically fills in new parameters (recipient, subject, etc.)
- Execution speed is significantly improved

**Example output:**
```
🚀 PHASE 2: REPLAY - Second Email Task
Task: Send email to another@example.com
🔄 Starting replay phase...
✅ Replay phase completed!
   - Success: ✓
   - Execution time: 8.5 seconds
   - Workflow reused: Yes
   
🎯 Performance Improvements:
   - Speed: 4.1x faster
   - LLM calls saved: 12
   - Time saved: 26.7 seconds
```

## Technical Features

### 1. Stable Element Location

- **XPath Priority**: Captures the complete XPath path of elements, providing good robustness against page structure changes.
- **Multiple Fallbacks**: Attempts CSS selectors, attribute selectors, etc., when XPath fails.
- **Intelligent Waiting**: Uses `wait_for(state='visible')` to ensure elements are loaded.

### 2. Workflow Capture Mechanism

```python
# Extract element information from browser-use's internal state
element = selector_map[index]
workflow_step = WorkflowStep(
    action_type=ActionType.CLICK,
    xpath=element.xpath,
    element_attributes={
        'id': element.attributes.get('id'),
        'class': element.attributes.get('class'),
        ...
    }
)
```

### 3. Intent Matching Algorithm

- Keyword matching
- Verb recognition (send, write, check, etc.)
- Success rate weighting
- Confidence scoring

## Performance Comparison

| Metric | Learning Phase | Replay Phase | Improvement |
|-----|---------|---------|-----|
| Execution Time | 30-40 seconds | 5-10 seconds | 3-5x |
| LLM Call Count | 10-15 times | 0 times | 100% |
| Success Rate | 85% | 95%+ | 10%+ |

## Knowledge Base Management

View knowledge base statistics:

```python
from learning_agent import KnowledgeBase

kb = KnowledgeBase("./knowledge_base")
stats = kb.get_statistics()
print(stats)
# {
#     'total_workflows': 5,
#     'total_executions': 23,
#     'success_rate': '91.3%',
#     'total_model_calls_saved': 156
# }
```

Clear the knowledge base:

```python
kb.clear_all()  # Use with caution
```

## Limitations and Notes

1. **Dynamic Content**: XPath may change for highly dynamic pages.
2. **Authentication State**: Login state is not saved; each run starts from scratch.
3. **Complex Interactions**: Drag-and-drop, right-click menus, and other complex operations are not yet supported.
4. **Multiple Tabs**: Tab handling is simplified in replay mode.

## Extension Suggestions

1. **Smarter Parameter Extraction**: Use NLP models to extract task parameters.
2. **Workflow Composition**: Combine multiple small workflows into complex tasks.
3. **Error Recovery**: Enhance recovery strategies for replay failures.
4. **Distributed Knowledge Base**: Support team sharing of learned results.

## Contributing

Issues and Pull Requests to improve this project are welcome.

## License

This project is developed based on browser-use and follows its open-source license agreement.
