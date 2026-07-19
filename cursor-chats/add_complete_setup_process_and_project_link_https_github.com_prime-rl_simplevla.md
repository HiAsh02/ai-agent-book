# Cursor Chat: ai-agent-book

## Metadata
- **Project**: ai-agent-book
- **Path**: `/Users/boj`
- **Date**: 2025-10-05 19:11:24
- **Session ID**: `f4b19584-855a-4b03-88ce-842901ee6cc3`

## Conversation

### 👤 You

Need to supplement the complete setup process and the project link @https://github.com/PRIME-RL/SimpleVLA-RL/

Make modifications based on the following content:
@@ -27,7 +27,20 @@ pip3 install -e .
 cd ..
 ```

-#### Step 2: Install LIBERO and OpenVLA-OFT
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
+#### Step 3: Install LIBERO and OpenVLA-OFT

 Follow the official [OpenVLA-OFT installation guide](https://github.com/moojink/openvla-oft):

@@ -61,7 +74,11 @@ pip install -r experiments/robot/libero/libero_requirements.txt

 Same as Option 1, Step 1.

-#### Step 2: Install RoboTwin 2.0
+#### Step 2: Install EGL Libraries for Headless Rendering
+
+Same as Option 1, Step 2.
+
+#### Step 3: Install RoboTwin 2.0


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

#### Step 2: Install LIBERO and OpenVLA-OFT

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

Same as Option 1, Step 1.

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
- All repositories (veRL, OpenVLA-OFT, RoboTwin) are recommended to clone at the same directory level as SimpleVLA-RL

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


## Supporting Additional Tasks in RoboTwin 2.0 (Optional) 

### Step 1: Collect Feasible Seeds

RoboTwin 2.0 tasks may have infeasible seeds (e.g., objects beyond arm reach). To optimize RL training, we pre-collect feasible seeds to avoid repeated validation during training epochs.

**Collection Process:**

1. Update `DATASET_NAME` in `pre_collect_robotwin2_seed.sh` with your target task name
2. Run the collection script:
   ```bash
   sh pre_collect_robotwin2_seed.sh
   ```
3. This generates `robotwin2_train_seeds.json` in the SimpleVLA-RL directory
4. Add the JSON content to:
   ```
   SimpleVLA-RL/verl/utils/envs/robotwin2/seeds/robotwin2_train_seeds.json
   ```

### Step 2: Register New Tasks

1. Add task name in `SimpleVLA-RL/verl/utils/dataset/rob_dataset.py`2. Add task name and corresponding max steps in `SimpleVLA-RL/verl/workers/rollout/rob_rollout.py`

### Step 3: Implement Task-Specific Functions

Add a `get_info()` function in the corresponding task file under `SimpleVLA-RL/verl/utils/envs/robotwin2/envs/task_name.py`.

For implementation reference, see:
```
SimpleVLA-RL/modified_codes/robotwin2/envs/handover_block.py
```

---

### 🤖 Cursor Assistant

Let me help you supplement the complete `SETUP.md` file for the SimpleVLA-RL project by adding the EGL Libraries installation steps and project links.

---

### 🤖 Cursor Assistant

I found that the `SETUP.md` file does not exist. I will create a complete `SETUP.md` file based on the content you provided, which already includes the EGL Libraries installation steps.

---

### 🤖 Cursor Assistant

Done! I have created the complete `SETUP.md` file with the following improvements:

## Main Updates:

### ✅ Added Content:
1. **Project Links** - Added GitHub repository link at the top of the file
2. **EGL Libraries Installation Steps** - Added as Step 2 in both installation options:
   - For headless rendering support
   - Resolves `eglQueryString` errors during SAPIEN/robot environment initialization
3. **Enhanced Troubleshooting Section** - Added explanations for EGL-related errors
4. **Verification Steps** - Added verification commands after installation
5. **Clearer Structure** - Renumbered steps to accommodate the new EGL installation step

## File Structure:

```
SimpleVLA-RL Installation Guide
├── Option 1: LIBERO Benchmark
│   ├── Step 1: Install veRL
│   ├── Step 2: Install EGL Libraries ⭐ (New)
│   └── Step 3: Install LIBERO and OpenVLA-OFT
└── Option 2: RoboTwin 2.0 Benchmark
    ├── Step 1: Install veRL
    ├── Step 2: Install EGL Libraries ⭐ (New)
    ├── Step 3: Install RoboTwin 2.0
    ├── Step 4: Install OpenVLA-OFT
    └── Step 5: Configure RoboTwin for SimpleVLA-RL
```

File saved to: `/Users/boj/ai-agent-book/projects/week7/SimpleVLA-RL/SETUP.md`

This installation guide now provides a complete, actionable setup process, with special emphasis on the importance of EGL libraries for headless server environments.

---

### 👤 You

No, I need you to supplement the complete setup process in Chinese into the README.

---

### 🤖 Cursor Assistant

I understand! You want me to supplement the complete setup process in Chinese into the `README.md` file. Let me first check the existing content of the README.md.

---

### 🤖 Cursor Assistant

I understand! I need to supplement the complete setup process in Chinese into the "Quick Start" section of the README.md. Let me modify the environment configuration section in README.md.

---

### 🤖 Cursor Assistant

Now let me delete the previously created separate `SETUP.md` file, since the complete setup process has been integrated into the README.md in Chinese:

---

### 🤖 Cursor Assistant

Done! I have successfully completed the following updates:

## ✅ Completed Modifications

### 1. **Added Project Link**
Added the GitHub repository link at the top of README.md:
```markdown
**Project Address**: [https://github.com/PRIME-RL/SimpleVLA-RL/](https://github.com/PRIME-RL/SimpleVLA-RL/)
```

### 2. **Replaced the Brief Description with a Complete Chinese Setup Process**
Expanded the "Step 1: Environment Configuration" section from a short dependency list into a complete installation guide, including:

#### Option 1: LIBERO Benchmark
- **Step 1.1**: Install veRL
- **Step 1.2**: Install EGL Libraries for Headless Rendering Support ⭐ (New)
- **Step 1.3**: Install LIBERO and OpenVLA-OFT

#### Option 2: RoboTwin 2.0 Benchmark
- **Step 2.1**: Install veRL
- **Step 2.2**: Install EGL Libraries for Headless Rendering Support ⭐ (New)
- **Step 2.3**: Install RoboTwin 2.0
- **Step 2.4**: Install OpenVLA-OFT
- **Step 2.5**: Configure RoboTwin for SimpleVLA-RL

### 3. **Added Important Sections**
- ✅ Troubleshooting Guide
- ✅ Directory Structure Explanation
- ✅ Installation Verification Commands
- ✅ RoboTwin 2.0 Additional Task Configuration (Optional)
  - Collect Feasible Seeds
  - Register New Tasks
  - Implement Task-Specific Functions

### 4. **Cleanup**
Deleted the previously created separate `SETUP.md` file. All content is now in `README.md`.

Now the README.md contains a complete, actionable Chinese setup guide, with special emphasis on the importance of EGL libraries for headless server environments. Users can follow the steps directly for installation and configuration!

---


*Exported from [Cursor View](https://github.com/saharmor/cursor-view)*