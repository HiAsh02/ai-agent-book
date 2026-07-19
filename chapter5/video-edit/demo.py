"""
Experiment 5-6: API-Based Intelligent Video Editing (Two-Step Vision Localization + Proposer-Reviewer)

Run with one command:
  python demo.py                 # Default requirement: "Cut out the surfing part"
  python demo.py "Cut out the skiing part and add subtitle Winter"   # Custom requirement

Pipeline:
  1. Programmatically generate a test video with 4 distinct scenes (HIKING/SURFING/SKIING/CYCLING);
  2. Proposer parses natural language requirement → target scene + effects;
  3. Video analysis sub-agent performs two-step localization (coarse every 10s → fine every 1s) to find precise boundaries;
  4. Proposer generates a Blender Python API (bpy) script to cut the clip (can include subtitles/slow motion);
     If Blender is installed, headless rendering; otherwise fallback to ffmpeg—but bpy script is always generated (code generation artifact);
  5. Reviewer checks keyframes of the output and provides feedback; if unqualified, Proposer revises boundaries and re-cuts, iterating.

Dependencies: ffmpeg/ffprobe (fallback backend + frame extraction), OPENAI_API_KEY (gpt-5.6-luna vision + text; if not configured, OPENROUTER_API_KEY can be used as fallback);
       Optional Blender (original scheme in the book, `--backend blender`).

Common commands (full usage see `python demo.py --help`):
  python demo.py                 # Default requirement, full pipeline
  python demo.py --quick         # Quick mode: coarse sampling + single round review, saves time and money
  python demo.py --smoke         # Smoke test: only editing pipeline + generate bpy script, no API calls
"""
import argparse
import os
import shutil
import sys

from dotenv import load_dotenv

load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output")
SOURCE_VIDEO = os.path.join(OUT_DIR, "source.mp4")   #Test video output location
FINAL_VIDEO = os.path.join(OUT_DIR, "final.mp4")
MAX_ROUNDS = 3  #Maximum number of re-cuts after Reviewer feedback (default, can be overridden with --max-rounds)

DEFAULT_REQUEST = "Cut out the surfing part"


def banner(title):
    print("\n" + "=" * 74)
    print(f"  {title}")
    print("=" * 74)


def build_arg_parser() -> argparse.ArgumentParser:
    """Command-line arguments: positional argument is the Chinese editing requirement, plus input/output/backend/model/quick etc. switches."""
    p = argparse.ArgumentParser(
        prog="demo.py",
        description="Experiment 5-6: API-Based Intelligent Video Editing (Two-Step Vision Localization + Proposer-Reviewer)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example: \n"
            "  python demo.py\n"
            "  python demo.py \"Cut out the skiing part and add subtitle Winter\"\n"
            "  python demo.py -i my.mp4 -o out.mp4 \"Cut out the speech opening\"\n"
            "  python demo.py --backend blender    # Force use Blender Python API for rendering\n"
            "  python demo.py --quick    # Fewer Vision calls, quick validation of pipeline\n"
            "  python demo.py --smoke    # Only run editing pipeline + generate bpy script, no API calls\n"
        ),
    )
    p.add_argument("request", nargs="?", default=DEFAULT_REQUEST,
                   help="Chinese editing requirement (default: %(default)s)")
    p.add_argument("--input", "-i", metavar="VIDEO", default=None,
                   help="Input video path (if not specified, programmatically generate a 4-scene test video)")
    p.add_argument("--output", "-o", metavar="VIDEO", default=FINAL_VIDEO,
                   help="Output video path (default output/final.mp4)")
    p.add_argument("--backend", choices=["auto", "blender", "ffmpeg"], default="auto",
                   help="Editing backend: auto=use bpy if Blender installed, otherwise ffmpeg;"
                        "blender=force Blender Python API; ffmpeg=force ffmpeg (default auto)")
    p.add_argument("--text-model", metavar="NAME", default=None,
                   help="Override text model (otherwise use $TEXT_MODEL, default gpt-5.6-luna)")
    p.add_argument("--vision-model", metavar="NAME", default=None,
                   help="Override vision model, must support image input (otherwise use $VISION_MODEL, default gpt-5.6-luna)")
    p.add_argument("--quick", action="store_true",
                   help="Quick mode: coarse sampling (15s/2s) + single round review, reduces Vision API calls")
    p.add_argument("--max-rounds", type=int, default=MAX_ROUNDS, metavar="N",
                   help="Maximum number of re-cut rounds after Reviewer feedback (default %(default)s; forced to 1 when --quick)")
    p.add_argument("--smoke", action="store_true",
                   help="Smoke test: only editing pipeline + generate bpy script, no API calls")
    return p


def smoke_check():
    """Smoke test: does not touch OpenAI, validates editing pipeline and generates Proposer's bpy script."""
    from blender_editor import blender_available
    from ffmpeg_utils import ensure_ffmpeg, extract_frame, format_probe
    from make_test_video import GROUND_TRUTH, make as make_test_video
    from video_editor import apply_edit

    banner("Smoke test | Editing pipeline + bpy script generation, no API calls")
    try:
        ensure_ffmpeg()
    except RuntimeError as e:
        print(f"\n[Error] {e}")
        sys.exit(1)
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    make_test_video(SOURCE_VIDEO)
    print(f"[1/3] Generate test video OK: {SOURCE_VIDEO}(Scene ground truth={GROUND_TRUTH}）")
    frame_dir = os.path.join(OUT_DIR, "frames")
    os.makedirs(frame_dir, exist_ok=True)   # extract_frame requires directory to exist
    frame = extract_frame(SOURCE_VIDEO, 20.0, os.path.join(frame_dir, "smoke.png"))
    print(f"[2/3] Frame extraction OK: {frame}")
    clip = os.path.join(OUT_DIR, "smoke_cut.mp4")
    script_path = os.path.join(OUT_DIR, "edit.py")
    # backend="auto": if Blender not installed, use ffmpeg for actual rendering, but still generate bpy script (code generation artifact).
    apply_edit(SOURCE_VIDEO, {"start": 15.0, "end": 20.0,
                              "effects": [{"type": "subtitle", "text": "SMOKE"}]},
               clip, backend="auto", script_path=script_path)
    used = "Blender bpy" if blender_available() else "ffmpeg (Blender not installed, falling back)"
    print(f"[3/3] Editing + subtitles OK (backend={used}）：\n{format_probe(clip)}")
    print(f"\nGenerated Proposer's Blender script:{script_path}")
    print("(This is exactly the output of 'Generate Blender Python API code' in the book; after installing Blender, you can directly")
    print(f" `blender --background --python {script_path}` headless rendering.)")
    print("\n✓ Smoke test passed: editing pipeline normal + bpy script generated (OpenAI not called).")


def preflight():
    """Startup self-check: provide clear Chinese error messages instead of traceback."""
    from ffmpeg_utils import ensure_ffmpeg
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")):
        print("\n[Error] OPENAI_API_KEY (or OPENROUTER_API_KEY fallback) not detected.\n"
              "  Please copy env.example to .env and fill in a valid OpenAI Key, or run:\n"
              "    export OPENAI_API_KEY=sk-...   # or export OPENROUTER_API_KEY=sk-or-...\n"
              "  This experiment uses gpt-5.6-luna for visual localization and review, a valid Key is required.")
        sys.exit(1)
    try:
        ensure_ffmpeg()
    except RuntimeError as e:
        print(f"\n[Error] {e}")
        sys.exit(1)


def main():
    args = build_arg_parser().parse_args()
    if args.smoke:                       #  For editing-only pipeline, no API Key needed, return early.
        smoke_check()
        return

    nl_request = args.request
    # --quick: coarsen sampling step and only review once, minimizing Vision calls (for fast pipeline validation).
    coarse_interval = 15.0 if args.quick else 10.0
    fine_interval = 2.0 if args.quick else 1.0
    max_rounds = 1 if args.quick else max(1, args.max_rounds)

    #Model override: write back to environment variables for agents module (lazy initialization) to read. Must be set before importing agents.
    if args.text_model:
        os.environ["TEXT_MODEL"] = args.text_model
    if args.vision_model:
        os.environ["VISION_MODEL"] = args.vision_model
    preflight()

    #Lazy import: ensure preflight errors take precedence over any SDK initialization.
    from agents import (ProposerAgent, ReviewerAgent, VideoAnalyzerAgent,
                        TokenMeter, TEXT_MODEL, VISION_MODEL)
    from blender_editor import blender_available
    from ffmpeg_utils import format_probe, probe_duration
    from make_test_video import make as make_test_video, GROUND_TRUTH
    from video_editor import apply_edit

    #Idempotent: always start from a clean output/ directory.
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    ground_truth = None
    if args.input:
        banner("Step 0 | Use external input video")
        source_video = os.path.abspath(args.input)
        if not os.path.isfile(source_video):
            print(f"\n[Error] Input video does not exist:{source_video}")
            sys.exit(1)
        print(f"Input video:{source_video}")
    else:
        banner("Step 0 | Generate test video (4 distinctly different scenes)")
        source_video = SOURCE_VIDEO
        make_test_video(source_video)
        ground_truth = GROUND_TRUTH
        print(f"Generated {source_video}")
        print(f"Scene ground truth (for checking localization error):{ground_truth}")
    total_dur = probe_duration(source_video)
    print(f"Duration {total_dur:.1f}s")
    print(f"Text model={TEXT_MODEL}  Vision model={VISION_MODEL}  Editing backend={args.backend}")

    #Separate token counting: main Agent (Proposer+Reviewer) vs sub-Agent (screenshot localization).
    main_meter = TokenMeter()
    sub_meter = TokenMeter()
    proposer = ProposerAgent(main_meter)
    reviewer = ReviewerAgent(main_meter)
    analyzer = VideoAnalyzerAgent(sub_meter)

    banner("Step 1 | Proposer parses natural language requirements")
    print(f"User requirements:{nl_request}")
    intent = proposer.parse_request(nl_request)
    target_query = intent["target_query"]
    effects = intent.get("effects", [])
    print(f"Parsed result: target scene='{target_query}'  Effects={effects}")

    banner("Step 2 | Video Analysis Sub-Agent: Two-Step Vision Localization"
           + ("(--quick fast sampling)" if args.quick else ""))
    start, end, trace = analyzer.locate(
        source_video, target_query,
        coarse_interval=coarse_interval, fine_interval=fine_interval,
        frame_dir=os.path.join(OUT_DIR, "frames"),
    )
    c = trace["coarse"]
    print(f"  [Coarse] Every {coarse_interval:.0f}s sample {len(c['timestamps'])} frames → Vision gets interval "
          f"[{c['start']:.0f}, {c['end']:.0f}]s (based on: {c['reason']}）")
    f = trace["fine"]
    print(f"  [Fine] Window {f['window']} every {fine_interval:.0f}s sample {f['timestamps_count']} frames → "
          f"precise boundary [{f['start']:.1f}, {f['end']:.1f}]s (based on: {f['reason']}）")
    print(f"  >>> Final localization: start {start:.1f}s end {end:.1f}s")

    # compare with ground truth, print localization error (acceptance: error ≤ ±3s). Only test clips have ground truth.
    key = _match_ground_truth(target_query, ground_truth) if ground_truth else None
    if key:
        gs, ge = ground_truth[key]
        print(f"  Ground truth [{gs}, {ge}]s → start error {abs(start - gs):.1f}s，"
              f"end error {abs(end - ge):.1f}s (acceptance requirement ≤ 3s)")

    banner("Step 3-4 | Proposer generates bpy script clip + Reviewer review (iteration)")
    plan = {"start": start, "end": end, "effects": effects}
    final_path = None
    for rnd in range(1, max_rounds + 1):
        print(f"\n--- Round {rnd} ---")
        clip = os.path.join(OUT_DIR, f"cut_round{rnd}.mp4")
        script_path = os.path.join(OUT_DIR, f"edit_round{rnd}.py")
        apply_edit(source_video, plan, clip, backend=args.backend,
                   script_path=script_path)
        cdur = probe_duration(clip)
        used = "Blender bpy" if (args.backend == "blender" or
                                 (args.backend == "auto" and blender_available())) else "ffmpeg"
        print(f"  Proposer generates Blender script → {script_path}")
        print(f"  clip segment [{plan['start']:.1f}, {plan['end']:.1f}]s (backend={used}），"
              f"final duration {cdur:.1f}s")

        review = reviewer.review(clip, target_query,
                                 frame_dir=os.path.join(OUT_DIR, "review_frames"))
        print(f"  Reviewer：pass={review['pass']} score={review.get('score')} "
              f"check frame={['%.1f' % t for t in review['frames_checked']]}")
        print(f"  Reviewer feedback:{review['feedback']}")

        if review.get("pass"):
            final_path = clip
            print("  ✓ Approved.")
            break
        if rnd == max_rounds:
            final_path = clip
            print("  Reached max rounds, adopting current clip.")
            break
        #  Failed: Proposer revises boundaries based on feedback and re-clips.
        ns, ne = proposer.revise_bounds(plan["start"], plan["end"],
                                        review["feedback"], total_dur)
        print(f"  Proposer corrects boundaries based on feedback: [{ns:.1f}, {ne:.1f}]s")
        plan["start"], plan["end"] = ns, ne

    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    shutil.copy(final_path, output_path)

    banner("Step 5 | Output Info (ffprobe)")
    print(format_probe(output_path))

    banner("Token Statistics (sub-agent isolated screenshot, main context not polluted)")
    print(f"  Main Agent (Proposer+Reviewer):{main_meter.total()} tokens "
          f"(prompt={main_meter.prompt}, completion={main_meter.completion})")
    print(f"  Sub-agent (two-step screenshot)    :{sub_meter.total()} tokens "
          f"(prompt={sub_meter.prompt}, completion={sub_meter.completion})")
    print(f"\nComplete:{output_path}")


def _match_ground_truth(query, gt):
    q = query.lower()
    for key in gt:
        if key in q:
            return key
    #  Chinese keyword fallback mapping.
    zh = {"Surfing": "surfing", "Hiking": "hiking", "Skiing": "skiing", "Cycling": "cycling",
          "hik": "hiking", "surf": "surfing", "ski": "skiing", "cycl": "cycling"}
    for k, v in zh.items():
        if k in q:
            return v
    return None


if __name__ == "__main__":
    main()
