"""
Experiment 10-3 One-click demo.

  python demo.py                       # Full run: Manager mode + Single Agent baseline
  python demo.py --help                # View all parameters
  python demo.py --dry-run             # Offline: draw four-agent collaboration diagram + token budget, no API calls
  python demo.py --model gpt-5.6-luna        # Use a stronger model
  python demo.py --skip-single         # Run only Manager mode, skip single-agent baseline (faster)
  python demo.py --no-proofreading     # Disable Proofreading Agent and revision loop
  python demo.py --source-lang English --target-lang Japanese     # Change translation direction
  python demo.py --sample-dir path/to/book --out-dir out  # Change input book / output directory

Workflow:
  1) Read several short English chapters under --sample-dir (default sample_book/);
  2) Run [Manager mode]: Glossary / Translation / Proofreading / Manager four agents collaborate,
     and print real-time traces of the four-agent collaboration;
  3) Run [Single Agent mode] as a baseline (unless --skip-single is specified);
  4) Print comparison table: context token consumption per agent, Manager/main context peak, terminology consistency.

Key conclusions:
  - In Manager mode, the Manager's context is significantly smaller than the cumulative context of a single agent (controlling context explosion);
  - Shared glossary ensures terminology consistency across chapters.
"""

import argparse
import glob
import os
import sys

from dotenv import load_dotenv

load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(HERE, "sample_book")
OUT_DIR = os.path.join(HERE, "output")


def parse_args():
    """Command-line arguments: when run without any arguments, behavior is exactly the same as the original."""
    parser = argparse.ArgumentParser(
        prog="demo.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Experiment 10-3: Book Translation Agent — Manager mode (Glossary/Translation/\n"
            "Proofreading/Manager four agents collaborate) vs Single Agent mode, \n"
            "compare context explosion and glossary compliance rate."
        ),
        epilog=(
            "Examples: \n"
            "  python demo.py --dry-run                 # Offline: draw agent diagram + token budget, no API calls\n"
            "  python demo.py --skip-single             # Run only Manager mode\n"
            "  python demo.py --no-proofreading         # Disable Proofreading Agent and revision loop\n"
            "  python demo.py --sample-dir book --out-dir out --model gpt-5.6-luna\n"
        ),
    )
    io = parser.add_argument_group("Input / Output")
    io.add_argument(
        "--sample-dir",
        default=SAMPLE_DIR,
        metavar="DIR",
        help="Book directory to translate (reads *.md chapters, sorted by filename). Default sample_book/.",
    )
    io.add_argument(
        "--out-dir",
        default=OUT_DIR,
        metavar="DIR",
        help="Output root directory (glossary / chapter translations / proofreading reports are written under its orchestration|single_agent/)."
             "Default output/.",
    )

    lang = parser.add_argument_group("Translation direction")
    lang.add_argument(
        "--source-lang", default="English", metavar="LANG",
        help="Source language, used only for prompt wording. Default English.",
    )
    lang.add_argument(
        "--target-lang", default="Chinese", metavar="LANG",
        help="Target language, used only for prompt wording. Default Chinese."
             "Note: built-in terminology consistency / compliance statistics are tuned for English→Chinese; changing direction still works for translation,"
             "but the statistics table is of limited significance.",
    )

    agents_grp = parser.add_argument_group("Which agents to enable")
    agents_grp.add_argument(
        "--no-glossary", action="store_true",
        help="Disable Glossary Agent (no term extraction, only keep editorial-specified terms). Enabled by default.",
    )
    agents_grp.add_argument(
        "--no-proofreading", action="store_true",
        help="Disable Proofreading Agent and Manager revision loop. Enabled by default.",
    )

    run = parser.add_argument_group("Execution mode")
    run.add_argument(
        "--model", default=None, metavar="MODEL",
        help="Override the model used (equivalent to setting OPENAI_MODEL environment variable)."
             "Defaults to OPENAI_MODEL environment variable, or gpt-5.6-luna if not set.",
    )
    run.add_argument(
        "--skip-single", action="store_true",
        help="Run only Manager mode, skip single-agent baseline (faster, but no core comparison table produced). Disabled by default.",
    )
    run.add_argument(
        "--dry-run", action="store_true",
        help="Offline preview: only print four-agent collaboration diagram, Manager plan, editorial glossary, and token budget for each agent,"
             "no API calls (no OPENAI_API_KEY required).",
    )
    return parser.parse_args()


def load_chapters(sample_dir):
    """Read sample_dir/*.md in filename order, return {chapter_name: original_text}."""
    files = sorted(glob.glob(os.path.join(sample_dir, "*.md")))
    chapters = {}
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        #  Use the first-level heading of the file as the chapter name, falling back to the file name
        name = os.path.splitext(os.path.basename(path))[0]
        for line in text.splitlines():
            if line.startswith("# "):
                name = line[2:].strip()
                break
        chapters[name] = text
    return chapters


def hr(title=""):
    print("\n" + "=" * 72)
    if title:
        print(title)
        print("=" * 72)


def print_agent_table(tracker, title):
    hr(title)
    agg = tracker.by_agent()
    print(f"{'Agent':<14}{'Call count':>8}{'Input tok':>12}{'Output tok':>12}{'Context peak':>12}")
    print("-" * 72)
    for name, a in agg.items():
        print(f"{name:<14}{a['calls']:>8}{a['in']:>12}{a['out']:>12}{a['peak_context']:>12}")
    print("-" * 72)
    print(f"{'Total':<14}{'':>8}{'':>12}{'':>12}  Total tokens:{tracker.total_tokens()}")


def print_consistency(analysis, label):
    print(f"\n[{label}] Terminology consistency:{analysis['consistent_terms']}/{analysis['total_terms']} "
          f" terms unified across the book ({analysis['rate']*100:.0f}%）")
    for r in analysis["results"]:
        flag = "Consistent" if r["consistent"] else "Inconsistent <==="
        used = " / ".join(f"{v}({len(chs)} chapter)" for v, chs in r["by_variant"].items())
        print(f"  - {r['en']:<12}  Actually used:{used}  [{flag}]")


def make_tracer():
    """Return a trace(str) callback that prints sub-Agent events with indentation, showing the Manager's real-time scheduling trajectory."""
    def tracer(msg):
        indent = "" if msg.startswith(("Manager", "Glossary", "Translation",
                                       "Proofreading")) else "  "
        #  Lines with leading spaces for "plan/sub-step" are output as-is
        print(f"  {indent}{msg}" if not msg.startswith("    ") else f"  {msg}")
    return tracer


def run_dry_run(args):
    """
    Offline rehearsal (no API calls): draw the four-Agent collaboration diagram, Manager plan, editorial terminology,
    and use tiktoken to estimate the context size each Agent will read, intuitively confirming that "Manager context is essentially independent of book length".
    """
    import agents
    import consistency

    chapters = load_chapters(args.sample_dir)
    if not chapters:
        print(f"Error:{args.sample_dir}  No .md chapters found under.", file=sys.stderr)
        sys.exit(1)

    hr(f"Experiment 10-3 · Offline rehearsal (--dry-run, no API calls, model={agents.MODEL}）")
    print(f"Book to translate:{args.sample_dir}（{len(chapters)} chapter)   Translation direction:"
          f"{args.source_lang} → {args.target_lang}")
    print(f"Enable Agents: Manager + " +
          ("Glossary + " if not args.no_glossary else "(Glossary disabled) ") +
          "Translation" +
          (" + Proofreading" if not args.no_proofreading else " (Proofreading disabled)"))

    hr("Four-Agent collaboration diagram (data flows through the file system, Manager only holds paths)")
    print("""
        ┌─────────────────────── Manager Agent ───────────────────────┐
        │  Only stores: tasks / plans / call records / file indexes (never stores full translations)      │
        └──┬───────────────┬────────────────────┬────────────────┬─────┘
           │ ①Dispatch          │ ②Dispatch per chapter           │ ③Dispatch           │ ④Decide based on report
           ▼               ▼                    ▼                ▼
     Glossary Agent   Translation Agent×N   Proofreading Agent  (send back revisions)
     Read book→glossary     Read only this chapter+glossary→translation    Read all translations+glossary      Re-translate affected chapters
           │               │                    │
           ▼ glossary.json  ▼ chapterN_zh.md      ▼ proofreading_report.json
        ══════════════════  Shared file system (out-dir) ══════════════════""")

    hr("Manager execution plan (4 steps)")
    for step in agents.ORCHESTRATION_PLAN:
        print(f"  {step}")

    hr("Editorial terminology (house style, forcibly written into shared glossary, unified across the book)")
    for en, zh in agents.EDITORIAL_MANDATE.items():
        print(f"  {en:<12} → {zh}")

    hr("Token budget estimation (tiktoken offline statistics, not actual API usage)")
    book_text = "\n\n".join(f"# {n}\n{t}" for n, t in chapters.items())
    book_tok = agents.count_tokens(book_text)
    print(f"  Glossary Agent    Read entire book           ≈ {book_tok} tok")
    per_chapter = []
    for name, text in chapters.items():
        t = agents.count_tokens(text)
        per_chapter.append(t)
        print(f"  Translation Agent reads 《{name}》(independent) ≈ {t} tok")
    print(f"  Proofreading Agent reads all translations       ≈ {sum(per_chapter)} tok (same order of magnitude as the full book)")

    #  Manager context estimate: task + plan + one call record per chapter + file index (paths only)
    import json as _json
    mock_manager = {
        "task": f"Translate a{args.source_lang}technical booklet into fluent{args.target_lang}, ensuring terminology consistency throughout the book.",
        "plan": list(agents.ORCHESTRATION_PLAN),
        "call_log": [{"agent": "Translation", "note": f"Translate {n}",
                      "output": f"{n}_zh.md", "prompt_tokens": 0, "completion_tokens": 0}
                     for n in chapters],
        "file_index": {n: os.path.join(args.out_dir, "orchestration", f"{n}_zh.md")
                       for n in chapters},
    }
    mgr_tok = agents.count_tokens(_json.dumps(mock_manager, ensure_ascii=False))
    print(f"\n  Manager context (task/plan/call records/file index, no body) ≈ {mgr_tok} tok")
    print(f"  Comparison: Single Agent cumulative context ≥ full book {book_tok} tok (linear growth per chapter, longer book means larger)")
    print("\n  Key point: Manager context only grows by a few lines of records per chapter, independent of chapter body length;")
    print("         Single Agent keeps all source and target text in one conversation, context grows linearly with book length.")

    hr("Terminology consistency / compliance rate will count tracked terms (see consistency.py)")
    print("  Tracked terms:" + "、".join(t["en"] for t in consistency.TRACKED_TERMS))
    print("  Specified terms (compliance rate):" +
          "、".join(f'{t["en"]}→{t["mandated"]}' for t in consistency.MANDATED_TERMS))
    print("\nOffline rehearsal finished. Remove --dry-run and set OPENAI_API_KEY to actually run the four-agent collaboration.")


def main():
    args = parse_args()
    if args.model:
        #  Must be set before importing agents: agents.py reads
        # OPENAI_MODEL environment variable to determine the model to use.
        os.environ["OPENAI_MODEL"] = args.model

    if args.dry_run:
        #  Offline mode: no API Key needed, no network calls made.
        run_dry_run(args)
        return

    #  Lazy import to ensure the override of OPENAI_MODEL takes effect before agents.py reads the environment variable.
    import agents
    import consistency

    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"):
        print("Error: OPENAI_API_KEY or OPENROUTER_API_KEY not set. Please `export OPENAI_API_KEY=...`"
              "(or OPENROUTER_API_KEY) or copy env.example to .env and fill it in (see env.example).\n"
              "Tip: To view the four-agent collaboration structure offline without a network or API key, run "
              "`python demo.py --dry-run`。", file=sys.stderr)
        sys.exit(1)

    chapters = load_chapters(args.sample_dir)
    if not chapters:
        print(f"Error:{args.sample_dir}  No .md chapters found under.", file=sys.stderr)
        sys.exit(1)
    print(f"Loading {len(chapters)} chapters:{list(chapters.keys())}  "
          f"（{args.source_lang} → {args.target_lang}）")

    # ---------------- Manager Mode ----------------
    hr("[Manager Mode] Four-Agent Collaboration Real-Time Trace")
    orch = agents.run_orchestration(
        chapters, os.path.join(args.out_dir, "orchestration"),
        source_lang=args.source_lang, target_lang=args.target_lang,
        enable_glossary=not args.no_glossary,
        enable_proofreading=not args.no_proofreading,
        trace=make_tracer(),
    )
    print_agent_table(orch["tracker"], "[Manager Mode] Token Consumption per Agent Context")
    print(f"\nManager context peak (only stores tasks/plans/call records/file indices):{orch['manager_context_peak']} tokens")
    print(f"Glossary (shared file, referenced by all Translation Agents):")
    for g in orch["glossary"]:
        print(f"    {g['en']} → {g['zh']}（{g.get('pos','')}）")
    if not args.no_proofreading:
        print(f"Review report summary:{orch['report'].get('summary','')[:120]}")

    # ---------------- Single Agent Mode ----------------
    if args.skip_single:
        hr("Skipped single agent control group (--skip-single)")
        print("Hint: The core comparison table requires single agent data; remove --skip-single to see the full comparison.")
        print(f"\nOutput directory:{args.out_dir}")
        return
    single = agents.run_single_agent(
        chapters, os.path.join(args.out_dir, "single_agent"),
        source_lang=args.source_lang, target_lang=args.target_lang,
    )
    print_agent_table(single["tracker"], "[Single Agent Mode] Main context token consumption")

    # ---------------- Terminology Consistency Comparison ----------------
    hr("Terminology consistency comparison (deterministic string matching, not model scoring)")
    orch_cons = consistency.analyze(orch["translations"])
    single_cons = consistency.analyze(single["translations"])
    print_consistency(orch_cons, "Manager mode")
    print_consistency(single_cons, "Single Agent mode")

    # ---------------- Glossary Compliance Rate Comparison (Core Evidence) ----------------
    hr("Glossary compliance rate comparison: whether editorial-specified terms are consistently applied throughout the book")
    orch_adh = consistency.check_adherence(orch["translations"])
    single_adh = consistency.check_adherence(single["translations"])
    print("(Manager mode writes specified terms into a shared glossary and enforces them; Single Agent mode cannot see the glossary)\n")
    print(f"{'Specified term':<14}{'Prescribed translation':<10}{'Default translation':<10}"
          f"{'Manager (compliant/occurrences)':>18}{'Single Agent (compliant/occurrences)':>20}")
    print("-" * 78)
    o_map = {r["en"]: r for r in orch_adh["rows"]}
    s_map = {r["en"]: r for r in single_adh["rows"]}
    for r in orch_adh["rows"]:
        s = s_map.get(r["en"], {"adhered": 0, "total": 0})
        o_cell = f"{r['adhered']}/{r['total']}"
        s_cell = f"{s['adhered']}/{s['total']}"
        print(f"{r['en']:<14}{r['mandated']:<10}{r['default']:<10}"
              f"{o_cell:>18}{s_cell:>20}")
    print("-" * 78)
    print(f"Glossary compliance rate: Manager mode {orch_adh['rate']*100:.0f}%  vs  "
          f"Single Agent {single_adh['rate']*100:.0f}%")

    # ---------------- Core Comparison Table ----------------
    hr("Core comparison table: Manager mode vs Single Agent mode")
    o_tr, s_tr = orch["tracker"], single["tracker"]
    o_mgr_peak = orch["manager_context_peak"]
    #In Manager mode, if Manager is treated as an LLM Agent, it also has a context peak for one decision call
    o_mgr_llm_peak = o_tr.by_agent().get("Manager", {}).get("peak_context", 0)
    s_main_peak = single["main_context_peak"]

    rows = [
        ("Main/Manager context peak (tokens)", o_mgr_peak, s_main_peak),
        ("Manager LLM decision call context (tokens)", o_mgr_llm_peak, "—"),
        ("Total token consumption across the entire workflow", o_tr.total_tokens(), s_tr.total_tokens()),
        ("Internal term consistency rate", f"{orch_cons['rate']*100:.0f}%", f"{single_cons['rate']*100:.0f}%"),
        ("Specified term compliance rate", f"{orch_adh['rate']*100:.0f}%", f"{single_adh['rate']*100:.0f}%"),
        ("Number of participating agent types", len(o_tr.by_agent()), 1),
    ]
    print(f"{'Metric':<32}{'Manager mode':>16}{'Single Agent':>16}")
    print("-" * 72)
    for label, a, b in rows:
        print(f"{label:<32}{str(a):>16}{str(b):>16}")
    print("-" * 72)

    if isinstance(s_main_peak, int) and o_mgr_peak and s_main_peak:
        ratio = s_main_peak / o_mgr_peak
        print(f"\nConclusion: The peak main context of a single agent is "
              f"{ratio:.1f} times that of the Manager context in manager mode.")
        print("Manager only saves tasks/plans/call records/file indexes, and the complete translation is all written to the file system,")
        print("so no matter how long the book is, the Manager context remains basically constant — this is the key to controlling context explosion.")
    print(f"\nOutput directory:{args.out_dir}")


if __name__ == "__main__":
    main()
