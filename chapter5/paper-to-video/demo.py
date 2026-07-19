#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experiment 5-5: Automatic Generation of Paper Explanation Videos (★★)

Pipeline (end-to-end self-contained, no dependency on 5-4):
  1) Slides: Use PIL to generate several PNG pages with titles/key points (simulating the output of "paper -> PPT"),
             or use --slides to pass an external JSON to replace the built-in example.
  2) Script: For each page, call gpt-5.6-luna to generate [conversational, guiding] explanation text
            (narrative rather than restating key points, responsible for transitions); or use --script to directly feed a ready-made script.
  3) TTS: Use OpenAI tts-1 (voice=alloy) to synthesize the explanation text into an mp3 audio for each page;
           or use --tts-provider offline to let ffmpeg generate placeholder silent audio (no API needed).
  4) Composition: Use ffmpeg to combine each page's PNG and its audio into a segmented video (duration per page = audio duration),
           then concatenate into a single output/lecture.mp4 (output path can be specified with --output).
  5) Validation: Use ffprobe to print the final mp4's duration/resolution/audio-video stream info.

Dependencies: ffmpeg / ffprobe (command line), Python packages see requirements.txt.
Environment variables: OPENAI_API_KEY (required when using openai provider; if not configured, OPENROUTER_API_KEY can be used as fallback for script generation, TTS degrades to offline placeholder),
           optional OPENAI_BASE_URL / TEXT_MODEL / TTS_MODEL / TTS_VOICE.
Tip: To verify the entire ffmpeg composition pipeline without API / network, use `python demo.py --offline`.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# ---------------------------------------------------------------------------
#Path and Configuration
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
SLIDES_DIR = OUTPUT_DIR / "slides"
AUDIO_DIR = OUTPUT_DIR / "audio"
SEG_DIR = OUTPUT_DIR / "segments"
FINAL_MP4 = OUTPUT_DIR / "lecture.mp4"

#Default model/voice: environment variables take precedence, command line --text-model etc. can override.
DEFAULT_TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-5.6-luna")
DEFAULT_TTS_MODEL = os.getenv("TTS_MODEL", "tts-1")
DEFAULT_TTS_VOICE = os.getenv("TTS_VOICE", "alloy")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def map_model_to_openrouter(model: str) -> str:
    """Map direct model names to OpenRouter IDs (non-mappable IDs fall back to the current cheap flagship)."""
    if not model or "/" in model:
        return model or "openai/gpt-5.6-luna"
    m = model.lower()
    if m.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai/" + model
    if m.startswith("claude"):
        if "haiku" in m:
            return "anthropic/claude-haiku-4.5"
        if "sonnet" in m:
            return "anthropic/claude-sonnet-4.6"
        return "anthropic/claude-opus-4.8"
    if m.startswith("gemini"):
        return "google/" + model
    return "openai/gpt-5.6-luna"

#Offline placeholder audio Chinese speech rate estimate (characters/second), used to convert script length into display duration.
OFFLINE_CHARS_PER_SEC = 4.5

#Video Parameters
WIDTH, HEIGHT = 1280, 720
FPS = 30

#Available Chinese fonts on macOS (fallback by priority)
FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]


@dataclass
class Config:
    """Adjustable parameters for a single run (assembled from command line/environment variables)."""

    provider: str = "openai"          # openai | offline
    text_model: str = DEFAULT_TEXT_MODEL
    tts_model: str = DEFAULT_TTS_MODEL
    tts_voice: str = DEFAULT_TTS_VOICE
    limit: "int | None" = None
    output: Path = FINAL_MP4
    slides: "list[dict] | None" = None   #Slide content (None = use built-in example)
    script: "list[str] | None" = None    #Ready-made script (None = generate on demand)


# ---------------------------------------------------------------------------
#Simulated output of "paper -> PPT": title and key points for each page.
#Here we use "Attention Is All You Need" (Transformer) as the example paper.
#In the real 5-4 pipeline, this data is generated from the paper PDF by the Proposer/Reviewer Agent.
#Alternatively, use --slides your_slides.json to pass external data with the same structure to replace this example.
# ---------------------------------------------------------------------------
SLIDES = [
    {
        "title": "Attention Is All You Need",
        "subtitle": "Transformer: A Novel Sequence Modeling Architecture",
        "bullets": [
            "Vaswani et al., 2017 at NeurIPS",
            "Fully based on attention mechanism, discarding recurrence and convolution",
            "Achieved state-of-the-art results on machine translation tasks",
        ],
    },
    {
        "title": "Research Background and Motivation",
        "subtitle": "Why abandon RNN?",
        "bullets": [
            "RNN computes sequentially over time steps, difficult to parallelize",
            "Long-range dependencies tend to decay during gradient propagation",
            "Computational efficiency becomes a bottleneck when training large models",
        ],
    },
    {
        "title": "Core Method: Self-Attention",
        "subtitle": "Self-Attention and Multi-Head Mechanism",
        "bullets": [
            "Use Query / Key / Value to compute associations between words",
            "Multi-head attention captures multiple relationships from different subspaces",
            "Positional encoding injects sequence order information into the model",
        ],
    },
    {
        "title": "Experimental Results",
        "subtitle": "Faster and more accurate",
        "bullets": [
            "WMT14 English-German translation BLEU reaches 28.4, a new high",
            "Training cost significantly lower than previous best models",
            "Highly parallelizable, fully utilizing GPU compute",
        ],
    },
    {
        "title": "Summary and Impact",
        "subtitle": "Ushering in the era of large models",
        "bullets": [
            "Transformer becomes the universal backbone of NLP",
            "Spawning pre-trained large models like BERT and GPT",
            "Impact extending to vision, speech, and multimodal domains",
        ],
    },
]


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load an available font (supports Chinese) from a candidate list."""
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def run(cmd: list) -> str:
    """Execute a command and return stdout; on failure, raise an exception and print stderr."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\nSTDERR:\n{proc.stderr}"
        )
    return proc.stdout


def ffprobe_duration(path: Path) -> float:
    """Read media file duration (in seconds) using ffprobe."""
    out = run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return float(out.strip())


def load_slides_file(path: Path) -> list:
    """Load slide content from a JSON file ([{title, subtitle, bullets}, ...])."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        sys.exit(f"[Error] --slides file must be a non-empty JSON list:{path}")
    for i, s in enumerate(data):
        if not all(k in s for k in ("title", "subtitle", "bullets")):
            sys.exit(f"[Error] --slides item {i + 1} is missing title/subtitle/bullets fields.")
    return data


def load_script_file(path: Path) -> list:
    """Load pre-written narration from a JSON file (list of strings, one per slide)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        sys.exit(f"[Error] --script file must be a JSON list of strings (one per slide):{path}")
    return data


# ---------------------------------------------------------------------------
# Step 1: Render Slide PNGs
# ---------------------------------------------------------------------------
def render_slide(slide: dict, index: int, total: int) -> Path:
    """Render a slide as a 1280x720 PNG."""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(23, 32, 56))  # Dark Blue Background
    draw = ImageDraw.Draw(img)

    title_font = load_font(58)
    subtitle_font = load_font(34)
    bullet_font = load_font(32)
    footer_font = load_font(22)

    # Top Decorative Bar
    draw.rectangle([0, 0, WIDTH, 12], fill=(88, 166, 255))

    # Title (auto-wrap if too wide)
    y = 90
    for line in textwrap.wrap(slide["title"], width=22):
        draw.text((90, y), line, font=title_font, fill=(255, 255, 255))
        y += 72

    # Subtitle
    y += 6
    draw.text((90, y), slide["subtitle"], font=subtitle_font, fill=(88, 166, 255))
    y += 70

    # Bullet Points
    for bullet in slide["bullets"]:
        draw.ellipse([94, y + 14, 110, y + 30], fill=(88, 166, 255))
        for j, line in enumerate(textwrap.wrap(bullet, width=30)):
            draw.text((130, y), line, font=bullet_font, fill=(220, 226, 240))
            y += 44
        y += 16

    # Footer: Page Number
    footer = f"Page {index + 1} / {total} of "
    draw.text((90, HEIGHT - 50), footer, font=footer_font, fill=(120, 132, 160))

    path = SLIDES_DIR / f"slide_{index + 1:02d}.png"
    img.save(path)
    return path


# ---------------------------------------------------------------------------
# Step 2: Generate Spoken Narration for Each Slide
# ---------------------------------------------------------------------------
def offline_narration(slide: dict) -> str:
    """Offline placeholder narration: Generate a readable text using subtitles + bullet points without calling LLM (for placeholder audio track time estimation)."""
    return f"{slide['subtitle']}。" + "；".join(slide["bullets"]) + "。"


def generate_narration(client, cfg: Config, slide: dict, index: int, total: int) -> str:
    """Call the text model (default gpt-5.6-luna) to generate conversational, guiding narration for the current page."""
    position = (
        "This is the first page of the presentation; please naturally introduce the topic." if index == 0
        else "This is the last page; please provide a concluding summary." if index == total - 1
        else "This is an intermediate page; please naturally connect with the previous page, bridging the content."
    )
    prompt = (
        "You are a science communicator narrating a video explaining a paper.\n"
        f"This is slide {index + 1}/{total}.{position}。\n\n"
        f"Slide title:{slide['title']}\n"
        f"Subtitle:{slide['subtitle']}\n"
        f"Bullet points:\n- " + "\n- ".join(slide["bullets"]) + "\n\n"
        "Please generate conversational narration for this slide, with the following requirements:\n"
        "1) It should be guiding spoken narration, not a point-by-point recitation;\n"
        "2) Natural and fluent, with transitions, like a real lecture;\n"
        "3) Keep it to 3–4 sentences (about 70–110 characters);\n"
        "4) Output only the narration text, without any prefixes, suffixes, titles, or list markers."
    )
    # Inference models (gpt-5 / o series, etc.) may not accept custom temperature; set to 1 uniformly.
    _reasoning = any(k in (cfg.text_model or "").lower()
                     for k in ("gpt-5", "o1", "o3", "o4", "thinking", "reasoner", "kimi-k3"))
    resp = client.chat.completions.create(
        model=cfg.text_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=1 if _reasoning else 0.7,
    )
    return resp.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Step 3: TTS speech synthesis
# ---------------------------------------------------------------------------
def synthesize_openai(client, cfg: Config, text: str, index: int) -> Path:
    """Use OpenAI tts-1 to synthesize the narration into mp3."""
    path = AUDIO_DIR / f"audio_{index + 1:02d}.mp3"
    # Use streaming write interface to avoid loading the entire audio into memory.
    with client.audio.speech.with_streaming_response.create(
        model=cfg.tts_model,
        voice=cfg.tts_voice,
        input=text,
    ) as response:
        response.stream_to_file(str(path))
    return path


def synthesize_offline(text: str, index: int) -> Path:
    """Offline placeholder TTS: Use ffmpeg to generate a "silent" mp3, with duration estimated based on narration word count.

    This allows running the full pipeline of "render -> estimate time -> ffmpeg synthesis" without any API/network,
    to verify ffmpeg's per-slide alignment and concatenation correctness (audio track is silent placeholder, not real voice).
    """
    path = AUDIO_DIR / f"audio_{index + 1:02d}.mp3"
    duration = max(2.0, len(text) / OFFLINE_CHARS_PER_SEC)
    run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
            "-t", f"{duration:.3f}",
            "-c:a", "libmp3lame", "-q:a", "9",
            str(path),
        ]
    )
    return path


def synthesize_speech(client, cfg: Config, text: str, index: int) -> Path:
    """Synthesize a voice audio segment by provider."""
    if cfg.provider == "offline":
        return synthesize_offline(text, index)
    return synthesize_openai(client, cfg, text, index)


# ---------------------------------------------------------------------------
# Step 4: ffmpeg synthesis
# ---------------------------------------------------------------------------
def build_segment(png: Path, mp3: Path, index: int, duration: float) -> Path:
    """Combine "one slide PNG + its audio" into an mp4.

    Use -t to precisely lock the total duration to the audio length of that slide, ensuring "each slide's display time exactly matches the voice duration"
    (relying solely on -loop + -shortest would cause the static image track to be about 1–2 seconds longer than the audio).
    """
    out = SEG_DIR / f"seg_{index + 1:02d}.mp4"
    run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(png),      # Static image loop as video track
            "-i", str(mp3),                     # Audio for this slide
            "-c:v", "libx264", "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-vf", f"scale={WIDTH}:{HEIGHT}",
            "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.3f}",            # Precisely lock to audio duration
            str(out),
        ]
    )
    return out


def concat_segments(segments: list, output: Path) -> Path:
    """Use concat demuxer to losslessly concatenate segments into the final mp4."""
    list_file = SEG_DIR / "concat.txt"
    list_file.write_text(
        "".join(f"file '{seg.name}'\n" for seg in segments), encoding="utf-8"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output),
        ]
    )
    return output


# ---------------------------------------------------------------------------
# Self-check (no API calls): Check if external commands and key configurations are ready.
# ---------------------------------------------------------------------------
def self_check(cfg: Config) -> int:
    """Quickly check ffmpeg/ffprobe, Chinese fonts, and key environment variables; return exit code."""
    ok = True
    print("=== Environment Self-Check (no API calls) ===")

    for tool in ("ffmpeg", "ffprobe"):
        found = shutil.which(tool)
        print(f"  {'[OK]' if found else '[Missing]'} {tool}: {found or 'Not found, please install ffmpeg'}")
        ok = ok and bool(found)

    font = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
    print(f"  {'[OK]' if font else '[Fallback]'} Chinese font: {font or 'No Chinese system font found, will fall back to default font'}")

    key_set = bool(os.getenv("OPENAI_API_KEY"))
    or_set = bool(os.getenv("OPENROUTER_API_KEY"))
    if cfg.provider == "offline":
        print("  [OK] Provider: offline (placeholder silent audio track, no OPENAI_API_KEY required)")
    else:
        print(f"  {'[OK]' if (key_set or or_set) else '[Missing]'} OPENAI_API_KEY: {'Set' if key_set else 'Not set'}"
              f"  OPENROUTER_API_KEY (fallback): {'Set' if or_set else 'Not set'}"
              + ("" if key_set else "  ← When no direct key is available, narration text goes through OpenRouter, TTS degrades to offline placeholder"))
    print(f"  [Config] provider={cfg.provider}  TEXT_MODEL={cfg.text_model}  "
          f"TTS_MODEL={cfg.tts_model}  TTS_VOICE={cfg.tts_voice}")
    print(f"  [Config] OPENAI_BASE_URL={os.getenv('OPENAI_BASE_URL') or '(Official default)'}")
    print(f"  [Config] Number of slides={len(cfg.slides or SLIDES)}  Output={cfg.output}")

    print("Self-check" + ("passed." if ok else "Failed: Please install the missing command-line tools first."))
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Main Flow
# ---------------------------------------------------------------------------
def main(cfg: Config) -> None:
    online = cfg.provider != "offline"
    need_llm = cfg.script is None and online  #  Call LLM to generate narration only when no script is provided and not offline

    #  Text (narration) and TTS use two clients: OpenAI voice API is not on OpenRouter,
    #  so TTS must use direct OPENAI_API_KEY; narration text can use general OpenRouter fallback.
    client = None       #  Text/Narration Client
    tts_client = None   #  TTS Client (direct OpenAI only)
    if online:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL") or None
        orkey = os.getenv("OPENROUTER_API_KEY")
        if not (api_key or orkey):
            sys.exit("[Error] OPENAI_API_KEY (or OPENROUTER_API_KEY fallback) not set. Copy env.example to .env and fill in;"
                     "or use --offline to verify the synthesis pipeline without an API.")
        from openai import OpenAI  #  Lazy import: --offline does not require installing/connecting to openai

        #  Text client: When no direct key is available, or default gpt-5.x (direct connection requires organization real-name authentication), switch to OpenRouter.
        prefer_or = bool(orkey) and (cfg.text_model or "").lower().startswith("gpt-5")
        if prefer_or or (not api_key and orkey):
            client = OpenAI(api_key=orkey, base_url=OPENROUTER_BASE_URL, timeout=120.0, max_retries=3)
            cfg.text_model = map_model_to_openrouter(cfg.text_model)
        else:
            client = OpenAI(base_url=base_url, timeout=120.0, max_retries=3)

        #  TTS client: Only direct OPENAI_API_KEY can be used; if missing, audio degrades to offline silent placeholder
        #(The commentary is still generated by the text client in real time).
        if api_key:
            tts_client = OpenAI(base_url=base_url, timeout=120.0, max_retries=3)
        else:
            print("[Tip] No direct OPENAI_API_KEY configured; OpenAI TTS is not available on OpenRouter;"
                  "Audio falls back to offline silent placeholder (commentary still generated by OpenRouter in real time).\n")
            cfg.provider = "offline"

    for d in (SLIDES_DIR, AUDIO_DIR, SEG_DIR):
        d.mkdir(parents=True, exist_ok=True)

    all_slides = cfg.slides or SLIDES
    # --limit / --quick: only process the first N pages, for quick smoke testing (reduces API calls and time).
    slides = all_slides[:cfg.limit] if cfg.limit else all_slides
    total = len(slides)

    if cfg.script is not None and len(cfg.script) < total:
        sys.exit(f"[Error] --script provided {len(cfg.script)} segments, fewer than the {total} pages to process.")

    segments = []
    manifest = []

    tag = f"(limited to {total}/{len(all_slides)} pages)" if cfg.limit else f"(total {total} pages)"
    mode = "offline placeholder" if not online else f"{cfg.provider}/{cfg.tts_model}"
    print(f"=== Paper Explanation Video Auto-Generation{tag}[{mode}] ===\n")

    for i, slide in enumerate(slides):
        print(f"[{i + 1}/{total}] {slide['title']}")

        # 1) Render slides
        png = render_slide(slide, i, total)
        print(f"    Slides: {png.relative_to(ROOT)}")

        # 2) Commentary: use provided script first, then LLM generation, offline uses placeholder text
        if cfg.script is not None:
            narration = cfg.script[i].strip()
        elif need_llm:
            narration = generate_narration(client, cfg, slide, i, total)
        else:
            narration = offline_narration(slide)
        print(f"    Commentary: {narration}")

        # 3) TTS speech synthesis (openai real voice via direct tts_client / offline silent placeholder)
        mp3 = synthesize_speech(tts_client, cfg, narration, i)
        dur = ffprobe_duration(mp3)
        print(f"    Audio:   {mp3.relative_to(ROOT)}  Duration {dur:.2f}s")

        # 4) Compose segmented videos
        seg = build_segment(png, mp3, i, dur)
        segments.append(seg)
        manifest.append(
            {"page": i + 1, "narration": narration,
             "audio": str(mp3.relative_to(ROOT)), "audio_seconds": round(dur, 2)}
        )
        print()

    # 5) Concatenate into final video
    print("=== Concatenate into Final Video ===")
    concat_segments(segments, cfg.output)

    audio_total = sum(m["audio_seconds"] for m in manifest)
    video_total = ffprobe_duration(cfg.output)

    #  Save commentary list for review
    (OUTPUT_DIR / "narration.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Total audio duration per page: {audio_total:.2f}s")
    print(f"Final video duration:   {video_total:.2f}s")
    try:
        shown = cfg.output.relative_to(ROOT)
    except ValueError:
        shown = cfg.output
    print(f"Output file:       {shown}")
    print("\nDone. Use the following command to view video metadata:")
    print(f"  ffprobe -v error -show_format -show_streams {cfg.output}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Paper explanation video auto-generation: commentary generation -> TTS -> ffmpeg page-by-page composition.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example: \n"
            "  python demo.py                       # Generate a full 5-page narrated video (requires OPENAI_API_KEY)\n"
            "  python demo.py --quick               # Run only page 1 for a quick smoke test\n"
            "  python demo.py --limit 2             # Run only the first 2 pages\n"
            "  python demo.py --offline             # No API needed: placeholder silent audio track, verify the entire ffmpeg pipeline\n"
            "  python demo.py --slides my.json      # Replace built-in slides with external slide content\n"
            "  python demo.py --script narr.json    # Use an existing narration script, skip LLM generation\n"
            "  python demo.py -o out/talk.mp4       # Specify the final video output path\n"
            "  python demo.py --check               # Environment self-check only, no API calls"
        ),
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Process only the first N slides (quick test, significantly reduces API calls and time)",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick test: equivalent to --limit 1",
    )
    parser.add_argument(
        "--slides", type=Path, default=None, metavar="FILE",
        help="Slide content JSON file ([{title,subtitle,bullets}, ...]); defaults to built-in examples",
    )
    parser.add_argument(
        "--script", type=Path, default=None, metavar="FILE",
        help="Existing narration JSON file (list of strings, one per slide); when provided, skips LLM narration generation",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=FINAL_MP4, metavar="FILE",
        help=f"Final narrated video output path (default {FINAL_MP4.relative_to(ROOT)}）",
    )
    parser.add_argument(
        "--tts-provider", choices=("openai", "offline"), default="openai",
        help="TTS provider: openai=real voice (requires API); offline=ffmpeg generates placeholder silent audio (no API)",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Fully offline: equivalent to --tts-provider offline, and uses bullet-point placeholder narration (no API calls at all)",
    )
    parser.add_argument(
        "--text-model", default=DEFAULT_TEXT_MODEL, metavar="NAME",
        help=f"Narration generation model (default {DEFAULT_TEXT_MODEL}, or env var TEXT_MODEL)",
    )
    parser.add_argument(
        "--tts-model", default=DEFAULT_TTS_MODEL, metavar="NAME",
        help=f"TTS model (default {DEFAULT_TTS_MODEL}, or env var TTS_MODEL)",
    )
    parser.add_argument(
        "--tts-voice", default=DEFAULT_TTS_VOICE, metavar="NAME",
        help=f"TTS voice (default {DEFAULT_TTS_VOICE}, options: nova/shimmer/echo, etc.)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Environment self-check (checks ffmpeg/ffprobe/fonts/config) then exits, no API calls",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> Config:
    """Assemble command-line arguments into a Config."""
    limit = 1 if args.quick else args.limit
    if limit is not None and limit < 1:
        sys.exit("[Error] --limit must be a positive integer.")

    provider = "offline" if args.offline else args.tts_provider
    slides = load_slides_file(args.slides) if args.slides else None
    script = load_script_file(args.script) if args.script else None

    return Config(
        provider=provider,
        text_model=args.text_model,
        tts_model=args.tts_model,
        tts_voice=args.tts_voice,
        limit=limit,
        output=args.output,
        slides=slides,
        script=script,
    )


if __name__ == "__main__":
    args = parse_args()
    cfg = build_config(args)
    if args.check:
        sys.exit(self_check(cfg))
    main(cfg)
