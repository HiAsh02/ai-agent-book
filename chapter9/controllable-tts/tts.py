"""
TTS Synthesis Layer (OpenAI TTS)
========================

Provider adaptation: The book's experiments use Fish Audio's control markers + voice cloning reference library.
Fish Audio has no available key, so OpenAI TTS is used here to demonstrate the same idea:

  - Preferred: gpt-4o-mini-tts: supports `instructions` parameter, can use a style prompt to precisely
    control emotion / speed / tone, closest to the semantics of "control markers -> stylized speech";
  - If that model is unavailable, fallback to tts-1: does not support instructions, uses multiple voices +
    `speed` parameter + text-level pauses as approximation.

After a control marker text is parsed into multiple segments:
  - speech segments: each synthesized with corresponding reference voice (same base voice + different instructions);
  - silence segments: real silence generated with ffmpeg;
Finally, all segments are concatenated in order into a single mp3 using ffmpeg (consistent timbre, varying prosody/emotion/pauses).
"""

import os
import subprocess
import tempfile

from openai import OpenAI

from voice_library import VOICE_LIBRARY, BASE_VOICE, build_instructions, speed_factor, profile_key

#  Override with TTS_MODEL environment variable; default prefers gpt-4o-mini-tts
PREFERRED_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
FALLBACK_MODEL = "tts-1"

_client = None
_active_model = None  #  Actual model determined after first call


def _get_client():
    global _client
    if _client is None:
        #  timeout + auto retry: single network/SSL glitch won't crash the entire synthesis
        _client = OpenAI(timeout=60.0, max_retries=3)
    return _client


def _synth_call(model, text, voice, instructions, speed, out_path):
    """Actual call to OpenAI TTS. gpt-4o-mini-tts uses instructions; tts-1 uses speed."""
    client = _get_client()
    kwargs = dict(model=model, voice=voice, input=text, response_format="mp3")
    if model == "tts-1":
        #  tts-1 does not support instructions, approximate speed control with speed parameter
        kwargs["speed"] = max(0.25, min(4.0, speed))
    else:
        kwargs["instructions"] = instructions
    with client.audio.speech.with_streaming_response.create(**kwargs) as resp:
        resp.stream_to_file(out_path)


def synth_speech(text, emotion, speed, style, emphasis, out_path):
    """
    Synthesize a speech segment, return the actual (model, voice, instructions/speed) for logging.
    Timbre fixed = BASE_VOICE, ensuring consistent timbre across the segment (simulating Fish Audio's timbre consistency).
    """
    global _active_model
    key = profile_key(emotion, speed, style)
    profile = VOICE_LIBRARY.get(key)
    voice = profile["base_voice"] if profile else BASE_VOICE
    instructions = build_instructions(emotion, speed, style, emphasis)
    spd = speed_factor(speed)

    model = _active_model or PREFERRED_MODEL
    try:
        _synth_call(model, text, voice, instructions, spd, out_path)
        _active_model = model
    except Exception as e:
        #  Fallback to tts-1 when preferred model is unavailable
        if model != FALLBACK_MODEL:
            print(f"  [warn] Model {model}  Call failed({repr(e)[:80]}), falling back to {FALLBACK_MODEL}")
            _synth_call(FALLBACK_MODEL, text, voice, instructions, spd, out_path)
            _active_model = FALLBACK_MODEL
            model = FALLBACK_MODEL
        else:
            raise
    return {"model": model, "voice": voice, "profile": key,
            "instructions": instructions, "speed_factor": spd}


def make_silence(ms, out_path):
    """Generate a real silence mp3 with ffmpeg (counts toward total duration, verifiable by ffprobe)."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", f"{ms/1000:.3f}", "-q:a", "9", out_path],
        check=True, capture_output=True,
    )


def concat_mp3(part_paths, out_path):
    """Concatenate multiple mp3 segments in order using ffmpeg concat demuxer (uniform re-encoding to avoid timebase issues)."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in part_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
        list_path = f.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
             "-ar", "24000", "-ac", "1", "-b:a", "64k", out_path],
            check=True, capture_output=True,
        )
    finally:
        os.unlink(list_path)


def synthesize_segments(segments, out_path, workdir):
    """
    Combine the segment list from parse() into a complete mp3.
    Return synthesis info list for each segment (for logging verification).
    """
    os.makedirs(workdir, exist_ok=True)
    parts, info = [], []
    for i, seg in enumerate(segments):
        part_path = os.path.join(workdir, f"seg_{i:02d}.mp3")
        if seg["type"] == "silence":
            make_silence(seg["ms"], part_path)
            info.append({"type": "silence", "ms": seg["ms"]})
        else:
            meta = synth_speech(seg["text"], seg["emotion"], seg["speed"],
                                seg["style"], seg.get("emphasis", False), part_path)
            meta["type"] = "speech"
            meta["text"] = seg["text"]
            info.append(meta)
        parts.append(part_path)

    if len(parts) == 1:
        os.replace(parts[0], out_path)
    else:
        concat_mp3(parts, out_path)
    return info
