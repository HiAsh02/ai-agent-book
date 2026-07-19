# VIRL-VL: Vision-Language Navigation with Reinforcement Learning

This document provides a detailed introduction to the design, implementation, and evaluation methods of the Vision-Language Navigation Reinforcement Learning experiment based on the V-IRL platform.

**V-IRL (Virtual Intelligence in Real Life)** is an open-source platform for building and testing virtual agents, enabling agents to interact in virtual real-world environments using real geospatial data and street view imagery.

## Table of Contents

- [1. Experiment Overview](#1-experiment-overview)
- [2. Experiment Objectives](#2-experiment-objectives)
- [3. Experiment Results](#3-experiment-results)
- [4. Environment Setup](#4-environment-setup)
- [5. Task Definition](#5-task-definition)
- [6. Action Space](#6-action-space)
- [7. RL Environment Details](#7-rl-environment-details)
- [8. Trajectory Generation Mechanism](#8-trajectory-generation-mechanism)
- [9. Dataset](#9-dataset)
- [10. Vision Input Processing](#10-vision-input-processing)
- [11. RL Training Process](#11-rl-training-process)
- [12. Hyperparameter Configuration](#12-hyperparameter-configuration)
- [13. Evaluation Methods](#13-evaluation-methods)
- [14. Experimental Results Analysis](#14-experimental-results-analysis)
- [15. References](#15-references)

---

## 1. Experiment Overview

This experiment implements the Vision-Language Navigation task based on the **V-IRL (Virtual Intelligence in Real Life)** platform, aiming to verify the **advantages of Reinforcement Learning (RL) over Supervised Fine-Tuning (SFT) in visual generalization capability**.

**V-IRL Platform Introduction**:
- **Platform Positioning**: An open-source platform for building and testing virtual agents, enabling agents to perceive, reason, and act in virtual but realistic environments
- **Core Features**:
  - Utilizes real-world geospatial data and street view imagery
  - Supports city-wide navigation and task execution globally
  - Provides rich sensory inputs (vision, geolocation, place information, etc.)
  - Supports multiple task types (navigation, place recommendation, urban planning, collaboration, etc.)
- **Technical Foundation**: Based on Google Maps Platform's Street View and geospatial APIs

**Core Findings of This Experiment**:
- RL-trained models can generalize to visually out-of-distribution (OOD) environments
- SFT-trained models tend to memorize training data and generalize poorly in OOD scenarios
- RL improves the model's underlying visual recognition capability through outcome-based reward

**Paper Source**: [SFT Memorizes, RL Generalizes](https://arxiv.org/pdf/2501.17161)  
**Code Repository**:
- **Recommended (my fork version)**：[bojieli/SFTvsRL](https://github.com/bojieli/SFTvsRL/) ⭐
- Official version：[LeslieTrue/SFTvsRL](https://github.com/LeslieTrue/SFTvsRL)

---

## 2. Experiment Objectives

### 2.1 Research Questions

Answer the following core questions:
1. **Visual Generalization**: Can a Vision-Language Model transfer navigation skills learned in one city (NYC) to a city with a completely different visual appearance (San Francisco)?
2. **Training Method Comparison**: Which method, SFT or RL, learns more generalizable visual representations?
3. **Source of RL Advantage**: Why does RL improve visual generalization? Does it enhance underlying visual recognition?

### 2.2 Experiment Design Principles

**Controlled Variables**:
- Same base model (Llama-3.2-11B-Vision)
- Same task environment (V-IRL platform navigation task)
- Same evaluation metrics (per-step accuracy, success rate)

**Independent Variables**:
- Training method: SFT vs RL (PPO)
- Visual environment: In-Distribution (NYC) vs Out-of-Distribution (San Francisco)
- Action space: Absolute directions vs Relative directions

---

## 3. Experiment Results

### 3.1 Main Results

According to the paper's Figure 1 and experimental results:

| Metric | SFT | RL (PPO) | Improvement |
|--------|-----|----------|-------------|
| **In-Distribution Per-Step Accuracy** | ~85% | ~90% | +5% |
| **Rule OOD Per-Step Accuracy** | ~15% | ~70% | +55% |
| **Visual OOD Generalization** | Failed (<10%) | Successful (~60%) | +50% |
| **V-IRL Mini Benchmark** | 44.0% | 77.8% | **+33.8%** |

### 3.2 Key Findings

1. **RL Achieves Visual Generalization**:
   - In the San Francisco (visual OOD) environment, the RL model maintains ~60% per-step accuracy
   - The SFT model drops to <10% in the same environment, close to random guessing

2. **RL Improves Visual Recognition Capability**:
   - Ablation experiments show that RL-trained models improve accuracy on the card recognition task (GeneralPoints-VL)
   - This indicates that RL not only learns navigation strategies but also improves the underlying visual encoder

3. **Necessity of SFT**:
   - Training RL directly from the base model fails (cannot output structured JSON)
   - SFT acts as a "format teacher" to stabilize output format, enabling effective RL training

---

## 4. Environment Setup

### 4.1 System Requirements

```bash
# Hardware Requirements
- GPU: 8×H100/H800/A100 (80GB) for training
- Memory: 1000GB RAM for training
- Storage: ~500GB for NYC route data + street views + checkpoints

# Software Environment
- Python: 3.13.0
```

### 4.2 Installation Steps

```bash
# 1. Clone repository (use the fixed fork version)
git clone https://github.com/bojieli/SFTvsRL.git
cd SFTvsRL

# 2. Create conda environment
conda create -n SFTvsRL python==3.13 -y
conda activate SFTvsRL

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install gym environments
cd gym
pip install -e .
cd ..

# 5. Download data from HuggingFace
huggingface-cli download tianzhechu/SFTvsRL_Data --local-dir ./data

# 6. Login to wandb (create an account on wandb.ai to obtain API key)
wandb login
```

### 4.3 Official Code Bugs and Fixes

**Problem Description**:

The official [LeslieTrue/SFTvsRL](https://github.com/LeslieTrue/SFTvsRL) repository has a serious bug that prevents saving checkpoints after training:

```python
# rl/trainer/base_trainer.py (official version, line 38)
def __init__(self, ..., save_every=None, ...):
    ...
    self.save_ckpt = save_ckpt
    self.save_every = None  # ❌ BUG: Hardcoded to None, ignores configuration parameter!
```

**Bug Impact**:

```python
# In the training loop
for update in range(self.num_updates):
    if self.save_ckpt:
        save_model = (update + 1) % self.save_every == 0  # ❌ TypeError!
        # Because self.save_every = None, modulo operation fails
```

Even with `save_every: 1` set in the configuration file, training will throw an error:

```
TypeError: unsupported operand type(s) for %: 'int' and 'NoneType'
```

**Fix**:

The [bojieli/SFTvsRL](https://github.com/bojieli/SFTvsRL/) fork fixes this issue:

```python
# rl/trainer/base_trainer.py (fixed, line 38)
def __init__(self, ..., save_every=None, ...):
    ...
    self.save_ckpt = save_ckpt
    self.save_every = save_every  # ✅ Correctly uses the configuration parameter
```

**Fixed Files**:

1. `rl/trainer/base_trainer.py`: Fixed `save_every` parameter passing
2. `rl/configs/llama_virl_vl.yaml`: Added missing `save_every: 1` configuration

**Why is this fix needed?**

```
After 15 hours of training:
- Official version: ❌ Cannot save checkpoint, losing training progress
- Fixed version: ✓ Successfully saves checkpoint, enabling evaluation and continued training
```

### 4.4 Data Download and Path Configuration

#### 4.4.1 Download Data

```bash
# 1. Create data directory
mkdir -p /root/SFTvsRL_Data
cd /root/SFTvsRL_Data

# 2. Download VIRL data (from HuggingFace)
huggingface-cli download tianzhechu/SFTvsRL_Data \
    --include "VIRL_routes/*" \
    --local-dir .

# 3. Unzip data
cd VIRL_routes
unzip nyc_1k_routes.zip
unzip VLN_mini.zip  # For Visual OOD evaluation

# 4. Verify directory structure
ls -la nyc_1k_routes/
# Should see:
# - route_infos.json
# - gps_pano_mapping.pkl
# - street_views/
```

#### 4.4.2 Final Directory Structure

```
/root/SFTvsRL_Data/
└── VIRL_routes/
    ├── nyc_1k_routes/              # NYC training data
    │   ├── route_infos.json        # Route information
    │   ├── gps_pano_mapping.pkl    # GPS to panorama ID mapping
    │   └── street_views/           # Street view image directory
    │       ├── pano_XXX_h000.jpg
    │       ├── pano_XXX_h090.jpg
    │       └── ...
    ├── VLN_mini/                   # San Francisco OOD data
    │   ├── route_infos.json
    │   ├── gps_pano_mapping.pkl
    │   └── street_views/
    └── ...
```

#### 4.4.3 Configure Training Script Paths (Optional)

If you do not have access to `/root`, configure the paths in `scripts/virl_training/vl_train.sh`:

```bash
BASE_DIR="/root/SFTvsRL_Data/VIRL_routes"
```

---

## 4.5 Start Training

After completing data download and configuration, you can directly run training:

```bash
# 1. Enter the code directory
cd /root/SFTvsRL

# 2. Activate environment
conda activate SFTvsRL

# 3. Start training (using the pre-configured script)
bash scripts/virl_training/vl_train.sh
```

**The training script automatically uses the following paths** (configured in the script):

```bash
BASE_DIR="/root/SFTvsRL_Data/VIRL_routes"
ROUTE_INFO="${BASE_DIR}/nyc_1k_routes/route_infos.json"
GPS_TO_PANO="${BASE_DIR}/nyc_1k_routes/gps_pano_mapping.pkl"
STREETVIEWS="${BASE_DIR}/nyc_1k_routes/street_views/"
```

**Expected Output**:```
Parsed instruction: ['First, turn right to face north.', ...]
Collecting Trajectories: 100%|████████| 256/256 [40:25<00:00]
PPO Training Epoch 0/4: 100%|████████| 256/256 [05:12<00:00]
PPO Training Epoch 1/4: 100%|████████| 256/256 [05:10<00:00]
...
Saving checkpoint to: train_ckpt/virl_vl/checkpoint-epoch-4/
```

**Check the checkpoint after training**:

```bash
ls -lh train_ckpt/virl_vl/
# Should see (if save_every=5):
# checkpoint-epoch-4/
# checkpoint-epoch-9/
# checkpoint-epoch-14/
```

---

## 5. Task Definition

### 5.1 Navigation Task Description

**Task**: The agent (VLM) must navigate to a target location in real-world street scenes based on natural language instructions.

**Input**:
1. **Global Instruction**: A complete description of the navigation route.
   ```
   1. First, turn left to face south.
   2. Move forward until you reach next intersection where Battery Park is nearby.
   3. Turn right to face west.
   4. Move forward until you reach destination.
   ```

2. **Visual Observation**: A 2×2 grid of street view images (4 directions).
   ```
   ┌─────────┬─────────┐
   │ Front   │ Right   │
   ├─────────┼─────────┤
   │ Back    │ Left    │
   └─────────┴─────────┘
   ```
   - Each image: 640×640 pixels
   - Total image size: 1280×1280 pixels (with 5px separator)
   - Actual model input: 2405×2405 pixels (1200×2 + 5)

3. **History Sequence (Observation-Action Sequence)**:
   ```
   O_0: "No landmarks nearby; You observe an intersection"
   A_0: "turn_direction(south)"
   O_1: "Battery Park on your right; No intersection"
   A_1: "forward()"
   ...
   ```

**Output**: A structured JSON action.
```json
{
  "current observation": "Battery Park on your right; You observe an intersection",
  "current instruction": "Turn right to face west",
  "action": "turn_direction(west)"
}
```

### 5.2 Success Conditions

An episode is successful if:
1. ✓ The correct destination is reached (executing `stop()` at the correct location).
2. ✓ Each waypoint is executed correctly within the allowed number of verification attempts (default 2).
3. ✓ The maximum number of steps is not exceeded.

---

## 6. Action Space

### 6.1 Absolute Action Space

The default action space used during training:

```python
ACTION_SPACE = [
    "forward()",                    # Move forward one step
    "turn_direction(north)",        # Turn to face north (0°)
    "turn_direction(northeast)",    # Turn to face northeast (45°)
    "turn_direction(east)",         # Turn to face east (90°)
    "turn_direction(southeast)",    # Turn to face southeast (135°)
    "turn_direction(south)",        # Turn to face south (180°)
    "turn_direction(southwest)",    # Turn to face southwest (225°)
    "turn_direction(west)",         # Turn to face west (270°)
    "turn_direction(northwest)",    # Turn to face northwest (315°)
    "stop()"                        # Stop (destination reached)
]
```

**Features**:
- Uses absolute direction terms (compass directions).
- Independent of the agent's current heading.
- Aligns with natural human navigation habits.

### 6.2 Relative Action Space

The action space used for Rule OOD evaluation:

```python
ACTION_SPACE_RELATIVE = [
    "forward()",                      # Move forward one step
    "turn_direction(left)",           # Turn left (~-90°)
    "turn_direction(right)",          # Turn right (~+90°)
    "turn_direction(slightly left)",  # Turn slightly left (-45° to 0°)
    "turn_direction(slightly right)", # Turn slightly right (0° to +45°)
    "stop()"                          # Stop
]
```

**Features**:
- Uses relative directions (relative to the current heading).
- Tests the model's generalization ability to different instruction formats.
- Action semantics are completely different, but the task objective is the same.

### 6.3 Action Space Configuration

Set in the configuration file:

```yaml
# rl/configs/llama_virl_vl.yaml
env_config:
  absolute_action: true  # True: Absolute, False: Relative
```

Override in training/evaluation scripts:

```bash
# Training with absolute actions
--env_config.absolute_action=True

# Evaluation with relative actions (Rule OOD)
--env_config.absolute_action=False
```

---

## 7. RL Environment Details

### 7.1 Environment Class Structure

VIRL uses the OpenAI Gym interface:

```python
class NavigationEnvironment(gym.Env):
    """
    V-IRL Navigation Environment
    
    Main Components:
    - Platform: Google Street View interface
    - Ground Truth Rail: Precomputed correct path
    - Verification System: Action verification and feedback mechanism
    """
    
    def __init__(self, 
        route_info_path,      # Path to route data
        resolution=1200,      # Image resolution
        verify_iter=2,        # Number of attempts per waypoint
        absolute_action=True, # Action space type
        relocation=True,      # GPS relocation to nearest panorama point
        drop_rate=0.5,        # Drop rate for interpolated points between waypoints
        ...
    )
```

### 7.2 Ground Truth Rail

The environment precomputes a "rail" (reference trajectory) containing:

1. **Dense waypoints**:
   - Original route: 5-10 intersections
   - After interpolation: one point every 5-10 meters
   - Total: ~20-40 waypoints per route

2. **Each waypoint contains**:
   ```python
   waypoint = {
       'geocode': [40.758, -73.985],           # GPS coordinates
       'heading': 180,                          # Heading (degrees)
       'gt_action': 'turn_direction(south)',   # Correct action
       'observation': 'Battery Park on right', # Landmark description
       'intersection_observation': 'You observe an intersection',
       'instruction': 'Turn left to face south',  # Current instruction to execute
       'instruction_idx': 1                     # Instruction index
   }
   ```

### 7.3 Verification Mechanism

**Multiple Attempt Mechanism** (`verify_iter=2`):

```python
# Step 1: Agent outputs an action
agent_action = model.generate(obs, instruction, history)

# Step 2: Compare with ground truth
if agent_action == gt_action:
    reward = +1  # CORRECT_ACTION
    move_to_next_waypoint()
    remaining_attempts = verify_iter  # Reset attempt count
else:
    reward = -1  # INCORRECT_ACTION
    remaining_attempts -= 1
    
    if remaining_attempts > 0:
        # Stay at current position, provide feedback, allow retry
        feedback = f"Incorrect action. Expected {gt_action}"
        stay_at_current_position()
    else:
        # Attempts exhausted, force move to next waypoint (penalty)
        reward = -1
        force_move_to_next_waypoint()
```

**Reward Function**:

```python
REWARD_FN_VIRL = {
    "CORRECT_ACTION": +1,           # Action is correct
    "INCORRECT_ACTION": -1,         # Action is incorrect
    "INCORRECT_OBS": -1.5,          # Observation description error (incorrectly detecting intersection)
    "INCORRECT_INSTRUCTION": -1.75  # Instruction understanding error
}
```

### 7.4 Episode Termination Conditions

An episode ends when any of the following occurs:

1. **Success**: `done=True, is_success=True`
   - Executes `stop()` at the correct location.
   
2. **Failure**: `truncated=True, is_success=False`
   - Exceeds the maximum number of steps (determined by rail length, typically 20-40 steps).
   
3. **Forced Advance**: `is_success=False`
   - Attempts for a waypoint are exhausted, forced to advance.
   - Episode continues but is marked as a failure.

### 7.5 Environment Configuration

```yaml
# rl/configs/llama_virl_vl.yaml
env_config:
  id: 'gym_virl/Navigation-v0'
  route_info_path: "..."           # Route data
  resolution: 1200                 # Street view image resolution
  verify_iter: 2                   # Verification attempt count
  absolute_action: true            # Action space type
  relocation: true                 # GPS relocation
  drop_rate: 0.5                   # Waypoint sampling rate
  straight_line_length: 5          # Number of interpolation points between two intersections
  
  platform_cfg:
    STREET_VIEW:
```      SIZE: [640, 640]             # Single street view size
      HEADING: 0                   # Default heading
      PITCH: 0                     # Pitch angle
      FOV: 90                      # Field of view
      SOURCE: outdoor              # Street view source
    
    OFFLINE:
      ENABLED: True                # Use offline cache
      PANORAMA_DIR: "..."          # Street view image directory
      GPS_TO_PANO_PATH: "..."      # GPS to panorama ID mapping
      MAPPING_RADIUS: 20           # Relocation search radius (meters)
```

---

## 8. Trajectory Generation Mechanism

### 8.1 Trajectory Collection During Training

**Collect 256 steps per update** (not episodes):

```python
def collect_trajectories(self):
    """
    Collect 256 environment interaction steps
    May span multiple episodes (routes)
    """
    obs, info = self.env.reset()  # Initialize first route
    
    for step in range(256):
        # 1. Construct prompt
        prompt = format_prompt(
            global_instruction=info['global_instruction'],
            obs_act_seq=info['obs_act_seq'],
            current_obs=obs
        )
        
        # 2. Model generates action (inference)
        with torch.no_grad():
            # Process 4 street view images
            obs_image = convert_to_2x2_grid(obs)  # [2400, 2400, 3]
            
            # VLM forward pass
            values, io_dict, output_text, action_log_prob = \
                actor_critic.act_oneline(
                    inputs=(obs_image, prompt),
                    temperature=0.2,
                    max_new_tokens=512
                )
            
            # Parse JSON output
            action = parse_json(output_text)['action']
        
        # 3. Execute action
        obs_next, reward, done, truncated, info = env.step(output_text)
        
        # 4. Store in rollout buffer
        rollouts.insert(
            obs={"image": obs, "io_dict": io_dict},
            action_log_prob=action_log_prob,
            value=values,
            reward=reward,
            mask=1-done
        )
        
        running_reward += reward
        
        # 5. Episode management
        if done or truncated:
            # Current episode ends, start new episode
            log_episode_reward(running_reward)
            running_reward = 0
            obs, info = env.reset()  # Load new route
        else:
            obs = obs_next
    
    return rollouts  # Data for 256 steps
```

**Key Points**:
- 256 steps may contain 10-15 complete episodes (depending on route length)
- The last episode may be incomplete (truncated)
- All data is saved for PPO training

### 8.2 Multi-Episode Trajectory Example

```
Update 1: Collect 256 steps
├─ Episode 1 (Route A, 14 steps): Success ✓
│  └─ Steps 0-13: [turn_direction(south), forward(), ..., stop()]
│
├─ Episode 2 (Route B, 22 steps): Success ✓
│  └─ Steps 14-35: [...]
│
├─ Episode 3 (Route C, 18 steps): Failed ✗
│  └─ Steps 36-53: [...] (exceeded attempts at waypoint 12)
│
├─ Episode 4 (Route D, 16 steps): Success ✓
│  └─ Steps 54-69: [...]
│
├─ ...
│
└─ Episode N (Route X, partial): Truncated
   └─ Steps 240-255: [...] (episode incomplete, but data still used for training)
```

### 8.3 LLM Input and Output Examples

LLM Input Example:

```
<|begin_of_text|><|start_header_id|>user<|end_header_id|>

<|image|>
[Task Description]
You are an expert in navigation. You will receive a sequence of instructions to follow while observing your surrounding street views. You
are also provided with your observation and action history in text. Your goal is to first analyze the instruction and identify the next sentence to be executed.
Then, you need to provide the action to be taken based on the current observation and instruction.

[Instruction]
1. First, turn left to face northeast.
2. Move forward until you reach next intersection where Battery Playscape is on your right behind.
3. Turn right to face north.
4. Move forward until you reach next intersection.
5. Turn slightly left to face northwest.
6. Move forward until you reach next intersection.
7. Turn left to face north.
8. Move forward until you reach next intersection.
9. Turn right to face southeast.
10. Move forward until you reach next intersection.
11. Turn right to face south.
12. Move forward until you reach destination where The destination Cafe De Novo is on your right.


[Observation format]
You observe a 2x2 grid of streetview images with the following headings:
[front, right
 back, left]
You need to identify if any of the landmarks in the instruction are visible in the street view grid.

[Action space]
"forward()": indicates moving forward one step
"turn_direction(x)": indicates adjust the ego agent direction towards x direction. x could be any following 8 directions ['north', 'northeast', 'east', 'southeast', 'south', 'southwest', 'west', 'northwest']
"stop()": indicates the navigation is finished.

[Observations and actions sequence]
O_1: No landmarks nearby;
A_1: turn_direction(northeast)
O_2: No landmarks nearby;
A_2: forward()
O_3: No landmarks nearby;
A_3: forward()
O_4: Battery Playscape is on your right behind; You observe an intersection
A_4: turn_direction(north)
O_5: No landmark nearby; You observe an intersection
A_5: turn_direction(northwest)
O_6: No landmarks nearby;
A_6: forward()
O_7: No landmarks nearby;
A_7: forward()
O_8: No landmarks nearby;
A_8: forward()
O_9: No landmark nearby; You observe an intersection
A_9: turn_direction(north)
O_10: No landmarks nearby;
A_10: forward()
O_11: No landmarks nearby;
A_11: forward()
O_12: No landmarks nearby;
A_12: forward()
O_13: You observe an image of 4 views; You observe an intersection
A_13:


[Output]
{
  "current observation": latest observation from the street view grid,
  "current instruction": analyze the full instruction and identify the sentence to be executed,
  "action": the action to be taken chosen from the action space,
}
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
```

LLM Output Example:

```
{
  "current observation": "No landmark nearby; You observe an intersection",
  "current instruction": "Turn right to face southeast.",
  "action": "turn_direction(southeast)",
}
```

---

## 9. Dataset

### 9.1 Training Dataset

**NYC 1K Routes**:

```
Data Source: Collected via Google Maps API
Number of Routes: 1,000
Coverage Area: Manhattan, Brooklyn, Queens, New York City
Total Waypoints: ~20,000-30,000
Street View Images: ~100,000 (640×640, 4 directions/location)
```

**Data Structure**:

```json
// route_infos.json
[
  [  // Route list
    {      "route_id": "nyc_001",
      "start_place": {
        "name": "Times Square",
        "geocode": [40.758, -73.985],
        "relocated_geocode": [40.7580, -73.9855]
      },
      "dest_place": {
        "name": "Central Park South",
        "geocode": [40.767, -73.979]
      },
      "init_heading": 0,
      "milestone_info": "Turn left to face south. Move forward...",
      "route_results": {
        "geocode_list": [[40.760, -73.984], ...],
        "landmark_list": ["Battery Park", "Plaza Hotel", ...]
      }
    },
    ...
  ],
  1000  // Total number of routes
]
```

**Street View Cache**:

```
nyc_1k_routes/street_views/
├─ pano_XXX_h000.jpg  # Heading 0° (Front)
├─ pano_XXX_h090.jpg  # Heading 90° (Right)
├─ pano_XXX_h180.jpg  # Heading 180° (Back)
└─ pano_XXX_h270.jpg  # Heading 270° (Left)
```

**GPS Mapping**:

```python
# gps_pano_mapping.pkl
{
    (40.758, -73.985): "pano_ABC123",  # GPS -> Panorama ID
    (40.759, -73.984): "pano_DEF456",
    ...
}
```

### 9.2 Evaluation Datasets

| Dataset | Type | Routes | Data Path | Purpose |
|---------|------|--------|-----------|---------|
| **NYC Test (In-Dist)** | In-Distribution | 48 | `/root/SFTvsRL_Data/VIRL_routes/nyc_1k_routes/` | Test training distribution performance |
| **NYC Test (Rule OOD)** | Rule OOD | 48 | `/root/SFTvsRL_Data/VIRL_routes/nyc_1k_routes/` | Test relative action generalization |
| **SF Routes (Visual OOD)** | Visual OOD | 18 | `/root/SFTvsRL_Data/VIRL_routes/VLN_mini/` | Test visual environment generalization |

**Visual OOD Data Characteristics** (San Francisco, VLN_mini):
- Different architectural styles (Victorian vs Modern)
- Different terrain (Hills vs Flat)
- Different color distributions (Pastel houses vs Glass buildings)
- Different landmark types (Cable cars, Golden Gate vs Yellow cabs, Statue of Liberty)

### 9.3 Data Statistics

```
NYC 1K Routes (Training + In-Dist/Rule OOD Evaluation):
- Location: /root/SFTvsRL_Data/VIRL_routes/nyc_1k_routes/
- Number of Routes: 1,000
- Street View Images: ~100,000
- Data Size: ~30-40 GB

VLN_mini (Visual OOD Evaluation):
- Location: /root/SFTvsRL_Data/VIRL_routes/VLN_mini/
- Number of Routes: 18 (San Francisco)
- Street View Images: ~2,000
- Data Size: ~1-2 GB
```

---

## 10. Vision Input Processing

### 10.1 Why Use 4-Direction Images Instead of Panoramas?

**Problem**: The Google Street View API provides 360° panoramas (equirectangular panorama). Why convert them into 4 static images?

#### Design Motivation

1. **Computational Efficiency**
   - Panorama: 2048×1024 or larger (~2-6 MB/image)
   - 4 static images: 4 × 640×640 = ~1.2 MB
   - Storage and loading speed improved by 2-5x

2. **Model Input Constraints**
   - Vision Transformers are sensitive to input dimensions
   - Processing a 2×2 grid (2405×2405) is more aligned with standard model training than a panorama (2048×1024)
   - The 2×2 grid is nearly square, reducing padding and distortion

3. **Task Relevance**
   - Human navigation also focuses on the four cardinal directions: front, back, left, right
   - No need to look up or down (pitch = 0°)
   - The 4 directions contain all the information needed for navigation

4. **Data Augmentation Flexibility**
   - Each direction can be processed independently
   - Easily extensible to different heading configurations
   - Facilitates attention visualization (which direction is more important)

5. **Consistency with V-IRL Original Design**
   - The V-IRL paper (Yang et al., 2024) originally used the 4-direction design
   - Maintaining consistency facilitates comparison of experimental results

#### Technical Comparison

| Approach | Panorama | 4 Static Images |
|----------|----------|-----------------|
| **Resolution** | 2048×1024 | 4 × 640×640 |
| **File Size** | 2-6 MB | 1.2 MB |
| **FOV Coverage** | 360° × 180° | 4 × 90° = 360° (Horizontal) |
| **Processing Complexity** | Requires equirectangular projection handling | Direct use |
| **Model Adaptation** | Requires special handling | Standard 2D CNN/ViT |
| **Storage Cost** | High (100K × 6MB = 600GB) | Low (100K × 1.2MB = 120GB) |

#### Disadvantages of Panoramas

1. **Distortion**:
   - Equirectangular projection is severely distorted near the poles
   - Requires special preprocessing or model adaptation

2. **Information Redundancy**:
   - Sky and ground occupy many pixels but have low information value
   - Navigation primarily focuses on horizontal landmarks

3. **Computational Overhead**:
   - Larger images require more GPU memory
   - Training and inference speed decrease significantly

### 10.2 Street View Image Acquisition

```python
def _get_visual_observation(self):
    """
    Get 4-direction street view images for the current location
    
    Returns:
        np.array: RGB image of shape [2405, 2405, 3]
    """
    # 1. Get 4 images from the Platform
    image_list = self.platform.get_all_streetview_from_geocode(
        geocode=self.current_geocode,
        cur_heading=self.current_heading
    )
    # image_list = [front, right, back, left] (each 640×640)
    
    # 2. Resize to a uniform resolution
    resized_images = [
        image.resize((self.resolution, self.resolution))  # 1200×1200
        for image in image_list
    ]
    
    # 3. Concatenate into a 2×2 grid
    line_width = 5  # Black separator line
    canvas = Image.new('RGB', 
                       (self.resolution * 2 + line_width,   # 2405
                        self.resolution * 2 + line_width),  # 2405
                       (0, 0, 0))  # Black background
    
    # Place images:
    # [0,0] -> (0, 0)           Front
    # [1,0] -> (1205, 0)        Right
    # [0,1] -> (0, 1205)        Back
    # [1,1] -> (1205, 1205)     Left
    for i, image in enumerate(resized_images):
        x = (i % 2) * (self.resolution + line_width)
        y = (i // 2) * (self.resolution + line_width)
        canvas.paste(image, (x, y))
    
    return np.array(canvas)  # [2405, 2405, 3]
```

### 10.3 Visual Input Diagram

```
2×2 Street View Grid (2405 × 2405 pixels)

┌─────────────────────┬─────────────────────┐
│                     │                     │
│    Front View       │    Right View       │
│    (1200×1200)      │    (1200×1200)      │
│                     │                     │
│    Heading: 0°      │    Heading: 90°     │
│                     │                     │
├─────────────────────┼─────────────────────┤
│                     │                     │
│    Back View        │    Left View        │
│    (1200×1200)      │    (1200×1200)      │
│                     │                     │
│    Heading: 180°    │    Heading: 270°    │
│                     │                     │
└─────────────────────┴─────────────────────┘

Black separator line: 5 pixels
```

### 10.4 Llama-3.2-Vision Image Processing

```python
def formulate_payload(self, question, obs=None):
    """
    Construct the input format for Llama-3.2-Vision
    
    Args:
        question: Text prompt
        obs: PIL.Image or np.array
    """
    self.payload = [
        {
            "role": "user",
            "content": [{"type": "text", "text": question}]
        }
    ]
    
    if obs is not None:
        # Convert to PIL Image
        if isinstance(obs, np.ndarray):
            obs = Image.fromarray(obs)
        
        # Insert at the beginning of content (Llama format requirement)
        self.payload[0]['content'].insert(0, {
            "type": "image", 
            "image": obs
        })

def process_input(self, obs, prompt):
    """
    Process input using the processor
    """
    # 1. Apply chat template
    input_text = self.processor.apply_chat_template(
        self.payload, 
        add_generation_prompt=True
    )
    
    # 2. Process image + text```python
    inputs = self.processor(
        obs,           # PIL Image
        input_text,    # Formatted prompt
        return_tensors="pt",
        add_special_tokens=False
    ).to(self.model.device)
    
    # inputs = {
    #     'input_ids': tensor([[..., image_tokens, ..., text_tokens]]),
    #     'attention_mask': tensor([[1, 1, ..., 1]]),
    #     'pixel_values': tensor([[[...]]]),  # Processed image features
    #     'cross_attention_mask': tensor([[[...]]])
    # }
    
    return inputs
```

### 10.5 Vision Encoder Processing Flow

```
Input Image (2405×2405×3)
    ↓
Llama-3.2-Vision Processor
    ↓
├─ Image Processor:
│  ├─ Resize to model input size
│  ├─ Normalize (mean=[0.48145466, 0.4578275, 0.40821073])
│  └─ Convert to tensor
│
└─ Vision Encoder (CLIP-based):
   ├─ Patch Embedding (16×16 patches)
   ├─ Vision Transformer Layers
   └─ Output: Visual tokens (sequence length ~1000)
       ↓
Cross-Attention with Language Model
    ↓
Language Decoder generates action JSON
```

### 10.6 Vision-Related Hyperparameters

```yaml
# Image acquisition configuration
platform_cfg:
  STREET_VIEW:
    SIZE: [640, 640]        # Single raw image dimensions
    FOV: 90                 # Field of view (degrees)
    PITCH: 0                # Pitch angle (horizontal)
    SOURCE: outdoor         # Outdoor street view

# Environment configuration
env_config:
  resolution: 1200          # Resized dimension per image
  # Final input: 2×1200 + 5 = 2405 pixels

# Model configuration (Llama-3.2-Vision built-in)
model:
  vision_encoder:
    image_size: 560         # Model input size (auto-resized)
    patch_size: 14          # Patch embedding size
    hidden_size: 1280       # Vision hidden dimension
```

---

## 11. RL Training Process

### 11.1 Training Flow Overview

```
SFT Initialization
    ↓
┌────────────────────────────────────────┐
│   RL Training Loop (15 Updates)        │
│                                        │
│  For update in [0, 1, ..., 14]:       │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │  Phase 1: Rollout (256 steps)   │ │
│  │  ├─ Multiple episodes            │ │
│  │  ├─ Collect (obs, action, reward)│ │
│  │  └─ Compute value predictions    │ │
│  └──────────────────────────────────┘ │
│            ↓                           │
│  ┌──────────────────────────────────┐ │
│  │  Phase 2: PPO Training (4 epochs)│ │
│  │  ├─ Compute advantages (GAE)     │ │
│  │  ├─ 4 epochs × 256 samples       │ │
│  │  ├─ Update value network         │ │
│  │  └─ Update learning rate         │ │
│  └──────────────────────────────────┘ │
│                                        │
└────────────────────────────────────────┘
    ↓
Save Final Checkpoint
```

### 11.2 PPO (Proximal Policy Optimization) Algorithm Principle

PPO is an **on-policy** reinforcement learning algorithm proposed by OpenAI in 2017. It ensures training stability by limiting the magnitude of policy updates and is currently one of the most popular RL algorithms.

#### 11.2.1 Core Idea

**Problem Background**:

In policy gradient methods, we aim to maximize the expected return:

$$J(\theta) = \mathbb{E}_{\tau \sim \pi_\theta}[R(\tau)]$$

Traditional Policy Gradient methods (e.g., REINFORCE) update the policy directly using gradient ascent, but suffer from two issues:
1. **Low sample efficiency**: Collected data can only be used once
2. **Training instability**: Large policy updates can lead to performance collapse

**PPO's Solution**:

PPO enables data reuse through **importance sampling** while using a **clipping** mechanism to limit the magnitude of policy updates, balancing sample efficiency and training stability.

#### 11.2.2 Importance Sampling

Core question: How to use data collected by the old policy $\pi_{\theta_{old}}$ to update the new policy $\pi_\theta$?

**Importance Sampling Formula**:

$$\mathbb{E}_{a \sim \pi_{\theta_{old}}}[f(a)] = \mathbb{E}_{a \sim \pi_\theta}\left[\frac{\pi_\theta(a|s)}{\pi_{\theta_{old}}(a|s)} f(a)\right]$$

Here, $\frac{\pi_\theta(a|s)}{\pi_{\theta_{old}}(a|s)}$ is called the **importance ratio**.

**Application in RL**:

We can use trajectories collected by the old policy to estimate the expected return of the new policy:

$$J(\theta) \approx \sum_{t} r_t \cdot \frac{\pi_\theta(a_t|s_t)}{\pi_{\theta_{old}}(a_t|s_t)}$$

**Problem**: When $\pi_\theta$ diverges significantly from $\pi_{\theta_{old}}$, the variance of the importance ratio explodes, leading to training instability.

#### 11.2.3 PPO-Clip Objective Function

PPO uses a **clipping** mechanism to constrain the range of the importance ratio, preventing overly large policy updates.

**Define ratio**:

$$r_t(\theta) = \frac{\pi_\theta(a_t|s_t)}{\pi_{\theta_{old}}(a_t|s_t)}$$

**PPO-Clip Objective Function**:

$$L^{CLIP}(\theta) = \mathbb{E}_t\left[\min\left(r_t(\theta) \hat{A}_t, \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon) \hat{A}_t\right)\right]$$

Where:
- $\hat{A}_t$: advantage function, indicating how much better the action is compared to the average
- $\epsilon$: clip parameter ($\epsilon=0.1$ in this experiment)
- $\text{clip}(r, 1-\epsilon, 1+\epsilon)$: constrains $r$ to the range $[0.9, 1.1]$

**Intuitive Understanding**:

1. **When Advantage > 0** (good action):
   - If $r_t > 1.1$: clipping limits increase, preventing over-optimism
   - If $0.9 < r_t < 1.1$: normal update
   - If $r_t < 0.9$: no penalty (probability has already decreased)

2. **When Advantage < 0** (bad action):
   - If $r_t < 0.9$: clipping limits decrease, preventing over-pessimism
   - If $0.9 < r_t < 1.1$: normal update
   - If $r_t > 1.1$: no reward (probability has already increased)

**Mathematical Expression**:

$$
L^{CLIP}(\theta) = \mathbb{E}_t\left[\min\left(
\begin{cases}
r_t \hat{A}_t & \text{if } \hat{A}_t \geq 0 \\
\text{clip}(r_t, 1-\epsilon, 1+\epsilon) \hat{A}_t & \text{if } \hat{A}_t < 0
\end{cases}
\right)\right]
$$

This ensures the policy does not deviate too far from the old policy, thereby maintaining training stability.

#### 11.2.4 Advantage Calculation (GAE)

**Advantage Function Definition**:

$$A^\pi(s_t, a_t) = Q^\pi(s_t, a_t) - V^\pi(s_t)$$

It measures how good it is to take action $a_t$ in state $s_t$ compared to the average.

**Problem**: We do not have the true $Q$ and $V$; they need to be estimated.

**Generalized Advantage Estimation (GAE)**:

GAE is an advantage estimation method that balances bias and variance:

$$\hat{A}_t^{GAE(\gamma, \lambda)} = \sum_{l=0}^{\infty} (\gamma \lambda)^l \delta_{t+l}$$

Where:
- $\delta_t = r_t + \gamma V(s_{t+1}) - V(s_t)$: TD error (temporal difference error)
- $\gamma$: discount factor ($\gamma=0.9$ in this experiment)
- $\lambda$: GAE parameter ($\lambda=0.95$ in this experiment)

**Recursive Calculation** (backwards):

$$\hat{A}_t = \delta_t + (\gamma \lambda) \hat{A}_{t+1}$$

**Intuitive Understanding**:

- $\lambda=0$: looks at only one-step TD error, low variance but high bias
- $\lambda=1$: looks at the full return, low bias but high variance
- $\lambda=0.95$: balances both, the best choice in practice

**Return Calculation**:

$$\hat{R}_t = \hat{A}_t + V(s_t)$$

This $\hat{R}_t$ is used to train the value network.

#### 11.2.5 Value Function Loss

In addition to the policy loss, PPO also needs to train the value network to estimate state values:

$$L^{VF}(\theta) = \mathbb{E}_t\left[\max\left((V_\theta(s_t) - \hat{R}_t)^2, (\bar{V}_t - \hat{R}_t)^2\right)\right]$$

Where:
- $V_\theta(s_t)$: current value estimate
- $\hat{R}_t$: target return (computed from GAE)
- $\bar{V}_t = V_{\theta_{old}}(s_t) + \text{clip}(V_\theta(s_t) - V_{\theta_{old}}(s_t), -\epsilon, \epsilon)$: clipped value

**Purpose of Clipping**:

Prevents the value function from updating too aggressively, similar stability considerations as policy clipping.

#### 11.2.6 Entropy Bonus

To encourage exploration, PPO adds an entropy bonus:

$$L^{ENT}(\theta) = \mathbb{E}_t[H(\pi_\theta(\cdot|s_t))]$$

Where $H$ is the entropy of the policy distribution. Higher entropy means the policy is more random and exploratory.

#### 11.2.7 Total Loss Function

The final loss function for PPO is a weighted sum of three terms:$$L(\theta) = -L^{CLIP}(\theta) + c_1 L^{VF}(\theta) - c_2 L^{ENT}(\theta)$$

In this experiment:
- $c_1 = 0.5$: value loss coefficient
- $c_2 = 0.01$: entropy coefficient

**Training Process**:

1. Collect 256-step trajectory data (using $\pi_{\theta_{old}}$)
2. Compute advantage and return for all time steps
3. Train for 4 epochs on these 256 samples:
   - Each epoch iterates over all samples
   - Compute loss and update parameters for each sample
   - Update once after accumulating gradients for 128 steps
4. Update $\theta_{old} \leftarrow \theta$, proceed to the next round

#### 11.2.8 Why is PPO Suitable for VLM Training?

1. **Stability**: The clipping mechanism prevents large updates, protecting expensive pretrained models
2. **Sample Efficiency**: Each batch of data can be trained for multiple epochs (4 epochs in this experiment)
3. **Simplicity**: Compared to TRPO, PPO does not require complex second-order optimization
4. **Scalability**: Easily integrates with distributed training frameworks like DeepSpeed

#### 11.2.9 PPO Configuration in This Experiment

```yaml
ppo_config:
  clip_param: 0.1           # ε = 0.1, limits ratio to [0.9, 1.1]
  ppo_epoch: 4              # Train 4 epochs per batch of data
  mini_batch_size: 1        # Train sample by sample (due to high VLM memory usage)
  value_loss_coef: 0.5      # c_1, value loss weight
  entropy_coef: 0.01        # c_2, entropy bonus weight
  max_grad_norm: 0.01       # Gradient clipping threshold (very small for stability)
```

### 11.3 Detailed PPO Code Implementation

#### 11.3.1 Advantage Calculation (GAE) Code

```python
def compute_returns(self, next_value, gamma=0.9, gae_lambda=0.95):
    """
    Use Generalized Advantage Estimation (GAE)
    to compute return and advantage for each step
    
    Args:
        next_value: value prediction for the last step
        gamma: discount factor
        gae_lambda: GAE λ parameter
    """
    self.value_preds[-1] = next_value
    gae = 0
    
    # Compute backwards
    for step in reversed(range(self.num_steps)):  # 255 → 0
        # TD error
        delta = (self.rewards[step] + 
                gamma * self.value_preds[step + 1] * self.masks[step + 1] -
                self.value_preds[step])
        
        # GAE accumulation
        gae = delta + gamma * gae_lambda * self.masks[step + 1] * gae
        
        # Return = Advantage + Value
        self.returns[step] = gae + self.value_preds[step]
    
    # Normalize advantages (for training stability)
    advantages = self.returns[:-1] - self.value_preds[:-1]
    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-5)
    
    return advantages
```

#### 11.3.2 PPO Loss Calculation Code

```python
def ppo_update(self, rollouts):
    """
    PPO training: 4 epochs × 256 samples
    
    Each epoch iterates over all 256 samples (mini_batch_size=1)
    """
    advantages = compute_advantages(rollouts)
    
    for epoch in range(4):  # ppo_epoch = 4
        for sample_idx in range(256):  # num_steps = 256
            # 1. Get sample
            obs_batch = rollouts.obs[sample_idx]
            old_action_log_prob = rollouts.action_log_probs[sample_idx]
            return_batch = rollouts.returns[sample_idx]
            value_pred_old = rollouts.value_preds[sample_idx]
            advantage = advantages[sample_idx]
            
            # 2. Re-evaluate (with gradients)
            new_value, new_action_log_prob = actor_critic.evaluate_actions(
                **obs_batch['io_dict']
            )
            
            # 3. Compute probability ratio
            ratio = torch.exp(new_action_log_prob - old_action_log_prob)
            
            # 4. Policy Loss (Clipped Surrogate Objective)
            surr1 = ratio * advantage
            surr2 = torch.clamp(ratio, 1.0 - clip_param, 1.0 + clip_param) * advantage
            
            # Ratio clipping protection (prevent gradient explosion)
            if torch.any(ratio > 10):
                policy_loss = -surr2.mean()
            else:
                policy_loss = -torch.min(surr1, surr2).mean()
            
            # 5. Value Loss (Clipped)
            value_pred_clipped = (value_pred_old + 
                torch.clamp(new_value - value_pred_old, 
                           -clip_param, clip_param))
            
            value_losses = (new_value - return_batch).pow(2)
            value_losses_clipped = (value_pred_clipped - return_batch).pow(2)
            value_loss = 0.5 * torch.max(value_losses, 
                                        value_losses_clipped).mean()
            
            # 6. Total Loss
            loss = (value_loss * value_loss_coef +  # 0.5
                   policy_loss +
                   entropy_loss * entropy_coef)      # 0.01
            
            # 7. Backward & Update
            accelerator.backward(loss)
            
            if accelerator.sync_gradients:
                accelerator.clip_grad_norm_(
                    actor_critic.parameters(),
                    max_grad_norm  # 0.01
                )
            
            optimizer.step()
            optimizer.zero_grad()
```

### 11.4 Model Architecture

```python
class VLMValue(nn.Module):
    """
    Value Network: Used to estimate state value
    """
    def __init__(self, base):
        super().__init__()
        self.base = base  # Llama-3.2-11B-Vision (frozen generation path)
        
        # 3-layer MLP value head
        self.value_head = nn.Sequential(
            nn.Linear(4096, 1024),
            nn.ReLU(),
            nn.Linear(1024, 512),
            nn.ReLU(),
            nn.Linear(512, 1)
        ).to(base.device, dtype=torch.bfloat16)
    
    def forward(self, inputs):
        # Forward pass to get hidden states
        outputs = self.base(**inputs, output_hidden_states=True)
        hidden_states = outputs.hidden_states  # All layers
        
        # Use the last token of the last layer
        last_hidden = hidden_states[-1][:, -1]  # [batch, 4096]
        
        # Value prediction
        values = self.value_head(last_hidden)  # [batch, 1]
        return values

class VLMPolicy(nn.Module):
    """
    Policy Network: Wraps Value Network + Generation
    """
    def __init__(self, tokenizer, value_model, generation_config):
        super().__init__()
        self.tokenizer = tokenizer
        self.value_model = value_model
        self.base = value_model.base
        self.temperature = generation_config.temperature
        self.max_new_tokens = generation_config.max_new_tokens
    
    def act_oneline(self, inputs, obs=None):
        """
        Generate action (inference, no gradients)
        
        Returns:
            values: state value estimates
            io_dict: input/output dictionary (for subsequent training)
            output_text: decoded JSON text
            action_log_prob: action log probability
        """
        with torch.no_grad():
            # 1. Generation
```            outputs = self.base.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                output_scores=True,
                output_hidden_states=True,
                return_dict_in_generate=True
            )
            
            output_ids = outputs['sequences'][:, inputs['input_ids'].shape[1]:]
            output_text = self.tokenizer.decode(output_ids[0], 
                                               skip_special_tokens=True)
            
            # 2. Concatenate input + output
            cated_io = torch.cat((inputs['input_ids'], output_ids), dim=1)
            
            # 3. Prepare inputs for evaluation
            io_dict = self._prepare_io_dict(inputs, output_ids)
            
            # 4. Evaluate to get value & log_prob
            values, sum_log_prob, action_tokens_log_prob = \
                self.evaluate(**io_dict, inference=True)
        
        return values, io_dict, output_text, sum_log_prob, action_tokens_log_prob
    
    def evaluate_actions(self, **io_dict):
        """
        Re-evaluate actions (training, with gradients)
        
        Returns:
            values: new value estimates
            action_log_probs: new log probabilities
        """
        # 1. Forward pass with gradients
        outputs = self.base(
            **io_dict['new_inputs'],
            output_hidden_states=True
        )
        
        # 2. Compute value
        hidden_states = outputs.hidden_states[-1][:, -1]
        values = self.value_model.value_head(hidden_states)
        
        # 3. Compute log probabilities
        logits = outputs.logits
        output_ids = io_dict['io_pair'][1]  # Generated tokens
        
        action_log_probs = self._compute_log_probs(logits, output_ids)
        
        return values, action_log_probs
```

### 11.5 DeepSpeed ZeRO Distributed Training Principles

This experiment uses **DeepSpeed ZeRO Stage 2** for distributed training across 8 GPUs. DeepSpeed is a deep learning optimization library developed by Microsoft, with ZeRO (Zero Redundancy Optimizer) as its core technology.

#### 11.5.1 Why DeepSpeed?

**Memory Challenges**:

Training the 11B-parameter Llama-3.2-Vision model faces significant memory pressure:

```
Model Parameters:
- Base Model: 11B × 2 bytes (bf16) = 22 GB
- Value Head: 4096×1024 + 1024×512 + 512×1 ≈ 5M × 2 = 10 MB

Optimizer States (Adam):
- Momentum: 11B × 4 bytes (fp32) = 44 GB
- Variance: 11B × 4 bytes (fp32) = 44 GB

Gradients:
- Gradients: 11B × 2 bytes (bf16) = 22 GB

Activations:
- Forward pass: ~20-40 GB (depends on batch size)
- Backward pass: ~20-40 GB

Total: ~170-190 GB
```

A single H800 GPU has only **80 GB** of memory, insufficient to hold the complete training state!

**Problems with Traditional Data Parallelism**:

Traditional DDP (Distributed Data Parallel) stores a complete model replica on each GPU:

```
GPU 0: [Full Model + Full Optimizer State + Gradients] = 170 GB ✗
GPU 1: [Full Model + Full Optimizer State + Gradients] = 170 GB ✗
...
GPU 7: [Full Model + Full Optimizer State + Gradients] = 170 GB ✗
```

**Memory Redundancy Issue**:
- Identical optimizer states stored across 8 GPUs (8 × 88 GB = 704 GB redundant!)
- Each GPU still requires 170 GB, exceeding single-card capacity

#### 11.5.2 Core Idea of ZeRO

**Zero Redundancy Optimizer** reduces memory usage by eliminating redundancy:

Core Principle: **Partitioning + Communication**

```
Instead of storing redundant data:
1. Partition data across different GPUs
2. Reconstruct complete data via communication (All-Gather) when needed
3. Trade communication time for memory space
```

**Three Stages of ZeRO**:

| Stage | Partitioned Content | Memory Savings | Communication Overhead |
|-------|---------------------|----------------|------------------------|
| **ZeRO-1** | Optimizer States | ~4× | Low |
| **ZeRO-2** | + Gradients | ~8× | Medium |
| **ZeRO-3** | + Parameters | ~64× | High |

This experiment uses **ZeRO Stage 2**, balancing memory savings and communication overhead.

#### 11.5.3 Detailed Mechanism of ZeRO Stage 2

**Memory Partitioning Strategy**:

```python
# 8 GPUs, each GPU stores only 1/8 of optimizer states and gradients

GPU 0: 
  - Full Model Parameters (22 GB)
  - Optimizer States [0:N/8] (44/8 = 5.5 GB)
  - Gradients [0:N/8] (22/8 = 2.75 GB)
  - Activations (~20 GB)
  → Total: ~50 GB ✓

GPU 1:
  - Full Model Parameters (22 GB)
  - Optimizer States [N/8:2N/8] (5.5 GB)
  - Gradients [N/8:2N/8] (2.75 GB)
  - Activations (~20 GB)
  → Total: ~50 GB ✓

... (GPU 2-7 similar)
```

**Training Workflow**:

1. **Forward Pass**
   ```
   Each GPU computes independently:
   - Input: its own batch (total batch / 8)
   - Uses: full model parameters (same on all GPUs)
   - Output: its own loss and activations
   ```

2. **Backward Pass**
   ```
   Each GPU computes gradients independently:
   GPU i: ∂L/∂θ (full gradients)
   
   Then Reduce-Scatter:
   GPU i: keep only ∂L/∂θ[i×N/8:(i+1)×N/8]
   → Each GPU stores only 1/8 of the gradients
   ```

3. **Optimizer Step**
   ```
   Each GPU updates its assigned parameter partition:
   GPU 0: θ[0:N/8] ← θ[0:N/8] - lr × ∂L/∂θ[0:N/8]
   GPU 1: θ[N/8:2N/8] ← θ[N/8:2N/8] - lr × ∂L/∂θ[N/8:2N/8]
   ...
   
   Then All-Gather:
   All GPUs broadcast their updated parameters to reconstruct the full model
   ```

**Key Communication Operations**:

1. **Reduce-Scatter** (Gradient Aggregation + Partitioning)
   ```
   Input: Full gradients on each GPU
   Operation: Sum and partition
   Output: Each GPU gets 1/8 of the aggregated gradients
   
   Time Complexity: O(N/P) where P=8
   ```

2. **All-Gather** (Parameter Reconstruction)
   ```
   Input: 1/8 of parameters on each GPU
   Operation: Collect and broadcast
   Output: Each GPU gets the full parameters
   
   Time Complexity: O(N/P)
   ```

#### 11.5.4 Optimizer Offload Mechanism

This experiment also uses **CPU Offloading**:

```yaml
deepspeed_config:
  offload_optimizer_device: cpu    # Offload optimizer states to CPU
  offload_param_device: none       # Do not offload parameters
```

**How It Works**:

```
During training:
1. Optimizer States are stored in CPU memory (cheap and large capacity)
2. When an update is needed, they are transferred to the GPU for computation
3. After the update is complete, they are transferred back to the CPU

Memory Distribution:
GPU: Model Parameters (22 GB) + Gradients (2.75 GB) + Activations (20 GB) ≈ 45 GB ✓
CPU: Optimizer States (5.5 GB per GPU) → Does not occupy GPU memory
```

**Trade-offs**:
- ✓ Saves GPU memory: ~5.5 GB per GPU
- ✗ Increases training time: CPU-GPU transfer overhead (~10-15%)

For the 11B model, this trade-off is worthwhile as it prevents OOM (Out of Memory).

#### 11.5.5 Gradient Accumulation

In conjunction with ZeRO, this experiment uses **gradient accumulation over 128 steps**:

```yaml
grad_accum_steps: 128
```

**Purpose**: Simulate a larger batch size

```
Actual Workflow:
for i in range(128):
    # Forward & Backward (do not update parameters)
    loss = model(batch_i)
    loss.backward()  # Accumulate gradients
    
# Update only after 128 accumulations
optimizer.step()  # Use accumulated gradients
optimizer.zero_grad()
```

**Effective Batch Size**:

```
Per-GPU Batch Size: 1
Num GPUs: 8
Grad Accum Steps: 128

Effective Batch Size = 1 × 8 × 128 = 1024
```

**Why Gradient Accumulation?**

1. **Memory Constraints**: Batch size = 1 is the maximum the VLM can handle
2. **Training Stability**: Large batch size (1024) helps stabilize RL training
3. **Sample Efficiency**: PPO requires a sufficiently large batch to estimate advantage

#### 11.5.6 Mixed Precision Training (BF16)

```yaml
mixed_precision: bf16
downcast_bf16: 'yes'
```

**BFloat16 vs Float32**:

| Type | Bits | Exponent Bits | Mantissa Bits | Range | Precision |
|------|------|---------------|---------------|-------|-----------|
| FP32 | 32 | 8 | 23 | ±3.4×10³⁸ | High |
| BF16 | 16 | 8 | 7 | ±3.4×10³⁸ | Medium |
| FP16 | 16 | 5 | 10 | ±6.5×10⁴ | Medium |

**Advantages of BF16**:
- ✓ Memory halved: 22 GB → 11 GB
- ✓ Computation accelerated: ~2× on H800
- ✓ Large dynamic range: Same as FP32 (prevents overflow)- ✓ No loss scaling needed (simpler than FP16)

**Training Flow**:

```python
# Forward & Backward in BF16
with autocast(dtype=torch.bfloat16):
    output = model(input)
    loss = criterion(output, target)

loss.backward()  # Gradients in BF16

# Optimizer in FP32 (Master Weights)
optimizer.step()  # Update FP32 parameters
model.to(torch.bfloat16)  # Convert back to BF16 for next forward pass
```

#### 11.5.7 Actual Memory Usage Analysis

**Single GPU Memory Distribution** (ZeRO-2 + Offload + BF16):

```
Model Parameters (BF16): 11B × 2 bytes = 22 GB
Gradients (BF16, 1/8): 11B × 2 / 8 = 2.75 GB
Activations (BF16): ~15-20 GB
Optimizer States (CPU Offload): 0 GB (on CPU)
Temporary Buffers: ~5 GB

Total per GPU: ~45-50 GB / 80 GB = 56-62% Utilization ✓
```

**Comparing Different Configurations**:

| Configuration | Memory Usage | Feasible |
|------|---------|---------|
| Single GPU, No Optimization | 170 GB | ✗ OOM |
| DDP, 8 GPUs | 170 GB each | ✗ OOM |
| ZeRO-2, 8 GPUs | 55 GB each | ✓ |
| ZeRO-2 + Offload | 50 GB each | ✓ |
| ZeRO-3 | 30 GB each | ✓ (but slower communication) |

**Communication Overhead**:

- Reduce-Scatter: ~0.1 seconds per step
- All-Gather: ~0.1 seconds per step  
- Total Overhead: ~10-15% of training time
- Trade-off: Acceptable (compared to being unable to train)

#### 11.5.8 DeepSpeed Configuration Details

```yaml
# scripts/config_zero2_8gpu.yaml

compute_environment: LOCAL_MACHINE
distributed_type: DEEPSPEED

# Core Configuration
deepspeed_config:
  zero_stage: 2                      # ZeRO Stage 2
  offload_optimizer_device: cpu      # Optimizer → CPU
  offload_param_device: none         # Parameters stay on GPU
  zero3_init_flag: false             # Do not use ZeRO-3 initialization
  overlap_comm: false                # Do not overlap communication with computation (more stable)

# Precision Configuration
mixed_precision: bf16                # BFloat16 Mixed Precision
downcast_bf16: 'yes'                 # Automatic conversion

# Distributed Configuration
num_machines: 1                      # Single node
num_processes: 8                     # 8 GPUs
rdzv_backend: static                 # Static topology (no dynamic joining)
same_network: true                   # Same network (low latency)
```

**Why Not ZeRO-3?**

ZeRO-3 saves more memory but has higher communication overhead:

| Stage | Communications/Step | Data Volume/Step | Training Speed |
|-------|------------|----------|---------|
| ZeRO-2 | 2 | 22 GB | 1.0× |
| ZeRO-3 | 4 | 44 GB | 0.6× |

For an 11B model, ZeRO-2 is sufficient, and the extra overhead of ZeRO-3 is unnecessary.

#### 11.5.9 Actual Training Performance

**Throughput**:

```
Rollout Phase (256 steps):
- Time: ~40 minutes
- Speed: 6.4 steps/min
- Bottleneck: Environment interaction + Model inference

PPO Training Phase (4 epochs × 256 samples):
- Time: ~20 minutes  
- Speed: 51.2 samples/min
- Bottleneck: Gradient computation + Communication

Total per Update: ~60 minutes
Total Training (15 updates): ~15 hours
```

**Scalability Analysis**:

| Number of GPUs | Theoretical Speedup | Actual Speedup | Efficiency |
|---------|-----------|-----------|------|
| 1 | 1.0× | 1.0× | 100% |
| 2 | 2.0× | 1.8× | 90% |
| 4 | 4.0× | 3.4× | 85% |
| 8 | 8.0× | 6.2× | 78% |

The efficiency loss is mainly due to communication overhead, but a 6× speedup is still achieved.

### 11.6 Training Monitoring Metrics

**Key Metrics Logged to WandB**:

```python
wandb.log({
    # Training Progress
    'total_num_steps': total_steps,
    'compute_tokens': token_count,
    
    # Loss
    'value_loss': value_loss,
    'action_loss': policy_loss,
    'dist_entropy': entropy,
    
    # Reward Statistics
    'reward.mean': rewards.mean(),
    'reward.std': rewards.std(),
    'reward.max': rewards.max(),
    'reward.min': rewards.min(),
    
    # Value Statistics
    'value.mean': values.mean(),
    'value.std': values.std(),
    
    # Return Statistics
    'return.mean': returns.mean(),
    'return.std': returns.std(),
    
    # Episode Statistics
    'episode_rewards.mean': np.mean(episode_rewards),
    'success_rate': success_rate,
    'per_step_accuracy': step_accuracy
})
```

---

## 12. Hyperparameter Configuration

### 12.1 Core Hyperparameter Overview

| Category | Parameter | Value | Description |
|------|------|-----|------|
| **Training Scale** | `num_updates` | 15 | Total training rounds |
| | `num_steps` | 256 | Steps collected per round |
| | `ppo_epoch` | 4 | PPO training epochs |
| | `grad_accum_steps` | 128 | Gradient accumulation steps |
| **Learning Rate** | `init_lr` | 1e-7 | Initial learning rate |
| | `lr_max_steps` | 20 | Total steps for LR scheduler |
| | `end_lr` | 1e-9 | Final learning rate |
| **PPO** | `clip_param` | 0.1 | PPO clip range |
| | `value_loss_coef` | 0.5 | Value loss coefficient |
| | `entropy_coef` | 0.01 | Entropy coefficient |
| | `max_grad_norm` | 0.01 | Gradient clipping threshold |
| **GAE** | `gamma` | 0.9 | Discount factor |
| | `gae_lambda` | 0.95 | GAE λ |
| **Environment** | `verify_iter` | 2 | Number of verification attempts |
| | `resolution` | 1200 | Image resolution |
| **Generation** | `temperature` | 0.2 | Generation temperature |
| | `max_new_tokens` | 512 | Maximum generation length |

### 12.2 Complete Configuration File

```yaml
# rl/configs/llama_virl_vl.yaml

trainer: LlamaTrainer

# Gradient Accumulation Configuration
grad_accum_steps: 128

# Optimizer Configuration
optimizer_config:
  init_lr: !!float 1e-6      # Will be overridden by script to 1e-7
  eps: !!float 1e-7
  weight_decay: 0
  lr_max_steps: 100           # Will be overridden by script to 20
  end_lr: !!float 1e-9

# PPO Configuration
ppo_config:
  clip_param: 0.1             # ε in PPO clip
  ppo_epoch: 4                # PPO training epochs per round
  mini_batch_size: 1          # Batch size
  value_loss_coef: 0.5        # Value loss weight
  entropy_coef: 0.01          # Entropy bonus weight
  max_grad_norm: 0.01         # Gradient clipping

# Return Computation Configuration
compute_return_kwargs:
  use_gae: true               # Use GAE
  gamma: 0.9                  # Discount factor γ
  gae_lambda: 0.95            # GAE λ
  use_proper_time_limits: False

# Training Configuration
report_to: wandb              # Log to WandB
run_name: "virl_vl_training"
num_steps: 512                # Will be overridden by script to 256
num_processes: 1
num_updates: 20               # Will be overridden by script to 15

# Environment Configuration
env_config:
  id: 'gym_virl/Navigation-v0'
  route_info_path: ""
  resolution: 1200
  verify_iter: 2
  absolute_action: true
  relocation: true
  drop_rate: 0.5
  straight_line_length: 5
  
  platform_cfg:
    STREET_VIEW:
      SIZE: [640, 640]
      HEADING: 0
      PITCH: 0
      FOV: 90
      SOURCE: outdoor
    
    OFFLINE:
      ENABLED: True
      PANORAMA_DIR: ""
      GPS_TO_PANO_PATH: ""
      MAPPING_RADIUS: 20
  
  platform_save_dir: "./logs/"

# Model Configuration
model: llama
model_path: ""

# Prompt Configuration
prompt_config:
  relocation: true
  use_vision: true
  use_language: false
  enable_verification: true
  prompt_vision: ["Q_VIRL_VL"]
  pattern_vision: ["action"]

# Generation Configuration
generation_config:
  temperature: 0.2
  max_tokens: 300
  max_new_tokens: 512
  thought_prob_coef: 0.5
  num_beams: 1

# Output Configuration
output_dir: logs/train.jsonl
seed: 42
save_ckpt: False
save_every: 1
```

### 12.3 Training Script Override Parameters

```bash
# scripts/virl_training/vl_train.sh

# Training Parameters
LR=1e-7
save_model=True
save_every=5  # Save every 5 updates
CKPT_NAME="tianzhechu/VIRL-VL-Init"
PORT=$((RANDOM % 10000 + 1000))

# Data Path (using absolute paths)
BASE_DIR="/root/SFTvsRL_Data/VIRL_routes"
```ROUTE_INFO="${BASE_DIR}/nyc_1k_routes/route_infos.json"
GPS_TO_PANO="${BASE_DIR}/nyc_1k_routes/gps_pano_mapping.pkl"
STREETVIEWS="${BASE_DIR}/nyc_1k_routes/street_views/"

# Start training
DS_SKIP_CUDA_CHECK=1 TOKENIZERS_PARALLELISM=false \
    accelerate launch \
    --config_file scripts/config_zero2_8gpu.yaml \
    --main_process_port ${PORT} -m rl.launcher \
    -f rl/configs/llama_virl_vl.yaml \
    --output_dir=train_ckpt/virl_vl/ \
    --optimizer_config.init_lr=${LR} \
    --optimizer_config.lr_max_steps=20 \
    --prompt_config.enable_verification=True \
    --num_updates=15 \
    --num_steps=256 \
    --model_path=${CKPT_NAME} \
    --save_ckpt=${save_model} \
    --save_every=${save_every} \
    --env_config.route_info_path=${ROUTE_INFO} \
    --env_config.platform_cfg.OFFLINE.PANORAMA_DIR=${STREETVIEWS} \
    --env_config.platform_cfg.OFFLINE.GPS_TO_PANO_PATH=${GPS_TO_PANO}
```

### 12.4 DeepSpeed ZeRO-2 Configuration

```yaml
# scripts/config_zero2_8gpu.yaml

compute_environment: LOCAL_MACHINE

deepspeed_config:
  offload_optimizer_device: cpu    # Offload optimizer to CPU
  offload_param_device: none       # Do not offload parameters
  zero3_init_flag: false
  zero_stage: 2                    # ZeRO Stage 2
  overlap_comm: false

distributed_type: DEEPSPEED
downcast_bf16: 'yes'               # BF16 mixed precision
machine_rank: 0
main_training_function: main
mixed_precision: bf16
num_machines: 1
num_processes: 8                   # 8 GPUs
rdzv_backend: static
same_network: true
use_cpu: false
```

### 12.5 Key Hyperparameter Explanations

**Why is `lr=1e-7` so small?**
- RL training requires stability; a large learning rate can cause policy collapse
- The value network is initialized from scratch and needs careful training
- Paper experiments verify: 1e-7 > 1e-6 (more stable)

**Why is `lr_max_steps=20` so short?**
- With only 15 updates, a 20-step LR schedule covers the entire training
- `lr_scheduler.step()` is called after each update
- Actual: ~1.3 updates per LR step (20/15)

**Why is `max_grad_norm=0.01` so small?**
- RL training is prone to gradient explosion (importance sampling)
- Strict gradient clipping ensures training stability
- Paper ablation studies confirm this value is optimal

**Why `verify_iter=2`?**
- Balances exploration and efficiency: 2 attempts are sufficient for learning
- Too many attempts → slow training, information redundancy
- Too few attempts → difficulty recovering from errors, unstable training

---

## 13. Evaluation Methods

### 13.1 Evaluation Pipeline

```bash
# 1. In-Distribution Evaluation
bash scripts/virl_evaluation/vl_indist_eval.sh

# 2. Rule OOD Evaluation  
bash scripts/virl_evaluation/vl_rule_ood_eval.sh

# 3. Visual OOD Evaluation
bash scripts/virl_evaluation/vl_visual_ood_eval.sh
```

### 13.2 Evaluation Configuration Comparison

| Configuration | In-Dist | Rule OOD | Visual OOD |
|--------|---------|----------|------------|
| `num_traj` | 48 | 48 | 18 |
| `absolute_action` | True | **False** | True |
| `route_info_path` | NYC routes | NYC routes | **SF routes** |
| `verify_iter` | 2 | 2 | 2 |
| Number of GPUs | 1 | 1 | 1 |

### 13.3 Evaluation Metrics

#### 13.3.1 Per-Step Accuracy

**Definition**: Accuracy of individual actions

```python
per_step_accuracy = (
    num_correct_actions / total_actions
) × 100%
```

**Example**:
```
Route 1: 15 steps, 13 correct → 13/15 = 86.7%
Route 2: 20 steps, 18 correct → 18/20 = 90.0%
...
Route 48: 12 steps, 10 correct → 10/12 = 83.3%

Overall Per-Step Accuracy = 
    (13 + 18 + ... + 10) / (15 + 20 + ... + 12) = 87.5%
```

#### 13.3.2 Success Rate

**Definition**: Complete route success rate

```python
success_rate = (
    num_successful_routes / total_routes
) × 100%
```

**Success Conditions**:
1. Reaches the correct destination
2. All waypoints are passed within the allowed number of attempts
3. Does not exceed the maximum number of steps

**Example**:
```
48 routes:
- 35 routes: Success ✓
- 10 routes: Partial failure (some waypoint errors) ✗
- 3 routes: Complete failure (did not reach destination) ✗

Success Rate = 35 / 48 = 72.9%
```

#### 13.3.3 Other Metrics

```python
metrics = {
    'mean_reward': Average total reward per route,
    'std_reward': Standard deviation of reward,
    'mean_steps': Average number of steps,
    'mean_verification_steps': Average number of verification steps (including retries)
}
```

### 13.4 Evaluation Output Example

```jsonl
// logs/virl_vl_indist_verify_2/virl_vl_indist.jsonl

// Route 1, Step 0
{"sample_id": 0, "veri_step": 0, "output": "{\"action\": \"turn_direction(south)\"}", "reward": 1, "info": {...}}

// Route 1, Step 1
{"sample_id": 0, "veri_step": 1, "output": "{\"action\": \"forward()\"}", "reward": 1, "info": {...}}

// ... more steps ...

// Route 1, Final step
{"sample_id": 0, "veri_step": 14, "output": "{\"action\": \"stop()\"}", "reward": 1, "info": {...}}

// Route 1 Summary
{"Success": true, "sample_id": 0, "output": "{\"action\": \"stop()\"}", "reward": 15, "info": {...}}
{"Split": "===================="}

// Route 2, Step 0 (Failed attempt)
{"sample_id": 1, "veri_step": 0, "output": "{\"action\": \"turn_direction(north)\"}", "reward": -1, "info": {"Verify Info": "Incorrect action..."}}

// Route 2, Step 1 (Retry, Success)
{"sample_id": 1, "veri_step": 1, "output": "{\"action\": \"turn_direction(south)\"}", "reward": 1, "info": {...}}

// ... 47 more routes ...

// Overall Statistics
{
  "mean_reward": 12.5,
  "std_reward": 3.2,
  "success_rate": 0.729,
  "per_step_accuracy": 0.875,
  "mean_steps": 14.2,
  "mean_verification_steps": 1.15
}
```

### 13.5 Detailed Evaluation Script

```bash
#!/bin/bash
# scripts/virl_evaluation/vl_indist_eval.sh

VITER=2                    # Number of verification attempts
ENABLE=True                # Enable verification mechanism
ABS=True                   # Use absolute action space
NUM_TRAJ=48                # Evaluate 48 routes
CKPT_NAME="train_ckpt/virl_vl/checkpoint-epoch-14"  # Trained checkpoint
OUTPUT_FOLDER="logs/virl_vl_indist_verify_${VITER}"
PORT=$((RANDOM % 10000 + 2000))

# Data paths (using absolute paths)
BASE_DIR="/root/SFTvsRL_Data/VIRL_routes"
ROUTE_INFO="${BASE_DIR}/nyc_1k_routes/route_infos.json"
GPS_TO_PANO="${BASE_DIR}/nyc_1k_routes/gps_pano_mapping.pkl"
STREETVIEWS="${BASE_DIR}/nyc_1k_routes/street_views/"

# Evaluate using 1 GPU
DS_SKIP_CUDA_CHECK=1 accelerate launch \
    --config_file scripts/config_zero2_1gpu.yaml \
    --main_process_port ${PORT} \
    -m evaluation.launcher \
    -f evaluation/configs/llama_virl_vl.yaml \
    --model_path=${CKPT_NAME} \
    --output_dir=${OUTPUT_FOLDER}/virl_vl_indist.jsonl \
    --env_config.route_info_path=${ROUTE_INFO} \
    --env_config.platform_cfg.OFFLINE.PANORAMA_DIR=${STREETVIEWS} \
    --env_config.platform_cfg.OFFLINE.GPS_TO_PANO_PATH=${GPS_TO_PANO} \
    --prompt_config.enable_verification=${ENABLE} \
    --env_config.verify_iter=${VITER} \
    --env_config.absolute_action=${ABS} \
    --num_traj=${NUM_TRAJ}
```

---

## 14. Experimental Results Analysis

### 14.1 Key Findings

Based on the paper's Figure 1 and experimental data:

#### 14.1.1 In-Distribution Performance| Model | Per-Step Accuracy | Success Rate |
|------|-------------------|--------------|
| SFT | ~85% | ~60% |
| RL (PPO) | ~90% | ~75% |

**Conclusion**: RL outperforms SFT on the training distribution as well (+5% step accuracy)

#### 14.1.2 Rule OOD Generalization

| Model | In-Dist | Rule OOD | Generalization Gap |
|------|---------|----------|--------------------|
| SFT | 85% | **15%** | **-70%** |
| RL | 90% | **70%** | **-20%** |

**Key Findings**:
- SFT collapses on Rule OOD (from 85% → 15%), indicating **memorization of training data**
- RL maintains 70% accuracy, indicating **learning of generalizable rules**

#### 14.1.3 Visual OOD Generalization

| Model | NYC (In-Dist) | SF (Visual OOD) | Generalization Gap |
|------|---------------|-----------------|---------------------|
| SFT | 85% | **<10%** | **-75%** |
| RL | 90% | **~60%** | **-30%** |

**Key Findings**:
- SFT nearly fails in a different city, indicating **overfitting to visual features**
- RL maintains 60% accuracy in SF, indicating **learning of transferable visual representations**

### 14.2 Why Does RL Generalize?

The paper analyzes the generalization mechanism of RL through ablation experiments:

#### 14.2.1 The Role of Outcome-based Reward

**Experiment Design**:
- RL-Process: Feedback given at each step (+1/-1)
- RL-Outcome: Reward given only at episode end

**Results**:
- RL-Outcome achieves higher accuracy on visual recognition (GeneralPoints-VL)
- This indicates that outcome-based reward forces the model to learn better visual representations

**Principle**:
```
Process Reward:
  Step 1: +1 (correct action, but maybe wrong reasoning)
  → Model may rely on shortcuts (e.g., memorized patterns)

Outcome Reward:
  All steps: 0, 0, 0, ..., +10 (final success)
  → Model must learn end-to-end reasoning, including visual understanding
```

#### 14.2.2 SFT as Format Teacher

**Experiment**: Train RL directly from the base model

**Result**: Failure (see Figure 20 of the paper)
- Model cannot output structured JSON
- Generates lengthy code snippets
- Fails to converge

**Conclusion**:
- SFT stabilizes output format ("format teacher")
- RL builds strategy and generalization ability on top of this
- **SFT + RL** is the optimal combination

#### 14.2.3 Training Curve Comparison

```
Per-Step Accuracy over Training

SFT:
  Update 0-5:   Rapid rise (0% → 80%)
  Update 5-10:  Continued rise (80% → 85%)
  Update 10-20: Overfitting begins (85% → 85%)
  
  Rule OOD: Continuous decline (80% → 15%)
  → Memorizes training rules

RL:
  Update 0-5:   Steady rise (85% → 88%)
  Update 5-10:  Continued rise (88% → 90%)
  Update 10-15: Remains stable (90% → 90%)
  
  Rule OOD: Synchronous rise (60% → 70%)
  → Learns generalizable rules
```

### 14.3 V-IRL Mini Benchmark SOTA

The paper achieves SOTA on the official V-IRL benchmark:

| Method | Success Rate |
|------|--------------|
| GPT-4V (Yang et al., 2024) | 44.0% |
| **RL (Ours)** | **77.8%** |
| **Improvement** | **+33.8%** |

**Explanation**:
- Multi-round RL training significantly improves navigation ability
- RL's generalization advantage is particularly evident in complex real-world environments

### 14.4 Failure Case Analysis

The paper provides two categories of failure cases:

#### 14.4.1 RL Failure Without SFT Initialization

```
Problem: Direct RL training produces unstructured output

Example Output:
"To solve this problem, we can use a brute force approach 
by generating all possible combinations... [generates Python code]"

Reason: The base model has not undergone instruction fine-tuning and does not understand the task format
```

#### 14.4.2 RL Failure from Overfitted Checkpoint

```
Problem: Starting RL from a severely overfitted SFT checkpoint

Example:
  Rule: Relative actions
  Model Output: "turn_direction(northwest)"  # Still using absolute!
  
Reason: SFT overfitting is too deep; RL cannot correct it
```

**Implications**:
- The training extent of SFT and RL needs to be balanced
- SFT should not be trained for too long (to avoid overfitting)
- Paper suggests: Train SFT only until a reasonable output format is achieved

---

## 15. References

### 15.1 Papers

- **Main Paper**: Chu, T., Zhai, Y., Yang, J., et al. (2025). *SFT Memorizes, RL Generalizes: A Comparative Study of Foundation Model Post-training*. ICML 2025. [arXiv:2501.17161](https://arxiv.org/pdf/2501.17161)

- **V-IRL Environment**: Yang, J., et al. (2024). *V-IRL: Grounding Virtual Intelligence in Real Life*. [V-IRL Platform](https://virl-platform.github.io/)

- **RL4VLM**: Zhai, Y., et al. (2024). *Fine-Tuning Large Vision-Language Models as Decision-Making Agents via Reinforcement Learning*. [RL4VLM](https://github.com/RL4VLM/RL4VLM)

### 15.2 Code Repositories

- **Recommended to use ()**: [bojieli/SFTvsRL](https://github.com/bojieli/SFTvsRL/) ⭐
- **Official Implementation**: [LeslieTrue/SFTvsRL](https://github.com/LeslieTrue/SFTvsRL)
- **Project Page**: [https://tianzhechu.com/SFTvsRL](https://tianzhechu.com/SFTvsRL)
- **Dataset**: [HuggingFace - SFTvsRL_Data](https://huggingface.co/datasets/tianzhechu/SFTvsRL_Data)
- **Model Checkpoints**: [HuggingFace - SFTvsRL Models](https://huggingface.co/collections/tianzhechu/sftvsrl-models-and-data-6797ba6de522c7de7fcb80ba)

**⚠️ Note**: Please use the bojieli fork version, which fixes a critical bug in the official version that prevents checkpoint saving (see Section 4.3 for details).

### 15.3 Related Work

- **Llama-3.2-Vision**: Dubey, A., et al. (2024). *The Llama 3 Herd of Models*. Meta AI.
- **PPO**: Schulman, J., et al. (2017). *Proximal Policy Optimization Algorithms*. arXiv:1707.06347
- **GAE**: Schulman, J., et al. (2016). *High-Dimensional Continuous Control Using Generalized Advantage Estimation*. ICLR 2016.

---

## Appendix

### A. Frequently Asked Questions

**Q0: Training error `TypeError: unsupported operand type(s) for %: 'int' and 'NoneType'`?**
- This is a bug in the official code!
- **Solution**: Use the fixed fork version
  ```bash
  git clone https://github.com/bojieli/SFTvsRL.git
  ```
- Detailed explanation in [Section 4.3](#43-official-code-bug-and-fix)

**Q1: Why is RL training so slow?**
- Requires online interaction with the environment (256 steps × 15 updates = 3,840 interactions)
- Each step requires image loading + model inference (~2-3 seconds/step)
- PPO training requires 4 epochs × 256 samples (~1 hour/update)

**Q2: Can I train with fewer GPUs?**
- Theoretically yes, but you need to adjust `grad_accum_steps` to maintain the effective batch size
- 8 GPUs → 4 GPUs: double `grad_accum_steps` (128 → 256)
- Training time will increase significantly

**Q3: How to reproduce the paper's results?**
1. Use the provided SFT checkpoint (`tianzhechu/VIRL-VL-Init`)
2. Train strictly with the hyperparameter configuration for 15 updates
3. Test on the same evaluation set (NYC 48 routes, SF 18 routes)

**Q4: Why is SFT initialization necessary?**
- Stabilizes output format (JSON structure)
- Provides basic instruction-following ability
- Accelerates RL convergence

### B. Training Checklist

Confirm the following before running training:

- [ ] **Use the fixed code** (`git clone https://github.com/bojieli/SFTvsRL.git`) ⭐
- [ ] **Verify the bug is fixed** (`grep "self.save_every = save_every" rl/trainer/base_trainer.py`)
- [ ] Install all dependencies (`pip install -r requirements.txt && cd gym && pip install -e .`)
- [ ] **Download and extract the dataset** to `/root/SFTvsRL_Data/VIRL_routes/`
  - [ ] Extract `nyc_1k_routes.zip`
  - [ ] Extract `VLN_mini.zip` (for Visual OOD evaluation)
  - [ ] Verify files exist: `route_infos.json`, `gps_pano_mapping.pkl`, `street_views/`
- [ ] Download the SFT checkpoint (`tianzhechu/VIRL-VL-Init`)
- [ ] **Confirm data paths are correct**:
  - [ ] `ROUTE_INFO="/root/SFTvsRL_Data/VIRL_routes/nyc_1k_routes/route_infos.json"`
  - [ ] `GPS_TO_PANO="/root/SFTvsRL_Data/VIRL_routes/nyc_1k_routes/gps_pano_mapping.pkl"`
  - [ ] `STREETVIEWS="/root/SFTvsRL_Data/VIRL_routes/nyc_1k_routes/street_views/"`
- [ ] Check GPU count and memory (8×80GB)
- [ ] Configure WandB API key (`wandb login`)

### C. Evaluation Checklist

Confirm the following before running evaluation:

- [ ] Training is complete and checkpoints are saved (`train_ckpt/virl_vl/checkpoint-epoch-*`)
- [ ] **Dataset is downloaded and extracted**:
  - [ ] In-Dist & Rule OOD: `/root/SFTvsRL_Data/VIRL_routes/nyc_1k_routes/`
  - [ ] Visual OOD: `/root/SFTvsRL_Data/VIRL_routes/VLN_mini/`
- [ ] **Modify the evaluation script**:
  - [ ] Update `CKPT_NAME="train_ckpt/virl_vl/checkpoint-epoch-14"`  - [ ] Confirm `BASE_DIR="/root/SFTvsRL_Data/VIRL_routes"`
  - [ ] Select the correct `ROUTE_INFO` path based on the evaluation type
