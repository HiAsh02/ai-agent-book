# Intuitor: Learning to Reason without External Rewards

Based on the paper: [Learning to Reason without External Rewards](https://arxiv.org/pdf/2505.19590)

[Paper Link](https://arxiv.org/abs/2505.19590) | [Hugging Face](https://huggingface.co/collections/sunblaze-ucb/intuitor-676e1dc23b2d64a88b0b0b79)

## 📖 Project Introduction

Intuitor is an innovative reinforcement learning method that uses **self-certainty**—the model's own internal confidence—as the sole reward signal to fine-tune large language models (LLMs). This approach is built upon a novel training paradigm: **Reinforcement Learning from Internal Feedback (RLIF)**.

### 🌊 Three Curves of LLM Capability Enhancement

Intuitor represents the **third curve** of LLM capability enhancement:

#### 🔵 First Curve: Pre-training
- **Core**: Self-supervised learning on massive unlabeled text
- **Goal**: Learn statistical patterns of language and world knowledge
- **Representatives**: GPT-3/4, LLaMA, Qwen, and other base models
- **Limitation**: Lacks goal orientation, struggles with complex reasoning tasks

#### 🟢 Second Curve: Reinforcement Learning from Verifiable Rewards (RLVR)
- **Core**: Uses automatically verifiable reward signals (e.g., answer correctness, code execution results)
- **Goal**: Improve reasoning ability in specific domains (math, code)
- **Representatives**: DeepSeek-R1, OpenAI o1, Kimi K1.5, MiMo
- **Limitations**:
  - ❌ Requires gold-standard answers or test cases
  - ❌ Only applicable to tasks with clear correct answers (math, code, science problems)
  - ❌ **Most real-world tasks lack a clear reward function**:
    - How to quantify writing quality?
    - How to automatically evaluate creative design?
    - How to verify if a conversation is engaging or helpful?
    - How to judge decision reasonableness in advance?

#### 🔴 Third Curve: Unsupervised Reinforcement Learning ✨ **The curve Intuitor belongs to**
- **Core**: Reinforcement learning without gold-standard answers or human preference labels, using various automated signals
- **Goal**: Provide training methods for tasks without explicit reward functions
- **Representative Methods**:
  - **Internal Feedback**: Intuitor (self-certainty)
  - **Rubrics-based**: Based on predefined rules or scoring criteria
  - **Novelty-based**: Encourages exploration of unknown regions
  - **Multi-agent Debate**: Reaching consensus through discussion
- **Advantages**:
  - ✅ Fully unsupervised, no labeled data required
  - ✅ Applicable to **any task**, including those without clear right/wrong answers
  - ✅ Stronger **cross-domain generalization ability**
  - ✅ Provides solutions for 90% of real-world tasks

### 🧭 What is RLIF?

**RLIF (Reinforcement Learning from Internal Feedback)** is an **unsupervised reinforcement learning** method proposed in this paper, representing one implementation of the third curve.

The core idea of RLIF is: language models improve themselves by optimizing **internal signals** (such as self-confidence, internal consistency) without any external rewards, ground-truth answers, or verifiers.

#### RLIF's Position in the Unsupervised RL Ecosystem

```
Third Curve: Unsupervised Reinforcement Learning
├─ Internal Feedback
│  └─ RLIF (this paper's method): uses self-certainty as reward
├─ Consistency
│  ├─ TTRL: uses plurality voting
│  └─ Self-consistency: consistency across multiple samples
├─ Rubrics-based
│  └─ Based on predefined scoring criteria
├─ Novelty-based
│  └─ Encourages exploration of unknown regions
└─ Multi-agent
   └─ Generates rewards through debate or collaboration
```

#### The Essence of the Three Curves

- **First Curve (Pretrain)**: What to learn? → Knowledge acquisition
- **Second Curve (RLVR)**: How to be correct? → Task-specific correctness
- **Third Curve (Unsupervised RL)**: How to be good? → Unsupervised general quality improvement

The third curve enables LLMs to achieve scalable and domain-agnostic fine-tuning in scenarios where human feedback or verifiable supervision is expensive or unavailable. This is crucial for future AI systems in open-ended, creative, and subjective tasks.

### 💡 Core Idea of Intuitor

Intuitor implements RLIF within the GRPO (Group Relative Policy Optimization) algorithm by using **Self-Certainty** as an intrinsic reward.

**Key Observation**: Large language models typically exhibit low confidence when facing difficult problems, but show higher certainty on familiar tasks. By optimizing the model's own confidence, it can be guided to learn more effective reasoning paths, thereby improving reasoning ability.

---

### ⚡ Why is Intuitor So Important?

#### 🎯 Core Breakthrough

Intuitor is not just "another reasoning model"; it represents a **paradigm shift** in LLM capability enhancement:

```
First Curve (Pretrain)          → Learning "what is" (knowledge)
Second Curve (RLVR)             → Learning "what is correct" (math, code correctness)
Third Curve (Unsupervised RL)   → Learning "what is good" (general quality improvement)
  └─ Intuitor achieves this using internal feedback (self-certainty)
```

#### 🔥 Real-World Pain Points

**The Ceiling of the Second Curve**:
- Models like DeepSeek-R1 and o1 are approaching human expert level in math/code
- But this accounts for only **< 10%** of real-world tasks
- 90% of tasks **have no clear right/wrong standard**:
  - 📝 Writing: What makes an article "good"?
  - 💬 Dialogue: What makes a response "helpful"?
  - 🎨 Creativity: What makes a design "excellent"?
  - 🤔 Decision-making: What makes a strategy "reasonable"?

**Intuitor's Solution**:
- ✅ Does not rely on external evaluation criteria
- ✅ Improves quality by optimizing internal consistency
- ✅ Applicable to **any domain**, requiring only a prompt

#### 💪 Experimental Evidence

| Metric | Result | Significance |
|-----|------|------|
| **Math (MATH500)** | 61.2% vs GRPO 63.6% | Comparable performance under unsupervised conditions |
| **Code (LiveCodeBench)** | +65% vs GRPO -8% | **Overwhelming cross-domain generalization** |
| **Instruction Following (AlpacaEval)** | 7.10 vs Base 3.72 | Significant general capability improvement |

**Key Finding**: The Intuitor model trained on MATH automatically learned code generation ability, outperforming GRPO trained on MATH! This proves it learns **general reasoning ability**, not task-specific patterns.

#### 🚀 Future Significance

When AI capabilities surpass human abilities (scientific discovery, strategic decision-making):
- Humans cannot provide reliable "correct answers" as supervision
- RLIF becomes the only viable path for improvement
- Intuitor provides a methodology for the "self-evolution" toward AGI

---

### 🎯 Main Advantages

Based on experimental results from the paper (using Qwen2.5-3B, trained on the MATH dataset):

1. **Fully Unsupervised Learning**
   - ✅ No need for standard answers or test cases
   - ✅ No need for human annotations or preference data
   - ✅ No need for domain-specific verifiers
   - ✅ Only requires clear task prompts

2. **Comparable In-Domain Performance**
   - **GSM8K**: Intuitor 79.2% vs GRPO 82.6%
   - **MATH500**: Intuitor 61.2% vs GRPO 63.6%
   - Performance close to supervised GRPO without requiring gold-standard answers

3. **Significantly Stronger Out-of-Domain Generalization** (key advantage)
   - **LiveCodeBench v6** (code generation)
     - Base: 9.3% → Intuitor: 15.3% (**+65% relative improvement**)
     - Base: 9.3% → GRPO: 8.5% (**performance degradation**)
   - **CRUXEval-O** (code reasoning)
     - Base: 23.6% → Intuitor: 41.6% (**+76% relative improvement**)
     - Base: 23.6% → GRPO: 34.1% (**+44% relative improvement**)

4. **Emergent Abilities**
   - **Structured Reasoning**: The model spontaneously produces long chains of reasoning (similar to R1 style)
   - **Instruction Following**: AlpacaEval score improved from 3.72 to 7.10
   - **Self-Understanding**: Qwen2.5-1.5B evolved from producing gibberish (0% on LiveCodeBench) to generating coherent code (9.9%)

5. **Fast Learning**
   - In early training (Step 10), Intuitor outperforms GRPO on both GSM8K and MATH
   - Faster initial learning speed indicates that internal signals provide more effective learning trajectories

## 🚀 Released Models

We have released four model checkpoints trained on the MATH dataset for one epoch:

| Model Name | Size | Method | Hugging Face Link |
|---------|------|------|-------------------|
| sunblaze-ucb/Qwen2.5-1.5B-Intuitor-MATH-1EPOCH | 1.5B | Intuitor | [View Model](https://huggingface.co/sunblaze-ucb/Qwen2.5-1.5B-Intuitor-MATH-1EPOCH) |
| sunblaze-ucb/Qwen2.5-3B-Intuitor-MATH-1EPOCH | 3B | Intuitor | [View Model](https://huggingface.co/sunblaze-ucb/Qwen2.5-3B-Intuitor-MATH-1EPOCH) |
| sunblaze-ucb/OLMo-2-7B-SFT-Intuitor-MATH-1EPOCH | 7B | Intuitor | [View Model](https://huggingface.co/sunblaze-ucb/OLMo-2-7B-SFT-Intuitor-MATH-1EPOCH) |
| sunblaze-ucb/Qwen3-14B-Intuitor-MATH-1EPOCH | 14B | Intuitor | [View Model](https://huggingface.co/sunblaze-ucb/Qwen3-14B-Intuitor-MATH-1EPOCH) |

## 📦 Repository Structure

This tutorial uses the **verl-intuitor** implementation, a high-performance RL training library based on [VERL](https://github.com/volcengine/verl), designed for large language models.

Original repository: [https://github.com/sunblaze-ucb/Intuitor](https://github.com/sunblaze-ucb/Intuitor)
- verl-intuitor is based on VERL commit c26b0f2

## 🛠️ Environment Setup

### 1. Clone the Intuitor Repository

```bash
git clone https://github.com/sunblaze-ucb/Intuitor.git
cd Intuitor/verl-intuitor
```

### 2. Install Dependencies

First, install VERL and related dependencies:

```bash
# Create a Python virtual environment (recommended)
conda create -n intuitor python=3.10
conda activate intuitor

# Install PyTorch (adjust based on your CUDA version)
pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu118

# Install VERL
pip install -e .

# Install other dependencies
pip install wandb transformers datasets accelerate
```

### 3. Prepare the MATH Dataset

Run the following Python script to download and preprocess the MATH dataset:

```bash
python examples/data_preprocess/math_dataset_ours.py --model Qwen2.5-3B
```

## 🚀 Training the Model

### 1. Configure WANDB API Key

Before running training, modify the `math_intuitor.sh` script to add your WANDB API Key:

```bash
# Edit math_intuitor.sh
vim math_intuitor.sh

# Add the following line at the beginning of the script:
export WANDB_API_KEY=YOUR_WANDB_API_KEY
```Replace `YOUR_WANDB_API_KEY` with your actual WANDB API Key (available at [wandb.ai/authorize](https://wandb.ai/authorize)).

### 2. Start Training

After configuration, run the training script:

```bash
bash math_intuitor.sh
```

**Important Note**: The only heuristic design in Intuitor is the prompt used to query the model. Therefore, performance may sometimes be sensitive to prompt design. If the model is not learning effectively, try alternative prompts or use the original prompt provided in our settings.

### 3. Multi-Node Training (Optional)

If you need to use Ray for multi-node training, please refer to the detailed instructions and scripts in the `./scripts_ray` folder.

## 📊 Model Evaluation

After training, perform standardized evaluation using **[lighteval](https://github.com/huggingface/lighteval)** following the paper's methodology.

> **Why use lighteval?**
> - ✅ Official evaluation tool used in the paper
> - ✅ Standard evaluation framework for Hugging Face Leaderboard
> - ✅ Supports 7,000+ evaluation tasks covering math, code, multilingual, etc.
> - ✅ Unified evaluation standards for comparable results

### 1. Install lighteval

```bash
pip install lighteval
```

### 2. Convert Model Format

First, convert the training checkpoint to Hugging Face format:

```bash
python -m verl.model_merger merge \
    --backend fsdp \
    --local_dir /root/Intuitor/verl-intuitor/checkpoints/verl/math_intuitor/global_step_57 \
    --target_dir math_intuitor_model
```

**Parameter Description**:
- `--backend fsdp`: Use FSDP (Fully Sharded Data Parallel) backend
- `--local_dir`: Path to the training checkpoint (adjust according to your actual path)
- `--target_dir`: Output directory for the Hugging Face format model

### 3. Modify lighteval Source Code (Important!)

**You must modify the lighteval source code before evaluation**, otherwise you will encounter two issues:
1. The default 256 token generation size is insufficient for the model to complete reasoning
2. The default normalizer cannot recognize the `\boxed{}` answer format

#### Step 1: Modify generation_size

Locate the task configuration file in the lighteval installation path:

```bash
# Find lighteval installation location
python3 -c "import lighteval; print(lighteval.__file__)"
# Example output: /path/to/site-packages/lighteval/__init__.py

# Edit the task configuration file
vim $(python3 -c "import lighteval.tasks.default_tasks as t; print(t.__file__)")
```

In `default_tasks.py`, find the GSM8K Leaderboard configuration (search for `"gsm8k_leaderboard"`) and change `generation_size` from `256` to `2048`:

```python
# Before modification:
LightevalTaskConfig(
    name="gsm8k",
    ...
    generation_size=256,  # ← Original value is too small
    ...
)

# After modification:
LightevalTaskConfig(
    name="gsm8k",
    ...
    generation_size=2048,  # ← Changed to 2048, providing sufficient token budget for the reasoning chain
    ...
)
```

#### Step 2: Modify gsm8k_normalizer to support \\boxed{} format

Find and edit the normalizer file:

```bash
# Edit normalizations.py
vim $(python3 -c "import lighteval.metrics.normalizations as n; print(n.__file__)")
```

Locate the `gsm8k_normalizer` function (around line 379) and replace it with the following code:

```python
def gsm8k_normalizer(text: str) -> str:
    """From https://github.com/openai/grade-school-math/blob/3101c7d5072418e28b9008a6636bde82a006892c/grade_school_math/dataset.py#L28
    
    Extended to support \\boxed{} format commonly used by reasoning models.

    Args:
        text (str): input text

    Returns:
        str: Output text, either the number found in the text or "[invalid]" if
        no number was found
    """
    INVALID_ANS = "[invalid]"
    
    # Try to extract from \\boxed{} format first (for reasoning models like Intuitor)
    # This pattern matches both \boxed{number} and \(\boxed{number}\)
    boxed_match = re.search(r'\\boxed\{([^}]+)\}', text)
    if boxed_match:
        match_str = boxed_match.group(1).strip()
        match_str = match_str.replace(",", "")
        # Extract only the number part (remove any non-numeric trailing text)
        number_match = re.search(r'-?[0-9\.\,]+', match_str)
        if number_match:
            return number_match.group(0).replace(",", "")
    
    # Original #### format (for standard GSM8K format)
    ans_re = re.compile(r"#### (\-?[0-9\.\,]+)")
    match = ans_re.search(text)
    if match:
        match_str = match.group(1).strip()
        match_str = match_str.replace(",", "")
        return match_str
    
    # If no pattern matched, return invalid
    return INVALID_ANS
```

**Modification Notes**:
- ✅ **Backward Compatible**: Retains support for the original `####` format
- ✅ **Supports `\boxed{}`**: Recognizes LaTeX boxed formats like `\boxed{52}` and `\(\boxed{5}\)`
- ✅ **Automatic Number Extraction**: Extracts numbers even if the box contains units (e.g., `\boxed{52 WPM}`)

**Why are these two modifications necessary?**
- **Generation size**: Intuitor generates CoT with detailed reasoning steps; 256 tokens will cause answers to be truncated
- **Normalizer**: Intuitor outputs LaTeX `\boxed{}` format, which differs from the standard GSM8K `####` format

### 4. Evaluate with lighteval

#### Evaluate GSM8K (Mathematical Reasoning)

```bash
lighteval accelerate \
    "model_name=math_intuitor_model/" \
    "leaderboard|gsm8k|0"
```

### 5. View Evaluation Results

lighteval will automatically generate a detailed evaluation report:

```bash
# Results are saved in the specified output directory
ls ./eval_results/

# View detailed results (JSON format)
cat ./eval_results/results.json
```

#### Recalculate Accuracy from Cached Parquet

If lighteval shows 0% accuracy (because the model outputs `\boxed{}` format instead of `####` format), you can use the provided script to recalculate accuracy from the cached parquet file:

```bash
# Find the cached parquet file
# Path format: ~/.cache/huggingface/lighteval/{model_name}/{hash}/leaderboard|gsm8k|0/{hash}/GENERATIVE.parquet
ls ~/.cache/huggingface/lighteval/math_intuitor_model/*/leaderboard\|gsm8k\|0/*/GENERATIVE.parquet

# Use the script to recalculate accuracy (supports \boxed{} format)
python3 evaluate_from_cache.py \
    ~/.cache/huggingface/lighteval/math_intuitor_model/*/leaderboard\|gsm8k\|0/*/GENERATIVE.parquet

# Display detailed information and error samples
python3 evaluate_from_cache.py \
    ~/.cache/huggingface/lighteval/math_intuitor_model/*/leaderboard\|gsm8k\|0/*/GENERATIVE.parquet \
    -v

# Save results to a JSON file
python3 evaluate_from_cache.py \
    ~/.cache/huggingface/lighteval/math_intuitor_model/*/leaderboard\|gsm8k\|0/*/GENERATIVE.parquet \
    -o results.json
```

**Script Features**:
- ✅ Supports `\boxed{}` answer extraction (including variants like `\(\boxed{}\)`)
- ✅ Automatically loads GSM8K gold answers from Hugging Face
- ✅ Standardizes number formats (removes commas, spaces, etc.)
- ✅ Displays detailed error sample analysis

**Example Output**:
```
📂 Reading predictions: /root/.cache/huggingface/lighteval/.../GENERATIVE.parquet
📊 Total samples: 1319
📥 Loading GSM8K gold answers...

================================================================================
📈 Evaluation Results
================================================================================
Total samples: 1319
Correct: 623
Incorrect: 696
Accuracy: 47.23%
================================================================================
```

### 6. Evaluation Benchmarks from the Paper

According to the paper, the main evaluation benchmarks are:

| Benchmark | lighteval Task Name | Type | Purpose |
|------|----------------|------|------|
| **GSM8K** | `leaderboard|gsm8k|0` | Mathematical Reasoning | In-domain Performance |
| **MATH500** | `leaderboard|math500|0` | Advanced Mathematics | In-domain Performance |
| **LiveCodeBench** | `leaderboard|lcb|0` | Code Generation | Out-of-domain Generalization |
| **CRUXEval-O** | `leaderboard|cruxeval|0` | Code Reasoning | Out-of-domain Generalization |
| **MMLU-Pro** | `leaderboard|mmlu_pro|0` | General Knowledge | General Capability |
| **AlpacaEval** | Requires separate tool | Instruction Following | Dialogue Ability |

**Note**: AlpacaEval requires evaluation using its [official tool](https://github.com/tatsu-lab/alpaca_eval), as it needs GPT-4 as a judge.

## 📈 Experimental Results

### Paper ResultsBased on the paper, experimental results on the Qwen2.5-3B base model:

#### Math Tasks (MATH dataset training)
- **GSM8K**: Intuitor and GRPO achieve comparable performance
- **MATH500**: Intuitor and GRPO achieve comparable performance

#### Code Generation Tasks (Out-of-Domain Generalization)
- **LiveCodeBench v6**: Intuitor achieves a relative improvement of **65%** (GRPO shows no improvement)
- **CRUXEval-O**: Intuitor improves by **76%** (GRPO improves by only 44%)

#### Emergent Abilities
For the Qwen2.5-1.5B base model (original model scores 0% on LiveCodeBench):
- After training, it can generate coherent reasoning chains and well-structured code
- LiveCodeBench accuracy reaches **9.9%**

---

### Reproduction Results (GSM8K Evaluation)

Evaluated using a modified lighteval (supports `\boxed{}` format + 2048 token generation size):

#### Qwen2.5-3B Model (After Training)

```bash
lighteval accelerate "model_name=math_intuitor_model" "leaderboard|gsm8k|0"
```

| Model | Accuracy | Correct Count | Total Count | Notes |
|-------|----------|---------------|-------------|-------|
| **Qwen2.5-3B + Intuitor** | **78.09%** | 1,030 | 1,319 | Trained on MATH dataset |

**Result Analysis**:
- ✅ The trained 3B model achieves **78.09%** accuracy on GSM8K
- ✅ The model can generate complete CoT reasoning chains
- ✅ Answer format is correct (`\boxed{number}` format)

#### Qwen2.5-1.5B Model: Before and After Training

| Model | Accuracy | Correct Count | Total Count | Notes |
|-------|----------|---------------|-------------|-------|
| **Qwen2.5-1.5B Base** | **0.38%** | 5 | 1,319 | Original base model, no training |
| **Qwen2.5-1.5B + Intuitor** | **70.13%** | 925 | 1,319 | Trained on MATH dataset |

**Result Analysis**:

**Base Model (0.38%)**:
- ❌ Unable to follow instruction format
- ❌ Does not output the standard `\boxed{answer}` format
- 💡 **Key Finding**: Instruction-following ability is fundamental for reasoning models

**Trained Model (70.13%)**:
- ✅ Answer format is standardized (`\boxed{number}` format)
- ✅ Demonstrates the effectiveness of Intuitor's unsupervised reinforcement learning

**1.5B vs 3B Comparison**:
- The 3B model (78.09%) outperforms the 1.5B model (70.13%) by approximately **8 percentage points**
- Both successfully learned reasoning and format-following capabilities

---

## 🔬 Detailed Algorithm Explanation

### 0. Intuitor vs DeepSeek R1-Zero: Key Differences

Many people easily confuse Intuitor with DeepSeek R1-Zero because neither uses human-annotated reasoning processes. However, they have fundamental differences:

#### DeepSeek R1-Zero (Second Curve: RLVR)

**Training Process**:
```
Question → Model generates reasoning chain + answer → Verify answer correctness → GRPO update
                                    ↑
                          Requires ground-truth answer!
```

**Characteristics**:
- ✅ Does not require annotated reasoning processes (difference from R1)
- ❌ Still requires **ground-truth answers** to verify the final result
- ❌ Reward signal: `r = 1 if answer correct else 0` (binary reward)
- ❌ Falls under **RLVR (Reinforcement Learning from Verifiable Rewards)**
- 🎯 Training objective: Enable the model to find reasoning chains that lead to correct answers
- 📍 Representative works: DeepSeek-R1-Zero, Kimi K1.5, QwQ-32B

**Paper Description** (DeepSeek R1 Technical Report):
> "We first explore RL without supervised fine-tuning (SFT) data, termed RL from scratch (dubbed R1-Zero). Starting from Qwen base model with only a few prompt engineering trials, R1-Zero successfully developed strong reasoning capabilities comparable to R1 with SFT."

**Key Point**: The "Zero" in R1-Zero refers to zero SFT data (no need for annotated reasoning processes), but it still relies on a verifiable reward function (answer correctness).

#### Intuitor (Third Curve: Unsupervised RL)

**Training Process**:
```
Question → Model generates reasoning chain + answer → Compute self-certainty → GRPO update
                                    ↑
                      Completely requires no external verification!
```

**Characteristics**:
- ✅ Does not require annotated reasoning processes
- ✅ Does not require ground-truth answers
- ✅ Reward signal: `u = Self-Certainty(output)` (continuous, token-level)
- ✅ Falls under **Unsupervised RL**, using **Internal Feedback (RLIF)** method
- 🎯 Training objective: Enable the model to generate reasoning chains it is confident about
- 📍 Third Curve Representative Works:
  - Internal Feedback: Intuitor, Absolute Zero
  - Consistency: TTRL (plurality voting)
  - Others: Rubrics-based, Multi-agent debate, etc.

#### Detailed Comparison Table

| Dimension | DeepSeek R1-Zero | Intuitor |
|-----------|------------------|----------|
| **Curve** | Second Curve (RLVR) | Third Curve (Unsupervised RL) |
| **Specific Method** | Verifiable Reward | Internal Feedback (RLIF) |
| **Requires Ground-Truth Answer?** | ✅ Mandatory | ❌ Not required |
| **Requires Annotated Reasoning?** | ❌ Not required | ❌ Not required |
| **Reward Source** | External Verifier | Intrinsic Confidence |
| **Reward Type** | Binary (Correct/Incorrect) | Continuous (Confidence Score) |
| **Reward Granularity** | Answer Level | Token Level |
| **Training Data Requirement** | Problems with answers | Only problem descriptions |
| **Applicable Scenarios** | Verifiable tasks (math, code) | **Any task** |
| **In-Domain Performance** | Excellent (84.4% GSM8K) | Comparable (79.2% GSM8K) |
| **Out-of-Domain Generalization** | Not reported | **Strong (+65% LCB)** |

#### Why is Distinguishing These Two Important?

1. **Application Scenario Differences**
   - R1-Zero: Only applicable to tasks with definite answers (math, code, science)
   - Intuitor: Applicable to tasks **without definite answers**, such as writing, dialogue, and creative tasks

2. **Data Requirement Differences**
   - R1-Zero: Requires constructing a training set containing ground-truth answers (e.g., MATH 7,500 problems)
   - Intuitor: Can use any text as training data (even unlabeled problems)

3. **Research Significance Differences**
   - R1-Zero: Proves that reasoning models can be trained without annotated reasoning processes
   - Intuitor: Proves that reasoning ability can be improved **without any external reward**

4. **Future Potential**
   - R1-Zero: Will encounter bottlenecks when applied to domains that are difficult for humans to verify
   - Intuitor: Provides a path for AI autonomous learning, surpassing human supervision

#### Spectrum of Third Curve Methods

The third curve (Unsupervised RL) encompasses multiple implementation approaches, all sharing the commonality: **no ground-truth answers or human preference annotations are required**.

| Method Type | Representative Work | Reward Signal Source | Characteristics |
|-------------|---------------------|----------------------|-----------------|
| **Internal Feedback** | Intuitor | Self-certainty (internal confidence) | ✅ Fully unsupervised, strong generalization |
| **Internal Feedback** | Absolute Zero | Internal signal | ✅ Zero-data learning |
| **Consistency** | TTRL | Plurality voting | ⚠️ Still requires problems (no answers needed) |
| **Consistency** | Genius | Self-consistency | ⚠️ Still requires problems (no answers needed) |
| **Rule-Based Reward** | Rubrics-based | Predefined scoring rules | ⚠️ Requires manually designed rules |
| **Novelty** | Novelty-based | Exploring unknown regions | ✅ Suitable for open-ended tasks |
| **Multi-Agent** | Multi-agent Debate | Consensus among agents | ✅ Improves quality through discussion |

**Intuitor Paper's Perspective**:
> "Concurrent works like Genius, TTRL, and Absolute Zero leverage queries without labels for reinforcement learning but remain **constrained to specific task distributions**, primarily in mathematical reasoning. INTUITOR aligns with this direction but introduces a lightweight, general-purpose alternative: using self-certainty as a confidence-based intrinsic reward."

**Key Differences**:
- **R1-Zero, GRPO** (Second Curve): Require ground-truth answers to verify correctness
- **TTRL, Genius** (Third Curve): Do not require ground-truth answers, but still depend on problem distribution and consistency assumptions
- **Intuitor** (Third Curve): Entirely based on intrinsic signals, has the widest applicability and strongest generalization ability

Various third-curve methods are exploring "how to improve model capabilities without explicit reward functions," which is a key path toward general AI.

### 1. From External Supervision to Internal Feedback

#### Limitations of Traditional Methods

**RLHF (Reinforcement Learning from Human Feedback)** Optimization Objective:
```
max E[r_φ(q, o) - β·KL(π_θ || π_ref)]
```
- `r_φ(q, o)`: Reward model trained on human preference data
- Problem: Requires extensive human annotation, high cost, may introduce bias and reward hacking issues

**RLVR (Reinforcement Learning from Verifiable Rewards)** Optimization Objective:
```
max E[v(q, o) - β·KL(π_θ || π_ref)]
```
- `v(q, o)`: Verifiable reward function (e.g., answer correctness: correct=α, incorrect=0)
- Problem: Requires ground-truth answers or test cases, only applicable to specific domains, difficult to generalize across tasks

#### Unsupervised RL (Third Curve)

**General Optimization Objective**:
```
max E[u(q, o) - β·KL(π_θ || π_ref)]
```

**Core Feature**: The reward signal `u(q, o)` **does not require ground-truth answers or human annotations**

Where:
- `q`: Input query (problem)
- `o`: Model-generated output (answer)
- `π_θ`: Policy model (to be optimized)
- `π_ref`: Reference model (initial model)
- `β`: KL divergence penalty coefficient

**Implementations of `u(q, o)` for Different Methods**:
- **RLIF (Intuitor)**: `u = Self-Certainty(o|q)` — Internal confidence
- **Consistency Methods (TTRL)**: `u = IsPlurality(o)` — Whether it is the majority answer
- **Rule-Based Reward**: `u = RubricsScore(o)` — Based on predefined rules
- **Novelty**: `u = Novelty(o)` — Degree of exploration
- **Multi-Agent**: `u = ConsensusScore(o)` — Degree of consensus among agents

### 2. Self-Certainty: Intuitor's Reward Signal

Among the many possible reward signals for unsupervised RL, **Intuitor chose Self-Certainty** as its reward function `u(q, o)`.

This is an **Internal Feedback (RLIF)** method, entirely based on the model's own output distribution, requiring no external information.

#### Mathematical Definition

Self-certainty is the average KL divergence between the model's output distribution and a uniform distribution:

```
Self-Certainty(o|q) = 1/|o| · Σ(i=1 to |o|) KL(U || p_π(·|q, o<i))
                    = -1/(|o|·|V|) · Σ(i=1 to |o|) Σ(j=1 to |V|) log(|V| · p_π(j|q, o<i))
```

Where:
- `|o|`: Length of the generated sequence (number of tokens)
- `|V|`: Vocabulary size
- `U`: Uniform distribution (each token probability is 1/|V|)
- `p_π(j|q, o<i)`: Model's probability of predicting token j at position i
- `o<i`: Tokens generated before position i

#### Key Characteristics

1. **Mode-Seeking**
   - Self-Certainty uses `KL(U || p_model)`, which is a mode-seeking metric.   - In contrast, entropy (or reverse KL) is mode-covering.
   - Mode-seeking encourages the model to be more confident in its answers rather than covering all possibilities.

2. **Insensitive to Length Bias**
   - Compared to perplexity or entropy, self-certainty is less prone to bias from long texts.
   - This makes it more suitable as a reward signal for reinforcement learning.

3. **Token-Level Confidence**
   - Rewards the entire **generation trajectory**, not just the final result.
   - Each token's generation contributes to the reward.
   - This is a key reason for Intuitor's strong generalization ability.

#### Intuitive Understanding

- **High Self-Certainty**: The model is very confident in its prediction for each token (sharp distribution, far from uniform).
  - Example: When generating "42", the model assigns high probability to both "4" and "2".
- **Low Self-Certainty**: The model is uncertain, and the output distribution is close to uniform (each token's probability is similar).
  - Example: The model wavers between multiple candidate words.

### 3. Intuitor Implementation: Based on GRPO

#### GRPO Algorithm Core

Intuitor uses **Group Relative Policy Optimization (GRPO)** as its policy optimization algorithm:

```
J_GRPO(θ) = E[1/G · Σ(i=1 to G) 1/|o_i| · Σ(t=1 to |o_i|) 
            min(c_i,t(θ)·Â_i,t, clip(c_i,t(θ), 1-ε, 1+ε)·Â_i,t) 
            - β·D_KL(π_θ || π_ref)]
```

Where:
- `G`: Number of candidate answers sampled per question (default 7)
- `c_i,t(θ) = π_θ(o_i,t | q, o_i,<t) / π_θ_old(o_i,t | q, o_i,<t)`: Importance sampling ratio
- `Â_i,t`: Advantage function
- `clip(c, 1-ε, 1+ε)`: Clipping function to prevent overly large policy updates

#### Intuitor's Key Innovation

**Replacing external rewards with self-certainty**:

```python
# 1. For each question q, sample G candidate answers
outputs = [o_1, o_2, ..., o_G]

# 2. Calculate the self-certainty score for each answer
u_i = Self-Certainty(o_i | q)  # Intrinsic reward, no external verification needed!

# 3. Calculate relative advantage within the group (normalization)
Â_i,t = (u_i - mean([u_1, ..., u_G])) / std([u_1, ..., u_G])

# 4. Update policy using GRPO
# The policy will tend to generate outputs with high self-certainty
```

#### Comparison with GRPO

| Feature | GRPO | Intuitor |
|---------|------|----------|
| **Reward Source** | External verifier (gold standard answer) | Intrinsic signal (self-certainty) |
| **Requires Supervision** | ✅ Requires standard answers | ❌ Completely unsupervised |
| **Reward Granularity** | Result level (answer correctness) | Token level (generation trajectory) |
| **In-Domain Performance** | Excellent | Comparable (slightly lower by 2-3%) |
| **Out-of-Domain Generalization** | Weak (even negative transfer) | **Strong (+65% on LCB)** |
| **Applicable Scenarios** | Tasks with standard answers | Any task (only needs a prompt) |

### 4. Why Does Intuitor Generalize Better?

#### Reason 1: Rewarding the Generation Process, Not the Result

- **GRPO**: `v(q, o) = 1 if answer is correct else 0`
  - Only cares about the final answer, regardless of the reasoning process.
  - The model might memorize specific patterns but cannot transfer them.

- **Intuitor**: `u(q, o) = avg(Self-Certainty per token)`
  - Rewards the entire reasoning chain, encouraging clear and confident expression.
  - What is learned is "how to reason clearly," which can transfer to new tasks.

#### Reason 2: Encouraging Structured Reasoning

The paper observes that models trained with Intuitor spontaneously:
1. Add natural language reasoning before code (even if the prompt doesn't require it).
2. Generate longer, more detailed reasoning chains.
3. Reason first, then summarize outside of JSON format (see Figure 5 of the paper).

**Why?** Because detailed reasoning steps make the model itself more confident (higher self-certainty), thereby earning a higher reward.

#### Reason 3: Online Self-Certainty Prevents Reward Hacking

- **Offline** Scorer (fixed model): Easily exploitable (see Figure 7 of the paper).
  - The model learns to "trick" the fixed scorer, generating high-scoring but meaningless outputs.
  
- **Online** Scorer (Intuitor): The scoring criterion co-evolves with the policy model.
  - The model cannot "trick" itself; it must genuinely improve reasoning quality.
  - Paper experiments show: Models trained with Intuitor are more reliable at distinguishing correct/incorrect answers (Figure 8).

### 5. Key Hyperparameters

| Parameter | 1.5B/3B Model | 7B/14B Model | Function |
|-----------|---------------|---------------|----------|
| **β (KL penalty)** | 0.0005 | 0.01 | Prevents excessive deviation from the initial model |
| **Group Size (G)** | 7 | 14 | Number of candidate answers per question |
| **Learning Rate** | 3×10⁻⁶ | 1×10⁻⁶ | Step size for policy updates |
| **Batch Size** | 128 | 64 | Number of questions per update |

**Important Finding** (Table 3 of the paper):
- KL penalty is **extremely sensitive** for out-of-domain generalization.
- β=0 (no KL penalty): Good in-domain, but poor out-of-domain.
- β=0.005: Best balance between in-domain and out-of-domain.
- β=0.01: Slightly lower out-of-domain, but still stronger than GRPO.

### 6. Core Insight: Why Does Optimizing Confidence Improve Reasoning?

This is Intuitor's most surprising finding: **Simply by optimizing the model's confidence in its own outputs, reasoning ability can be significantly improved.**

#### Theoretical Explanation

1. **Confidence ≈ Internal Consistency**
   - When the model is confident in an answer, it means its internal representations are consistent and coherent.
   - By optimizing confidence, the model learns to build more coherent reasoning chains.

2. **Emergence of Long-Chain Reasoning**
   - Detailed reasoning steps allow the model to "see" its own thought process.
   - If each step is clear, overall confidence is high.
   - Result: The model spontaneously generates longer, more detailed reasoning (see Figures 3, 6 of the paper).

3. **Self-Explanation Loop**
   ```
   Model uncertain → Generates detailed reasoning → Understands better → Confidence increases → Receives reward
   ```
   This forms a positive feedback loop, prompting the model to learn to "explain to itself."

4. **From Specific to General**
   - GRPO learns "the answer pattern for this type of math problem" (specific).
   - Intuitor learns "how to clearly express reasoning" (general).
   - The latter naturally transfers to other domains like code and text.

#### Empirical Evidence

The paper validates this mechanism through several experiments:

1. **Response Length Evolution** (Figure 3)
   - Qwen2.5-1.5B: Length decreases early in training (removing gibberish), then stabilizes.
   - Qwen2.5-3B: Continuously increases during training, from 600 → 850 tokens.
   - Indicates the model learns to boost confidence through detailed reasoning.

2. **Emergence of Reasoning in Code Generation** (Figure 6)
   - Step 0-10: Invalid code → Step 20-30: Valid code (no reasoning).
   - Step 40-50: Valid code + detailed reasoning + explanation.
   - Reasoning emerges **spontaneously**, even though the prompt does not require it!

3. **Mann-Whitney U Test** (Figure 8)
   - The Intuitor model shows the largest difference in self-certainty scores when distinguishing correct/incorrect answers.
   - p-value = 1.7e-15, effect size r = 0.35.
   - Indicates the model has learned more reliable self-assessment.

#### Philosophical and Practical Significance

Intuitor reveals a profound insight:
> **Intelligent systems do not need external rewards; they can improve themselves by optimizing internal consistency (confidence).**

This is analogous to human learning:
- When solving difficult problems, we often "explain to ourselves" to deepen understanding.
- When we can clearly articulate an idea, it usually means we truly understand it.
- Intuitor formalizes this mechanism into a reinforcement learning algorithm.

**Key Observations**:
- RLVR (the second curve) has pushed mathematical reasoning to its limits (R1, o1).
- However, this covers only a **small fraction** of AI applications.
- Truly general AI needs to handle tasks **without clear right or wrong answers**.
- Intuitor provides a training method for these tasks.

**Future Outlook**:
As model capabilities surpass human ones (e.g., scientific research, strategic decision-making), it will become increasingly difficult to provide reliable external rewards. At that point, **unsupervised RL (the third curve)** may be the only viable path for improvement.

#### Limitations and Future Directions

1. **Sensitive to Prompts**
   - Self-certainty is the sole heuristic signal.
   - Prompt design significantly impacts performance.
   - Future: More robust prompt design or adaptive prompting.

2. **Requires Online Updates**
   - Purely offline training can lead to reward hacking (Figure 7).
   - Future: Hybrid online-offline training strategies.

3. **Combining with External Rewards**
   - This paper uses a single reward for comparison purposes.
   - In practice, rewards can be combined: Self-Certainty + Correctness + Format Compliance.

## 📝 Citation

If you use Intuitor in your research, please cite the following paper:

```bibtex
@article{zhao2025intuitor,
  title={Learning to Reason without External Rewards},
  author={Zhao, Xuandong and Kang, Zhewei and Feng, Aosong and Levine, Sergey and Song, Dawn},
  journal={arXiv preprint arXiv:2505.19590},
  year={2025}
}
```

## 📄 License

This project is open-sourced under the Apache 2.0 license.

## 🙏 Acknowledgements

- [VERL](https://github.com/volcengine/verl): High-performance RL training framework
- [GSM8K-eval](https://github.com/Guangxuan-Xiao/GSM8K-eval): Math reasoning evaluation tool
- [MATH Dataset](https://github.com/hendrycks/math): Math problem dataset

## 📮 Contact

For questions or suggestions, please reach out via:
- GitHub Issues: [https://github.com/sunblaze-ucb/Intuitor/issues](https://github.com/sunblaze-ucb/Intuitor/issues)
- Paper Authors: Xuandong Zhao (xuandongzhao@berkeley.edu), Zhewei Kang (waynekang@berkeley.edu)

---

**Note**: This README focuses on the verl-intuitor implementation. For the open-r1-intuitor implementation, please refer to the original repository.
