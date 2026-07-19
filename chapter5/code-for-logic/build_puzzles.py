#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate/validate "Knights and Knaves" puzzles and export to puzzles.json.

Each sentence of every puzzle is represented using the structured DSL in csp_solver.py (see the top of that file),
which can both render into Chinese puzzle text (for LLM consumption) and be directly translated into python-constraint constraints for solving.
This script uses python-constraint to verify that each puzzle has a unique solution before writing it out—this ensures unambiguous truth-value solutions,
while demonstrating the core of Experiment 5-2: formalizing puzzles as CSPs and solving them offline with a solver.

Convention: knights always tell the truth, knaves always lie. t[name]=True means knight.

Usage:
    python build_puzzles.py                       # Export the built-in 12 curated puzzles (default)
    python build_puzzles.py --generate 20         # Randomly generate 20 puzzles with unique solutions
    python build_puzzles.py --generate 20 --min-people 3 --max-people 5 --seed 7
    python build_puzzles.py --output my.json      # Specify output file
"""
import argparse
import json
import random

from csp_solver import render_nl, solve, solve_labeled

#  Each puzzle: id, list of names, dict{name: structured statement}. The Chinese puzzle text is automatically rendered from the structured statements,
#  but curated puzzles retain hand-written more natural Chinese (see STATEMENTS_NL override).
CURATED = [
    ("kk01", ["A", "B"], {
        "A": ["is", "B", "knave"],
        "B": ["and", ["is", "A", "knave"], ["is", "B", "knave"]]}),
    ("kk02", ["A", "B"], {
        "A": ["same", "A", "B"],
        "B": ["diff", "A", "B"]}),
    ("kk03", ["A", "B"], {
        "A": ["count", "knight", ">=", 1],
        "B": ["is", "A", "knave"]}),
    ("kk04", ["A", "B", "C"], {
        "A": ["is", "B", "knave"],
        "B": ["is", "C", "knave"],
        "C": ["and", ["is", "A", "knave"], ["is", "B", "knave"]]}),
    ("kk05", ["A", "B", "C"], {
        "A": ["is", "B", "knight"],
        "B": ["is", "C", "knave"],
        "C": ["same", "A", "B"]}),
    ("kk06", ["A", "B", "C"], {
        "A": ["same", "B", "C"],
        "B": ["is", "A", "knave"],
        "C": ["same", "C", "A"]}),
    ("kk07", ["A", "B", "C"], {
        "A": ["or", ["is", "A", "knave"], ["is", "B", "knight"]],
        "B": ["is", "A", "knight"],
        "C": ["is", "B", "knave"]}),
    ("kk08", ["A", "B", "C", "D"], {
        "A": ["same", "B", "D"],
        "B": ["is", "C", "knave"],
        "C": ["is", "D", "knight"],
        "D": ["diff", "B", "C"]}),
    ("kk09", ["A", "B", "C", "D"], {
        "A": ["is", "B", "knight"],
        "B": ["is", "C", "knave"],
        "C": ["is", "D", "knight"],
        "D": ["diff", "A", "B"]}),
    ("kk10", ["A", "B", "C", "D"], {
        "A": ["count", "knave", ">=", 3],
        "B": ["is", "A", "knave"],
        "C": ["is", "B", "knight"],
        "D": ["is", "C", "knave"]}),
    ("kk11", ["A", "B", "C", "D", "E"], {
        "A": ["is", "B", "knight"],
        "B": ["is", "C", "knave"],
        "C": ["is", "D", "knight"],
        "D": ["is", "E", "knave"],
        "E": ["count", "knight", ">=", 2]}),
    ("kk12", ["A", "B", "C", "D", "E"], {
        "A": ["is", "B", "knight"],
        "B": ["is", "C", "knave"],
        "C": ["is", "D", "knave"],
        "D": ["is", "E", "knight"],
        "E": ["same", "A", "C"]}),
]

#  Hand-written Chinese puzzle text for curated puzzles (more natural than auto-rendered). Uncovered sentences fall back to render_nl.
STATEMENTS_NL = {
    ("kk01", "B"): "Neither of us is a knight.",
    ("kk02", "A"): "I am of the same type as B (both knights or both knaves).",
    ("kk02", "B"): "I am of a different type from A.",
    ("kk03", "A"): "At least one of us is a knight.",
    ("kk04", "C"): "A and B are both knaves.",
    ("kk06", "C"): "I am of the same type as A.",
    ("kk07", "A"): "I am a knave, or B is a knight.",
    ("kk09", "D"): "A and B are not of the same type.",
    ("kk10", "A"): "At least three of the four of us are knaves.",
    ("kk11", "E"): "At least two of the five of us are knights.",
    ("kk12", "E"): "A and C are of the same type.",
}


def build_puzzle(pid, names, structs, nl_overrides=None):
    """Solve and validate (require unique solution) and assemble into one record for writing to puzzles.json."""
    sols = solve_labeled(names, structs)
    if len(sols) != 1:
        raise ValueError(f"{pid}  Solution not unique: {len(sols)} solutions -> {sols}")
    solution = sols[0]

    nl_overrides = nl_overrides or {}
    statements = {n: nl_overrides.get(n, render_nl(structs[n])) for n in names}
    lines = [f"{n}: 「{statements[n]}」" for n in names]
    desc = (
        f"There are {len(names)} inhabitants on this island: {', '.join(names)}。"
        "Each inhabitant is either a knight (always tells the truth) or a knave (always lies)."
        "They each said the following:\n" + "\n".join(lines)
    )
    return dict(id=pid, num_people=len(names), names=names,
                statements=statements, statements_struct=structs,
                description=desc, solution=solution)


# ---------------- Random Generator ----------------
def _random_stmt(speaker, names, rng):
    """Randomly generate a valid structured statement for the speaker."""
    others = [n for n in names if n != speaker]
    kind = rng.choice(["is", "is", "same", "diff", "count"])
    if kind == "is":
        return ["is", rng.choice(others), rng.choice(["knight", "knave"])]
    if kind == "same":
        return ["same", speaker, rng.choice(others)]
    if kind == "diff":
        return ["diff", speaker, rng.choice(others)]
    # count: the number of people of a certain role among all satisfies a comparison
    role = rng.choice(["knight", "knave"])
    op = rng.choice([">=", "<=", "=="])
    k = rng.randint(1, len(names))
    return ["count", role, op, k]


def generate(count, min_people, max_people, seed):
    """Randomly generate count puzzles with unique solutions (filtered using python-constraint)."""
    rng = random.Random(seed)
    names_pool = ["A", "B", "C", "D", "E", "F", "G"]
    puzzles = []
    attempts = 0
    while len(puzzles) < count and attempts < count * 2000:
        attempts += 1
        n = rng.randint(min_people, max_people)
        names = names_pool[:n]
        structs = {sp: _random_stmt(sp, names, rng) for sp in names}
        if len(solve(names, structs)) != 1:      #  Only keep puzzles with unique solutions
            continue
        pid = f"gen{len(puzzles) + 1:03d}"
        puzzles.append(build_puzzle(pid, names, structs))
    if len(puzzles) < count:
        print(f"Warning: {attempts} attempts only generated {len(puzzles)}/{count} puzzles with unique solutions.")
    return puzzles


def build_curated():
    out = []
    for pid, names, structs in CURATED:
        nl = {n: STATEMENTS_NL[(pid, n)]
              for n in names if (pid, n) in STATEMENTS_NL}
        out.append(build_puzzle(pid, names, structs, nl))
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Generate/validate knights and knaves puzzles and export puzzles.json"
                    "(Solve offline with python-constraint, verify each puzzle has a unique solution)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--generate", type=int, metavar="N", default=0,
                    help="Randomly generate N puzzles with unique solutions (default 0 = export built-in 12 selected puzzles)")
    ap.add_argument("--min-people", type=int, default=2,
                    help="Minimum number of residents per puzzle when randomly generating (default 2)")
    ap.add_argument("--max-people", type=int, default=5,
                    help="Maximum number of residents per puzzle when randomly generating (difficulty cap, default 5)")
    ap.add_argument("--seed", type=int, default=42,
                    help="Random seed for reproducibility (default 42)")
    ap.add_argument("--output", default="puzzles.json",
                    help="Output file path (default puzzles.json)")
    args = ap.parse_args()

    if args.generate > 0:
        print(f"Randomly generate {args.generate} puzzles"
              f"({args.min_people}~{args.max_people} people, seed={args.seed})...")
        out = generate(args.generate, args.min_people, args.max_people, args.seed)
    else:
        out = build_curated()

    for p in out:
        print(f"{p['id']}: OK unique solution = {p['solution']}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nWritten {len(out)} puzzles to {args.output}")


if __name__ == "__main__":
    main()
