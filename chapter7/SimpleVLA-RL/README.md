## Scaling Vision-Language-Action Model Training via Reinforcement Learning

**Project URL**: [https://github.com/PRIME-RL/SimpleVLA-RL/](https://github.com/PRIME-RL/SimpleVLA-RL/)

**SimpleVLA-RL** Overview. SimpleVLA-RL is an efficient VLA reinforcement learning framework that improves long-horizon planning under data-scarce conditions, outperforms supervised fine-tuning (SFT) in both simulated and real-world tasks, reveals the novel "pushcut" action phenomenon, and enhances generalization across space, objects, and goals.

---

# 📑 Table of Contents

- [🎉 Latest News](#-latest-news)
- [📖 Project Overview](#-project-overview)
  - [Research Background](#research-background)
  - [Core Innovations](#core-innovations)
  - [Technical Architecture](#technical-architecture)
- [🔑 Three Key Techniques](#-three-key-techniques)
- [📃 Main Experimental Results](#-main-experimental-results)
- [✨ Quick Start](#-quick-start)
- [📊 Training Process Details](#-training-process-details)
- [🔍 Important Concept Explanations](#-important-concept-explanations)
- [⚠️ Notes](#️-notes)
- [🌻 Acknowledgments](#-acknowledgments)
- [📨 Contact](#-contact)
- [📝 TODO](#-todo)
- [🎈 Citation](#-citation)

---

# 🎉 Latest News

- **[2025-10-01]** **SimpleVLA-RL** now supports the RoboTwin2.0 benchmark. Welcome to try it out!
- **[2025-09-12]** **SimpleVLA-RL** paper officially released! See details: [Paper Link](https://arxiv.org/abs/2509.09674)
- **[2025-05-27]** Released the complete **SimpleVLA-RL** code.

---

# 📖 Project Overview

## Research Background

Vision-Language-Action (VLA) models have emerged as a powerful paradigm in robotic manipulation, capable of unifying visual perception, language understanding, and action generation. However, the current development of VLA models faces two core challenges:

### Challenge 1: Data Scarcity and High Cost

Traditional VLA training heavily relies on large-scale human-operated robot trajectory data for supervised fine-tuning (SFT). The collection of this data suffers from the following issues:
- **High acquisition cost**: Requires carefully designed experimental scenarios, diverse manipulation objects, and skilled operators
- **Limited data scale**: The number of human demonstrations is far from sufficient for large-scale training needs
- **Insufficient diversity**: Human demonstrations tend to concentrate on specific manipulation patterns, lacking adequate exploration

### Challenge 2: Insufficient Generalization

VLA models trained on limited, scenario-specific data show significant performance degradation when facing:
- Unseen tasks and environments
- Long-horizon compositional tasks
- Real-world scenarios with distribution shifts

### Inspiration: Drawing from Large Language Model Reinforcement Learning

Recent breakthroughs in large reasoning models (e.g., DeepSeek-R1) demonstrate that reinforcement learning (RL), even when relying solely on outcome rewards, can significantly enhance a model's step-by-step reasoning ability. This naturally raises the question:

**Can RL similarly enhance the ability of VLA models to generate precise actions step by step?**

## Core Innovations

SimpleVLA-RL is an efficient reinforcement learning framework specifically designed for VLA models, featuring the following innovations:

### 1. **Using Only Outcome Rewards**
- No need to manually design process rewards for each sub-action
- Uses only binary task success/failure signals (0/1)
- Inspired by the successful experience of LLM reinforcement learning (DeepSeek-R1)
- Greatly enhances the scalability of the method

### 2. **Three Exploration Enhancement Strategies**
Based on the latest LLM RL research, three key technical enhancements are introduced:
- **Dynamic Sampling**: Filters out all-success/all-failure sample groups to ensure stable gradients
- **Clip Higher**: Asymmetric PPO clipping range to encourage bolder exploration
- **Higher Rollout Temperature**: Generates diverse trajectories to discover new strategies

The combination of these three can achieve approximately **30%** improvement over the baseline within 300 training steps!

### 3. **Discovery of Novel Action Patterns**
The "Pushcut" phenomenon emerges during training:
- The SFT model only learns the "grasp-lift-move" pattern
- After RL training, the model autonomously discovers the "push-slide" strategy
- **These action patterns never appeared in the training data!**
- Proves that RL can surpass human demonstrations to discover optimal strategies

## Technical Architecture

SimpleVLA-RL is built on the following technology stack:
- **Base Framework**: [veRL](https://github.com/volcengine/verl) - Volcengine LLM reinforcement learning framework
- **VLA Model**: [OpenVLA-OFT](https://github.com/moojink/openvla-oft) - 7B parameter open-source VLA model
- **Simulation Environments**:
  - [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO) - Long-horizon manipulation benchmark
  - [RoboTwin2.0](https://github.com/RoboTwin-Platform/RoboTwin) - Dual-arm manipulation benchmark
- **RL Algorithm**: Group Relative Policy Optimization (GRPO) + Proximal Policy Optimization (PPO)

---

# 🔑 Three Key Techniques

## Technique 1: Dynamic Sampling

### Problem
All-success or all-failure sample groups have zero advantage variance, leading to unstable gradients and inefficient training.

### Solution
Only retain sample groups with mixed results (partial success/partial failure) for training:

```python
# Mathematical expression (Paper Formula 10)
0 < |{trajectory_i | is_success(trajectory_i)}| < G

# Implementation code
data.accuracy_lower_bound=0.1  # Exclude all-failure groups (0%)
data.accuracy_upper_bound=0.9  # Exclude all-success groups (100%)
```

### Effect
- Ensures non-zero advantage, providing meaningful learning signals
- Naturally forms a curriculum learning process, focusing on tasks of appropriate difficulty
- Achieves approximately **~15%** improvement over baseline (Paper Figure 3a)

---

## Technique 2: Clip Higher

### Problem
Standard PPO's symmetric clipping `[0.8, 1.2]` limits the probability increase of low-probability actions, suppressing exploration.

### Solution
Adopt an asymmetric clipping range `[0.8, 1.28]`:

```bash
actor_rollout_ref.actor.clip_ratio_low=0.2   # Lower bound 1-0.2 = 0.8
actor_rollout_ref.actor.clip_ratio_high=0.28  # Upper bound 1+0.28 = 1.28
```

### Effect
- Allows low-probability actions greater room for probability increase
- Encourages exploration of new action patterns
- Achieves approximately **~10%** improvement over baseline (Paper Figure 3b)
- Inspired by DAPO (Yu et al., 2025)

---

## Technique 3: Higher Rollout Temperature

### Problem
Low temperature (1.0) leads to deterministic, repetitive trajectory generation, lacking exploration.

### Solution
Increase the sampling temperature during the rollout phase from 1.0 to 1.6:

```bash
actor_rollout_ref.rollout.temperature=1.6
```

**Note**: Used only when collecting data during rollout, not during training.

### Effect
- Generates diverse trajectories, enhancing exploration capability
- Crucial for discovering new successful strategies (e.g., the "pushcut" phenomenon)
- Achieves approximately **~15%** improvement over baseline (Paper Figure 3c)
- Widely used in the latest LLM RL research

---

# 📃 Main Experimental Results

## LIBERO Benchmark

We evaluated using OpenVLA-OFT on the LIBERO benchmark. SimpleVLA-RL boosts performance to **97.6 points** (out of 100), setting a new state-of-the-art.

### Key Results

| Setting | LIBERO-Long Success Rate | Improvement |
|---------|--------------------------|-------------|
| Baseline SFT | 60% | - |
| SFT + 300-step RL | 90% | +30% |
| **Final Performance** | **97.6%** | **+37.6%** |

### Cold Start Experiment (Extreme Data Scarcity Scenario)

**Experimental Setup**: Only **1 trajectory** per task used for SFT initialization

| Method | Success Rate | Improvement |
|--------|--------------|-------------|
| SFT only (1 trajectory) | 17.3% | - |
| SFT + SimpleVLA-RL | **91.7%** | **+74.4% (430.1%)** |

This demonstrates the powerful capability of RL in extreme data scarcity scenarios!

## RoboTwin 2.0 Benchmark

SimpleVLA-RL also achieves excellent results on the RoboTwin 2.0 dual-arm manipulation benchmark, surpassing the π₀ model on some tasks.

### RoboTwin 2.0 Introduction

RoboTwin 2.0 is a scalable dual-arm robot manipulation benchmark platform with the following features:
- **Strong Domain Randomization**: Multi-dimensional randomization of environments, objects, camera viewpoints, etc.
- **Dual-Arm Coordination**: Requires coordination between left and right arms to complete tasks
- **Realistic Physics**: Based on the SAPIEN physics engine, high-fidelity simulation
- **Diverse Tasks**: Covers various manipulation types including grasping, placing, tool use, etc.

---

# ✨ Quick Start

## Step 1: Environment Setup

### Installation Options

Choose the installation option based on the benchmark you want to use:

- **Option 1**: Run RL on the LIBERO benchmark
- **Option 2**: Run RL on the RoboTwin 2.0 benchmark

---

### Option 1: Run RL on the LIBERO Benchmark

#### Step 1.1: Install veRL

> **Note**: It is recommended to use veRL version 0.2 or 0.3. The latest version may have library conflicts.

Refer to the official [veRL Installation Guide](https://verl.readthedocs.io/en/v0.3.x/start/install.html):

```bash
# Create and activate conda environment
conda create -n simplevla python==3.10
conda activate simplevla

# Install PyTorch
pip3 install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu124

# Clone veRL (recommended to place it in the same parent directory as simplevla-rl, not inside the simplevla-rl folder)
git clone -b v0.2.x https://github.com/volcengine/verl.git
cd verl
pip3 install -e .
cd ..
```

#### Step 1.2: Install EGL Libraries for Headless Rendering

**This step is required for both the LIBERO and RoboTwin 2.0 benchmarks.**

Install EGL libraries to enable headless rendering in Docker containers or remote servers without a display:

```bash
sudo apt-get update
sudo apt-get install -y libegl1 libegl-dev libegl-mesa0 libegl1-mesa-dev libgles2-mesa-dev
```

> **Note**: Without these libraries, you may encounter an `AttributeError: 'NoneType' object has no attribute 'eglQueryString'` error when initializing the SAPIEN/robot environment.

#### Step 1.3: Install LIBERO and OpenVLA-OFT

Refer to the official [OpenVLA-OFT Installation Guide](https://github.com/moojink/openvla-oft):

```bash
conda activate simplevla
pip3 install torch torchvision

# Clone OpenVLA-OFT (place it in the same parent directory as simplevla-rl, not inside the simplevla-rl folder)
git clone https://github.com/moojink/openvla-oft.git
cd openvla-oft
pip install -e .

# Install Flash Attention 2 for training
# If you encounter issues, first try `pip cache remove flash_attn`
pip install packaging ninja
ninja --version; echo $?  # Should return exit code "0"
pip3 install flash-attn --no-build-isolation

cd ..

# Install LIBERO
git clone https://github.com/Lifelong-Robot-Learning/LIBERO.git
pip install -e LIBERO
cd openvla-oft
pip install -r experiments/robot/libero/libero_requirements.txt
cd ..
```

---

### Option 2: Run RL on the RoboTwin 2.0 Benchmark

#### Step 2.1: Install veRL

Same as Step 1.1 in Option 1.

#### Step 2.2: Install EGL Libraries for Headless Rendering

Same as Step 1.2 in Option 1.

#### Step 2.3: Install RoboTwin 2.0Refer to the official [RoboTwin 2.0 Installation Guide](https://robotwin-platform.github.io/doc/usage/robotwin-install.html#1-dependencies):

```bash
# Install system dependencies
sudo apt install libvulkan1 mesa-vulkan-drivers vulkan-tools

conda activate simplevla

# Clone and install RoboTwin
git clone https://github.com/RoboTwin-Platform/RoboTwin.git
cd RoboTwin
bash script/_install.sh

# Download RoboTwin assets
bash script/_download_assets.sh
cd ..
```

#### Step 2.4: Install OpenVLA-OFT

```bash
conda activate simplevla
pip3 install torch torchvision

# Clone OpenVLA-OFT (place it in the same directory as simplevla-rl, not inside the simplevla-rl folder)
git clone https://github.com/moojink/openvla-oft.git
cd openvla-oft
pip install -e .

# Install Flash Attention 2
pip install packaging ninja
ninja --version; echo $?  # Should return exit code "0"
pip3 install flash-attn --no-build-isolation
cd ..
```

#### Step 2.5: Configure RoboTwin for SimpleVLA-RL

Apply the necessary RoboTwin modifications:

```bash
git clone https://github.com/PRIME-RL/SimpleVLA-RL.git
cd SimpleVLA-RL

# Apply RoboTwin modifications
bash copy_overwrite_robotwin2.sh <your_robotwin_path> <your_simplevlarl_path>
# Example: bash copy_overwrite_robotwin2.sh /mnt/petrelfs/SimpleVLA-RL /mnt/petrelfs/RoboTwin
```

---

### Troubleshooting

- If you encounter issues during the RoboTwin 2.0 installation, please refer to the [RoboTwin documentation](https://robotwin-platform.github.io/doc/) or check its GitHub Issues.
- If you encounter EGL-related errors, ensure all EGL libraries are correctly installed (see Steps 1.2/2.2).
- If you encounter Flash Attention installation issues, try clearing the pip cache: `pip cache remove flash_attn`
- It is recommended to clone all code repositories (veRL, OpenVLA-OFT, RoboTwin, LIBERO) into the same directory level as SimpleVLA-RL.

### Directory Structure

After installation, your directory structure should look like this:

```
your_workspace/
├── SimpleVLA-RL/
├── verl/
├── openvla-oft/
├── LIBERO/          (for Option 1)
└── RoboTwin/        (for Option 2)
```

### Verify Installation

After completing the installation, verify your setup:

```bash
# Activate environment
conda activate simplevla

# Verify PyTorch installation
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"

# Verify OpenVLA-OFT installation
python -c "import openvla; print('OpenVLA imported successfully')"

# For LIBERO (Option 1)
python -c "import libero; print('LIBERO imported successfully')"

# For RoboTwin (Option 2)
python -c "import robotwin; print('RoboTwin imported successfully')"
```

---

### (Optional) Support Additional Tasks in RoboTwin 2.0

#### Step A: Collect Feasible Seeds

RoboTwin 2.0 tasks may have infeasible seeds (e.g., objects out of the robot arm's reach). To optimize RL training, we pre-collect feasible seeds to avoid repeated validation during training epochs.

**Collection Process**:

1. Update `DATASET_NAME` in `pre_collect_robotwin2_seed.sh` to your target task name
2. Run the collection script:
   ```bash
   sh pre_collect_robotwin2_seed.sh
   ```
3. This will generate `robotwin2_train_seeds.json` in the SimpleVLA-RL directory
4. Add the JSON content to:
   ```
   SimpleVLA-RL/verl/utils/envs/robotwin2/seeds/robotwin2_train_seeds.json
   ```

#### Step B: Register New Tasks

1. Add the task name in `SimpleVLA-RL/verl/utils/dataset/rob_dataset.py`
2. Add the task name and corresponding maximum steps in `SimpleVLA-RL/verl/workers/rollout/rob_rollout.py`

#### Step C: Implement Task-Specific Functions

Add the `get_info()` function in the corresponding task file at `SimpleVLA-RL/verl/utils/envs/robotwin2/envs/task_name.py`.

Reference implementation example:
```
SimpleVLA-RL/modified_codes/robotwin2/envs/handover_block.py
```

## Step 2: Prepare the SFT Model

Reinforcement learning training requires an **SFT (Supervised Fine-Tuning)** VLA model as a starting point.

### Option 1: Download a Pre-trained SFT Model

Download from the [SimpleVLA-RL Collection](https://huggingface.co/collections/Haozhan72/simplevla-rl-6833311430cd9df52aeb1f86):

**LIBERO Benchmark Models**:
- `libero-10 traj1 SFT`: Trained with 1 trajectory per task (cold-start experiment)
- `libero-10 trajall SFT`: Trained with all trajectories per task
- `libero-goal traj1 SFT`: Goal generalization experiment
- `libero-object traj1 SFT`: Object generalization experiment
- `libero-spatial traj1 SFT`: Spatial generalization experiment

**RoboTwin 2.0 Benchmark Models**:
- `Robotwin2.0 tasks traj1000 SFT`: Trained with 1000 trajectories per task

### Option 2: Start from the Official OpenVLA Model

Download the pre-trained model from the [Official OpenVLA Repository](https://huggingface.co/openvla).

### Option 3: Fine-Tune Yourself

If you need to use other models or custom data, you will need to perform SFT fine-tuning yourself.

## Step 3: Configure Training Parameters

Before running the training script, you need to configure the following key parameters:

### 1. Configure WandB (Optional but Recommended)

Replace with your WandB API key in `SimpleVLA-RL/align.json`:

```json
{
  "WANDB_API_KEY": "your_wandb_api_key_here"
}
```

### 2. Modify the Training Script

Edit `examples/run_openvla_oft_rl_libero.sh` or `examples/run_openvla_oft_rl_twin2.sh`:

```bash
# Experiment configuration
export EXPERIMENT_NAME="libero_long_rl_exp1"     # Experiment name
export SFT_MODEL_PATH="/path/to/your/sft/model" # SFT model path
export CKPT_PATH="/path/to/save/checkpoints"    # Checkpoint save path

# Dataset configuration
export DATASET_NAME="libero-long"  # Options: libero-10, libero-long, 
                                   #          robotwin2_beat_block_hammer, etc.

# Compute resource configuration
export NUM_GPUS=8      # Number of GPUs per node
export NUM_NODES=1     # Number of nodes

# WandB configuration
export ALIGN_PATH="SimpleVLA-RL/align.json"
```

### 3. Key Hyperparameter Explanation

```bash
# Data sampling configuration
data.train_batch_size=64                # Sample 64 task instances per training step
data.n_samples=8                        # Sample 8 trajectories per task (required by GRPO)

# Dynamic sampling (Key Technique 1)
data.filter_accuracy=True
data.accuracy_lower_bound=0.1          # Filter out task groups with success rate < 10%
data.accuracy_upper_bound=0.9          # Filter out task groups with success rate > 90%

# Inference configuration (Key Technique 3)
actor_rollout_ref.rollout.temperature=1.6  # Higher sampling temperature

# PPO configuration (Key Technique 2)
actor_rollout_ref.actor.clip_ratio_low=0.2    # Lower clipping bound
actor_rollout_ref.actor.clip_ratio_high=0.28  # Upper clipping bound (higher!)

# Optimizer configuration
actor_rollout_ref.actor.optim.lr=5e-6       # Learning rate
actor_rollout_ref.actor.ppo_mini_batch_size=128
actor_rollout_ref.actor.ppo_micro_batch_size=8

# Training progress configuration
trainer.total_epochs=20                 # Total epochs (paper uses 20 epochs = 300 steps)
trainer.save_freq=20                    # Save checkpoint every 20 steps
trainer.test_freq=4                     # Validate every 4 steps
```

## Step 4: Start RL Training

### LIBERO Benchmark

```bash
bash examples/run_openvla_oft_rl_libero.sh
```

### RoboTwin 2.0 Benchmark

```bash
bash examples/run_openvla_oft_rl_twin2.sh
```

### Expected Training Time

**Hardware Configuration**: 8×NVIDIA A800 GPU (80GB)

| Configuration | Training Steps | Estimated Time | Description |
|------|---------|---------|------|
| Paper Setting | 300 steps | ~4.3 days | 20 epochs, ~20 minutes per step |
| Configuration File | 1500 steps | ~21 days | 100 epochs (adjustable) |

**Time Breakdown (per training step)**:
- Data Collection (Rollout): ~18 minutes (87.8%)
- PPO Update: ~2.4 minutes (11.8%)
- Other Operations: ~0.2 minutes (0.4%)

## Step 5: Run Evaluation

To evaluate the trained model, enable validation mode in the script:

```bash
# Add to run_openvla_oft_rl_libero.sh
trainer.val_only=True
```

Then run the same script:

```bash
bash examples/run_openvla_oft_rl_libero.sh
```

---

# 📊 Detailed Training Process

## Training Loop Overview

Each training step consists of the following phases:

```
Training Step i
│
├─ 1. Data Sampling
│   └─ Sample 64 task instances from the dataset
│
├─ 2. Trajectory Inference (Rollout)
│   ├─ Generate 8 trajectories per task
│   ├─ VLA model inference
│   ├─ Environment interaction
│   └─ Collect trajectory data
│
├─ 3. Dynamic Sampling Filtering
│   └─ Filter out task groups that are all successful or all failed
│
├─ 4. Reward Calculation
│   └─ Apply outcome rewards (Success=1.0, Failure=0.0)
│
├─ 5. Advantage Estimation (GRPO)
│   ├─ Group by task
│   ├─ Calculate intra-group average return as baseline
│   └─ Advantage = Individual return - Group average
│
├─ 6. Policy Update (PPO)
│   ├─ Mini-batch loop
│   ├─ Calculate policy loss (with clipping)
```│   ├─ Backpropagation
│   └─ Gradient Clipping and Optimizer Update
│
├─ 7. Validation (every 4 steps)
│   └─ Evaluate success rate on 256 tasks
│
└─ 8. Save Checkpoint (every 20 steps)
    └─ Save model weights and optimizer state
```

## Detailed Explanation of GRPO Advantage Estimation

**Group Relative Policy Optimization (GRPO)** is an advantage estimation method specifically designed for outcome-based rewards:

### Why GRPO?

Traditional Generalized Advantage Estimation (GAE) requires:
- Training an additional value network V(s)
- Dense intermediate reward signals
- A more complex training pipeline

Advantages of GRPO:
- ✅ No value network needed
- ✅ Only requires outcome rewards
- ✅ Learns through relative comparison within a group

### Algorithm Principle

For N trajectories of the same task:

```python
# 1. Compute the total return for each trajectory
R_i = Σ rewards  # i = 1, 2, ..., N (N=8)

# 2. Compute the group average as the baseline
baseline = (1/N) × Σ R_i

# 3. Compute the advantage
A_i = R_i - baseline
```

### Example

```
8 trajectories for Task 1:
Returns: [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0]
Baseline: 0.5
Advantages: [-0.5, 0.5, -0.5, 0.5, -0.5, 0.5, 0.5, -0.5]
             ↑    ↑    ↑    ↑     ↑    ↑    ↑    ↑
            Bad  Good  Bad  Good  Bad  Good  Good  Bad

Meaning: Successful trajectories receive positive advantages, failed ones receive negative advantages.
         The policy will learn to increase the probability of successful trajectories and decrease that of failed ones.
```

## Detailed Explanation of PPO Policy Update

### Standard PPO vs SimpleVLA-RL

```python
# Standard PPO objective function
ratio = π(a|s) / π_old(a|s)
clipped_ratio = clip(ratio, 0.8, 1.2)  # Symmetric clipping
loss = -min(ratio × A, clipped_ratio × A)

# SimpleVLA-RL: Clip Higher
clipped_ratio = clip(ratio, 0.8, 1.28)  # Asymmetric clipping!
loss = -min(ratio × A, clipped_ratio × A)
```

### Why is Clip Higher Effective?

**Scenario**: A low-probability action (p=0.1) succeeds during exploration

```
Standard PPO (clip_high=0.2):
- ratio = 0.15 / 0.1 = 1.5
- clipped_ratio = 1.2 (clipped!)
- Probability increases by at most 20%
- New probability ≤ 0.12

Clip Higher (clip_high=0.28):
- ratio = 1.5
- clipped_ratio = 1.5 (not clipped!)
- Probability can increase by 50%
- New probability ≤ 0.15

Result: Clip Higher allows larger policy updates, encouraging exploration.
```

---

# 🔍 Explanation of Important Concepts

## What is the "Pushcut" Phenomenon?

**Pushcut** is a novel manipulation pattern autonomously discovered by the policy during RL training, **never present in the training demonstrations**.

### Discovery Process

**SFT Model**: Learns only from human demonstrations
```
Standard Action Sequence:
1. Approach object
2. Grasp object
3. Lift object vertically (clear the table)
4. Move horizontally to target position
5. Place object down
6. Release gripper
```

**After RL Training**: A superior strategy is discovered
```
"Pushcut" Action Sequence:
1. Approach object
2. Grasp or contact object
3. Stay low (close to the table surface)
4. Push/drag object horizontally to target position
5. Task complete!
   ↑
   No lifting required, faster and more robust!
```

### Tasks Where Pushcut Was Observed

- ✅ **move_can_pot**: Push the can instead of lifting it
- ✅ **place_a2b_left/right**: Push object A instead of picking and placing
- ❌ **beat_block_hammer**: Not observed (requires tool grasping)

### Why is Pushcut Superior?

1. **Faster Execution**: Less vertical movement, more direct path
2. **More Robust**: Lower precision requirements
3. **Energy Efficient**: No need to fight gravity
4. **Collision Safety**: Staying close to the table reduces collision risk
5. **Maintains Contact**: Pushing naturally maintains object contact

### Significance

This discovery proves:
- ✅ RL can discover strategies not demonstrated by humans
- ✅ It surpasses the limitations of imitation learning
- ✅ It demonstrates a true understanding of the task objective (not just copying actions)
- ✅ Similar to AlphaGo discovering unconventional but optimal moves

## How Does Action Chunking Work?

### Comparison with ReAct Mode

**ReAct Mode** (Single Step):
```
Each Step:
  Observe → LLM Reason → Generate 1 Action → Execute → Next Step

Total (200 environment steps): 200 LLM calls
```

**VLA Action Chunking** (Multi-Step Planning):
```
Each Round:
  Observe → VLA Reason → Generate 25 Future Actions → Execute All → Next Round

Total (200 environment steps): 8 VLA calls (200÷25=8)
```

### Execution Timeline

```
Timeline:   0ms    300ms    1800ms   2100ms   3600ms
          |       |         |        |        |
GPU:      [VLA 1]  Idle     [VLA 2]  Idle     [VLA 3]
          ↓                         ↓
Actions:  Generate 25  Execute 25  Generate 25  Execute 25
          Actions      Actions     Actions      Actions
          
Env Steps:   0       0→24      25      25→49    50
          
Robot:    Stationary  Moving...  Moving...  Moving...  Moving...
```

### Why Use Action Chunking?

1. **Computational Efficiency**: 8 inferences vs 200 = **25x reduction**
2. **Natural Motion**: Produces smooth trajectories, avoids jitter
3. **Temporal Consistency**: Enforces coherence in action sequences
4. **Reduced Accumulated Error**: Fewer replanning steps reduce drift

### Does the Robot Pause in Real Deployment?

**Answer: No!** Real deployment uses **buffered execution**:

```
VLA Thread:    Continuously compute the next batch of 25 actions
               ↓
Action Buffer: [Actions 0-24] → [Actions 25-49] → [Actions 50-74]
               ↓                ↓                 ↓
Control Thread: Execute Actions  Execute Actions   Execute Actions
               (50Hz)           (50Hz)            (50Hz)

Result: The robot maintains continuous, smooth motion, no pauses!
```

**Key Condition**:
```
VLA Inference Time < Action Chunk Execution Time
300ms < (25 actions × 50ms/action) = 1250ms ✓

Safety Margin: 1250ms / 300ms = 4x ✓
```

---

# ⚠️ Important Notes

## Training Configuration

### Key Hyperparameters

The hyperparameters for the three key techniques **must be retained**:

```bash
# 1. Dynamic Sampling
data.accuracy_lower_bound=0.1
data.accuracy_upper_bound=0.9

# 2. Higher Clip Bound
actor_rollout_ref.actor.clip_ratio_high=0.28

# 3. Higher Inference Temperature
actor_rollout_ref.rollout.temperature=1.6
```

These three parameters together contribute approximately **30%** performance improvement!

---

# Experimental Results

[SimpleVLA RL rollout results (videos of the robot operating in a virtual environment)](https://01.me/files/ai-agent-book/SimpleVLA-RL-rollouts.zip)

[wandb experimental results](https://wandb.ai/bojieli-pine-ai/SimpleVLA-RL)

## Experiment Overview

According to the documentation, this experiment ran two key tasks on the RoboTwin 2.0 benchmark:
- **beat_block_hammer**: Tool use task (grasp hammer to hit block)
- **move_can_pot**: Spatial reasoning task (move can next to pot)

## Detailed Analysis

### 1. Actor Training Metrics Analysis

**PPO KL Divergence (ppo_kl)**:
- KL divergence for both tasks remained at low levels (~0.002-0.008)
- Indicates moderate policy update magnitude, not deviating excessively from the reference policy
- Meets the stability requirements of the PPO algorithm

**Policy Gradient Loss (pg_loss)**:
- `beat_block_hammer` shows higher loss values and larger fluctuations
- `move_can_pot` loss is relatively stable and lower
- Reflects the higher complexity of the tool use task

**Policy Gradient Clip Fraction (pg_clipfrac)**:
- Both tasks remain within the 0.01-0.03 range
- Moderate clipping indicates the **higher clip bound (1.28)** technique is effective
- Allows for bolder policy exploration while maintaining training stability

**Learning Rate and Gradient Norm**:
- Learning rate stable at 5e-6, consistent with configuration
- Gradient norm within a reasonable range, training process stable

### 2. Training Reward Analysis

**Verifier Reward (train_reward/verifier)**:
- `beat_block_hammer` (orange): Increased from ~0.3 to ~0.75, **150% growth**
- `move_can_pot` (blue): Increased from ~0.15 to ~0.6, **300% growth**
- Indicates both tasks benefit significantly from reinforcement learning

**Total Reward (train_reward/reward_all)**:
- Trend similar to verifier reward but with higher values
- This aligns with the GRPO algorithm design, where the group average serves as the baseline

### 3. Validation Score Analysis

**Training Validation Score (train_verify_score/all)**:
- `beat_block_hammer` ultimately reaches ~0.8 (80% success rate)
- `move_can_pot` ultimately reaches ~0.67 (67% success rate)
- Consistent with the 60-80% success rate expected by the paper

**Test Validation Score (val/test_score)**:
- **IID Test** (within training distribution):
  - `beat_block_hammer`: ~0.85 success rate
  - `move_can_pot`: ~0.63 success rate
- **OOD Test** (out of distribution):
  - `beat_block_hammer`: ~0.78 success rate
  - `move_can_pot`: ~0.58 success rate
- Small gap between IID/OOD performance indicates good generalization ability

### 4. Critic Network Analysis

**Reward Score Statistics**:
- **Minimum**: Both tasks start from 0, consistent with the binary reward setting
- **Mean**: Steadily increasing, reflecting improved average success rate
- **Maximum**: Both tasks reach the highest reward value

**Score Distribution**:
- Shows a healthy exploration-exploitation balance
- Consistent with the expected effect of the **dynamic sampling** technique

### 5. Exploration Strategy Analysis

**Entropy Loss (actor_after/entropy_loss_eval)**:
- `beat_block_hammer` shows higher entropy values (more exploration)
- `move_can_pot` entropy gradually decreases but remains at a reasonable level
- Indicates the **higher inference temperature (1.6)** successfully promotes exploration

## Performance Comparison

### Comparison with Paper Baseline

Results of this experiment on RoboTwin 2.0:
- `beat_block_hammer`: 80% success rate
- `move_can_pot`: 67% success rate
- Consistent with the performance range expected by the paper

### Cold Start Capability
The experiment demonstrates RL's powerful capability under data-scarce conditions:
- Starts from a limited SFT initialization
- Achieves significant performance improvement through outcome rewards
- Proves that RL can **surpass the limitations of human demonstrations**

---

# 🌻 Acknowledgements

This project is developed based on the following excellent open-source projects:

- **[veRL](https://github.com/volcengine/verl)**: Volcengine LLM Reinforcement Learning Framework
- **[OpenVLA-OFT](https://github.com/moojink/openvla-oft)**: Open-source Vision-Language-Action Model
- **[RoboTwin2.0](https://github.com/RoboTwin-Platform/RoboTwin)**: Dual-arm Robot Manipulation Benchmark
- **[LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO)**: Lifelong Robot Learning Benchmark
- **[PRIME](https://github.com/PRIME-RL/PRIME)**: Reinforcement Learning Research Framework

Thank you for the significant contributions of these projects! For more details and updates, please refer to the official documentation and code repositories of each project.

---

# 📨 Contact Information

For questions or suggestions, please feel free to contact:

- **Li Haozhan**: zhan72426@gmail.com
- **Ding Ning**: dingning@mail.tsinghua.edu.cn

Or submit an issue on [GitHub Issues](https://github.com/PRIME-RL/SimpleVLA-RL/issues).

---

# 📝 TODO

## Model Support- ✅ Support for OpenVLA and OpenVLA-OFT
- ⏳ Support for Pi0 fast tokenizer
- ⏳ Support for more VLA architectures (RT-1, RT-2)

## Benchmarks

- ✅ Support for LIBERO benchmark
- ✅ Support for RoboTwin benchmark
- ⏳ Support for CALVIN benchmark
- ⏳ Support for real robot hardware

## Algorithm Improvements

- ⏳ Support for GPU-accelerated simulator (Isaac Gym)
- ⏳ Support for distributed training (multi-node)
- ⏳ Support for online curriculum learning

---

# 🎈 Citation

If you find SimpleVLA-RL helpful for your research, please cite our paper:

```bibtex
@article{li2025simplevla,
  title={SimpleVLA-RL: Scaling VLA Training via Reinforcement Learning},
  author={Li, Haozhan and Zuo, Yuxin and Yu, Jiale and Zhang, Yuhao and Yang, Zhaohui and Zhang, Kaiyan and Zhu, Xuekai and Zhang, Yuchen and Chen, Tianxing and Cui, Ganqu and others},
  journal={arXiv preprint arXiv:2509.09674},
  year={2025}
}
```

Also, please cite the RoboTwin 2.0 benchmark:

```bibtex
@article{robotwin2025,
  title={RoboTwin 2.0: A Scalable Data Generator and Benchmark with Strong Domain Randomization for Robust Bimanual Robotic Manipulation},
  author={...},
  journal={arXiv preprint arXiv:2506.18088},
  year={2025}
}
```
