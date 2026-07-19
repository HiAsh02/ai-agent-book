#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experiment 9-3: Simulating Streaming Speech Perception

The original experiment in the book uses Qwen2-Audio for "chunked input simulating streaming processing", cutting continuous audio into small chunks,
each chunk along with the accumulated audio context is fed into the model, gradually producing text, and measuring the latency of each chunk;
It demonstrates the latency vs. accuracy trade-off between "premature chunking causing misrecognition / missing context" and "waiting for the complete audio before recognition".

Qwen2-Audio currently has no directly callable key/endpoint. This demo uses OpenAI Whisper
(whisper-1) as an **available ASR alternative** to demonstrate the same phenomenon: Whisper is also a "whole-input
non-streaming model" (its encoder requires a full audio segment to start working), so by cutting audio into chunks of increasing length
and recognizing each chunk separately, it reproduces the "cost of premature decision".

Pipeline (online mode):
  1) Use OpenAI TTS (tts-1) to synthesize a Chinese test audio; alternatively, use --audio to directly specify an audio file.
  2) Use ffmpeg to cut the audio into chunks of increasing length (increasing by --chunk-step seconds each time) representing "all audio received so far",
     simulating streaming: t=0.5s, 1.0s, 1.5s ...
  3) For each prefix chunk, call Whisper to get the "current partial recognition result", recording the recognized text and the latency of that single chunk.
  4) Compare: the result and latency of recognizing the entire audio only at the end (whole-utterance / batch approach).
  5) Print a per-chunk recognition table + whole-utterance recognition comparison, quantifying the trade-off between "first available recognition" and whole-utterance latency.

Two comparisons:
  - Streaming (chunked) vs. whole-utterance: a single chunk granularity is sufficient to see the effect.
  - **Comparison between different chunk granularities**: add --compare-chunks to run the streaming simulation for multiple chunk granularities (e.g.,
    0.5/1.0/2.0s) and output a cross-granularity latency comparison table.

Offline self-check (--offline): no network, no ffmpeg required, uses a **synthetic recognizer** (SYNTHETIC) to drive the same
chunking/timing logic — text is revealed proportionally to the prefix length (reproducing "early truncation → convergence as audio accumulates"), latency is synthesized as
"BASE + SLOPE × prefix seconds" (modeling a non-incremental encoder where "longer prefix means slower single chunk"). Numbers are synthetic,
used only to verify chunking/timing/comparison logic, **do not represent any real model's performance**.

Dependencies: openai (Python SDK), local ffmpeg/ffprobe (online mode); offline mode has no external dependencies.
Environment variable: OPENAI_API_KEY (online mode, see env.example).
"""

import argparse
import json
import os
import random
import sys
import shutil
import subprocess
import tempfile
import time
from collections import namedtuple
from pathlib import Path

# Read OPENAI_API_KEY from .env in the same directory (if python-dotenv is installed)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# ----------------------------- Tunable Parameters -----------------------------

# Test sentence: contains time information "两点半" (2:30). When the first half is truncated, recognition is often incomplete / ambiguous;
# the second half provides context and converges. TTS synthesis speed is moderate, the whole sentence is about 5~8 seconds, can be cut into 10+ chunks.
TEST_SENTENCE = "Please help me change tomorrow afternoon's meeting to 2:30, still in Conference Room 3, and don't forget to notify everyone."

CHUNK_STEP = 0.5            # Audio length increment per step (seconds), simulating streaming chunk granularity
TTS_MODEL = "tts-1"        # OpenAI speech synthesis model
TTS_VOICE = "alloy"        # Voice timbre
ASR_MODEL = "whisper-1"    # OpenAI ASR model
ASR_LANGUAGE = "zh"        # Prompt Whisper target language as Chinese

# Default comparison set (seconds) when --compare-chunks is not explicitly given
DEFAULT_CHUNK_SIZES = [0.5, 1.0, 2.0]

# Offline synthetic recognizer (SYNTHETIC) parameters: latency = BASE + SLOPE × prefix seconds.
# Modeling "non-incremental encoder re-encodes each chunk from scratch, longer accumulated audio means slower single chunk inference", numbers are for demonstration only.
MOCK_LATENCY_BASE = 0.08    # Base single-chunk inference overhead (seconds)
MOCK_LATENCY_SLOPE = 0.035  # Additional re-encoding overhead per second of accumulated audio (seconds/second)
MOCK_LATENCY_JITTER = 0.01  # Synthetic jitter amplitude (seconds), using a fixed seed for reproducibility
MOCK_SECONDS_PER_CHAR = 0.30  # Estimated whole-utterance duration (seconds/character) from sentence length in offline mode

AUDIO_DIR = Path(__file__).parent / "audio"   # Audio output directory
FULL_AUDIO = AUDIO_DIR / "sentence.wav"        # Synthesized full audio

# Single-chunk recognition result: prefix end time, single-chunk latency, cumulative latency, recognized text
Row = namedtuple("Row", ["end", "latency", "cumulative", "text"])

# ----------------------------- Utility Functions -----------------------------


def die(msg: str) -> None:
    print(f"\n[Error] {msg}", file=sys.stderr)
    sys.exit(1)


def check_prereqs(offline: bool, need_synth: bool):
    """Check prerequisites: offline mode requires no external dependencies."""
    if offline:
        return
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            die(f"Not found {tool}, please install ffmpeg first (brew install ffmpeg).")
    if not os.getenv("OPENAI_API_KEY"):
        die("OPENAI_API_KEY not set. Please copy env.example to .env and fill it in, or export directly."
            "(If you only want to verify chunking/timing logic, use --offline for offline self-check, no key needed.)")


def get_client():
    from openai import OpenAI
    # Automatically read OPENAI_API_KEY; timeout + automatic retry to avoid single network fluctuation crashing the whole process
    return OpenAI(timeout=60.0, max_retries=3)


def synth_audio(client, sentence: str) -> None:
    """Use OpenAI TTS to synthesize the full test audio, save as wav (for precise ffmpeg chunking)."""
    AUDIO_DIR.mkdir(exist_ok=True)
    print(f"[1/4] Synthesize test audio (TTS={TTS_MODEL}, voice={TTS_VOICE}）...")
    print(f"      Sentence:{sentence}")
    with client.audio.speech.with_streaming_response.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=sentence,
        response_format="wav",
    ) as resp:
        resp.stream_to_file(str(FULL_AUDIO))
    print(f"      Saved:{FULL_AUDIO}")


def audio_duration(path: Path) -> float:
    """Read audio duration (seconds) with ffprobe."""
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        text=True,
    )
    return float(out.strip())


def cut_prefix(src: Path, end_sec: float, dst: Path) -> None:
    """Use ffmpeg to cut the prefix audio [0, end_sec], simulating "all audio received so far"."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(src),
            "-t", f"{end_sec:.3f}",
            "-c", "copy" if src.suffix == dst.suffix else "pcm_s16le",
            str(dst),
        ],
        check=True,
    )


def build_endpoints(total: float, chunk_step: float):
    """Generate incremental prefix end times based on chunk granularity, last chunk = full audio."""
    if chunk_step <= 0:
        die("--chunk-step must be positive.")
    endpoints = []
    t = chunk_step
    while t < total:
        endpoints.append(round(t, 3))
        t += chunk_step
    endpoints.append(round(total, 3))
    return endpoints


# ----------------------------- Recognizer -----------------------------


class RealRecognizer:
    """Online recognizer: ffmpeg cut prefix + OpenAI Whisper recognition, measure real per-chunk latency."""

    label = "OpenAI Whisper (real recognition)"

    def __init__(self, client, full_audio: Path, asr_model: str, language: str):
        self.client = client
        self.full_audio = full_audio
        self.asr_model = asr_model
        self.language = language
        self.tmpdir = Path(tempfile.mkdtemp(prefix="stream_chunks_"))

    def _transcribe_file(self, path: Path) -> str:
        with open(path, "rb") as f:
            resp = self.client.audio.transcriptions.create(
                model=self.asr_model,
                file=f,
                language=self.language,
            )
        return resp.text.strip()

    def transcribe_prefix(self, end_sec: float, total: float, idx: int):
        """Recognize [0, end_sec] prefix, return (text, per-chunk latency seconds)."""
        chunk_path = self.tmpdir / f"chunk_{idx:03d}.wav"
        cut_prefix(self.full_audio, end_sec, chunk_path)
        t0 = time.perf_counter()
        text = self._transcribe_file(chunk_path)
        return text, time.perf_counter() - t0

    def transcribe_full(self, total: float):
        """Recognize entire segment (batch) once, return (text, latency seconds)."""
        t0 = time.perf_counter()
        text = self._transcribe_file(self.full_audio)
        return text, time.perf_counter() - t0

    def close(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class MockRecognizer:
    """Offline synthetic recognizer (SYNTHETIC, no network / no ffmpeg needed).

    - Text: reveal reference sentence characters proportionally to prefix ratio, reproducing "early truncation incomplete → convergence as audio accumulates";
      only models "truncation-style incompleteness", does not fabricate specific typos of any real model.
    - Latency: latency = BASE + SLOPE × prefix seconds (+ small jitter with fixed seed), modeling non-incremental
      encoder "longer prefix, slower per-chunk re-encoding". Numbers are synthetic, **do not represent any real model performance**.
    """

    label = "Synthetic recognizer (SYNTHETIC / offline self-check)"

    def __init__(self, sentence: str, seed: int = 42):
        self.sentence = sentence
        self._rng = random.Random(seed)

    def _reveal(self, end_sec: float, total: float) -> str:
        frac = 0.0 if total <= 0 else max(0.0, min(1.0, end_sec / total))
        n = round(frac * len(self.sentence))
        n = max(0, min(len(self.sentence), n))
        return self.sentence[:n]

    def _latency(self, end_sec: float) -> float:
        jitter = self._rng.uniform(-MOCK_LATENCY_JITTER, MOCK_LATENCY_JITTER)
        return max(0.0, MOCK_LATENCY_BASE + MOCK_LATENCY_SLOPE * end_sec + jitter)

    def transcribe_prefix(self, end_sec: float, total: float, idx: int):
        return self._reveal(end_sec, total), self._latency(end_sec)

    def transcribe_full(self, total: float):
        return self.sentence, self._latency(total)

    def close(self):
        pass


# ----------------------------- Streaming Simulation -----------------------------


def simulate_stream(recognizer, total: float, chunk_step: float, verbose: bool = True):
    """Run "incremental prefix streaming simulation" over given chunk granularity, return (rows, first_usable).

    Cumulative latency = sum of per-chunk recognition latencies (real measurement for online mode, synthetic for offline mode),
    reflecting cumulative inference cost of "edge-to-edge, re-encoding from scratch per chunk".
    """
    endpoints = build_endpoints(total, chunk_step)
    rows = []
    first_usable = None
    cumulative = 0.0
    for i, end in enumerate(endpoints, 1):
        text, latency = recognizer.transcribe_prefix(end, total, i)
        cumulative += latency
        if first_usable is None and text:
            first_usable = cumulative
        rows.append(Row(end, latency, cumulative, text))
        if verbose:
            print(f"  Chunk#{i:02d}  Audio prefix {end:>4.1f}s  Per-chunk latency {latency:5.2f}s  "
                  f"Cumulative {cumulative:6.2f}s | Recognition:{text or '(empty)'}")
    return rows, first_usable


# ----------------------------- Output -----------------------------


def run_single(recognizer, total: float, chunk_step: float, sentence: str):
    """Default mode: streaming simulation for single chunk granularity + batch comparison + trade-off summary. Return result dict."""
    print(f"[2/4] Streaming simulation: every {chunk_step}s increment, recognize current accumulated audio chunk by chunk"
          f"(Recognizer:{recognizer.label}）")
    print("      (Encoder is non-incremental, each chunk re-recognizes accumulated audio from scratch — this is the cost of \"simulated streaming\")\n")
    rows, first_usable = simulate_stream(recognizer, total, chunk_step)

    print(f"\n[3/4] Baseline: wait for full audio, then recognize entire segment once (batch)")
    full_text, full_latency = recognizer.transcribe_full(total)
    print(f"      Batch recognition latency {full_latency:.2f}s | Recognition:{full_text}")

    print(f"\n[4/4] Comparison Summary (Latency vs Accuracy Trade-off)")
    print(f"  Original sentence: {sentence}")
    print(f"  Full recognition result: {full_text}")
    print(f"  Full segment recognition requires waiting     ：{total:.2f}s (recording finished) + {full_latency:.2f}s (reasoning)")
    if first_usable is not None:
        print(f"  First available recognition for streaming  : only about {rows[0].end:.1f}s The audio produces partial results immediately."
              f"Earlier than the whole segment {total - rows[0].end:.1f}s get the first version")
    early = rows[0].text if rows else ""
    print(f"\n  The cost of premature chunking:")
    print(f"    Earliest chunking ({rows[0].end:.1f}s) Identify →  {early or '(empty/incomplete)'}")
    print(f"    Converges as audio grows →              {rows[-1].text}")
    print(f"    Compare whole segment recognition →            {full_text}")
    print(f"\n  Conclusion: Streaming chunking can give 'partial results' very early (low first-packet latency), but early chunks lack the latter half of the sentence."
          f"Context, identify possible incompleteness/errors (e.g., time, numbers truncated or misjudged); gradually as audio accumulates"
          f"Convergence. Whole-segment recognition is the most accurate, but it must wait for the entire sentence to finish + inference, resulting in the highest first-word latency. This is exactly streaming."
          f"Latency/accuracy trade-off for speech perception.")

    return {
        "mode": "single",
        "recognizer": recognizer.label,
        "sentence": sentence,
        "total_seconds": round(total, 3),
        "chunk_step": chunk_step,
        "full_text": full_text,
        "full_latency": round(full_latency, 3),
        "first_usable_latency": None if first_usable is None else round(first_usable, 3),
        "chunks": [
            {"end": r.end, "latency": round(r.latency, 3),
             "cumulative": round(r.cumulative, 3), "text": r.text}
            for r in rows
        ],
    }


def run_compare_chunks(recognizer, total: float, chunk_sizes, sentence: str):
    """Comparison mode: run streaming simulation at multiple chunk granularities and output a cross-granularity latency comparison table."""
    print(f"[Comparison] Latency comparison across different chunk granularities (recognizer:{recognizer.label}）")
    print(f"       Total duration {total:.2f}s; comparison granularity:{', '.join(f'{c}s' for c in chunk_sizes)}\n")

    full_text, full_latency = recognizer.transcribe_full(total)

    results = []
    for cs in chunk_sizes:
        rows, first_usable = simulate_stream(recognizer, total, cs, verbose=False)
        stream_total = rows[-1].cumulative if rows else 0.0
        last_latency = rows[-1].latency if rows else 0.0
        converged = bool(rows) and rows[-1].text == sentence
        results.append({
            "chunk_step": cs,
            "num_chunks": len(rows),
            "first_usable_latency": None if first_usable is None else round(first_usable, 3),
            "last_chunk_latency": round(last_latency, 3),
            "stream_total_latency": round(stream_total, 3),
            "final_text": rows[-1].text if rows else "",
            "converged_to_full": converged,
        })

    # Header
    print(f"  {'Chunk granularity':<8}{'Number of blocks':>5}{'First partial result':>14}{'Last block single block delay':>14}"
          f"{'Total streaming recognition time':>16}{'Last chunk = full segment?':>12}")
    print("  " + "-" * 70)
    for r in results:
        fu = "—" if r["first_usable_latency"] is None else f"{r['first_usable_latency']:.2f}s"
        conv = "Yes" if r["converged_to_full"] else "No"
        print(f"  {str(r['chunk_step']) + 's':<8}{r['num_chunks']:>5}{fu:>14}"
              f"{r['last_chunk_latency']:>13.2f}s{r['stream_total_latency']:>15.2f}s{conv:>12}")
    print("  " + "-" * 70)
    print(f"  {'Full segment (batch)':<8}{'—':>5}{'—':>14}{full_latency:>13.2f}s"
          f"{'(Must wait until recording finishes ' + format(total, '.2f') + 's）':>18}")
    print(f"\n  Reading table: the smaller the chunk granularity, the earlier the 'first partial result' arrives (lower first-packet latency), but more chunks and"
          f"\n       higher 'total streaming recognition time' (accumulated re-encoding from scratch per chunk) — this is the trade-off between 'low first packet' and"
          f"\n       'high cumulative computation' under non-incremental encoders. The full-segment (batch) scheme uses the least computation per inference,"
          f"\n       but must wait for the entire audio segment to finish recording ({total:.2f}s) before starting, resulting in the highest first-word latency.")

    return {
        "mode": "compare-chunks",
        "recognizer": recognizer.label,
        "sentence": sentence,
        "total_seconds": round(total, 3),
        "full_text": full_text,
        "full_latency": round(full_latency, 3),
        "per_chunk_size": results,
    }


# ----------------------------- Main Flow -----------------------------


def parse_chunk_sizes(spec: str):
    """Parse a list of chunk granularities in the form '0.5,1.0,2.0'."""
    if not spec:
        return list(DEFAULT_CHUNK_SIZES)
    try:
        sizes = [float(x) for x in spec.split(",") if x.strip()]
    except ValueError:
        die(f"The --compare-chunks parameter cannot be parsed as a numeric list:{spec!r}")
    if not sizes or any(s <= 0 for s in sizes):
        die("All chunk granularities in --compare-chunks must be positive numbers.")
    return sizes


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="demo.py",
        description="Experiment 9-3: Simulate streaming speech perception. Use TTS synthesis (or --audio to specify) a Chinese sentence,"
                    "chunk by increasing prefix length and recognize each chunk, reproducing the 'early chunks misrecognize due to missing later context, converging as audio"
                    "accumulates' latency vs. accuracy trade-off, and compare with full-segment (batch) recognition; use "
                    "--compare-chunks to compare latency across multiple chunk granularities, or use --offline for offline self-check.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: \n"
               "  python demo.py                          # Default: TTS synthesis + 0.5s granularity streaming recognition\n"
               "  python demo.py --quick                  # Increase granularity to 1.5s, Whisper calls reduced to ~1/3\n"
               "  python demo.py --audio my.wav           # Use an existing audio file, skip TTS synthesis\n"
               "  python demo.py --compare-chunks         # Latency comparison table across 0.5/1.0/2.0s\n"
               "  python demo.py --compare-chunks 0.3,0.8 # Custom chunk granularities for comparison\n"
               "  python demo.py --offline --compare-chunks  # Offline self-check (synthesize digits, no network)\n"
               "  python demo.py --output result.json     # Save results as JSON",
    )
    inp = p.add_argument_group("Input")
    inp.add_argument("--sentence", default=TEST_SENTENCE,
                     help="Test sentence (default: a sentence with time information similar to the book).")
    inp.add_argument("--audio", metavar="PATH",
                     help="Use an existing audio file as input (skip TTS synthesis); offline mode ignores this.")

    chunk = p.add_argument_group("Chunk")
    chunk.add_argument("--chunk-step", type=float, default=CHUNK_STEP,
                       help=f"Chunk granularity (seconds); smaller values produce more chunks and are slower (default {CHUNK_STEP}）。")
    chunk.add_argument("--quick", action="store_true",
                       help="Fast mode: enlarge chunk granularity to 1.5s, reducing recognition calls to about 1/3.")
    chunk.add_argument("--compare-chunks", nargs="?", const="", metavar="S1,S2,...",
                       help="Cross-reference multiple chunk granularities with delay comparison and print a comparison table; if no value is provided, use default "
                            f"{','.join(str(c) for c in DEFAULT_CHUNK_SIZES)}(seconds).")

    model = p.add_argument_group("Model / Language")
    model.add_argument("--tts-model", default=TTS_MODEL,
                       help=f"OpenAI TTS model (default {TTS_MODEL}）。")
    model.add_argument("--voice", default=TTS_VOICE,
                       help=f"TTS voice (default {TTS_VOICE}）。")
    model.add_argument("--asr-model", default=ASR_MODEL,
                       help=f"OpenAI ASR model (default {ASR_MODEL}）。")
    model.add_argument("--language", default=ASR_LANGUAGE,
                       help=f"ASR target language hint (default {ASR_LANGUAGE}）。")

    misc = p.add_argument_group("Run / Output")
    misc.add_argument("--offline", action="store_true",
                      help="Offline self-check: no network, no ffmpeg needed; uses a synthetic recognizer to drive chunking/timing logic,"
                           "the numbers are SYNTHETIC, only for verifying the workflow.")
    misc.add_argument("--duration", type=float, default=None, metavar="SEC",
                      help="Total duration of the segment in offline mode (seconds); if omitted, estimated from sentence length.")
    misc.add_argument("--output", metavar="PATH",
                      help="Save results (per-chunk table / comparison table) to a JSON file.")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # argparse overrides module-level defaults (only parameter tuning, does not change core workflow)
    global TTS_MODEL, TTS_VOICE, ASR_MODEL, ASR_LANGUAGE
    TTS_MODEL, TTS_VOICE = args.tts_model, args.voice
    ASR_MODEL, ASR_LANGUAGE = args.asr_model, args.language
    sentence = args.sentence
    chunk_step = 1.5 if args.quick else args.chunk_step

    check_prereqs(args.offline, need_synth=not args.audio)

    # ---- Prepare recognizer and total segment duration ----
    if args.offline:
        total = args.duration if args.duration else max(3.0, len(sentence) * MOCK_SECONDS_PER_CHAR)
        print("[Offline self-check] Using synthetic recognizer (SYNTHETIC): the following text is revealed by prefix ratio, delays are synthetic values,")
        print("           only for verifying chunking / timing / comparison logic, not representing any real model performance.")
        print(f"           Sentences:{sentence}")
        print(f"           Estimated total duration:{total:.2f}s\n")
        recognizer = MockRecognizer(sentence)
    else:
        client = get_client()
        if args.audio:
            src = Path(args.audio)
            if not src.exists():
                die(f"--audio specified file does not exist:{src}")
            AUDIO_DIR.mkdir(exist_ok=True)
            print(f"[1/4] Using existing audio:{src}")
        else:
            synth_audio(client, sentence)
            src = FULL_AUDIO
        total = audio_duration(src)
        print(f"      Total duration:{total:.2f} seconds\n")
        recognizer = RealRecognizer(client, src, ASR_MODEL, ASR_LANGUAGE)

    # ---- Run comparison / single granularity ----
    try:
        if args.compare_chunks is not None:
            chunk_sizes = parse_chunk_sizes(args.compare_chunks)
            result = run_compare_chunks(recognizer, total, chunk_sizes, sentence)
        else:
            result = run_single(recognizer, total, chunk_step, sentence)
    finally:
        recognizer.close()

    # ---- Optional: persist results ----
    if args.output:
        Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[Output] Results written to:{args.output}")


if __name__ == "__main__":
    main()
