"""Experiment 5-11: Conversational Interface Customization System — End-to-End Demo and Automated Verification.

This demo, in a "browserless" environment, closes the verification loop on [Natural Language → Code Modification Correctly Applied]:

  For each natural language customization request:
    1) Call the real OpenAI API, let the Agent locate and rewrite the frontend source code (agent.customize);
    2) Print the diff snippet before and after the change (difflib), and write the changes back to frontend/src;
    3) Read back the source code and assert that the changes "indeed meet the requirements" (color values/fonts/text changed as requested);
    4) Run `npm run build` (vite build) to confirm the changes do not break the application (compilation passes).

  Run multiple rounds (3 rounds in this example) to verify that multi-round iterative customizations all take effect and do not break the build.

Note: The actual "visual instant refresh via HMR in the browser" requires manually running `npm run dev` + opening the browser to view;
This demo automatically verifies that "code modifications are correctly applied, and the build always passes".

Run:
  python demo.py            # Run all 3 rounds of customization with full verification
  python demo.py --quick    # Run only the 1st round (time-saving, for quick smoke test)
  python demo.py --rounds 2 # Run only the first 2 rounds
  python demo.py --no-build # Skip vite build (only verify "changes are correctly applied")
  python demo.py -h         # View all parameters
"""

import sys
import shutil
import difflib
import argparse
import subprocess
from pathlib import Path

import agent

HERE = Path(__file__).resolve().parent
FRONTEND = HERE / "frontend"
BASELINE = HERE / "baseline"  #Initial snapshot of frontend source code to ensure demo reproducibility


# ---------------------------------------------------------------------------
#Customization request for each round + corresponding verification function.
#verify(sources) receives {relative_path: rewritten_content} and returns (passed, description).
# ---------------------------------------------------------------------------
def _all_text(sources: dict) -> str:
    return "\n".join(sources.values())


ROUNDS = [
    {
        "requirement": "Change the theme color of the send button and user message bubble from green to blue, using the blue #2563eb.",
        "verify": lambda s: (
            "#2563eb" in _all_text(s).lower().replace("#2563EB".lower(), "#2563eb"),
            "The blue value #2563eb appears in the source code",
        ),
    },
    {
        "requirement": "Change the font of the entire interface to monospace.",
        "verify": lambda s: (
            "monospace" in _all_text(s).lower(),
            "The monospace font appears in the source code",
        ),
    },
    {
        "requirement": "Change the top title text to \"我的专属客服\".",
        "verify": lambda s: (
            "My exclusive customer service" in _all_text(s),
            "The new title text \"我的专属客服\" appears in the source code",
        ),
    },
]


def restore_baseline():
    """Restore editable files under frontend/src to the initial snapshot to ensure reproducibility."""
    for rel in agent.EDITABLE_FILES:
        src = BASELINE / rel
        dst = FRONTEND / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def ensure_node_modules():
    """Ensure dependencies are installed; first npm install may be slow, which is normal."""
    if (FRONTEND / "node_modules").exists():
        return
    print(">> node_modules not found, running npm install (first time may be slow, please wait)…")
    r = subprocess.run(["npm", "install"], cwd=FRONTEND)
    if r.returncode != 0:
        raise SystemExit("npm install failed, please check Node/npm environment.")


def run_build() -> bool:
    """Run vite build and return whether compilation passes."""
    r = subprocess.run(
        ["npm", "run", "build"],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
    )
    tail = (r.stdout + r.stderr).strip().splitlines()
    for line in tail[-6:]:
        print("   | " + line)
    return r.returncode == 0


def print_diff(rel: str, old: str, new: str):
    """Print a unified diff snippet of a file before and after changes (up to a few lines)."""
    diff = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
            lineterm="",
        )
    )
    if not diff:
        print(f"   （{rel} No change)")
        return
    shown = 0
    for line in diff:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            print("   " + line)
        elif line.startswith("+"):
            print("   \033[32m" + line + "\033[0m")  # Green: added
            shown += 1
        elif line.startswith("-"):
            print("   \033[31m" + line + "\033[0m")  # Red: deleted
            shown += 1
        else:
            continue  # Omit context lines, show only actual changes
        if shown >= 20:
            print("   … (diff snippet truncated)")
            break


def parse_args(argv=None):
    """Parse command-line arguments: control how many rounds to run and whether to skip build."""
    parser = argparse.ArgumentParser(
        description="Experiment 5-11: Conversational Interface Customization System — NL → Code Modification Closed-Loop Verification."
        "For each natural language UI customization request, let the Agent rewrite the frontend source code,"
        "and assert that the changes take effect and vite build is not broken.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: run only the 1st round of customization (equivalent to --rounds 1).",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=None,
        metavar="N",
        help=f"Run only the first N rounds of customization (1..{len(ROUNDS)}); default runs all.",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip vite build, only verify 'changes are correctly applied' (faster, but does not check build).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    #  Determines the number of rounds for this run: --quick takes precedence, then --rounds, default is all.
    limit = len(ROUNDS)
    if args.quick:
        limit = 1
    elif args.rounds is not None:
        limit = max(1, min(args.rounds, len(ROUNDS)))
    rounds = ROUNDS[:limit]
    do_build = not args.no_build

    print("=" * 72)
    print("Experiment 5-11: Conversational Interface Customization System — NL → Code Modification Closed-Loop Verification")
    print("=" * 72)

    client, model = agent.build_client_and_model()
    print(f"Model: {model}")
    print(f"Rounds for this run: {limit}/{len(ROUNDS)}    Build verification: {'Enabled' if do_build else 'Disabled'}")

    restore_baseline()

    if do_build:
        ensure_node_modules()
        print("\n>> Baseline build check (before customization, ensure the app itself compiles)…")
        if not run_build():
            raise SystemExit("Baseline build failed. Please fix the frontend project first.")
        print("   Baseline build: Passed ✅")

    all_pass = True
    for i, round_def in enumerate(rounds, 1):
        req = round_def["requirement"]
        print("\n" + "-" * 72)
        print(f"Round {i} NL customization requirement: {req}")
        print("-" * 72)

        old_sources = agent.read_editable_sources(FRONTEND)

        # 1) Call Agent (real OpenAI) to get a rewrite plan
        result = agent.customize(client, model, FRONTEND, req)
        print(f"Agent description:{result.get('summary', '(None)')}")

        # 2) Write back + print diff
        changed = {}
        for f in result["files"]:
            rel = f["path"]
            new_content = f["content"]
            print(f"\n[Modified file] {rel}")
            print_diff(rel, old_sources[rel], new_content)
            (FRONTEND / rel).write_text(new_content, encoding="utf-8")
            changed[rel] = new_content

        # 3) Read back source code and assert "changes meet requirements"
        current = agent.read_editable_sources(FRONTEND)
        ok, desc = round_def["verify"](current)
        print(f"\nAssertion:{desc} -> {'Passed ✅' if ok else 'Failed ❌'}")
        if not ok:
            all_pass = False

        # 4) Build verification "did not break the app" (skipped with --no-build)
        if do_build:
            print("Build verification (vite build):")
            build_ok = run_build()
            print(f"   Build result:{'Passed ✅' if build_ok else 'Failed ❌'}")
            if not build_ok:
                all_pass = False
        else:
            print("Build verification (vite build): Skipped (--no-build)")

    print("\n" + "=" * 72)
    print(f"Multi-round customization summary:{'All passed ✅' if all_pass else 'Some failures ❌'}")
    print("Tip: Run `npm run dev` manually and open http://localhost:5173 to see HMR visuals take effect instantly.")
    print("=" * 72)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
