#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Experiment 10-8: Voice Werewolf Agent System — Run a full game with one click.

Accompanies Chapter 10 "Experiment 10-8: Voice Werewolf Agent System" of "Deep Understanding of AI Agents".

This demo demonstrates three things (corresponding to the architecture design in the book):
1. **Multi-Agent**: Each player = an independent LLM Agent (OpenAI, default gpt-5.6-luna).
2. **Information permission control**: The judge delivers information into each Agent's private context according to the role — werewolves know their teammates, the seer knows the check result, public speeches go to everyone. After the game, print an audit table + automatic verification, objectively proving correct information isolation.
3. **Judge orchestration**: Deterministic judge orchestrates night (kill/check/heal) → day (death announcement/speech/vote) → settlement.

Voice is an **optional enhancement** (--voice, uses OpenAI tts-1 to synthesize public speeches). The default text mode can run a full game completely and reproducibly.

Usage:
    export OPENAI_API_KEY=sk-...
    python demo.py                 # Text mode: run a full game (LLM decisions, default)
    python demo.py --offline       # Offline mode: rule-based decisions, zero cost, reproducible, no API Key needed
    python demo.py --seed 7        # Change the role distribution for a game
    python demo.py --players 9 --wolves 3   # Customize number of players and werewolves
    python demo.py --voice         # Additionally synthesize public speeches to audio/
    python demo.py --voice --play  # Synthesize and play (macOS afplay)
    python demo.py --offline --log game.log  # Save a copy of the full game log to a file
"""

import argparse
import os
import sys


class _Tee:
    """Write to multiple streams simultaneously (for --log: both print to terminal and write to file)."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()

try:
    from dotenv import load_dotenv
    load_dotenv()  #  Load .env if it exists (optional)
except Exception:
    pass

from werewolf.game import Judge, create_players
from werewolf.roles import Role


def verify_isolation(judge: Judge):
    """Automatically verify information isolation correctness and print evidence. Returns whether all passed."""
    print("\n" + "=" * 78)
    print("Automatic information isolation verification (prove each sensitive information only enters its intended context)")
    print("=" * 78)
    ok = True

    wolves = judge.wolves()
    wolf_names = {w.name for w in wolves}
    non_wolves = [p for p in judge.players if p.role != Role.WEREWOLF]
    seer = next((p for p in judge.players if p.role == Role.SEER), None)

    #  Evidence 1: Werewolf teammate identities only appear in werewolf contexts
    team_line_marker = "Players in the werewolf faction are"
    wolves_have = all(any(team_line_marker in m for m in w.memory) for w in wolves)
    nonwolves_have = any(any(team_line_marker in m for m in p.memory) for p in non_wolves)
    check1 = wolves_have and not nonwolves_have
    ok &= check1
    print(f"\n[Check 1] 'Werewolf teammate identities' only enter werewolf contexts:{'Passed ✓' if check1 else 'Failed ✗'}")
    print(f"   - Does each werewolf context contain teammate identities?{wolves_have}")
    print(f"   - Does any non-werewolf context contain teammate identities?{nonwolves_have}(Should be False)")

    #  Evidence 2: Seer check results only appear in the seer's own context
    if seer:
        seer_marker = "You checked"
        seer_has = any(seer_marker in m for m in seer.memory)
        others_have = any(any(seer_marker in m for m in p.memory)
                          for p in judge.players if p.name != seer.name)
        check2 = seer_has and not others_have
        ok &= check2
        print(f"\n[Check 2] 'Seer check result' only enters seer({seer.name}) context:{'Passed ✓' if check2 else 'Failed ✗'}")
        print(f"   - Does the seer context contain the check result?{seer_has}")
        print(f"   - Does any other player's context contain the check result?{others_have}(Should be False)")

    #  Evidence 3: In the audit log, each record's visible_to matches its category
    def cat_visible(cat):
        return [set(r.visible_to) for r in judge.audit.records if r.category == cat]
    check3 = all(v == wolf_names for v in cat_visible("Werewolf teammate identities")) and \
             all(v == wolf_names for v in cat_visible("Werewolf night consensus"))
    ok &= check3
    print(f"\n[Check 3] In audit log, visible set of werewolf-exclusive info == werewolf set {sorted(wolf_names)}："
          f"{'Passed ✓' if check3 else 'Failed ✗'}")

    check4 = all(set(r.visible_to) == set(judge.names)
                 for r in judge.audit.records if r.category.startswith("Public"))
    ok &= check4
    print(f"[Check 4] In audit log, visible set of all 'Public-*' info == all players:"
          f"{'Passed ✓' if check4 else 'Failed ✗'}")

    #  Side-by-side display: a werewolf vs a villager's full private context
    villager = next((p for p in judge.players if p.role == Role.VILLAGER), None)
    a_wolf = wolves[0] if wolves else None
    print("\n—— Comparison: two players' private contexts at the same moment (proving each sees their own) ——")
    if a_wolf:
        print(f"\n[Werewolf {a_wolf.name}'s private context] (contains teammate identities, night consensus)")
        for m in a_wolf.memory:
            print(f"   · {m}")
    if villager:
        print(f"\n[Villager {villager.name}'s private context (without anyone else's identity/inspection result)")
        for m in villager.memory:
            print(f"   · {m}")
    if seer:
        print(f"\n【Seer {seer.name}'s private context (with exclusive inspection result)")
        for m in seer.memory:
            print(f"   · {m}")

    print("\n" + "=" * 78)
    print(f"Information isolation total check:{'All passed ✓✓✓' if ok else 'Failure exists ✗'}")
    print("=" * 78)
    return ok


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Experiment 10-8: Voice Werewolf Agent System — Judge orchestration + information permission control + multi-agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example: \n"
            "  python demo.py                 Text mode to run a full game (LLM decision, API Key required)\n"
            "  python demo.py --offline       Offline rule-based decision, zero cost, reproducible, no API Key required\n"
            "  python demo.py --players 9 --wolves 3   Customize number of players and werewolves\n"
            "  python demo.py --voice --play  Additionally synthesize and play public speech (API Key required)\n"))
    parser.add_argument("--offline", "--mock", dest="offline", action="store_true",
                        help="Offline mode: Use rule strategy instead of LLM, no API Key required, zero cost and reproducible")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (determines identity distribution and offline decisions, reproducible, default 42)")
    parser.add_argument("--players", type=int, default=7,
                        help="Total number of players (default 7)")
    parser.add_argument("--wolves", type=int, default=None,
                        help="Number of werewolves (default auto-derived from total players: 7 players -> 2 werewolves)")
    parser.add_argument("--max-rounds", type=int, default=6, dest="max_rounds",
                        help="Maximum number of rounds for day-night cycle (default 6)")
    parser.add_argument("--model", type=str, default=None,
                        help="Override LLM model (default gpt-5.6-luna, only effective in online mode)")
    parser.add_argument("--voice", action="store_true",
                        help="Use OpenAI tts-1 to synthesize public speech into audio (API Key required; default off, i.e., text-only mode)")
    parser.add_argument("--play", action="store_true",
                        help="Play synthesized speech immediately (macOS afplay; requires --voice)")
    parser.add_argument("--log", type=str, default=None, metavar="PATH",
                        help="Save a copy of the full game log (including audit table) to a specified file")
    return parser


def run_game(args):
    if args.model:
        os.environ["OPENAI_MODEL"] = args.model

    mode = "Offline (rule-based decision)" if args.offline else "Online (LLM decision)"
    roles_note = "" if args.wolves is None else f"(Number of werewolves={args.wolves}）"
    print("=" * 78)
    print("Experiment 10-8: Voice Werewolf Agent System")
    print(f"Mode:{mode} | Model:{os.environ.get('OPENAI_MODEL', 'gpt-5.6-luna') if not args.offline else '—'} | "
          f"Seed:{args.seed} | Voice:{'On' if args.voice else 'Off (Text Mode)'}")
    print(f"Configuration:{args.players} Human Game{roles_note} | Max rounds: {args.max_rounds}")
    print("=" * 78)

    tts = None
    if args.voice:
        from werewolf.tts import TTS
        tts = TTS(os.path.join(os.path.dirname(__file__), "audio"), play=args.play)

    players = create_players(seed=args.seed, players=args.players,
                             wolves=args.wolves, offline=args.offline)
    judge = Judge(players, seed=args.seed, tts=tts, max_rounds=args.max_rounds)
    winner = judge.run()

    # Print information visibility audit table + automatic verification
    judge.audit.print_table(judge.names)
    ok = verify_isolation(judge)

    print(f"\nFinal result:{winner.value}  Win.")
    return ok


def main():
    args = build_parser().parse_args()

    # API Key is only required for online mode (LLM decision / speech synthesis); offline mode does not need it.
    # LLM decision support OPENAI_API_KEY or (fallback) OPENROUTER_API_KEY; speech synthesis (--voice, 
    # OpenAI tts-1 currently only supports OPENAI_API_KEY, OpenRouter has no TTS endpoint.
    has_llm_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if args.voice and not os.environ.get("OPENAI_API_KEY"):
        print("Error: Speech synthesis (--voice, OpenAI tts-1) requires OPENAI_API_KEY."
              "Please first export OPENAI_API_KEY=sk-... (see env.example), or remove --voice to run in plain text mode.")
        sys.exit(1)
    if not args.offline and not has_llm_key:
        print("Error: LLM decision requires OPENAI_API_KEY or OPENROUTER_API_KEY."
              "Please export first (see env.example), or switch to offline mode: python demo.py --offline")
        sys.exit(1)

    log_file = None
    orig_stdout = sys.stdout
    if args.log:
        log_file = open(args.log, "w", encoding="utf-8")
        sys.stdout = _Tee(orig_stdout, log_file)
    try:
        run_game(args)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(2)
    finally:
        if log_file:
            sys.stdout = orig_stdout
            log_file.close()
            print(f"(Full game log saved to {args.log}）")


if __name__ == "__main__":
    main()
