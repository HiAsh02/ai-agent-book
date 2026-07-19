# Fine-tuning a Multilingual Reasoning Model

This project demonstrates how to fine-tune OpenAI’s open-source reasoning model `openai/gpt-oss-20b` using Hugging Face’s TRL library, enabling it to reason effectively in multiple languages.

## Project Overview

Large reasoning models such as OpenAI o3 generate a chain-of-thought to improve response accuracy and quality. However, most models reason in English even when prompted in another language.

This project addresses this issue by:
- Adding a “reasoning language” option to the model’s system prompt
- Performing supervised fine-tuning (SFT) with a multilingual reasoning dataset
- Supporting reasoning in English, Spanish, French, Italian, German, and other languages

## Features

✨ **Multilingual Reasoning**: The model can generate a chain-of-thought in multiple languages  
🔀 **Mixed-Language Support**: Ask in one language, reason in another, and answer in a third  
🚀 **Efficient Training**: Uses Mxfp4Config quantization + LoRA (Low-Rank Adaptation) for memory-efficient fine-tuning  
🎯 **MoE-Optimized**: Training parameters specifically configured for Mixture-of-Experts architectures  
📊 **Real-Time Monitoring**: Tracks loss and metrics during training  
🌏 **Strong Cross-Lingual Generalization**: Even though the fine-tuning dataset does not contain Chinese, the model’s generalization ability allows it to generate reasoning in Chinese!

## System Requirements

### ⚠️ Important: GPU Memory Requirements

**Peak GPU memory usage during training is approximately 97 GB**

- **Recommended**: H200 GPU (141 GB memory)
- **Not Recommended**: Single 80 GB GPU (H100/A100) – will cause OOM (Out of Memory) errors
- **Alternatives**: 
  - Use multi-GPU training (model parallelism / data parallelism)
  - Reduce batch size and max sequence length
  - Use gradient checkpointing
  - Use memory optimization techniques such as DeepSpeed ZeRO-3

### Other Requirements

- CUDA: 12.8 or higher
- Python: 3.8+
- Storage: At least 100 GB (for model and checkpoints)

## Installing Dependencies

```bash
# Install PyTorch (CUDA 12.8)
pip install torch --index-url https://download.pytorch.org/whl/cu128

# Install other dependencies
pip install "trl>=0.20.0" "peft>=0.17.0" "transformers>=4.55.0" trackio datasets accelerate
```

## Quick Start

### 1. Set Up the Environment

First, make sure you are logged in to Hugging Face:

```python
from huggingface_hub import notebook_login
notebook_login()
```

Or use the command line:

```bash
huggingface-cli login
```

### 2. Prepare the Dataset

This project uses the `HuggingFaceH4/Multilingual-Thinking` dataset, which contains reasoning chains in multiple languages:

```python
from datasets import load_dataset

dataset = load_dataset("HuggingFaceH4/Multilingual-Thinking")
```

**⚠️ Important Note**: Although this dataset does not contain Chinese data, thanks to the model’s strong generalization ability, the fine-tuned model can still reason in Chinese! See the “Important Note on Chinese Reasoning” section below for details.

### 3. Understanding the Chat Template and Harmony Format

The `gpt-oss` model uses the **Harmony response format** to define conversation structure, generate reasoning output, and construct function calls. This format mimics the OpenAI Responses API and includes the following message types:

#### Message Types

| Type | Description |
|------|-------------|
| **developer** | Developer messages for providing custom instructions (equivalent to the system role) |
| **user** | User messages for providing input |
| **assistant** | Model output, which can be a tool call or a message output. The output may be associated with a specific “channel” that identifies the message intent |
| **analysis** | Messages for the model’s chain-of-thought |
| **final** | Messages marked in the final channel, intended to be shown to the end user and represent the model’s response |
| **messages** | A list of messages that combines the above to form a complete conversation |

#### Important Features

**Special Fields in Assistant Messages**:
- `thinking`: Contains the model’s reasoning process
- `content`: Contains the final response to the user

**Two Types of System Messages**:
1. **Default system message**: Applies to all messages (e.g., “You are ChatGPT, a large language model trained by OpenAI...”)
2. **Special developer message**: Contains custom instructions (defined by the `system` role in the messages object)

#### Chat Template Example

Use the tokenizer’s `apply_chat_template()` method to format messages:

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("openai/gpt-oss-20b")

# Example messages
messages = [
    {"role": "system", "content": "reasoning language: German"},
    {"role": "user", "content": "¿Cuál es el capital de Australia?"}
]

# Apply the chat template
conversation = tokenizer.apply_chat_template(messages, tokenize=False)
print(conversation)
```

**Output Format Features**:
- Uses special tokens: `<|start|>` and `<|end|>` to mark the beginning and end of messages
- The `<|return|>` token marks the end of the conversation
- Includes `<|channel|>` markers (e.g., `analysis`, `final`) to distinguish reasoning from the final response

#### Formatting Example

```
<|start|>system<|message|>You are ChatGPT, a large language model trained by OpenAI.
Knowledge cutoff: 2024-06
Current date: 2025-10-03

Reasoning: medium

# Valid channels: analysis, commentary, final. Channel must be included for every message.<|end|>
<|start|>developer<|message|># Instructions

reasoning language: German

<|end|>
<|start|>user<|message|>¿Cuál es el capital de Australia?<|end|>
<|start|>assistant<|channel|>analysis<|message|>[Model’s reasoning process]<|end|>
<|start|>assistant<|channel|>final<|message|>[Final response]<|return|>
```

The TRL library automatically handles dataset formatting, applying the chat template, and tokenization, so you do not need to handle these details manually during training.

### 4. Run Fine-Tuning

```bash
python gpt_oss_20b_sft.py
```

### 5. Inference Testing

After fine-tuning, you can use the model for multilingual reasoning:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

# Load the model and tokenizer
tokenizer = AutoTokenizer.from_pretrained("openai/gpt-oss-20b")
model = AutoModelForCausalLM.from_pretrained("your_model_path")

# Set the reasoning language
REASONING_LANGUAGE = "German"
SYSTEM_PROMPT = f"reasoning language: {REASONING_LANGUAGE}"
USER_PROMPT = "¿Cuál es el capital de Australia?"  # Spanish: What is the capital of Australia?

messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": USER_PROMPT},
]

# Generate a response
input_ids = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt")
output_ids = model.generate(input_ids, max_new_tokens=512, temperature=0.6)
response = tokenizer.decode(output_ids[0])
print(response)
```

## Training Configuration

### Hyperparameters (Exactly Matching the OpenAI Cookbook Tutorial)

- **Model**: `openai/gpt-oss-20b` (20B parameters)
- **Quantization**: Mxfp4Config (4-bit floating-point format optimized for OpenAI models)
- **LoRA rank**: 8
- **LoRA alpha**: 16
- **Batch size**: 4 (per_device_train_batch_size)
- **Gradient accumulation steps**: 4
- **Effective batch size**: 16 (4 × 4)
- **Learning rate**: 2e-4
- **Learning rate scheduler**: cosine_with_min_lr (minimum learning rate is 10% of the initial)
- **Warmup ratio**: 0.03
- **Number of training epochs**: 1
- **Maximum sequence length**: 2048
- **Gradient checkpointing**: True
- **Peak memory usage**: ~97 GB

### LoRA Configuration

Using LoRA (Low-Rank Adaptation) technology, only a small number of parameters are trained:
- **Target modules**: `all-linear` (all linear layers)
- **MoE expert layers**: Additionally train the MLP expert projection layers (gate_up_proj and down_proj) in layers 7, 15, and 23
- **Advantages**: 
  - Significantly reduces training time and memory usage
  - Keeps the base model weights unchanged
  - Optimized for Mixture-of-Experts (MoE) architectures

## Project Structure

```
MultilingualReasoning/
├── README.md                    # Project documentation
├── gpt_oss_20b_sft.py          # Complete training and inference script
└── requirements.txt             # Dependency list (optional)
```

## Training Time and Resource Consumption

### Standard Configuration (OpenAI Cookbook Test Results)

- **GPU**: H100 (80 GB memory)
- **Training time**: Approximately 18 minutes
- **Peak memory usage**: ~97 GB ⚠️ **Will cause OOM!**

### Recommended Configuration in Practice

Since peak memory usage exceeds 80 GB, it is recommended to use:
- **H200 GPU** (141 GB memory) – works perfectly
- **Multiple H100 GPUs** – use model parallelism
- **Optimized configuration** – see “Performance Optimization Suggestions” below

### Influencing Factors

Training time and memory usage depend on:
- GPU model and memory size
- Batch size
- Sequence length (max_seq_length)
- Number of gradient accumulation steps
- Whether mixed-precision training is used

## Inference Examples

The following examples show how the model performs multilingual reasoning using the Harmony format. Note the key elements in the output:
- `<|start|>` and `<|end|>`: Mark message boundaries
- `<|channel|>analysis`: Reasoning process (internal thinking)
- `<|channel|>final`: Final response (presented to the user)
- `<|return|>`: End-of-conversation marker

### Example 1: Spanish Question + German Reasoning

This example demonstrates cross-lingual reasoning ability: the user asks in Spanish, the model thinks in German, and then answers in English.

```
Generating response...
Reasoning language: German
User question: ¿Cuál es el capital de Australia?
--------------------------------------------------------------------------------
<|start|>system<|message|>You are ChatGPT, a large language model trained by OpenAI.
Knowledge cutoff: 2024-06
Current date: 2025-10-03

Reasoning: medium### 🌏 Important Note on Chinese Reasoning

**⚠️ Zero-shot Generalization Demonstration**

Although the training dataset `HuggingFaceH4/Multilingual-Thinking` **does not contain any Chinese data**, the model can still generate high-quality reasoning processes in Chinese! This is because:

1. **Multilingual capability of the base model**: The GPT-OSS-20B base model itself supports multiple languages, including Chinese
2. **Transfer of reasoning patterns**: By learning reasoning patterns in other languages (English, Spanish, German, etc.), the model can generalize this ability to unseen languages
3. **Guidance from system prompts**: Through the `reasoning language: Chinese` system prompt, the model can understand and switch to Chinese for reasoning

This **zero-shot cross-lingual generalization** is an important characteristic of large language models, demonstrating that even without training data in a specific language, the model can still perform well in new languages.

**Practical significance**:
- No need to collect training data for each language
- Reduces the training cost of multilingual models
- Proves that reasoning ability is a transferable general capability

Examples 2 and 3 below demonstrate the model's reasoning ability in Chinese:

### Example 2: English Question + Chinese Reasoning

This example demonstrates zero-shot cross-lingual generalization: although there is no Chinese data in the training set, the model can still reason in Chinese.

```
Generating response...
Reasoning language: Chinese
User question: What is the national symbol of Canada?
--------------------------------------------------------------------------------
<|start|>system<|message|>You are ChatGPT, a large language model trained by OpenAI.
Knowledge cutoff: 2024-06
Current date: 2025-10-03

Reasoning: medium

# Valid channels: analysis, commentary, final. Channel must be included for every message.<|end|><|start|>developer<|message|># Instructions

reasoning language: Chinese

<|end|><|start|>user<|message|>What is the national symbol of Canada?<|end|><|start|>assistant<|channel|>analysis<|message|>
Let me first think about Canada's national symbols. Canada's flag is red and white with a maple leaf in the center. The maple leaf is Canada's iconic symbol, often used to represent the country. The maple leaf holds an important place in Canadian culture and history, for example, maple syrup is a traditional Canadian food, and the maple leaf is also used on many official emblems and souvenirs.

I also recall that Canada's coat of arms and flag both feature the maple leaf as a core element. The maple leaf symbolizes Canada's natural landscape and diversity, and also reflects Canadians' love for the land and nature. Therefore, I can confidently say that the maple leaf is Canada's national symbol.<|end|><|start|>assistant<|channel|>final<|message|>The national symbol of Canada is the **maple leaf**. The maple leaf is prominently featured on Canada’s national flag (the Red Ensign), its coat of arms, and is widely used in government and cultural contexts to represent Canadian identity. The maple leaf symbolizes Canada's natural environment, its multicultural heritage, and its historical ties to the maple tree, which is abundant in the country.<|return|>
--------------------------------------------------------------------------------
```

### Example 3: Chinese Question + Chinese Reasoning

This example demonstrates fully Chinese reasoning: asking a math question in Chinese, and the model provides a detailed reasoning process in Chinese.

```
Generating response...
Reasoning language: Chinese
User question: Solve for the roots of x^2 - 2x + 1 = 0
--------------------------------------------------------------------------------
<|start|>system<|message|>You are ChatGPT, a large language model trained by OpenAI.
Knowledge cutoff: 2024-06
Current date: 2025-10-03

Reasoning: medium

# Valid channels: analysis, commentary, final. Channel must be included for every message.<|end|><|start|>developer<|message|># Instructions

reasoning language: Chinese

<|end|><|start|>user<|message|>Solve for the roots of x^2 - 2x + 1 = 0<|end|><|start|>assistant<|channel|>analysis<|message|>
First, I need to confirm that I understand the user's input. The user asks to solve for the roots of the equation x^2 - 2x + 1 = 0.

Next, I recall the general method for solving quadratic equations. The standard form of a quadratic equation is ax^2 + bx + c = 0. Here, a = 1, b = -2, c = 1.

I can use the quadratic formula: x = [-b ± sqrt(b^2 - 4ac)] / (2a). Let's substitute the values:

b^2 = (-2)^2 = 4
4ac = 4 * 1 * 1 = 4
b^2 - 4ac = 4 - 4 = 0

Since the discriminant (b^2 - 4ac) is 0, the equation has a repeated root. Calculate the root:

x = [-b ± sqrt(0)] / (2a) = [2 ± 0] / 2 = 2 / 2 = 1

Therefore, the root is x = 1.

I want to double-check to make sure there are no errors. Substitute x = 1 into the original equation:

(1)^2 - 2*(1) + 1 = 1 - 2 + 1 = 0

This verifies my answer. The root is x = 1, and since the discriminant is 0, it is a repeated root.

I should state in the response that the root is x = 1, and mention that it is a repeated root.
<|end|><|start|>assistant<|channel|>final<|message|>The equation \(x^2 - 2x + 1 = 0\) has a **double root** (also called a repeated root) at \(x = 1\).

**Solution:**

1. **Using the quadratic formula**:
   \[
   x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
   \]
   For the equation \(x^2 - 2x + 1 = 0\), we have \(a = 1\), \(b = -2\), and \(c = 1\).

   \[
   \Delta = b^2 - 4ac = (-2)^2 - 4 \cdot 1 \cdot 1 = 4 - 4 = 0
   \]

   Since the
--------------------------------------------------------------------------------
```

## Technical Details

### Harmony Response Format and Chat Template

The `gpt-oss` model uses the **Harmony Response Format**, a dialogue format specifically designed for reasoning models.

#### Differences from Standard Dialogue Formats

In traditional dialogue formats, the assistant has only a simple response. In the Harmony format:

```python
# Traditional format
{"role": "assistant", "content": "The answer is..."}

# Harmony format
{
    "role": "assistant",
    "thinking": "Let me think... first... then...",  # Reasoning process
    "content": "The answer is..."  # Final response
}
```

#### Channel Mechanism

The Harmony format uses "channels" to distinguish different types of output:

- **analysis**: Used for internal reasoning and thought processes
- **commentary**: Used for supplementary explanations and comments
- **final**: Used for the final response presented to the user

#### Role of the Chat Template

The `apply_chat_template()` method converts structured messages into a text format the model can understand:

```python
# Input (structured)
messages = [
    {"role": "system", "content": "reasoning language: Chinese"},
    {"role": "user", "content": "What is 2+2?"}
]

# Output (formatted text)
<|start|>system<|message|>You are ChatGPT...
<|start|>developer<|message|>reasoning language: Chinese<|end|>This process includes:
- Adding special tokens (`<|start|>`, `<|end|>`, `<|message|>`, `<|channel|>`, etc.)
- Injecting the default system prompt
- Correctly handling developer and system messages
- Setting the inference level and valid channels

### Dataset Format

The `HuggingFaceH4/Multilingual-Thinking` dataset already uses the Harmony format, containing:
- System prompt (specifying the inference language)
- User message (question)
- Assistant reasoning (chain-of-thought, via the `thinking` field or `analysis` channel)
- Assistant response (final answer, via the `content` field or `final` channel)

### LoRA Advantages

1. **Memory Efficiency**: Only trains a small number of parameters (typically <1% of model parameters)
2. **Fast Training**: Reduces computational requirements
3. **Easy Deployment**: LoRA weights can be merged with the base model
4. **Multiple Adapters**: Multiple LoRA adapters can be trained for different tasks

## Performance Optimization Suggestions

### 1. Reduce VRAM Usage (for 80GB GPUs)

Since peak VRAM demand is 97GB, here are optimization strategies for running on 80GB GPUs:

```bash
# Option 1: Further reduce batch size
python gpt_oss_20b_sft.py --batch_size 2 --max_seq_length 1536

# Option 2: Reduce sequence length
python gpt_oss_20b_sft.py --batch_size 3 --max_seq_length 1024

# Option 3: Combined optimization
python gpt_oss_20b_sft.py --batch_size 2 --max_seq_length 1024
```

**Note**: These modifications deviate from the original OpenAI Cookbook configuration and may affect training results. The current default configuration (batch_size=4, max_length=2048) is fully aligned with the official tutorial.

### 2. Use Multi-GPU Training

```bash
# Using DeepSpeed ZeRO-3 (recommended)
deepspeed --num_gpus=2 gpt_oss_20b_sft.py --mode train

# Or using PyTorch FSDP
torchrun --nproc_per_node=2 gpt_oss_20b_sft.py --mode train
```

### 3. Gradient Checkpointing

Enabled by default (`gradient_checkpointing=True`), which reduces training speed but saves VRAM.

## Frequently Asked Questions

**Q: Why is 97GB of VRAM needed? Is my H100 (80GB) sufficient?**
A: No, it is not sufficient. Peak VRAM during training reaches 97GB, so a single 80GB GPU will encounter OOM errors. An H200 (141GB) or multi-GPU training is recommended.

**Q: What if I don't have enough VRAM?**
A: There are several options:
   1. Use an H200 GPU (recommended, allows running the notebook configuration fully)
   2. Use multi-GPU training (2 H100s)
   3. Reduce batch size and sequence length (will deviate from the original configuration)
   4. Use DeepSpeed ZeRO-3 or FSDP

**Q: Can I train on an A100 (80GB)?**
A: Not recommended. Both the A100 and H100 have 80GB of VRAM and will encounter OOM issues.

**Q: Why does the official tutorial say an H100 can run this?**
A: The official tutorial provides an estimate under ideal conditions. In practice, due to additional overhead (activations, optimizer states, etc.), peak VRAM exceeds 80GB. This project recommends using an H200 based on practical testing experience.

**Q: Can I train on other languages?**
A: Yes! Simply prepare a reasoning dataset in the desired language. Due to the model's strong zero-shot generalization ability, it may perform well even if a language is not in the training data.

**Q: What is the Harmony format? Why use it?**
A: Harmony is a specialized format used by gpt-oss models. It allows the model to separate the reasoning process (thinking/analysis) from the final response (content/final). This enables:
   - Transparent and visible reasoning processes
   - Reasoning and answering in different languages
   - Support for more complex, multi-step reasoning

**Q: Do I need to manually handle the Chat Template?**
A: No. TRL's `SFTTrainer` will automatically call `apply_chat_template()` to format the dataset. You only need to ensure the dataset conforms to the standard message format (containing `role` and `content` fields).

**Q: How do I evaluate the model after training?**
A: You can evaluate reasoning quality, accuracy, and fluency on a multilingual test set. Focus on two aspects:
   1. Whether the reasoning process is clear and logically correct
   2. Whether the final answer is accurate

**Q: Will modifying hyperparameters affect performance?**
A: Yes. The current default configuration is fully aligned with the official tutorial (batch_size=4, learning_rate=2e-4, lora_rank=8, etc.). Further reducing batch size, sequence length, etc., will deviate from the official configuration and may affect the final model quality.

## References

- [OpenAI Cookbook Official Tutorial](https://cookbook.openai.com/articles/gpt-oss/fine-tune-transfomers)
- [OpenAI GPT-OSS-20B Model](https://huggingface.co/openai/gpt-oss-20b)
- [Multilingual-Thinking Dataset](https://huggingface.co/datasets/HuggingFaceH4/Multilingual-Thinking)
- [TRL Library Documentation](https://github.com/huggingface/trl)
- [LoRA Paper](https://arxiv.org/abs/2106.09685)

## Contributing

Contributions of code, issue reports, or improvement suggestions are welcome!

## License

This project follows the corresponding open-source license. Please comply with OpenAI's model usage terms when using it.

## Acknowledgements

- The OpenAI team for releasing the open-source reasoning model
- The Hugging Face team for providing the TRL library and datasets
- Original tutorial authors: Edward Beeching, Quentin Gallouédec, Lewis Tunstall
