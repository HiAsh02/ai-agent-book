"""
Experiment 9-5 Demo: Control Tag-Driven Controllable TTS
======================================

Demonstrates two things:
  1) Comparison of three configurations (as required in the book): The same text with control tags, using
     A. No control tags (fluent but robotic)
     B. Single reference voice (natural but emotionally monotone)
     C. Multi-reference voice library (switches emotion/speed/pause according to control tags, close to human customer service)
  2) Same sentence text, different control tags -> synthesize multiple audio clips with different styles.

Run: python demo.py
Output: output/*.mp3
"""

import argparse
import os
import re
import subprocess

from dotenv import load_dotenv

from markup import parse, format_marker_reference
from tts import synthesize_segments, PREFERRED_MODEL
from voice_library import VOICE_LIBRARY, BASE_VOICE, EMOTIONS, SPEEDS, STYLES

load_dotenv()

OUT_DIR = os.path.join(os.path.dirname(__file__), "output")
TMP_DIR = os.path.join(OUT_DIR, ".tmp")

# LLM output example from the book (with control tags)
DEMO_TEXT = ("[EMO:happy][SPEED:fast]Great! Your order has been confirmed."
             "[THINKING]Hmm, let me check the delivery time..."
             "[EMO:neutral][SPEED:normal]Expected delivery tomorrow afternoon.")

# Same sentence text + different control tags -> different styles
STYLE_VARIANTS = {
    "variant_happy_fast":  "[EMO=happy][SPEED=fast]Your order has been confirmed, expected delivery tomorrow afternoon.",
    "variant_frustrated":  "[EMO=frustrated][SPEED=slow]Your order has been confirmed, expected delivery tomorrow afternoon.",
    "variant_thinking":    "[THINKING]Your order has been confirmed, [PAUSE]expected delivery tomorrow afternoon.",
    "variant_casual_laugh": "[EMO=happy][STYLE=relaxed]Your order has been confirmed<laugh>, expected delivery tomorrow afternoon.",
    "variant_emphasis":    "Your order <emphasis>has been confirmed</emphasis>, expected <emphasis>tomorrow afternoon</emphasis> delivery.",
}


def strip_markers(text: str) -> str:
    """Remove all control tags to get plain text (for the 'no control tags' baseline)."""
    return re.sub(r"\[[^\]]*\]|<[^>]+>", "", text).strip()


def ffprobe(path: str) -> str:
    """Print mp3 duration/format/bitrate to verify audio is actually generated."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,format_name,bit_rate", "-of",
         "default=noprint_wrappers=1:nokey=0", path],
        capture_output=True, text=True,
    ).stdout.strip().replace("\n", "  ")
    size = os.path.getsize(path)
    return f"{out}  size={size}B"


def render(name: str, segments, print_info=True):
    """Synthesize an audio file and print its synthesis info + ffprobe."""
    out_path = os.path.join(OUT_DIR, f"{name}.mp3")
    info = synthesize_segments(segments, out_path, os.path.join(TMP_DIR, name))
    if print_info:
        for seg in info:
            if seg["type"] == "silence":
                print(f"    · [Silence {seg['ms']}ms]")
            else:
                emph = " +emphasis" if "emphasis" in seg.get("instructions", "") else ""
                print(f"    · [{seg['profile']:26s}{emph}] {seg['model']:16s} "
                      f"voice={seg['voice']} text='{seg['text']}'")
    print(f"  => {os.path.relpath(out_path)}  |  {ffprobe(out_path)}")
    return out_path


def print_voice_library():
    """Print the full reference voice library offline (no API key needed)."""
    print(f"Reference voice library total {len(VOICE_LIBRARY)} entries = emotion {len(EMOTIONS)} × speed "
          f"{len(SPEEDS)} × style {len(STYLES)}; full library fixed base voice = {BASE_VOICE}"
          f"(simulating Fish Audio's consistent timbre), only instructions differ.\n")
    print(f"{'Archive (emotion_speed_style)':<28} {'base voice':<11} instructions")
    print("-" * 100)
    for key, v in VOICE_LIBRARY.items():
        print(f"{key:<28} {v['base_voice']:<11} {v['instructions']}")


def print_marker_mapping(text: str):
    """Print the control tag mapping table + parsing process for given text offline (no API key needed)."""
    print("Control tag -> action static mapping table:\n")
    print(format_marker_reference())
    print("\n" + "=" * 72)
    print("Real-time parsing of example text (tag -> reference voice / silence):")
    print("Text:", text)
    print("=" * 72)
    trace = []
    segments = parse(text, trace=trace)
    print("-- Parsing process --")
    for line in trace:
        print(line)
    print("-- Parsed segment sequence --")
    for i, seg in enumerate(segments):
        if seg["type"] == "silence":
            print(f"  {i:02d}. [Mute {seg['ms']}ms]")
        else:
            profile = f"{seg['emotion']}_{seg['speed']}_{seg['style']}"
            emph = " +emphasis" if seg.get("emphasis") else ""
            print(f"  {i:02d}. [Voice {profile}{emph}] '{seg['text']}'")


def build_marked_text(text: str, emotion, speed, style) -> str:
    """Prepend --emotion/--speed/--style as state marker prefixes to text (stacking when text already has markers)."""
    prefix = ""
    if emotion:
        prefix += f"[EMO:{emotion}]"
    if speed:
        prefix += f"[SPEED:{speed}]"
    if style:
        prefix += f"[STYLE:{style}]"
    return prefix + text


def parse_args():
    p = argparse.ArgumentParser(
        description="Experiment 9-5: Control marker-driven controllable TTS. Default (no arguments) comparison"
                    "of three configurations: \"No marker / Single reference voice / Multi-reference voice library\", and synthesize multiple"
                    "style variants (output output/*.mp3). Also can synthesize a single custom text, or"
                    "offline view reference voice library / control marker mapping (no API key required).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: \n"
               "  python demo.py                       # Run full comparison + style variants (requires API)\n"
               "  python demo.py --quick               # Run only three-configuration comparison\n"
               "  python demo.py --list-voices         # Offline: print 24 reference voice library entries\n"
               "  python demo.py --dump-mapping        # Offline: print control marker mapping table\n"
               "  python demo.py --text '[Emotion=Happy][Speed=Fast]Your order has been confirmed.' -o out.mp3\n"
               "  python demo.py --text 'Your order has been confirmed.' --emotion thinking --speed slow",
    )
    p.add_argument(
        "--text", metavar="Text",
        help="Synthesize only this text segment (can embed control markers, e.g., [Emotion=Happy][THINKING]...)."
             "If not specified, run the default three-configuration comparison + style variants.",
    )
    p.add_argument(
        "--emotion", choices=list(EMOTIONS.keys()),
        help="Specify emotion reference voice for --text (equivalent to prepending [EMO:x] to text).",
    )
    p.add_argument(
        "--speed", choices=list(SPEEDS.keys()),
        help="Specify speed for --text (equivalent to prepending [SPEED:x] to text).",
    )
    p.add_argument(
        "--style", choices=list(STYLES.keys()),
        help="Specify tone style for --text (equivalent to prepending [STYLE:x] to text).",
    )
    p.add_argument(
        "-o", "--output", metavar="Path",
        help="Output mp3 path for --text mode (default output/custom.mp3).",
    )
    p.add_argument(
        "--list-voices", action="store_true",
        help="Offline print full reference voice library (24 entries and their instructions), no API key required.",
    )
    p.add_argument(
        "--dump-mapping", action="store_true",
        help="Offline print control marker -> action mapping table, and demonstrate parsing process with example text, no API key required.",
    )
    p.add_argument(
        "--quick", action="store_true",
        help="Run only three-configuration comparison (A/B/C), skip 5 style variants, reduce TTS calls and time.",
    )
    return p.parse_args()


def main():
    args = parse_args()

    # ---- Offline path (no API key required): View reference voice library / control marker mapping ----
    if args.list_voices:
        print_voice_library()
        return
    if args.dump_mapping:
        print_marker_mapping(args.text or DEMO_TEXT)
        return

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Please set OPENAI_API_KEY first (see env.example);"
                         "or use --list-voices / --dump-mapping to view voice library and marker mapping offline.")
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---- Single custom text synthesis ----
    if args.text or args.emotion or args.speed or args.style:
        text = build_marked_text(args.text or "", args.emotion, args.speed, args.style)
        if not text.strip():
            raise SystemExit("Please use --text to provide the text to be synthesized.")
        out_path = args.output or os.path.join(OUT_DIR, "custom.mp3")
        print(f"Preferred model: {PREFERRED_MODEL}(automatically falls back to tts-1 when unavailable)\n")
        print("Text:", text)
        trace = []
        segs = parse(text, trace=trace)
        print("-- Control token parsing process --")
        for line in trace:
            print(line)
        print("-- Synthesis segment --")
        name = os.path.splitext(os.path.basename(out_path))[0]
        render(name, segs)
        if os.path.abspath(os.path.join(OUT_DIR, f"{name}.mp3")) != os.path.abspath(out_path):
            os.replace(os.path.join(OUT_DIR, f"{name}.mp3"), out_path)
            print(f"  => Written {out_path}")
        return

    print(f"Preferred model: {PREFERRED_MODEL}(automatically falls back to tts-1 when unavailable)"
          f"{'  [--quick mode: skip style variants]' if args.quick else ''}\n")

    # ================= Comparison of Three Configurations =================
    print("=" * 72)
    print("Comparative experiment: same text with control tokens, three configurations")
    print("Original text:", DEMO_TEXT)
    print("=" * 72)

    # ---- Configuration A: No control tokens (baseline, fluent but mechanical) ----
    print("\n[A] No control tokens (strip all tokens, single default synthesis)")
    plain = strip_markers(DEMO_TEXT)
    print("    Plain text:", plain)
    seg_a = parse(plain)  #  No tokens -> single neutral segment
    render("A_no_markers", seg_a)

    # ---- Configuration B: Single reference voice (natural but emotionally monotone) ----
    print("\n[B] Single reference voice (remove tokens, use the same neutral/normal/formal reference voice throughout)")
    seg_b = [dict(type="speech", text=plain, emotion="neutral",
                  speed="normal", style="formal", emphasis=False)]
    render("B_single_voice", seg_b)

    # ---- Configuration C: Multi-reference voice library (switch by control tokens) ----
    print("\n[C] Multi-reference voice library (parse control tokens -> switch reference voice per segment + pauses)")
    trace = []
    seg_c = parse(DEMO_TEXT, trace=trace)
    print("    -- Control token parsing process --")
    for line in trace:
        print(line)
    print("    -- Synthesis segment --")
    render("C_voice_library", seg_c)

    # ================= Same Text / Different Control Tokens =================
    if not args.quick:
        print("\n" + "=" * 72)
        print("Same sentence text + different control tokens -> different style audio")
        print("=" * 72)
        for name, text in STYLE_VARIANTS.items():
            print(f"\n[{name}] {text}")
            trace = []
            segs = parse(text, trace=trace)
            for line in trace:
                print(line)
            render(name, segs)

    # ================= Summary =================
    print("\n" + "=" * 72)
    print("All output files (ffprobe duration comparison)")
    print("=" * 72)
    for f in sorted(os.listdir(OUT_DIR)):
        if f.endswith(".mp3"):
            p = os.path.join(OUT_DIR, f)
            print(f"  {f:26s} {ffprobe(p)}")


if __name__ == "__main__":
    main()
