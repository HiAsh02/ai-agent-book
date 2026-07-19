# Cursor Chat: ai-agent-book

## Metadata
- **Project**: ai-agent-book
- **Path**: `/Users/boj`
- **Date**: 2025-10-05 18:49:34
- **Session ID**: `c3e4aaa2-468b-45ee-8da0-aa3c375643a0`

## Conversation

### 👤 You

Based on the details of the two papers @https://arxiv.org/pdf/2509.09674 @https://arxiv.org/pdf/2506.18088 and the document below, write a comprehensive README in Chinese.

<div align="center">

<img src="figs/logo.png" width="260"/>

## 🚀 Scaling VLA Training via Reinforcement Learning

[![Paper](https://img.shields.io/badge/Paper-A42C25?style=for-the-badge&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2509.09674) [![Github](https://img.shields.io/badge/SimpleVLA--RL-000000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/PRIME-RL/SimpleVLA-RL) [![Hugging Face Collection](https://img.shields.io/badge/Models-fcd022?style=for-the-badge&logo=huggingface&logoColor=000)](https://huggingface.co/collections/Haozhan72/simplevla-rl-6833311430cd9df52aeb1f86) [![Twitter](https://img.shields.io/badge/Twitter-%23000000.svg?style=for-the-badge&logo=x&logoColor=white)](https://x.com/stingning/status/1927770654385860804) [![WeChat](https://img.shields.io/badge/WeChat--Group-07C160?style=for-the-badge&logo=wechat&logoColor=white)](figs/wechat-group.png)

</div>

<!-- <div align="center">
  <p>
    <a href="#news" style="text-decoration: none; font-weight: bold;">🎉 News</a> •
    <a href="#overview" style="text-decoration: none; font-weight: bold;">📖 Overview</a> •
    <a href="#main-results" style="text-decoration: none; font-weight: bold;">📃 Main Results</a> •
    <a href="#getting-started" style="text-decoration: none; font-weight: bold;">✨ Getting Started</a>
  </p>
  <p>
    <a href="#acknowledgement" style="text-decoration: none; font-weight: bold;">🌻 Acknowledgement</a> •
    <a href="#contact" style="text-decoration: none; font-weight: bold;">📨 Contact</a> •
    <a href="#todo" style="text-decoration: none; font-weight: bold;">📝 TODO</a> •
    <a href="#citation" style="text-decoration: none; font-weight: bold;">🎈 Citation</a>
  </p>
</div> -->

> We demonstrate that even simple 0/1 rewards can enable effective, scalable, generalizable online RL for VLA models.


<div align="center">
<img src="figs/teaser.png" alt="Overview of SimpleVLA-RL." width="90%" />

Overview of **SimpleVLA-RL**. SimpleVLA-RL is an efficient RL framework for VLA that improves long-horizon planning under data scarcity, outperforms SFT in simulation and real-world tasks, reveals a "pushcut" new-action phenomenon, and strengthens spatial/object/goal generalization.

<!-- <sub>*Our openvla-oft model design differs from the official one. Our setup: third-person image, language instruction; parallel decoding (PD) & action chunking (AC). Official setup: third-person image, wrist camera image, robot proprioceptive state, language instruction; PD, AC, and continuous actions with L1 regression (Cont-L1).*</sub> -->

</div>

# 🎉News
- **[2025-10-01]** **SimpleVLA-RL** now supports RoboTwin2.0 Benchmark. Feel free to experiment with it!
- **[2025-09-12]** Excited to release the **SimpleVLA-RL** paper! Check it out: [Paper](https://arxiv.org/abs/2509.09674).
- **[2025-05-27]** We release the code of **SimpleVLA-RL**.

# 📖Overview

We introduce SimpleVLA-RL, a simple yet effective approach for online Reinforcement Learning (RL) for Vision-Language-Action (VLA) models, which utilizes only outcome-level 0/1 rule-based reward signals directly obtained from simulation environments.

<div align="center">
<img src="figs/simplevla-rl.png" alt="Overview of SimpleVLA-RL." width="90%" />
</div>

# 📃Main Results

We evaluate SimpleVLA-RL on the LIBERO using OpenVLA-OFT. SimpleVLA-RL improves the performance of OpenVLA-OFT to **97.6 points** on LIBERO-Long and sets a new state-of-the-art. Remarkably, using only one trajectory per task for cold-start SFT, SimpleVLA-RL raises the performance of OpenVLA-OFT from 17.3 to 91.7, yielding an improvement of **74.4 points (430.1%)**.

<div align="center">
<img src="figs/main.png" alt="Main Results of SimpleVLA-RL." width="90%" />
</div>

# ✨Getting Started

#### 1. Set Up the Environment

See [SETUP.md](SETUP.md) for detailed instructions on setting up the conda environment.  

#### 2. Prepare the SFT Model

An **SFT (Supervised Fine-Tuning)** VLA model is required for RL training. Below are the available options:

* **OpenVLA-OFT SFT Models**  
  Download from the [SimpleVLA-RL Collection](https://huggingface.co/collections/Haozhan72/simplevla-rl-6833311430cd9df52aeb1f86). Available models include:
  - `libero-10 traj1/trajall SFT`
  - `libero-goal/object/spatial traj1 SFT`
  - `Robotwin2.0 tasks traj1000 SFT`
* **OpenVLA SFT Models**  
  Download from [here](https://huggingface.co/openvla).

* **Other Models**  
  For other models, you may need to fine-tune them yourself.

#### 3. Train with SimpleVLA-RL

Before running the training script, ensure the following configurations are properly set:

- **Set Your Weights and Biases (WandB) API Key**  
   Replace the `WANDB_API_KEY` field in `SimpleVLA-RL/align.json` with your own WandB API key.

- **Modify Key Variables**  
   Update the following variables in `examples/run_openvla_oft_rl_libero/twin2.sh` as needed:
  - `WANDB_API_KEY`: Your WandB API key.
  - `EXPERIMENT_NAME`: The name of your experiment. You can choose any name.
  - `SFT_MODEL_PATH`: Path to your SFT model.
  - `CKPT_PATH`: Path where your checkpoints will be saved.
  - `DATASET_NAME`: For detailed options, refer to `examples/run_openvla_oft_rl_libero/twin2.sh`.
  - `ALIGN_PATH`: Path to the `SimpleVLA-RL/align.json` file.
  - `NUM_GPUS`: Number of GPUs available per node (e.g., `8`).
  - `NUM_NODES`: Number of nodes used for RL training (e.g., `1`).

> [!NOTE]
> 
> - The script has been tested on the following configurations:
>   - Single-node setup: `NUM_NODES=1`, `NUM_GPUS=8` (1 node with 8 NVIDIA A800 GPUs, each having 80GB memory).>   - Multi-node setup: `NUM_NODES=2`, `NUM_GPUS=8` (2 nodes with 16 NVIDIA A800 GPUs, each having 80GB memory).
> - The driver version used is `470.161.03`, and the CUDA version is `12.4`. *(Not necessary)*

- **Run RL Training**  
   Use the following command to start RL training for OpenVLA-OFT on the LIBERO or RoboTwin2.0 benchmark:
  
  ```bash
  bash examples/run_openvla_oft_rl_libero.sh
  or
  bash examples/run_openvla_oft_rl_twin2.sh
  ```
  

#### 4. Run Evaluation

To evaluate the performance of your model, enable evaluation mode by setting `trainer.val_only=True` in `examples/run_openvla_oft_rl_libero/twin2.sh`. Then, execute the same script:

```bash
bash examples/run_openvla_oft_rl_libero.sh
or
bash examples/run_openvla_oft_rl_twin2.sh
```

# 🌻Acknowledgement

We develop this preview version of the code based on [veRL](https://github.com/volcengine/verl), [OpenVLA-OFT](https://github.com/moojink/openvla-oft), [RoboTwin2.0](https://github.com/RoboTwin-Platform/RoboTwin.git), and [PRIME](https://github.com/PRIME-RL/PRIME). We acknowledge their significant contributions!
For further details and updates, please refer to the official documentation and repositories of the respective projects.

# 📨Contact

- Haozhan Li: zhan72426@gmail.com
- Ning Ding: dingning@mail.tsinghua.edu.cn

# 📝TODO

- **Models**:
  - ✅ Support OpenVLA and OpenVLA-OFT
  - ⏳ Support Pi0 fast tokenizer
- **Benchmarks**:
  - ✅ Support LIBERO benchmark
  - ✅ Support RoboTwin benchmark

# 🎈Citation

If you find SimpleVLA-RL helpful, please cite us.

```bibtex
@article{li2025simplevla,
  title={SimpleVLA-RL: Scaling VLA Training via Reinforcement Learning},
  author={Li, Haozhan and Zuo, Yuxin and Yu, Jiale and Zhang, Yuhao and Yang, Zhaohui and Zhang, Kaiyan and Zhu, Xuekai and Zhang, Yuchen and Chen, Tianxing and Cui, Ganqu and others},
  journal={arXiv preprint arXiv:2509.09674},
  year={2025}
}
```


# SimpleVLA-RL Installation Guide

This guide provides step-by-step instructions for setting up the SimpleVLA-RL environment. Our project builds upon [veRL](https://github.com/volcengine/verl), and the installation process involves three main components: veRL, simulation benchmarks, and the VLA model (OpenVLA-OFT).

## Installation Options

### Option 1: Running RL on LIBERO Benchmark

#### Step 1: Install veRL

> **Note:** We recommend veRL version 0.2 or 0.3. Latest versions may have library conflicts.

Follow the official [veRL installation guide](https://verl.readthedocs.io/en/v0.3.x/start/install.html):

```bash
# Create and activate conda environment
conda create -n simplevla python==3.10
conda activate simplevla

# Install PyTorch
pip3 install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu124

# Clone veRL (recommended to place at the same level as simplevla-rl, not inside the simplevla-rl folder)
git clone -b v0.2.x https://github.com/volcengine/verl.git
cd verl
pip3 install -e .
cd ..
```

+#### Step 2: Install EGL Libraries for Headless Rendering
+
+**Required for both LIBERO and RoboTwin 2.0 benchmarks.**
+
+Install EGL libraries to enable headless rendering in Docker containers or remote servers without displays:
+
+```bash
+sudo apt-get update
+sudo apt-get install -y libegl1 libegl-dev libegl-mesa0 libegl1-mesa-dev libgles2-mesa-dev
+```
+
+> **Note:** Without these libraries, you may encounter `AttributeError: 'NoneType' object has no attribute 'eglQueryString'` when initializing SAPIEN/robotics environments.
+

#### Step 3: Install LIBERO and OpenVLA-OFT

Follow the official [OpenVLA-OFT installation guide](https://github.com/moojink/openvla-oft):

```bash
conda activate simplevla
pip3 install torch torchvision

# Clone OpenVLA-OFT (place at the same level as simplevla-rl, not inside the simplevla-rl folder)
git clone https://github.com/moojink/openvla-oft.git
cd openvla-oft
pip install -e .

# Install Flash Attention 2 for training
# If you encounter issues, try `pip cache remove flash_attn` first
pip install packaging ninja
ninja --version; echo $?  # Should return exit code "0"
pip3 install flash-attn --no-build-isolation

cd ..

# Install LIBERO
git clone https://github.com/Lifelong-Robot-Learning/LIBERO.git
pip install -e LIBERO
cd openvla-oft
pip install -r experiments/robot/libero/libero_requirements.txt
```

### Option 2: Running RL on RoboTwin 2.0 Benchmark

#### Step 1: Install veRL

Same as Option 1, Step 1 and Step 2.

#### Step 2: Install RoboTwin 2.0

Follow the official [RoboTwin 2.0 Installation Guide](https://robotwin-platform.github.io/doc/usage/robotwin-install.html#1-dependencies):

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

#### Step 3: Install OpenVLA-OFT

```bash
conda activate simplevla
pip3 install torch torchvision

# Clone OpenVLA-OFT (place at the same level as simplevla-rl, not inside the simplevla-rl folder)
git clone https://github.com/moojink/openvla-oft.git
cd openvla-oft
pip install -e .

# Install Flash Attention 2
pip install packaging ninja
ninja --version; echo $?  # Should return exit code "0"
pip3 install flash-attn --no-build-isolation
cd ..
```

#### Step 4: Configure RoboTwin for SimpleVLA-RL

Apply necessary modifications to RoboTwin:

```bash
git clone https://github.com/PRIME-RL/SimpleVLA-RL.git
cd SimpleVLA-RL

# Apply RoboTwin modifications
bash copy_overwrite_robotwin2.sh <your_robotwin_path> <your_simplevlarl_path>
# Example: bash copy_overwrite_robotwin2.sh /mnt/petrelfs/SimpleVLA-RL /mnt/petrelfs/RoboTwin
```

## Troubleshooting

- If you encounter issues with RoboTwin 2.0 installation, refer to the [RoboTwin documentation](https://robotwin-platform.github.io/doc/) or check their GitHub issues
- All repositories (veRL, OpenVLA-OFT, RoboTwin) are recommended to be cloned at the same directory level as SimpleVLA-RL.

## Directory Structure

After installation, your directory structure should look like:
```
your_workspace/
├── SimpleVLA-RL/
├── verl/
├── openvla-oft/
├── LIBERO/          (for Option 1)
└── RoboTwin/        (for Option 2)
```

---

### 🤖 Cursor Assistant

I need to first retrieve the content of the second paper, then synthesize both papers and the existing documentation to write a comprehensive Chinese README.

---

### 🤖 Cursor Assistant

Based on the two papers and the provided documentation, I will write a comprehensive Chinese README for you.

---

### 🤖 Cursor Assistant

I have written a comprehensive Chinese README based on the two papers and the provided documentation. Key features include:

## ✨ Key Improvements

### 1. **More Complete Structure**
- Added a detailed table of contents
- Includes research background and motivation
- Detailed technical architecture introduction

### 2. **In-depth Explanation of Core Technologies**
- Detailed explanation of three key technologies (Dynamic Sampling, Higher Clipping Boundary, Higher Inference Temperature)
- Each technology includes: Problem, Solution, Code Example, and Effect Demonstration

### 3. **More Detailed Experimental Results**
- Detailed data from LIBERO benchmark tests
- Impressive cold-start experiment results (+430%)
- Introduction to RoboTwin 2.0

### 4. **More Comprehensive Training Guide**
- Step-by-step configuration instructions
- Detailed explanation of key parameters
- Expected training time and hardware requirements

### 5. **New Important Sections**
- 📊 Detailed Training Process (In-depth explanation of GRPO, PPO)
- 🔍 Explanation of Important Concepts ("Push-Cut" phenomenon, Action Chunking mechanism)
- ⚠️ Important Notes (Configuration differences, monitoring metrics, exception handling)

### 6. **Enhanced Practicality**
- Provides a comparison table of paper settings vs. configuration files
- Specific thresholds for key monitoring metrics
- Solutions to common problems

### 7. **Chinese Localization**
- Uses standard Chinese expressions throughout
- Retains necessary English technical terms
- Added explanations and examples suitable for Chinese readers

This README is not just a usage guide, but a complete learning resource to help readers deeply understand the core ideas and implementation details of SimpleVLA-RL.

---

### 👤 You

{"root":{"children":[{"children":[],"format":"","indent":0,"type":"paragraph","version":1}],"format":"","indent":0,"type":"root","version":1}}

---

### 🤖 Cursor Assistant

I will update the README for you, adding the complete environment configuration process and project links.

---


*Exported from [Cursor View](https://github.com/saharmor/cursor-view)*