"""
Experiment 5-4: Automatic PPT Generation from Papers (Proposer-Reviewer Mechanism)

Complete workflow:
  1. Start from a condensed paper (paper/sample_paper.md) + programmatically reproduced figures;
  2. 【Dual Agent】Proposer generates slides.md → Slidev renders each page as PNG → Reviewer uses Vision LLM
     to view images and provide structured feedback → Proposer revises based on feedback → iterate until pass or max rounds reached;
  3. 【Single Agent Self-Review】Same agent generates → renders → feeds its own screenshots back into the **same context** for self-review and revision → iterate;
  4. Use the same "independent judge" (Vision) to score the final PPTs of both approaches, fairly comparing **quality**;
  5. Print the **context token consumption** comparison for both approaches (total, peak single prompt token).

Run: python demo.py            # Full comparison (both approaches)
     python demo.py --help     # View all parameters
     python demo.py --mode dual --max-rounds 1   # Quick: only run dual agent, only first version
     python demo.py --smoke     # Only verify Slidev rendering pipeline, no LLM calls
     python demo.py --dry-run   # Offline walkthrough of proposer-reviewer loop (real rendering + scripted revision)
Dependencies: Node/Slidev (rendering), OPENAI_API_KEY (gpt-5.6-luna vision + text; if not configured, falls back to OPENROUTER_API_KEY).
"""
import argparse
import json
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

import agents  # noqa: E402  —— reference TEXT_MODEL/VISION_MODEL by module name for easy CLI override
from agents import (  # noqa: E402
    Proposer, Reviewer, SelfReviewAgent, TokenMeter, independent_judge,
)
from make_figures import generate_all  # noqa: E402
from renderer import render_slides  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PAPER_PATH = os.path.join(HERE, "paper", "sample_paper.md")
DEFAULT_OUT_DIR = os.path.join(HERE, "output")
OUT_DIR = DEFAULT_OUT_DIR  # can be overridden by --out-dir (global assignment in main)
MAX_ROUNDS = 3  # maximum number of iterations per approach (first round + up to 2 revisions)


def banner(title):
    print("\n" + "=" * 74)
    print(f"  {title}")
    print("=" * 74)


def save_text(name, text):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def summarize_review(review: dict) -> str:
    n_high = sum(1 for x in review.get("issues", []) if x.get("severity") == "high")
    n_med = sum(1 for x in review.get("issues", []) if x.get("severity") == "medium")
    n_low = sum(1 for x in review.get("issues", []) if x.get("severity") == "low")
    return (f"score={review.get('overall_score')} pass={review.get('pass')} "
            f"issues={len(review.get('issues', []))} (high={n_high}, med={n_med}, low={n_low})")


# --------------------------------------------------------------------------- #
# Approach A: Proposer-Reviewer (Dual Agent)
# --------------------------------------------------------------------------- #
def run_proposer_reviewer(paper_md, figures, max_rounds=MAX_ROUNDS):
    banner("Approach A: Proposer-Reviewer (Dual Agent Division of Labor)")
    proposer_meter = TokenMeter("Proposer (text only)")
    reviewer_meter = TokenMeter("Reviewer (only sees latest screenshot each round)")

    proposer = Proposer(proposer_meter, paper_md, figures)
    reviewer = Reviewer(reviewer_meter)

    history = []  # (score, review) per round
    slides = proposer.propose()
    final_pngs = None

    for rnd in range(1, max_rounds + 1):
        print(f"\n[Dual Agent] Round {rnd}: Proposer produces slides.md ({slides.count(chr(10) + '---' + chr(10)) + 1} segments separated)")
        md_path = save_text(f"dual_round{rnd}_slides.md", slides)
        pngs = render_slides(slides, f"dual_round{rnd}")
        final_pngs = pngs
        print(f"  Rendered {len(pngs)} page PNGs, e.g.:{pngs[0]}")

        review = reviewer.review(pngs)
        print(f"  Reviewer (Vision) review:{summarize_review(review)}")
        # Print actual suggestion JSON (first few items)
        print("  Reviewer structured suggestion JSON:")
        print(_indent(json.dumps(review, ensure_ascii=False, indent=2), 4))
        save_text(f"dual_round{rnd}_review.json",
                  json.dumps(review, ensure_ascii=False, indent=2))
        history.append((review.get("overall_score", 0), review))

        blocking = [i for i in review.get("issues", [])
                    if i.get("severity") in ("high", "medium")]
        if review.get("pass") and not blocking:
            print("  ✓ Reviewer deemed pass (no high/medium issues), early termination of iteration.")
            break
        if rnd == max_rounds:
            break

        print("  → Proposer receives structured text feedback and revises (context only appends text, no images)")
        slides = proposer.revise(review)

    return {
        "slides": slides,
        "final_pngs": final_pngs,
        "history": history,
        "proposer_meter": proposer_meter,
        "reviewer_meter": reviewer_meter,
    }


# --------------------------------------------------------------------------- #
# Approach B: Single Agent Self-Review
# --------------------------------------------------------------------------- #
def run_single_agent(paper_md, figures, max_rounds=MAX_ROUNDS):
    banner("Approach B: Single Agent Self-Review (images accumulate in same context)")
    meter = TokenMeter("SingleAgent (self-review, images accumulate)")
    agent = SelfReviewAgent(meter, paper_md, figures)

    slides = agent.propose()
    final_pngs = None

    for rnd in range(1, max_rounds + 1):
        print(f"\n[Single Agent] Round {rnd}: Generate/revise slides.md")
        save_text(f"single_round{rnd}_slides.md", slides)
        pngs = render_slides(slides, f"single_round{rnd}")
        final_pngs = pngs
        print(f"  Rendered {len(pngs)} page PNGs")
        print(f"  Current context peak prompt token = {meter.peak_prompt_tokens}")

        if rnd == max_rounds:
            break
        print("  → Feed %d screenshots back into the same context, agent self-reviews and revises (historical images not cleared)" % len(pngs))
        slides = agent.self_review_and_revise(pngs)

    return {"slides": slides, "final_pngs": final_pngs, "meter": meter}


def _indent(text, n):
    pad = " " * n
    return "\n".join(pad + line for line in text.splitlines())


def smoke_test():
    """Quick smoke test: only verify Slidev rendering pipeline is available, no LLM calls, no API Key required."""
    from renderer import render_slides
    banner("Smoke test: only verify Slidev rendering pipeline (no LLM calls)")
    demo_md = (
        "---\ntheme: default\n---\n\n"
        "# Smoke Test\n\nRendering Pipeline Self-Check\n\n---\n\n"
        "# Page 2\n\n- Slidev + playwright-chromium works\n"
    )
    pngs = render_slides(demo_md, "smoke")
    print(f"✓ Rendering succeeded, output {len(pngs)} PNG pages:")
    for p in pngs:
        print("  ", p)
    print("Slidev rendering pipeline is available.")


# --------------------------------------------------------------------------- #
# Offline dry-run: no LLM calls, go through the **structure** of the proposer-reviewer loop.
#   - The two versions of the Proposer's draft are scripted (crowded initial draft → split revised draft), not LLM-generated;
#   - Rendering is **real** (actually calls Slidev to export PNG);
#   - The Reviewer uses **deterministic heuristic rules** (judges overcrowded by text amount per page),
#     explicitly not a Vision LLM—only used for offline demonstration of the "generate→render→review→revise" loop.
# For real Vision review, use `python demo.py` (requires OPENAI_API_KEY).
# --------------------------------------------------------------------------- #
def _split_paragraphs(paper_md: str) -> list[str]:
    """Split body paragraphs by blank lines, excluding title lines and tables/images, for scripted layout."""
    paras = []
    for block in re.split(r"\n\s*\n", paper_md):
        block = block.strip()
        if not block or block.startswith("#") or block.startswith("|"):
            continue
        paras.append(re.sub(r"\s+", " ", block))
    return paras


def _paper_title(paper_md: str) -> str:
    m = re.search(r"^#\s+(.+)$", paper_md, re.MULTILINE)
    return m.group(1).strip() if m else "Paper demo"


def _dry_first_draft(paper_md: str, figures: dict) -> str:
    """Scripted "crowded initial draft": compress the entire paper into about 4 pages, stuffing multiple paragraphs per page (inevitably overflowing)."""
    title = _paper_title(paper_md)
    paras = _split_paragraphs(paper_md) or ["(Paper body is empty)"]
    fig_names = list(figures.keys())
    # Pack paragraphs into 3 content pages as much as possible
    groups, per = [], max(1, (len(paras) + 2) // 3)
    for i in range(0, len(paras), per):
        groups.append(paras[i:i + per])
    pages = [f"---\ntheme: default\n---\n\n# {title}\n\nAuto-generated demo (offline dry-run initial draft)"]
    for gi, g in enumerate(groups[:3]):
        body = "\n\n".join(g)
        img = f"\n\n![]({fig_names[gi]})" if gi < len(fig_names) else ""
        pages.append(f"# Part {gi + 1}\n\n{body}{img}")
    return "\n\n---\n\n".join(pages) + "\n"


def _dry_revised(paper_md: str, figures: dict) -> str:
    """Scripted "revised draft": one paragraph per page, bullet-point style, figures on separate pages—clearly more spacious, can pass heuristics."""
    title = _paper_title(paper_md)
    paras = _split_paragraphs(paper_md) or ["(Paper body is empty)"]
    fig_names = list(figures.keys())
    pages = [f"---\ntheme: default\n---\n\n# {title}\n\nAuto-generated demo (offline dry-run revised draft)"]
    for i, para in enumerate(paras):
        # Only one paragraph per page, truncated to about 220 characters, simulating "condensed into bullet points"
        text = para if len(para) <= 220 else para[:210].rstrip() + "……"
        pages.append(f"# Key point {i + 1}\n\n{text}")
    for name in fig_names:  # Figures each on separate pages, size controlled
        pages.append(f"# Figure\n\n<img src=\"{name}\" class=\"h-80 mx-auto\" />")
    return "\n\n---\n\n".join(pages) + "\n"


def _heuristic_review(slides_md: str) -> dict:
    """Deterministic heuristic (non-Vision LLM): judge overcrowded by character count of body text per page."""
    parts = re.split(r"(?m)^---\s*$", slides_md)
    pages, page_no = [], 0
    for part in parts:
        s = part.strip()
        if not s or s.startswith("theme:") or "theme:" in s.split("\n")[0]:
            continue
        pages.append(s)
    issues = []
    for idx, page in enumerate(pages, 1):
        text = re.sub(r"!\[.*?\]\(.*?\)|<img[^>]*>", "", page)  # Excluding images
        n = len(re.sub(r"\s+", "", text))
        if n > 500:
            issues.append({"page": idx, "issue_type": "overcrowded", "severity": "high",
                           "suggestion": f"This page has about {n} characters, severely overflowing, suggest splitting into multiple pages and condensing into bullet points."})
        elif n > 300:
            issues.append({"page": idx, "issue_type": "overcrowded", "severity": "medium",
                           "suggestion": f"This page has about {n} characters, slightly crowded, suggest splitting or trimming."})
    blocking = [i for i in issues if i["severity"] in ("high", "medium")]
    score = max(0, 100 - 15 * len(blocking) - 3 * (len(issues) - len(blocking)))
    return {"overall_score": score, "pass": not blocking, "issues": issues,
            "_reviewer": "heuristic (offline, NOT a Vision LLM)"}


def dry_run(paper_path: str):
    """Offline walkthrough of proposer-reviewer loop: real rendering + scripted revision + heuristic review."""
    banner("Dry-run: offline demonstration of proposer-reviewer loop (real rendering, scripted revision, heuristic review)")
    if not os.path.exists(paper_path):
        print(f"Paper file not found:{paper_path}")
        sys.exit(1)
    with open(paper_path, encoding="utf-8") as f:
        paper_md = f.read()
    figures = generate_all()
    print(f"Paper:{paper_path}（{len(paper_md)} characters); reproduced figures:{', '.join(figures)}")
    print("Note: This mode does not call any LLM. The Reviewer is played by deterministic heuristic rules (not a Vision LLM),")
    print("      only used for offline demonstration of the \"generate → render → review → revise\" loop; for real Vision review, use `python demo.py`.")

    stages = [
        ("Crowded draft", _dry_first_draft(paper_md, figures)),
        ("Split-page revision", _dry_revised(paper_md, figures)),
    ]
    last_review = None
    for rnd, (label, slides) in enumerate(stages, 1):
        n_pages = slides.count("\n---\n")  # page separator count ≈ page count
        print(f"\n[dry-run] Round {rnd}: Proposer produces slides.md ({label}, approximately {n_pages} pages)")
        save_text(f"dryrun_round{rnd}_slides.md", slides)
        pngs = render_slides(slides, f"dryrun_round{rnd}")
        print(f"  Rendered {len(pngs)} page PNGs, e.g.:{pngs[0]}")
        review = _heuristic_review(slides)
        print(f"  Reviewer (heuristic) review:{summarize_review(review)}")
        print("  Reviewer structured suggestion JSON:")
        print(_indent(json.dumps(review, ensure_ascii=False, indent=2), 4))
        save_text(f"dryrun_round{rnd}_review.json",
                  json.dumps(review, ensure_ascii=False, indent=2))
        last_review = review
        if review["pass"]:
            print("  ✓ Reviewer judges it passes (no high/medium issues), loop ends.")
            break
        if rnd < len(stages):
            print("  → Proposer receives structured text feedback and revises (split pages, trim; here scripted revision)")

    banner("Dry-run summary")
    print(f"Loop demo complete: initial draft judged crowded → revision pass={last_review['pass']}"
          f" (heuristic score {last_review['overall_score']}）。")
    print(f"Real rendered PNG: slidev_workspace/exports/dryrun_round*/")
    print(f"Scripted slides.md and review JSON:{OUT_DIR}/dryrun_round*")
    print("For real Vision review loop (gpt-5.6-luna looks at pixels), run: python demo.py --mode dual --max-rounds 3")


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="demo.py",
        description="Experiment 5-4: Paper → PPT auto-generation (proposer-reviewer vs single agent self-review comparison)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example: \n"
            "  python demo.py                          # Full comparison: two schemes + independent judge + token comparison\n"
            "  python demo.py --mode dual              # Run only dual agent (saves half time/cost)\n"
            "  python demo.py --max-rounds 1           # Only first draft per scheme (fastest real LLM smoke test)\n"
            "  python demo.py --paper my.md --out-dir run1   # Change paper and output directory\n"
            "  python demo.py --vision-model gpt-5.6-luna      # Override vision model\n"
            "  python demo.py --dry-run                # Offline walkthrough of proposer-reviewer loop, no LLM calls\n"
            "  python demo.py --smoke                  # Only verify Slidev rendering, no LLM calls\n\n"
            "Models/providers can also be configured via environment variables (see env.example); command line --text-model /\n"
            "--vision-model has higher priority: OPENAI_API_KEY / OPENAI_BASE_URL / TEXT_MODEL / VISION_MODEL"
        ),
    )
    p.add_argument("--paper", metavar="PATH", default=DEFAULT_PAPER_PATH,
                   help="Input the Markdown path of the paper (default paper/sample_paper.md)."
                        "Replace with your own paper; retaining the chapter structure allows Proposer to parse it.")
    p.add_argument("--out-dir", metavar="DIR", default=DEFAULT_OUT_DIR,
                   help="Output directory for artifacts: slides.md / review.json / comparison_summary.json per round"
                        "(default output/). Rendered PNGs are always in slidev_workspace/exports/.")
    p.add_argument("--text-model", metavar="NAME", default=None,
                   help="Model used by Proposer / single Agent text part, overrides TEXT_MODEL environment variable"
                        f"(default {agents.TEXT_MODEL}）。")
    p.add_argument("--vision-model", metavar="NAME", default=None,
                   help="Model used by Reviewer / independent judge for image viewing, must support image input, overrides VISION_MODEL "
                        f"environment variable (default {agents.VISION_MODEL}）。")
    p.add_argument("--mode", choices=["both", "dual", "single"], default="both",
                   help="Which scheme to run: both=run both and compare (default); dual=only proposer-reviewer;"
                        "single=only single Agent self-review. Running only one can significantly save time and cost.")
    p.add_argument("--max-rounds", type=int, default=MAX_ROUNDS, metavar="N",
                   help=f"Maximum number of iteration rounds per scheme (default {MAX_ROUNDS}). Setting to 1 means only the first version is produced,"
                        "no revision, which is the fastest real-run smoke test.")
    p.add_argument("--dry-run", action="store_true",
                   help="Offline demo of proposer-reviewer loop: realistically render two versions of scripted slides.md (crowded draft →"
                        "split-page revision), use heuristic rules (not Vision LLM) to act as Reviewer, demonstrating"
                        "the closed loop of generation → rendering → review → revision. Does not call any LLM, no API Key required.")
    p.add_argument("--smoke", action="store_true",
                   help="Only verify the Slidev rendering pipeline (render a two-page deck), does not call any LLM, no API Key required.")
    return p.parse_args(argv)


def _save_partial_summary(dual, dual_final, single, single_final):
    """When running a single scheme (--mode dual/single), save the quality and token results of that scheme."""
    summary = {"models": {"text": agents.TEXT_MODEL, "vision": agents.VISION_MODEL}}
    if dual:
        pm, rm = dual["proposer_meter"], dual["reviewer_meter"]
        summary["dual_agent"] = {
            "iteration_scores": [h[0] for h in dual["history"]],
            "final_quality": dual_final,
            "total_tokens": pm.total_tokens + rm.total_tokens,
            "peak_context_prompt_tokens": max(pm.peak_prompt_tokens, rm.peak_prompt_tokens),
        }
    if single:
        sm = single["meter"]
        summary["single_agent"] = {
            "final_quality": single_final,
            "total_tokens": sm.total_tokens,
            "peak_context_prompt_tokens": sm.peak_prompt_tokens,
        }
    p = save_text("comparison_summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nResults saved:{p}")
    print(f"All slides.md / review.json / rendered PNGs are located at:{OUT_DIR}/ and slidev_workspace/exports/")


def main(argv=None):
    global OUT_DIR
    args = parse_args(argv)

    #  Output directory (--out-dir): all save_text is written here
    OUT_DIR = os.path.abspath(args.out_dir)
    #  Model overrides (--text-model / --vision-model take precedence over environment variables)
    if args.text_model:
        agents.TEXT_MODEL = args.text_model
    if args.vision_model:
        agents.VISION_MODEL = args.vision_model

    if args.smoke:
        smoke_test()
        return
    if args.dry_run:
        dry_run(args.paper)
        return
    if args.max_rounds < 1:
        print("--max-rounds must be at least 1")
        sys.exit(1)
    if not os.path.exists(args.paper):
        print(f"Paper file not found:{args.paper}(specify with --paper, or refer to default paper/sample_paper.md)")
        sys.exit(1)
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")):
        print("Please set OPENAI_API_KEY first (or OPENROUTER_API_KEY as fallback, see env.example)")
        sys.exit(1)

    banner("Preparation: paper + programmatically reproducible figures")
    with open(args.paper, encoding="utf-8") as f:
        paper_md = f.read()
    figures = generate_all()
    print(f"Paper:{args.paper}（{len(paper_md)} characters)")
    print(f"Output directory:{OUT_DIR}")
    print(f"Text model:{agents.TEXT_MODEL}   Vision model:{agents.VISION_MODEL}")
    print(f"Run mode:{args.mode}   Max rounds:{args.max_rounds}")
    print("Generated charts:")
    for k, v in figures.items():
        print(f"  {k} -> {v}")

    # Plan A / Plan B (--mode controls which one to run; only 'both' enables cross-plan comparison)
    dual = run_proposer_reviewer(paper_md, figures, args.max_rounds) \
        if args.mode in ("both", "dual") else None
    single = run_single_agent(paper_md, figures, args.max_rounds) \
        if args.mode in ("both", "single") else None

    # ------- Use the same independent judge to score the final PPTs of both plans (quality comparison, as fair as possible) -------
    banner("Independent judge: score the final PPTs (same Vision rubric)")
    judge_meter = TokenMeter("Independent judge (not counted in the cost of either plan)")
    dual_final = independent_judge(dual["final_pngs"], judge_meter) if dual else None
    single_final = independent_judge(single["final_pngs"], judge_meter) if single else None
    if dual_final:
        print(f"Final quality of Plan A (dual-agent):{summarize_review(dual_final)}")
    if single_final:
        print(f"Final quality of Plan B (single-agent):{summarize_review(single_final)}")

    if not (dual and single):
        # Single-plan run: skip cross-plan token comparison, only persist existing results
        _save_partial_summary(dual, dual_final, single, single_final)
        return

    # ------- Iterative improvement (dual-agent) -------
    banner("Iterative quality improvement (Plan A: proposer-reviewer)")
    scores = [h[0] for h in dual["history"]]
    if len(scores) >= 2:
        print(f"Reviewer score changes with iterations:{scores}  "
              f"（{'↑ Improvement' if scores[-1] >= scores[0] else '↓'} {scores[-1] - scores[0]:+d}）")
    else:
        print(f"Reached threshold in just 1 round, Reviewer score:{scores}")

    # ------- Context token consumption comparison -------
    banner("Context token consumption comparison: single-agent self-review vs proposer-reviewer")
    pm, rm, sm = dual["proposer_meter"], dual["reviewer_meter"], single["meter"]
    dual_total = pm.total_tokens + rm.total_tokens
    dual_peak = max(pm.peak_prompt_tokens, rm.peak_prompt_tokens)

    def row(label, calls, prompt, completion, total, peak):
        print(f"  {label:<34} calls={calls:<3} prompt={prompt:<8} "
              f"completion={completion:<7} total={total:<8} peak_ctx={peak}")

    print("Dual-agent (Plan A) breakdown:")
    row(pm.name, pm.calls, pm.prompt_tokens, pm.completion_tokens, pm.total_tokens, pm.peak_prompt_tokens)
    row(rm.name, rm.calls, rm.prompt_tokens, rm.completion_tokens, rm.total_tokens, rm.peak_prompt_tokens)
    print("-" * 74)
    row("[Plan A Total]", pm.calls + rm.calls, pm.prompt_tokens + rm.prompt_tokens,
        pm.completion_tokens + rm.completion_tokens, dual_total, dual_peak)
    row("[Plan B Single-agent self-review]", sm.calls, sm.prompt_tokens, sm.completion_tokens,
        sm.total_tokens, sm.peak_prompt_tokens)
    print("-" * 74)
    print(f"Prompt token sequence per call:")
    print(f"  Plan A Proposer : {pm.per_call_prompt}")
    print(f"  Plan A Reviewer : {rm.per_call_prompt}   ← Each round independent, only sees latest screenshot, does not accumulate across iterations")
    print(f"  Plan B Single-agent : {sm.per_call_prompt}   ← Images accumulate in the same context, peak increases with iterations")
    print()
    print(f"Key conclusions:")
    print(f"  · Context peak (single prompt token, determines whether the context window is exceeded):")
    print(f"      Plan A = {dual_peak}   Plan B = {sm.peak_prompt_tokens}   "
          f"（B/A = {sm.peak_prompt_tokens / max(dual_peak,1):.2f}x）")
    print(f"  · The Proposer never sees images, its peak is only {pm.peak_prompt_tokens} tokens (pure text feedback).")
    print(f"  · Plan B has the highest peak because images accumulate in the same context; the more pages and iterations, the larger the gap.")

    #  Summary saved
    summary = {
        "models": {"text": agents.TEXT_MODEL, "vision": agents.VISION_MODEL},
        "dual_agent": {
            "iteration_scores": scores,
            "final_quality": dual_final,
            "proposer_tokens": pm.__dict__,
            "reviewer_tokens": rm.__dict__,
            "total_tokens": dual_total,
            "peak_context_prompt_tokens": dual_peak,
        },
        "single_agent": {
            "final_quality": single_final,
            "tokens": sm.__dict__,
            "total_tokens": sm.total_tokens,
            "peak_context_prompt_tokens": sm.peak_prompt_tokens,
        },
    }
    p = save_text("comparison_summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nFull comparison saved:{p}")
    print(f"All slides.md / review.json / rendered PNGs are located at:{OUT_DIR}/ and slidev_workspace/exports/")


if __name__ == "__main__":
    main()
