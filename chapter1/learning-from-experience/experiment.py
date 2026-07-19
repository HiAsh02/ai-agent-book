"""
Experiment runner to compare traditional RL vs LLM-based in-context learning.
This replicates the key insights from "The Second Half" blog post.
"""

import os
import json
import time
import random
import argparse
from datetime import datetime
from typing import Dict, Any, List
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from game_environment import TreasureHuntGame
from rl_agent import QLearningAgent
from llm_agent import LLMAgent


class ExperimentRunner:
    """
    Runs experiments comparing different learning approaches.
    """
    
    def __init__(self, results_dir: str = "results"):
        """Initialize experiment runner."""
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
        
        # Create timestamp for this experiment run
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.experiment_dir = self.results_dir / self.timestamp
        self.experiment_dir.mkdir(exist_ok=True)
        
        self.results = {}
    
    def run_rl_experiment(self,
                         num_training_episodes: int = 10000,
                         num_eval_episodes: int = 100,
                         verbose: bool = True,
                         stochastic: bool = False,
                         learning_rate: float = 0.2,
                         discount_factor: float = 0.99,
                         epsilon_decay: float = 0.9995,
                         epsilon_min: float = 0.1,
                         checkpoint_interval: int = 1000) -> Dict[str, Any]:
        """
        Run experiment with traditional Q-learning agent.

        Args:
            num_training_episodes: Number of episodes to train
            num_eval_episodes: Number of episodes to evaluate
            verbose: Whether to print details
            stochastic: Whether to use stochastic environment
            learning_rate: Q-learning learning rate (alpha)
            discount_factor: Discount factor (gamma)
            epsilon_decay: Per-episode epsilon decay
            epsilon_min: Minimum exploration rate
            checkpoint_interval: Record/print a learning-curve row every N episodes
        """
        print("\n" + "="*60)
        print("TRADITIONAL RL EXPERIMENT (Q-Learning)")
        print("="*60)

        # Initialize agent with the given hyperparameters
        agent = QLearningAgent(
            learning_rate=learning_rate,
            discount_factor=discount_factor,
            epsilon=1.0,
            epsilon_decay=epsilon_decay,
            epsilon_min=epsilon_min
        )

        # Training phase
        print(f"\nTraining for {num_training_episodes} episodes...")
        start_time = time.time()

        train_results = agent.train(
            num_episodes=num_training_episodes,
            verbose=verbose,
            stochastic=stochastic,
            checkpoint_interval=checkpoint_interval
        )

        training_time = time.time() - start_time

        # Show the learning curve (success rate over episodes) -- this is the
        # core point of experiment 7-1: the agent slowly LEARNS from experience.
        self._print_learning_curve(train_results.get("learning_curve", []),
                                    checkpoint_interval)
        
        # Evaluation phase
        print(f"\nEvaluating on {num_eval_episodes} episodes...")
        eval_results = agent.evaluate(
            num_episodes=num_eval_episodes,
            verbose=False,
            stochastic=stochastic
        )
        
        # Compile results
        results = {
            "method": "Q-Learning",
            "training_episodes": num_training_episodes,
            "training_time": training_time,
            "q_table_size": train_results["q_table_size"],
            "training_victories": train_results["total_victories"],
            "training_victory_rate": train_results["victory_rate"],
            "eval_victories": eval_results["victories"],
            "eval_victory_rate": eval_results["victory_rate"],
            "eval_avg_reward": eval_results["avg_reward"],
            "eval_avg_steps": eval_results["avg_length"],
            "episode_rewards": train_results["episode_rewards"],
            "episode_lengths": train_results["episode_lengths"],
            "learning_curve": train_results.get("learning_curve", [])
        }

        # Save agent
        agent.save(self.experiment_dir / "rl_agent.pkl")
        
        print(f"\nRL Training Summary:")
        print(f"  Training time: {training_time:.2f} seconds")
        print(f"  Q-table size: {train_results['q_table_size']} states")
        print(f"  Training victory rate: {train_results['victory_rate']:.2%}")
        print(f"  Evaluation victory rate: {eval_results['victory_rate']:.2%}")
        
        return results
    
    def _print_learning_curve(self, learning_curve: List[Dict[str, Any]],
                              checkpoint_interval: int):
        """Print the Q-learning success-rate-over-episodes table.

        This is the whole point of experiment 7-1: watch the victory rate climb
        from 0% (blind exploration) to ~100% only after thousands of episodes.
        """
        if not learning_curve:
            return

        window = checkpoint_interval if checkpoint_interval > 0 else 1000
        print("\n" + "-"*60)
        print(f"LEARNING CURVE (Q-Learning success rate over episodes)")
        print(f"Win rate based on the most recent {window} sliding window of games")
        print("-"*60)
        print(f"{'Episodes':>10} | {'Victory rate':>12} | {'Q-table':>8} | {'epsilon':>8}")
        print(f"{'-'*10}-+-{'-'*12}-+-{'-'*8}-+-{'-'*8}")
        for row in learning_curve:
            print(f"{row['episode']:>10} | {row['victory_rate']*100:>11.1f}% | "
                  f"{row['q_table_size']:>8} | {row['epsilon']:>8.3f}")
        print("-"*60)

    def run_llm_experiment(self,
                          num_training_episodes: int = 20,
                          num_eval_episodes: int = 10,
                          verbose: bool = True,
                          stochastic: bool = False,
                          model: str = "kimi-k3") -> Dict[str, Any]:
        """
        Run experiment with LLM-based in-context learning agent.
        
        Args:
            num_training_episodes: Number of episodes to train
            num_eval_episodes: Number of episodes to evaluate
            verbose: Whether to print details
            stochastic: Whether to use stochastic environment
        """
        print("\n" + "="*70)
        print(f"LLM-BASED IN-CONTEXT LEARNING EXPERIMENT ({model})")
        print("="*70)

        # Check for API key
        api_key = os.getenv("MOONSHOT_API_KEY")
        if not api_key and not os.getenv("OPENROUTER_API_KEY"):
            print("\n⚠️ Warning: MOONSHOT_API_KEY not set. Skipping LLM experiment.")
            print("📝 Please set your Kimi API key: export MOONSHOT_API_KEY='your-key-here'")
            print("🔗 Get your key at: https://platform.moonshot.cn/")
            print("💡 Or set OPENROUTER_API_KEY as a universal fallback.")
            return None

        print("\n✅ API key found. Initializing LLM agent...")
        print(f"🧠 Using {model} model for reasoning and in-context learning")
        print("📖 The LLM will show its complete thought process for each decision")

        # Initialize agent
        agent = LLMAgent(
            api_key=api_key,
            model=model,
            temperature=0.7,
            max_experiences=50
        )
        
        # Training phase (experience collection)
        print(f"\n🎓 Training Phase: Playing {num_training_episodes} episodes")
        print("💡 Watch how the LLM learns from experience without any parameter updates!")
        print("-"*70)
        
        start_time = time.time()
        
        train_results = agent.train(
            num_episodes=num_training_episodes,
            verbose=verbose,
            stochastic=stochastic
        )
        
        training_time = time.time() - start_time
        
        # Evaluation phase
        print(f"\nEvaluating on {num_eval_episodes} episodes...")
        eval_results = agent.evaluate(
            num_episodes=num_eval_episodes,
            verbose=False,
            stochastic=stochastic
        )
        
        # Compile results
        results = {
            "method": "LLM In-Context Learning",
            "training_episodes": num_training_episodes,
            "training_time": training_time,
            "experiences_collected": train_results["experiences_collected"],
            "api_calls": train_results["total_api_calls"],
            "total_tokens": train_results["total_tokens"],
            "training_victories": train_results["total_victories"],
            "training_victory_rate": train_results["victory_rate"],
            "eval_victories": eval_results["victories"],
            "eval_victory_rate": eval_results["victory_rate"],
            "eval_avg_reward": eval_results["avg_reward"],
            "eval_avg_steps": eval_results["avg_length"],
            "episode_rewards": train_results["episode_rewards"],
            "episode_lengths": train_results["episode_lengths"]
        }
        
        # Save experiences
        agent.save_experiences(self.experiment_dir / "llm_experiences.json")
        
        print(f"\nLLM Training Summary:")
        print(f"  Training time: {training_time:.2f} seconds")
        print(f"  Experiences collected: {train_results['experiences_collected']}")
        print(f"  API calls: {train_results['total_api_calls']}")
        print(f"  Training victory rate: {train_results['victory_rate']:.2%}")
        print(f"  Evaluation victory rate: {eval_results['victory_rate']:.2%}")
        
        return results
    
    def compare_learning_curves(self, rl_results: Dict, llm_results: Dict):
        """
        Create visualization comparing learning curves of both methods.
        """
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Plot 1: Victory rate over episodes
        ax = axes[0, 0]
        
        # RL victory rate (computed over windows)
        rl_rewards = rl_results["episode_rewards"]
        window_size = 100
        rl_victories = []
        for i in range(0, len(rl_rewards), window_size):
            window = rl_rewards[i:i+window_size]
            victories = sum(1 for r in window if r > 50) / len(window)
            rl_victories.append(victories)
        
        ax.plot(range(0, len(rl_rewards), window_size), rl_victories, 
                label=f"Q-Learning ({len(rl_rewards)} episodes)", linewidth=2)
        
        # LLM victory rate (per episode)
        if llm_results:
            llm_rewards = llm_results["episode_rewards"]
            llm_victories = [1 if r > 50 else 0 for r in llm_rewards]
            llm_cumulative = np.cumsum(llm_victories) / (np.arange(len(llm_victories)) + 1)
            ax.plot(range(len(llm_cumulative)), llm_cumulative,
                   label=f"LLM In-Context ({len(llm_rewards)} episodes)", linewidth=2)
        
        ax.set_xlabel("Episodes")
        ax.set_ylabel("Victory Rate")
        ax.set_title("Learning Progress: Victory Rate Over Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Plot 2: Average reward over episodes
        ax = axes[0, 1]
        
        # RL rewards (smoothed)
        rl_smooth = []
        for i in range(0, len(rl_rewards), window_size):
            window = rl_rewards[i:i+window_size]
            rl_smooth.append(np.mean(window))
        
        ax.plot(range(0, len(rl_rewards), window_size), rl_smooth,
                label="Q-Learning", linewidth=2)
        
        # LLM rewards
        if llm_results:
            llm_rewards = llm_results["episode_rewards"]
            ax.plot(range(len(llm_rewards)), llm_rewards,
                   label="LLM In-Context", linewidth=2, alpha=0.7)
        
        ax.set_xlabel("Episodes")
        ax.set_ylabel("Episode Reward")
        ax.set_title("Learning Progress: Reward Over Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Plot 3: Sample efficiency comparison
        ax = axes[1, 0]
        
        categories = ["Training\nEpisodes", "Evaluation\nVictory Rate", "Training\nTime (s)"]
        rl_values = [
            rl_results["training_episodes"],
            rl_results["eval_victory_rate"] * 100,
            rl_results["training_time"]
        ]
        
        if llm_results:
            llm_values = [
                llm_results["training_episodes"],
                llm_results["eval_victory_rate"] * 100,
                llm_results["training_time"]
            ]
        else:
            llm_values = [0, 0, 0]
        
        x = np.arange(len(categories))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, rl_values, width, label='Q-Learning')
        bars2 = ax.bar(x + width/2, llm_values, width, label='LLM In-Context')
        
        ax.set_ylabel('Value')
        ax.set_title('Sample Efficiency Comparison')
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend()
        
        # Add value labels on bars
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax.annotate(f'{height:.1f}',
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom')
        
        # Plot 4: Key insights text
        ax = axes[1, 1]
        ax.axis('off')
        
        insights = [
            "KEY INSIGHTS (Replicating 'The Second Half' Findings):",
            "",
            "1. SAMPLE EFFICIENCY:",
            f"   • Q-Learning: {rl_results['training_episodes']} episodes needed",
            f"   • LLM: {llm_results['training_episodes'] if llm_results else 'N/A'} episodes needed",
            f"   • Improvement: {rl_results['training_episodes'] / (llm_results['training_episodes'] if llm_results and llm_results['training_episodes'] > 0 else 1):.1f}x fewer samples",
            "",
            "2. GENERALIZATION:",
            "   • Q-Learning: Learns specific state-action mappings",
            "   • LLM: Reasons about patterns and transfers knowledge",
            "",
            "3. HIDDEN MECHANICS DISCOVERY:",
            "   • Q-Learning: Requires extensive exploration",
            "   • LLM: Can hypothesize and test theories",
            "",
            "4. COMPUTATIONAL TRADE-OFF:",
            f"   • Q-Learning: Fast inference, slow learning",
            f"   • LLM: Slower inference (API calls), fast adaptation"
        ]
        
        y_pos = 0.9
        for line in insights:
            if line.startswith("KEY INSIGHTS"):
                ax.text(0.5, y_pos, line, transform=ax.transAxes,
                       fontsize=12, fontweight='bold', ha='center')
            elif line.startswith(("1.", "2.", "3.", "4.")):
                ax.text(0.1, y_pos, line, transform=ax.transAxes,
                       fontsize=11, fontweight='bold')
            else:
                ax.text(0.1, y_pos, line, transform=ax.transAxes,
                       fontsize=10)
            y_pos -= 0.06
        
        plt.tight_layout()
        plt.savefig(self.experiment_dir / "comparison_plots.png", dpi=150)
        plt.show()
        
        print(f"\nPlots saved to {self.experiment_dir / 'comparison_plots.png'}")
    
    def run_full_experiment(self,
                           rl_episodes: int = 10000,
                           llm_episodes: int = 20,
                           eval_episodes: int = 100,
                           verbose: bool = False,
                           stochastic: bool = False,
                           model: str = "kimi-k3",
                           checkpoint_interval: int = 1000,
                           rl_hyperparams: Dict[str, float] = None):
        """
        Run full comparison experiment.

        Args:
            rl_episodes: Number of episodes for RL training
            llm_episodes: Number of episodes for LLM training
            eval_episodes: Number of episodes for RL evaluation
            verbose: Whether to print details
            stochastic: Whether to use stochastic environment
            model: LLM model name (Moonshot/Kimi)
            checkpoint_interval: Learning-curve sampling interval (RL)
            rl_hyperparams: Optional dict overriding Q-learning hyperparameters
        """
        print("\n" + "="*70)
        print("EXPERIMENT: Traditional RL vs LLM In-Context Learning")
        print("Replicating insights from 'The Second Half' by Shunyu Yao")
        print("="*70)

        # Show game rules for reference
        game = TreasureHuntGame(stochastic=stochastic)
        print("\n" + game.get_hidden_rules())

        rl_hyperparams = rl_hyperparams or {}

        # Run RL experiment
        rl_results = self.run_rl_experiment(
            num_training_episodes=rl_episodes,
            num_eval_episodes=eval_episodes,
            verbose=verbose,
            stochastic=stochastic,
            checkpoint_interval=checkpoint_interval,
            **rl_hyperparams
        )
        self.results["rl"] = rl_results

        # Run LLM experiment
        llm_results = self.run_llm_experiment(
            num_training_episodes=llm_episodes,
            num_eval_episodes=10,
            verbose=verbose,
            stochastic=stochastic,
            model=model
        )
        self.results["llm"] = llm_results
        
        # Save combined results
        with open(self.experiment_dir / "experiment_results.json", 'w') as f:
            json.dump(self.results, f, indent=2)
        
        # Generate comparison plots
        if llm_results:
            self.compare_learning_curves(rl_results, llm_results)
        
        # Print final comparison
        print("\n" + "="*70)
        print("EXPERIMENT RESULTS SUMMARY")
        print("="*70)
        
        print("\n1. SAMPLE EFFICIENCY:")
        print(f"   Q-Learning needed {rl_results['training_episodes']} episodes")
        if llm_results:
            print(f"   LLM needed {llm_results['training_episodes']} episodes")
            print(f"   → LLM is {rl_results['training_episodes'] / llm_results['training_episodes']:.1f}x more sample efficient")
        
        print("\n2. PERFORMANCE:")
        print(f"   Q-Learning eval victory rate: {rl_results['eval_victory_rate']:.2%}")
        if llm_results:
            print(f"   LLM eval victory rate: {llm_results['eval_victory_rate']:.2%}")
        
        print("\n3. COMPUTATIONAL COST:")
        print(f"   Q-Learning: {rl_results['training_time']:.2f} seconds, {rl_results['q_table_size']} states")
        if llm_results:
            print(f"   LLM: {llm_results['training_time']:.2f} seconds, {llm_results['api_calls']} API calls")
        
        print(f"\nResults saved to: {self.experiment_dir}")
        
        return self.results


def main():
    """Main entry point for the experiment."""
    parser = argparse.ArgumentParser(
        description="Experiment 7-1 / 7-2: Compare Q-learning and LLM's \"learning from experience\" in a treasure hunt game."
                    "Q-learning runs completely offline (no API required); LLM mode requires Moonshot/Kimi API Key.",
        epilog="Example: \n"
               "  python experiment.py --mode qlearning              # Run Q-learning only (offline, output learning curve)\n"
               "  python experiment.py --mode qlearning --rl-episodes 10000 --seed 42\n"
               "  python experiment.py --mode both --model kimi-k3  # RL vs LLM comparison\n"
               "  python experiment.py --mode llm --llm-episodes 20   # Run LLM agent only",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--mode", choices=["both", "qlearning", "rl", "llm"], default="both",
        help="Which agent to run: qlearning/rl runs Q-learning only (offline),"
             "llm runs LLM agent only (requires API), both runs both for comparison (default)"
    )
    parser.add_argument(
        "--rl-episodes", type=int, default=10000,
        help="Number of training episodes for Q-learning (default 10000, corresponds to Experiment 7-1)"
    )
    parser.add_argument(
        "--llm-episodes", type=int, default=20,
        help="Number of training episodes for LLM agent (default 20)"
    )
    parser.add_argument(
        "--eval-episodes", type=int, default=100,
        help="Number of greedy evaluation episodes after Q-learning training (default 100)"
    )
    parser.add_argument(
        "--checkpoint-interval", type=int, default=1000,
        help="Learning curve sampling interval: record win rate / Q-table size every N episodes (default 1000)"
    )
    parser.add_argument(
        "--model", type=str, default=os.getenv("MOONSHOT_MODEL", "kimi-k3"),
        help="LLM model name (Moonshot/Kimi, default kimi-k3, can be overridden by MOONSHOT_MODEL environment variable)"
    )
    parser.add_argument(
        "--output", type=str, default="results",
        help="Output directory (default results/, a timestamped subdirectory will be created for each run)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility of Q-learning learning curve (default not fixed)"
    )
    # Q-learning hyperparameters
    parser.add_argument("--learning-rate", type=float, default=0.2,
                        help="Q-learning learning rate alpha (default 0.2)")
    parser.add_argument("--discount", type=float, default=0.99,
                        help="Discount factor gamma (default 0.99)")
    parser.add_argument("--epsilon-decay", type=float, default=0.9995,
                        help="Epsilon decay factor per episode (default 0.9995)")
    parser.add_argument("--epsilon-min", type=float, default=0.1,
                        help="Minimum exploration rate epsilon (default 0.1)")
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print detailed information during training"
    )
    parser.add_argument(
        "--skip-llm", action="store_true",
        help="[Legacy usage] Skip LLM experiment, equivalent to --mode qlearning"
    )
    parser.add_argument(
        "--stochastic", action="store_true",
        help="Use stochastic environment (rewards and actions have random perturbations)"
    )
    parser.add_argument(
        "--deterministic", action="store_true",
        help="Use deterministic environment (default)"
    )

    args = parser.parse_args()

    # Handle environment mode
    if args.deterministic and args.stochastic:
        print("Error: Cannot specify both --deterministic and --stochastic")
        return

    # Resolve run mode (--skip-llm kept as a backwards-compatible alias)
    mode = "qlearning" if args.skip_llm else args.mode

    # Seed for reproducible Q-learning learning curves
    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)
        print(f"\n🎲 Random seed set to {args.seed} for reproducibility")

    stochastic = args.stochastic  # Default is False (deterministic)

    if stochastic:
        print("\n🎲 Running experiment with STOCHASTIC environment")
        print("  - Random reward variations")
        print("  - 3% chance of action failure")
        print("  - Combat and crafting variations\n")
    else:
        print("\n🎯 Running experiment with DETERMINISTIC environment\n")

    rl_hyperparams = {
        "learning_rate": args.learning_rate,
        "discount_factor": args.discount,
        "epsilon_decay": args.epsilon_decay,
        "epsilon_min": args.epsilon_min,
    }

    # Run experiment
    runner = ExperimentRunner(results_dir=args.output)

    if mode in ("qlearning", "rl"):
        # Run only the Q-learning experiment (fully offline, no API needed)
        rl_results = runner.run_rl_experiment(
            num_training_episodes=args.rl_episodes,
            num_eval_episodes=args.eval_episodes,
            verbose=args.verbose,
            stochastic=stochastic,
            checkpoint_interval=args.checkpoint_interval,
            **rl_hyperparams
        )
        runner.results["rl"] = rl_results
        with open(runner.experiment_dir / "experiment_results.json", 'w') as f:
            json.dump(runner.results, f, indent=2)
        print(f"\nResults saved to: {runner.experiment_dir}")
        print("\nSkipped LLM experiment. Use --mode both with an API key to compare.")
    elif mode == "llm":
        # Run only the LLM experiment
        llm_results = runner.run_llm_experiment(
            num_training_episodes=args.llm_episodes,
            verbose=args.verbose,
            stochastic=stochastic,
            model=args.model
        )
        runner.results["llm"] = llm_results
        with open(runner.experiment_dir / "experiment_results.json", 'w') as f:
            json.dump(runner.results, f, indent=2)
        print(f"\nResults saved to: {runner.experiment_dir}")
    else:
        # Run full comparison
        results = runner.run_full_experiment(
            rl_episodes=args.rl_episodes,
            llm_episodes=args.llm_episodes,
            eval_episodes=args.eval_episodes,
            verbose=args.verbose,
            stochastic=stochastic,
            model=args.model,
            checkpoint_interval=args.checkpoint_interval,
            rl_hyperparams=rl_hyperparams
        )

    print("\nExperiment complete!")


if __name__ == "__main__":
    main()
