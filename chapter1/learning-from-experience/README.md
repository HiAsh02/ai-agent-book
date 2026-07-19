# Learning from Experience: RL vs LLM In-Context Learning

This experiment compares traditional Reinforcement Learning (Q-learning) with LLM-based in-context learning, replicating the key insights from Shunyu Yao's blog post ["The Second Half"](https://ysymyth.github.io/The-Second-Half/).

## 🎯 Experiment Overview

The experiment demonstrates how LLMs can generalize through reasoning while traditional RL methods require extensive training to learn game mechanics. We use a text-based treasure hunt game with hidden mechanics that agents must discover through experience.

### Key Insights Being Tested

1. **Sample Efficiency**: LLMs can learn from far fewer examples than traditional RL
2. **Generalization**: LLMs use reasoning to understand patterns, while RL memorizes state-action mappings
3. **Prior Knowledge**: Language pre-training provides powerful priors for reasoning about new tasks
4. **Hidden Mechanics Discovery**: LLMs can form hypotheses and test them, while RL requires exhaustive exploration

### What You'll See

When running the LLM experiment, you'll see the **complete decision-making process**:

```
============================================================
LLM DECISION PROCESS
============================================================
📊 Experiences in memory: 15
🎮 Current room: hallway
🎯 Available actions: 8

💡 Recent successful patterns learned:
   • take red key → +5.0 reward
   • try crafting → +10.0 reward

🤔 LLM is thinking...

📝 LLM Reasoning:
----------------------------------------
  Based on my past experiences, I've learned that:
  1. The red key opens the locked door to the guard room
  2. Crafting rusty sword + magic crystal creates a silver sword
  3. The silver sword can defeat the strong guard
  
  Since I have the silver sword and I'm in the hallway...
----------------------------------------

✅ Chosen action: go north
```

This transparency shows exactly how the LLM learns and reasons, unlike the black-box nature of Q-learning!

## 🎮 The Game

A text-based treasure hunt game where agents must:
- Navigate through multiple rooms
- Collect items and keys
- Defeat guards using appropriate weapons
- Discover hidden mechanics through experience

### Hidden Mechanics (Not Revealed to Agents)

1. **Color-coded locks**: Specific colored keys open matching doors
2. **Weapon effectiveness**: Different weapons work against different enemies
3. **Crafting system**: Certain items combine to create better items
4. **Potion effects**: Temporary abilities from consuming potions

## 🚀 Quick Start

### Installation

```bash
# Navigate to the project directory
cd chapter1/learning-from-experience

# Install dependencies
pip install -r requirements.txt
```

> Corresponds to **Experiment 7-1 (Q-learning Performance in Treasure Hunt Game)** and **Experiment 7-2 (Comparative Study of Traditional RL vs LLM Agent)** in the book.
> The Q-learning part runs entirely offline without any API key; the LLM part requires a Moonshot/Kimi API key.

### Setting up Kimi K3 API

To run the LLM experiments, you need a Kimi (Moonshot) API key:

1. Get your API key from [Moonshot AI](https://platform.moonshot.cn/)
2. Set the environment variable:

```bash
export MOONSHOT_API_KEY="your-api-key-here"
```

Or create a `.env` file:
```bash
echo "MOONSHOT_API_KEY=your-api-key-here" > .env
```

**Universal Fallback (OpenRouter)**: If `MOONSHOT_API_KEY` is not set but `OPENROUTER_API_KEY` is,
the LLM part will automatically switch to OpenRouter. Since Kimi models are not stably available on OpenRouter, the fallback uses
`OPENROUTER_MODEL` (default `openai/gpt-5.6-luna`):
```bash
export OPENROUTER_API_KEY=sk-or-v1-your-key-here
python quick_demo.py   # Automatically runs via OpenRouter when MOONSHOT_API_KEY is missing
```

### Running the Experiment

#### Quick Demo (See LLM Learning in Action)

```bash
python quick_demo.py
```

This shows a detailed view of how the LLM learns through reasoning, displaying:
- Complete thought process for each decision
- How experiences accumulate and influence future decisions
- The dramatic difference in learning speed vs traditional RL

#### Command-Line Interface (`experiment.py`)

`experiment.py` now provides a full CLI with Chinese help text. View all parameters:

```bash
python experiment.py --help
```

Main parameters:

| Parameter | Description | Default |
| --- | --- | --- |
| `--mode {both,qlearning,rl,llm}` | Which agent to run: `qlearning`/`rl` runs only Q-learning (offline), `llm` runs only LLM Agent, `both` compares both | `both` |
| `--rl-episodes` | Number of Q-learning training episodes (use 10000 for Experiment 7-1) | `10000` |
| `--llm-episodes` | Number of LLM Agent training episodes | `20` |
| `--eval-episodes` | Number of greedy evaluation episodes after Q-learning training | `100` |
| `--checkpoint-interval` | Learning curve sampling interval (record win rate/Q-table size every N episodes) | `1000` |
| `--model` | LLM model name (can also use `MOONSHOT_MODEL` environment variable) | `kimi-k3` |
| `--output` | Result output directory | `results` |
| `--seed` | Random seed for reproducing Q-learning learning curves | Not fixed |
| `--learning-rate` / `--discount` / `--epsilon-decay` / `--epsilon-min` | Q-learning hyperparameters | `0.2 / 0.99 / 0.9995 / 0.1` |
| `--stochastic` | Use stochastic environment | Deterministic |
| `--skip-llm` | Compatible with old usage, equivalent to `--mode qlearning` | — |

#### Q-Learning Only (Experiment 7-1, Offline, No API Required)

```bash
python experiment.py --mode qlearning --rl-episodes 10000 --seed 42
```

Training completes in under 3 seconds and prints a **learning curve table**, intuitively showing how the agent gradually learns to complete the game from 0% win rate through nearly ten thousand episodes of trial and error (see "Experiment Results" below).

#### Full Comparison (RL vs LLM, Experiment 7-2)

```bash
python experiment.py --mode both --model kimi-k3
```

This will:
1. Train a Q-learning agent for 10000 episodes (takes ~3 seconds) and print its learning curve
2. Train an LLM agent for 20 episodes with detailed reasoning display
3. Evaluate both agents
4. Generate comparison plots
5. Save results to the `results/` directory

**Note**: The LLM training shows the complete reasoning process for the first 3 episodes and the last episode, so you can see exactly how it learns! Each LLM episode takes ~1-2 minutes (real API calls), matching the cost trade-off discussed in Experiment 7-2.

#### LLM Only

```bash
python experiment.py --mode llm --llm-episodes 20
```

#### Interactive Game Play

Test the game manually:

```python
from game_environment import TreasureHuntGame

game = TreasureHuntGame()
print(game.get_state_description())
print("Available actions:", game.get_available_actions())

# Try an action
feedback, reward, done = game.execute_action("take rusty sword")
```print(f"Feedback: {feedback}")
print(f"Reward: {reward}")
```

## 📊 Experiment Results

The experiment generates several outputs:

### Metrics Compared

1. **Sample Efficiency**
   - Episodes needed to achieve good performance
   - Learning speed comparison

2. **Performance**
   - Victory rate in evaluation
   - Average rewards and episode lengths

3. **Computational Cost**
   - Training time
   - Memory usage (Q-table size vs. experience storage)
   - API calls for LLM

### Visualizations

The experiment creates comparison plots showing:
- Learning curves over time
- Victory rate progression
- Sample efficiency comparison
- Key insights summary

### Expected Results

#### Q-Learning learning curve (measured locally, `--mode qlearning --rl-episodes 10000 --seed 42`)

Measured learning curve (deterministic environment, victory rate computed over a sliding window of the last 1000 episodes, full training ~3 seconds):

| Episodes | Victory rate | Q-table states | epsilon |
| ---: | ---: | ---: | ---: |
| 1000 | 0.1% | 124 | 0.606 |
| 2000 | 0.0% | 129 | 0.368 |
| 3000 | 0.0% | 130 | 0.223 |
| 5000 | 0.0% | 132 | 0.100 |
| 7000 | 0.0% | 138 | 0.100 |
| 8000 | 0.0% | 140 | 0.100 |
| 9000 | 9.3% | 143 | 0.100 |
| 10000 | **99.8%** | 143 | 0.100 |

After training, greedy evaluation (`--eval-episodes 100`) yields a victory rate of **100%**, with an average of 15 steps to complete. This is the core phenomenon of Experiment 7-1: for the first 8000 episodes, the victory rate is nearly 0%, with only blind exploration; the value signal takes nearly ten thousand episodes of trial and error to propagate. (Due to variance in random exploration, the inflection point may vary slightly across runs when `--seed` is not fixed, but the overall pattern remains consistent.)

#### RL vs LLM (Comparison conclusions from Experiment 7-2)

- **Q-Learning**: Requires nearly 10,000 episodes to achieve stable completion; treats "door/key/sword" as meaningless symbols, relying solely on statistical brute-force exploration.
- **LLM In-Context**: Carries pre-trained priors, often completing the game within a dozen steps on the first episode; understands the conceptual structure of the game through reasoning.
- **Sample Efficiency**: LLM sample efficiency is 2-3 orders of magnitude higher; however, per-episode reasoning is slow (API call ~1-2 minutes), while Q-learning runs 10,000 episodes in about 3 seconds — the trade-off depends on interaction cost, as detailed in Experiment 7-2 of the book.

## 🏗️ Project Structure

```
learning-from-experience/
├── game_environment.py    # Text-based game with hidden mechanics
├── rl_agent.py            # Q-learning implementation
├── llm_agent.py           # LLM with in-context learning
├── experiment.py          # Main experiment runner
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── results/              # Experiment outputs (created on run)
    └── [timestamp]/
        ├── rl_agent.pkl           # Trained Q-learning agent
        ├── llm_experiences.json   # LLM's collected experiences
        ├── experiment_results.json # Numerical results
        └── comparison_plots.png   # Visualization
```

## 🔬 Technical Details

### Q-Learning Agent

- **Algorithm**: Tabular Q-learning with ε-greedy exploration
- **State Representation**: Hashed combination of room, inventory, and game state
- **Learning Rate**: 0.2 (configurable via `--learning-rate`)
- **Discount Factor**: 0.99 (configurable via `--discount`)
- **Exploration**: ε starts at 1.0, decays by `--epsilon-decay` (0.9995) to `--epsilon-min` (0.1)

### LLM Agent (Kimi K3)

- **Model**: `kimi-k3` (Kimi K3; override with `--model` or `MOONSHOT_MODEL`)
- **Reasoning model**: Kimi K3 emits a chain-of-thought (`message.reasoning_content`) before its
  final answer (`message.content`), so the code uses a generous `max_tokens=2048` to make sure the
  `ACTION:` line is not truncated by the reasoning budget.
- **Learning Method**: In-context learning with experience memory (up to 50 experiences)
- **Context Management**: Stores successful and failed experiences
- **Reasoning**: Prompts LLM to reason about past experiences before acting
- **Temperature**: requested 0.7, but reasoning models (Kimi K3, GPT-5) only accept
  `temperature=1`, so the code auto-forces `1` for those (see `_reasoning_safe_temperature`)

## 📈 Extending the Experiment

### Ideas for Further Research

1. **Different Games**: Try other hidden-mechanic games
2. **Hybrid Approaches**: Combine RL with LLM guidance
3. **Transfer Learning**: Test how well agents transfer to similar games
4. **Ablation Studies**: Remove reasoning prompts to isolate their impact
5. **Other LLMs**: Compare different language models

### Modifying the Game

Edit `game_environment.py` to:
- Add new rooms and items
- Create more complex hidden mechanics
- Adjust difficulty and rewards
- Add new types of puzzles

## 🎓 Educational Value

This experiment demonstrates:

1. **The Power of Priors**: How language pre-training provides useful knowledge
2. **Reasoning vs. Memorization**: Different approaches to learning
3. **Sample Efficiency**: Why it matters for real-world applications
4. **The Second Half Thesis**: Moving from "can we solve it?" to "how efficiently?"

## 📚 References

- [The Second Half](https://ysymyth.github.io/The-Second-Half/) by Shunyu Yao
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- Original Q-learning paper: Watkins & Dayan (1992)

## 🤝 Contributing

Feel free to:
- Add new hidden mechanics to the game
- Implement other RL algorithms (DQN, PPO, etc.)
- Try different LLM providers
- Create more sophisticated evaluation metrics

## 📝 License

This project is for educational purposes, inspired by academic research on AI and reinforcement learning.
