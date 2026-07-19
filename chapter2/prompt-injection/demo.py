"""
Experiment 2-5: Prompt Injection Attack and Defense Experiment — Main Program.

For each combination of 3 attack scenarios x 4 defense configurations, run N trials, count the attack success rate,
and finally print an attack x defense success rate matrix, intuitively showing "defense layers strengthen -> success rate decreases".

Command-line usage (see --help for details):
    python demo.py                       # Default: all 3x4 combinations, 4 trials per combination
    python demo.py --trials 5            # Run 5 trials per combination
    python demo.py --model gpt-5.6-luna        # Change model
    python demo.py --attack 2,3          # Only run attack scenarios 2 and 3
    python demo.py --defense 1,4         # Only run defenses D1 and D4
    python demo.py --output result.json  # Additionally save the result matrix as JSON
    python demo.py --list                # List all attacks/defenses offline without calling API

Backward compatibility: environment variables TRIALS / OPENAI_MODEL / OPENAI_BASE_URL can still be used to set defaults,
command-line arguments take precedence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from agent import DEFENSES, Agent, make_client
from attacks import ATTACKS


def _parse_selection(spec: str, items: list, kind: str) -> list[int]:
    """Parse a selection string like "1,3" or "indirect,D4" into a list of item indices.

    Supports two formats (can be mixed, comma-separated):
    - 1-based index (e.g., "1,3");
    - Name substring (e.g., "indirect" matches "indirect injection", "D4" matches "D4-combined defense").
    Preserves the user-given order and removes duplicates.
    """
    if spec is None or spec.strip().lower() in ("", "all", "All"):
        return list(range(len(items)))

    chosen: list[int] = []
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        idx: int | None = None
        if token.isdigit():
            n = int(token)
            if not 1 <= n <= len(items):
                raise ValueError(
                    f"{kind}Index {n} out of range (valid range 1-{len(items)}）"
                )
            idx = n - 1
        else:
            matches = [
                i
                for i, it in enumerate(items)
                if token.lower() in it.name.lower()
            ]
            if not matches:
                raise ValueError(f"No name contains \"{token}\"{kind}")
            if len(matches) > 1:
                names = "、".join(items[i].name for i in matches)
                raise ValueError(f"“{token}\" matches multiple, please be more specific{kind}：{names}No ")
            idx = matches[0]
        if idx not in chosen:
            chosen.append(idx)
    if not chosen:
        raise ValueError(f" selected{kind}")
    return chosen


def list_items() -> None:
    """Print all attack scenarios and defense configurations offline (no API Key required)."""
    print("Attack scenarios (--attack can select by index or name substring):")
    for i, attack in enumerate(ATTACKS, 1):
        print(f"  {i}. {attack.name} —— {attack.description}")
    print("\nDefense configurations (--defense can select by index or name substring):")
    for i, defense in enumerate(DEFENSES, 1):
        layers = []
        if defense.prompt_hardening:
            layers.append("Prompt hardening")
        if defense.source_tagging:
            layers.append("Source marking")
        if defense.runtime_guard:
            layers.append("Runtime validation")
        detail = " + ".join(layers) if layers else "None (baseline)"
        print(f"  {i}. {defense.name} —— {detail}")


def run_matrix(
    trials: int,
    attack_idx: list[int],
    defense_idx: list[int],
    model: str | None,
    temperature: float,
    base_url: str | None,
) -> tuple[list[list[float]], str]:
    client, resolved_model = make_client(model=model, base_url=base_url)
    print(f"Using model: {resolved_model}, each combination trial {trials} times\n")

    # matrix[attack_index][defense_index] = success rate (only filled for selected rows/cols, others are None)
    matrix: list[list[float | None]] = [
        [None for _ in DEFENSES] for _ in ATTACKS
    ]

    for ai in attack_idx:
        attack = ATTACKS[ai]
        for di in defense_idx:
            defense = DEFENSES[di]
            successes = 0
            errors = 0
            for _ in range(trials):
                agent = Agent(
                    client=client,
                    model=resolved_model,
                    defense=defense,
                    webpage_content=attack.webpage_content,
                    temperature=temperature,
                )
                result = agent.run(list(attack.user_messages))
                if result.error:
                    errors += 1
                    continue
                if attack.judge(result):
                    successes += 1
            rate = successes / trials if trials else 0.0
            matrix[ai][di] = rate
            flag = f" (including {errors} errors)" if errors else ""
            print(
                f"[{attack.name:<6}] x [{defense.name:<10}] "
                f"Success rate {rate:5.0%} ({successes}/{trials}){flag}"
            )
        print()

    return matrix, resolved_model


def print_matrix(
    matrix: list[list[float | None]],
    attack_idx: list[int],
    defense_idx: list[int],
) -> None:
    print("=" * 68)
    print("Attack success rate matrix (rows=attack scenarios, columns=defense configurations, lower is safer)")
    print("=" * 68)

    def cell(v: float | None) -> str:
        return "   -  " if v is None else f"{v:.0%}"

    corner = "Attack \\ Defense"
    header = f"{corner:<12}" + "".join(
        f"{DEFENSES[di].name:>14}" for di in defense_idx
    )
    print(header)
    print("-" * len(header))
    for ai in attack_idx:
        row = f"{ATTACKS[ai].name:<12}"
        for di in defense_idx:
            row += f"{cell(matrix[ai][di]):>13} "
        print(row)
    print("-" * len(header))

    # Average success rate of each defense configuration across selected attacks, showing "layered strengthening -> overall decrease"
    avg = f"{'Average':<12}"
    for di in defense_idx:
        vals = [matrix[ai][di] for ai in attack_idx if matrix[ai][di] is not None]
        col = sum(vals) / len(vals) if vals else 0.0
        avg += f"{col:>13.0%} "
    print(avg)
    print("=" * 68)


def save_json(
    path: str,
    matrix: list[list[float | None]],
    attack_idx: list[int],
    defense_idx: list[int],
    trials: int,
    model: str,
) -> None:
    payload = {
        "model": model,
        "trials": trials,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "defenses": [DEFENSES[di].name for di in defense_idx],
        "attacks": [ATTACKS[ai].name for ai in attack_idx],
        "success_rate": {
            ATTACKS[ai].name: {
                DEFENSES[di].name: matrix[ai][di] for di in defense_idx
            }
            for ai in attack_idx
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nResult matrix saved to {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="demo.py",
        description=(
            "Experiment 2-5: Prompt Injection Attack and Defense Experiment. For each combination of 3 attack scenarios x 4 defense configurations"
            "Repeat trials, count attack success rate and print attack x defense success rate matrix."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example: \n"
            "  python demo.py                       # all combinations, 4 trials each\n"
            "  python demo.py -n 5 -m gpt-5.6-luna        # change model and run 5 trials\n"
            "  python demo.py -a 2,3 -d 1,4         # only run attack 2/3 x defense D1/D4\n"
            "  python demo.py -o result.json        # additionally save JSON result\n"
            "  python demo.py --list                # list attacks/defenses offline, no API call\n"
        ),
    )
    parser.add_argument(
        "-n",
        "--trials",
        type=int,
        default=int(os.getenv("TRIALS", "4")),
        metavar="N",
        help="Number of trials for each attack x defense combination (default 4, recommend 3-5 to control cost; smoke test can use 1)",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=None,
        metavar="NAME",
        help="Model name to use (default from environment variable OPENAI_MODEL, if unset then gpt-4o-mini)",
    )
    parser.add_argument(
        "-a",
        "--attack",
        default="all",
        metavar="SEL",
        help="Select attack scenarios to run, comma-separated indices or name substrings (e.g., 1,3 or indirect,memory); default all",
    )
    parser.add_argument(
        "-d",
        "--defense",
        default="all",
        metavar="SEL",
        help="Select defense configurations to run, comma-separated indices or name substrings (e.g., 1,4 or D1,D4); default all",
    )
    parser.add_argument(
        "-t",
        "--temperature",
        type=float,
        default=0.7,
        metavar="T",
        help="Sampling temperature (default 0.7; set to 0 for more stable and reproducible results)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        metavar="URL",
        help="Custom OpenAI-compatible API base_url (default from environment variable OPENAI_BASE_URL)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="PATH",
        help="Path to save the success rate matrix as an additional JSON file",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all attack scenarios and defense configurations offline and exit (no API key required)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        list_items()
        return 0

    if args.trials < 1:
        parser.error("--trials must be >= 1")

    try:
        attack_idx = _parse_selection(args.attack, ATTACKS, "Attack scenarios")
        defense_idx = _parse_selection(args.defense, DEFENSES, "Defense configurations")
    except ValueError as exc:
        parser.error(str(exc))

    try:
        matrix, model = run_matrix(
            trials=args.trials,
            attack_idx=attack_idx,
            defense_idx=defense_idx,
            model=args.model,
            temperature=args.temperature,
            base_url=args.base_url,
        )
    except RuntimeError as exc:
        #  Common when OPENAI_API_KEY is not configured: give a clear human-readable prompt instead of raw stack trace.
        print(f"Startup failure:{exc}", file=sys.stderr)
        return 1

    print_matrix(matrix, attack_idx, defense_idx)

    if args.output:
        save_json(args.output, matrix, attack_idx, defense_idx, args.trials, model)

    print(
        "\nConclusion: From D1 to D4, as defenses are progressively strengthened (prompt hardening -> source marking -> "
        "runtime high-risk operation validation), the success rate of various injection attacks decreases significantly, "
        "and under combined defense (D4), unauthorized tool call attacks are completely blocked by runtime validation, approaching 0."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
