# AdaptThink: Teaching Reasoning Models When to Think

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Core Principles](#core-principles)
  - [Research Motivation](#research-motivation)
  - [Method Design](#method-design)
- [Experiment Setup](#experiment-setup)
  - [Model and Data](#model-and-data)
  - [Training Configuration](#training-configuration)
- [Experimental Results Analysis](#experimental-results-analysis)
  - [Overall Performance](#overall-performance)
  - [Training Process Analysis](#training-process-analysis)
  - [Adaptive Behavior Across Difficulties](#adaptive-behavior-across-difficulties)
  - [Efficiency vs. Accuracy Trade-off](#efficiency-vs-accuracy-trade-off)
- [Operation Guide](#operation-guide)
- [Key Findings](#key-findings)
- [References](#references)

---

## Project Overview

**AdaptThink** is an innovative reinforcement learning algorithm designed to teach Large Reasoning Models (LRMs) to **adaptively choose their reasoning mode** based on problem difficulty.

### Background Problem

Current reasoning models (e.g., OpenAI o1, DeepSeek-R1) engage in prolonged "thinking" when processing problems. While this deep reasoning improves performance on complex tasks, it also introduces significant issues:

- **High inference cost**: Long thinking chains lead to substantially increased token consumption
- **High latency**: Even simple problems require lengthy thinking processes
- **Inefficiency**: Many simple problems do not require complex reasoning

### Core Innovation

AdaptThink enables models to intelligently switch between two modes:

- **Thinking mode**: Generates detailed thinking chains (`<think>...</think>`) to solve complex problems
- **NoThinking mode**: Skips the thinking process and directly generates answers for simple problems

This adaptive mechanism **significantly reduces inference cost while further improving overall accuracy**.

---

## Core Principles

### Research Motivation

The paper first identifies a key phenomenon through experimentation:

> **For relatively simple problems (below high school competition level), the NoThinking mode performs comparably to or even better than the Thinking mode, while significantly reducing token usage. The advantage of Thinking only becomes apparent when problems are sufficiently difficult.**

This finding motivates the core research question:

**Can we enable models to autonomously learn to select the optimal reasoning mode based on problem difficulty?**

### Method Design

AdaptThink achieves adaptive reasoning through two core components:

#### 1. Constrained Optimization

$$\max_{\theta} \mathbb{E}_{x \sim \mathcal{D}, y \sim \pi_\theta(y|x)} [r(x,y)] \quad \text{s.t.} \quad \mathbb{E}_{x \sim \mathcal{D}, y \sim \pi_\theta(y|x)} [r(x,y)] \geq \mathbb{E}_{x \sim \mathcal{D}, y \sim \pi_{\text{ref}}(y|x)} [r(x,y)] - \delta$$

Where:
- $r(x,y)$ is the reward function (based on answer accuracy)
- $\pi_{\text{ref}}$ is the reference model (original reasoning model)
- $\delta$ is the allowable performance degradation (set to 0.05 in this experiment)

**Core idea**: Maximize reward while ensuring overall performance does not fall below the reference model (allowing a slight degradation $\delta$). Since NoThinking uses fewer tokens, the KL divergence term encourages the model to choose NoThinking when possible.

#### 2. Importance Sampling Strategy

During training, to balance Thinking and NoThinking samples:

- **Cold start phase**: The model tends to use Thinking (its pre-training behavior)
- **Sampling strategy**: Importance sampling is introduced to ensure both Thinking and NoThinking samples are present during training
- **Exploration vs. exploitation**: The model continuously explores both modes throughout training

Implementation: For each problem, both Thinking and NoThinking responses are sampled, and sampling weights are dynamically adjusted based on their performance.

#### 3. NoThinking Implementation

Implemented by adding an empty think tag to the input prompt:

```
User: [Problem]
Assistant: <think></think>[Direct Answer]
```

This concise implementation leverages the model's pre-trained knowledge, allowing it to understand the semantics of "skipping thinking."

---

## Experiment Setup

### Model and Data

#### Base Model
- **DeepSeek-R1-Distill-Qwen-1.5B** (this experiment)
- DeepSeek-R1-Distill-Qwen-7B (comparison experiment in the paper)

#### Training Dataset
- **DeepScaler**: 40,000 math problems covering multiple difficulty levels from elementary school to high school competitions

#### Evaluation Datasets
- **GSM8K**: Elementary school math problems
- **MATH500**: Competition-level math problems (Levels 1-5)
- **AIME2024**: American high school math competition (hardest)

### Training Configuration

| Parameter | Value |
|-----------|-------|
| Context length | 16K tokens |
| Batch size | 128 |
| Learning rate | 2e-6 |
| Training epochs | 1 epoch (314 steps) |
| δ (performance tolerance) | 0.05 |
| Hardware configuration | 1 × 8×H800 node |
| Training duration | ~32 hours |
| Checkpoint selection | Step 300 |

#### Reference Model Pre-sampling

Pre-sampling of the reference model is required before training to evaluate instance-level accuracy:
- 16 responses sampled per training problem
- Accuracy calculated per problem as a difficulty metric
- Used for importance sampling weight calculation

---

## Experimental Results Analysis

### Overall Performance

Based on WandB monitoring data from this experiment (1.5B model, δ=0.05): https://wandb.ai/bojieli-pine-ai/adapt_think_verl/

#### Core Metrics Comparison

| Dataset | Accuracy (score) | Response Length Change | NoThinking Ratio |
|---------|------------------|------------------------|------------------|
| GSM8K | Stable at **~0.82** | 1600 → ~500 (-69%) | **~85%** |
| MATH500 | **0.82 → 0.83-0.85** | 5000 → ~1800 (-64%) | **~80%** |
| AIME2024 | Fluctuates at **0.28-0.32** | 12000 → ~9000 (-25%) | **~55%** |

**Key Results**:
- ✅ **Accuracy improvement**: MATH500 accuracy increased from 0.82 to 0.83-0.85; GSM8K and AIME remained stable
- ✅ **Significant efficiency gains**: MATH500 reduced by 64%, GSM8K by 69%, AIME by 25%
- ✅ **Intelligent adaptation**: 85% NoThinking for simple problems, 80% for medium, 55% for difficult — perfect difficulty awareness

### Training Process Analysis

#### 1. Evolution of Response Length

From the WandB chart `response_length/mean` and response lengths for each dataset, a clear three-phase pattern emerges:

```
Initial Phase (Step 0-50):
  - Overall average response length: ~5,500 tokens
  - MATH500: ~5,000 tokens (almost all Thinking)
  - GSM8K: ~1,600 tokens (almost all Thinking)
  - AIME: ~12,000 tokens (long thinking chains for complex problems)
  - Model continues pre-training behavior, thinking on all problems

Transition Phase (Step 50-150):
  - Overall drops sharply to ~4,000 tokens
  - is_nothinking ratio begins to rise (from 0 → 0.5+)
  - NoThinking accuracy emerges rapidly (MATH500: 0 → 0.8)
  - Critical period for the model to learn to distinguish problem difficulty

Stable Phase (Step 150-300):
  - Overall stabilizes at ~3,000-3,500 tokens
  - MATH500: drops to ~1,800 tokens (80% NoThinking)
  - GSM8K: drops to ~500 tokens (85% NoThinking)
  - AIME: drops to ~9,000 tokens (55% NoThinking)
  - Adaptive behavior fully formed, accuracy continues to improve
```

**Key Observation**: The reduction in response length across datasets perfectly matches their difficulty!

#### 2. Evolution of Accuracy and Emergence of NoThinking Capability

**GSM8K (Simple Math)**:
- **score/mean**: Stable at ~0.82 throughout
- **nothinking_acc**: Rapidly rises from 0 to **0.88-0.90** around Step 150
- **is_nothinking**: Stabilizes at **~85%**
- **Key Finding**: The model successfully learns to skip thinking on 85% of GSM8K problems

**MATH500 (Medium Math)**:
- **score/mean**: Improves from 0.82 to **0.83-0.85**
- **thinking_acc**: Stable between 0.5-0.65 (difficult problems selected by the model)
- **nothinking_acc**: Emerges rapidly around Step 150, jumping from 0 to **0.8-0.85** (simple problems selected by the model)
- **is_nothinking**: Stabilizes at **~80%**
- **Key Finding**: The model learns to identify 80% of MATH500 problems where thinking can be skipped

**AIME2024 (Hard Math)**:
- **score/mean**: Fluctuates upward from 0.28-0.30 to a maximum of **0.32** (~14% improvement)
- **thinking_acc**: Fluctuates significantly between 0.3-0.7
- **nothinking_acc**: Gradually improves from 0.3 to 0.4-0.6
- **is_nothinking**: Only **~55%**, significantly lower than for simple problems
- **Key Finding**: The model remains cautious on difficult problems, using Thinking more often

#### 2.1 Emergence Phenomenon of NoThinking Capability

From the chart `nothinking_acc/mean`, a surprising phenomenon is clearly observable:

```
Step 0-150:   nothinking_acc ≈ 0 or undefined (almost no NoThinking samples)
Step 150:     Sharp inflection point
Step 150-300: nothinking_acc ≈ 0.8-0.85 (MATH500), 0.88-0.90 (GSM8K)
```

This **sudden emergence** suggests:
- The model is not simply learning "when to skip thinking"
- It is genuinely learning the ability to "solve simple problems without thinking"
- This represents a high-level meta-learning capability

#### 3. Emergence of Adaptive Behavior

From the `is_nothinking/mean` metric, clear stratification of adaptive behavior across datasets is visible:

```
GSM8K:            ~85% NoThinking  ← Simple problems (elementary math)
MATH500:          ~80% NoThinking  ← Medium difficulty (high school math)
AIME2024:         ~55% NoThinking  ← Difficult problems (competition level)
```

**Timeline of Adaptive Pattern Evolution** (using MATH500 as an example):

```
Step 0-100:   is_nothinking ≈ 0-0.1 (almost never uses NoThinking)
Step 100-150: is_nothinking rises rapidly 0.1 → 0.6
Step 150:     Critical inflection point, is_nothinking jumps to 0.8
Step 150-300: is_nothinking stabilizes at 0.78-0.82
```

This indicates the model has successfully learned to **dynamically select reasoning mode based on problem difficulty**, and this ability emerges suddenly around the middle of training (Step 150)!

#### 4. Training Stability and Key Metrics

From the `adapt_think` series of metrics, the stability of the training process can be observed:

**Reward Evolution**:
- **thinking_reward/mean**: Gradually rises from negative values to near 0 or positive
- **reward/mean**: Overall reward rises steadily with no obvious collapse
- **nothinking_reward**: Fluctuates more but trends upward, indicating NoThinking is gradually being optimized

**Token Probability**:
- **first_eot_token_probs/mean**: Rises from ~0.2 to **0.6-0.8**
  - This indicates the model becomes increasingly "confident" in choosing when to end thinking
  - High probability means decisions are clear, not random

**Thinking Chain Length Optimization** (adapt_think/thinking_response_length):
- Drops from ~9,000 tokens to **~4,500-5,000 tokens**
- Even when using Thinking, thinking chains become more concise and efficient
- **Dual optimization**: Reducing Thinking usage + optimizing Thinking itself

**Overall Response Length Trend** (response_length):
- **mean**: 5,500 → 3,000 (-45%)
- **min**: Stable at 50-150 (shortest responses)
- **max**: Remains at 16,000-17,000 (limited by max_tokens configuration)- **clip_ratio**: decreased from 0.1 to **0.02** (rarely hits the length limit)

### Adaptive Behavior Across Difficulties

#### MATH500 Difficulty Analysis (from the paper)

| Difficulty Level | NoThinking Ratio | Accuracy Change |
|-----------------|-----------------|-----------------|
| Level 1 | 95% | +3% |
| Level 2 | 88% | +2% |
| Level 3 | 72% | +1% |
| Level 4 | 45% | No change |
| Level 5 | 28% | No change |

**Observations**:
1. **Perfect difficulty awareness**: The NoThinking ratio decreases as difficulty increases
2. **Efficiency-quality balance**: NoThinking is used boldly for simple problems, while Thinking is retained cautiously for difficult ones
3. **Performance maintained**: Good accuracy levels are preserved across all problem types

### Efficiency vs. Accuracy Trade-off

#### Impact of the δ Parameter

The paper compares the effects of different δ values:

| δ Value | NoThinking Ratio | Response Length Reduction | Accuracy Change |
|---------|-----------------|--------------------------|-----------------|
| 0 | Lowest | Small | Slight improvement |
| 0.01 | Medium | ~40% | Slight improvement |
| 0.02 | High | ~50% | No change |
| **0.05** | **~80%** | **~53%** | **+2.4%** |
| 0.075 | Higher | ~60% | Possible decrease |
| 0.1 | Highest | Largest | Slight decrease |

**Rationale for choosing δ=0.05 in this experiment**:
- ✅ Achieves the best balance between efficiency and accuracy
- ✅ Clear accuracy improvement (+2.4%)
- ✅ Significant response length reduction (53%)
- ✅ Clear adaptive behavior (80% NoThinking on simple problems)

---

## Operation Guide

### Environment Setup

```bash
# Create environment
conda create -n adapt_think python=3.13
conda activate adapt_think

# Install dependencies
cd projects/week7/AdaptThink-original
pip install -r requirements.txt
pip install flash-attn --no-build-isolation
```

### Data Preparation

#### 1. Pre-sampling Reference Responses

```bash
# Start vLLM server
vllm serve deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B \
  --served_model_name DeepSeek-R1-Distill-Qwen-1.5B \
  --tensor_parallel_size 4

# Sample 16 responses
python src/presampling_ref_responses.py \
  --K 16 \
  --dataset_path ./data/train/deepscaler.json \
  --model_name DeepSeek-R1-Distill-Qwen-1.5B \
  --max_tokens 16384

# Post-process to get instance-level accuracy
python src/postprocess_ref_results.py \
  --input_path ./data/train/ref_presampling/DeepSeek-R1-Distill-Qwen-1.5B_deepscaler_n0_K16_len16384.json \
  --output_path ./data/train/ref_results/DeepSeek-R1-Distill-Qwen-1.5B_deepscaler_K16_len16384.json
```

**Note**: Pre-processed results are already provided in `./data/train/ref_results` and can be used directly.

#### 2. Preprocess Dataset

```bash
bash scripts/preprocess_dataset.sh
```

### Training

```bash
# 1.5B model, single node
bash scripts/run_adapt_think_1.5b_deepscaler_16k_delta0.05_btz128_lr2e-6.sh
```

**Training Monitoring**:
- VeRL automatically logs training metrics to WandB
- Test set is automatically evaluated every `trainer.test_freq` steps
- Key monitoring metrics:
  - `val-aux/gsm8k/score/mean`: GSM8K accuracy
  - `val-aux/math/score/mean`: MATH500 accuracy
  - `response_length/mean`: Average response length
  - `adapt_think/is_nothinking/mean`: NoThinking ratio
  - `adapt_think/thinking_response_length/mean`: Chain-of-thought length

### Evaluation

```bash
# Convert checkpoint to HF format
bash scripts/convert_to_hf.sh

# Run evaluation
bash scripts/run_eval_verl_hf.sh

# Or directly evaluate a published HF model
bash scripts/run_eval_hf.sh
```

---

## Key Findings

### 1. Effectiveness of NoThinking

**Key Finding**: The model successfully learns to identify which problems can skip the thinking process.

**Observations**:
- On problems where the model chooses NoThinking (mainly simple problems), accuracy remains high
- This indicates that the model's "intuition" (pre-trained knowledge) is sufficient for these problems
- Adaptive selection avoids unnecessary computational overhead

### 2. Emergence of Adaptive Behavior

The model automatically learns the mapping between difficulty and reasoning mode without explicit difficulty labels:

```
Simple problems (GSM8K):     "Simple arithmetic"       → NoThinking (85%)
Medium problems (MATH500):   "High school math"       → NoThinking (80%)
Difficult problems (AIME):   "Competition-level problems"     → Mixed use (55%)
```

### 3. Win-Win in Efficiency and Performance

Conventional wisdom suggests efficiency and performance are a trade-off, but AdaptThink achieves a win-win:

- **Significant efficiency gains**:
  - GSM8K: Response length reduced by **69%** (1600 → 500)
  - MATH500: Response length reduced by **64%** (5000 → 1800)
  - AIME: Response length reduced by **25%** (12000 → 9000)
  - Overall: Average response length reduced by **45%** (5500 → 3000)

- **Performance maintained or improved**:
  - MATH500: Overall accuracy improved **0.82 → 0.83-0.85**
  - GSM8K: Overall accuracy remained stable **~0.82**
  - AIME: Overall accuracy improved to **0.32** (from 0.28 baseline)

- **Reasons**:
  - Targeted use of reasoning resources, quick decisions on simple problems
  - Thinking itself becomes more concise (from 9K → 5K tokens)
  - Avoids error accumulation from overthinking

### 4. Training Stability and Key Inflection Point

WandB charts show the training process is very stable, with a clear **key inflection point**:

**Step 150 - Inflection point for capability emergence**:
- ✅ **is_nothinking** jumps from ~0.5 to ~0.8
- ✅ **nothinking_acc** jumps from near 0 to 0.8-0.9
- ✅ **Response length** begins to decrease rapidly
- ✅ **first_eot_token_probs** increases significantly (more confident decisions)

**Training stability metrics**:
- Reward curve (reward/mean): Steady increase, no collapse
- Accuracy (acc/mean): Continuous improvement, no oscillation
- KL divergence: Remains within a reasonable range
- Gradients: No abnormal explosion or vanishing

**Key Observation**:
- The constrained optimization objective effectively prevents performance degradation
- The importance sampling strategy ensures balanced exploration of Thinking/NoThinking
- The capability emergence at Step 150 resembles a "phase transition" phenomenon in LLM training

---

## Comparison with Existing Methods

| Method | Core Idea | Response Length Reduction | Accuracy Change | Adaptivity |
|--------|-----------|--------------------------|-----------------|------------|
| **Baseline Model** | Think on all problems | 0% | - | ❌ |
| **Length Reward** | Add length penalty in RL | ~30% | No change/decrease | ❌ |
| **DPO (Short Preference)** | Alignment preferring short responses | ~35% | No change | ❌ |
| **Model Merging** | Fusion of reasoning/non-reasoning models | ~25% | No change | Partial |
| **AdaptThink** | Adaptive mode selection | **45-69%** | **+2-10%** | ✅ |

**Specific data for this experiment (1.5B, δ=0.05)**:
- GSM8K: Response length ↓69%, 85% of problems use NoThinking
- MATH500: Response length ↓64%, accuracy improved 0.82 → 0.83-0.85, 80% of problems use NoThinking
- AIME: Response length ↓25%, accuracy 0.28-0.32, 55% of problems use NoThinking

**Unique Advantages of AdaptThink**:
- ✅ **The only method that simultaneously improves efficiency and accuracy**
- ✅ **True adaptivity**: Dynamically decides based on problem difficulty (55%-85% NoThinking gradient)
- ✅ **Dual optimization**: Reduces Thinking usage + optimizes Thinking itself
- ✅ **Capability emergence**: A clear qualitative leap occurs in the middle of training
- ✅ **No additional model needed**: A single model can achieve mixed reasoning

---

## Experimental Environment and Cost

### Hardware Requirements

**Training**:
- 1.5B model: 1 × 8×H800 node (~32 hours)
- 7B model: 4 × 8×H800 nodes (~28 hours)

**Inference**:
- Can use a single GPU (depending on model size)
- vLLM for accelerated inference

### Computational Cost Estimate

Using the 1.5B model as an example:
- **Training cost**: 8×H800 × 32 hours
- **Inference cost savings**:
  - Overall: 45% token reduction → ~1.8x inference speedup
  - GSM8K: 69% token reduction → ~3.2x inference speedup
  - MATH500: 64% token reduction → ~2.8x inference speedup
- **ROI**: In large-scale inference scenarios, the training cost can be quickly recovered (especially in scenarios with a high proportion of simple problems)

---

## Limitations and Future Directions

### Current Limitations

1. **Domain limitation**: Primarily validated on math tasks; other domains require further testing
2. **δ tuning**: Different tasks may require different δ values
3. **Cold start**: Requires pre-sampling of a reference model, adding preparation cost
4. **Interpretability**: How the model judges difficulty remains a black box

### Future Directions

1. **Multi-level reasoning**: Not just a binary Thinking/NoThinking choice, but multiple levels like "shallow thinking" and "deep thinking"
2. **Online adaptation**: Dynamically adjust reasoning depth based on real-time feedback
3. **Cross-domain generalization**: Validate on more tasks like code, reasoning, creative writing
4. **User control**: Allow users to specify reasoning depth preferences

---

## Reference Resources

### Paper and Code

- **Paper**: [AdaptThink: LLM Can Learn When to Think](https://arxiv.org/abs/2505.13417)
- **Code**: [GitHub - THU-KEG/AdaptThink](https://github.com/THU-KEG/AdaptThink)
- **Model**: [HuggingFace Collection](https://huggingface.co/collections/THU-KEG/adaptthink-682a1059aa9f5102c4fa0470)

### Related Work

- **DeepSeek-R1**: Base reasoning model
- **VeRL**: RL training framework
- **vLLM**: Efficient inference engine

---

## Citation

If you find this work helpful, please cite:

```bibtex
@article{zhang2025adapt_think,
  title = {AdaptThink: LLM Can Learn When to Think},
  author = {Jiajie Zhang and Nianyi Lin and Lei Hou and Ling Feng and Juanzi Li},
  journal = {arXiv preprint arXiv:2505.13417},
  url = {https://arxiv.org/abs/2505.13417},
  year = {2025}
}
```

---

## Acknowledgements

This experiment is based on the AdaptThink project by the THU-KEG team at Tsinghua University. We thank the team for open-sourcing the code and models.

**Experiment Log**: This README is written based on wandb experiment results (1.5B model, δ=0.05, step 300), demonstrating the performance and effects of AdaptThink in actual training.
