"""
ffmpeg / ffprobe thin wrapper: all external process calls are centralized here, with unified error checking.

Design highlights:
  - run() catches non-zero exit codes and throws a clear exception with stderr (instead of leaking traceback);
  - Provides probe_duration / probe_streams for Reviewer and validation steps to read clip info;
  - extract_frame captures a frame at a given time as a PNG (scaled to 512 width to save Vision tokens).
"""
import json
import os
import shutil
import subprocess

# macOS built-in fonts; change here when switching platforms (Linux common DejaVuSans.ttf).
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
]


def find_font() -> str:
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return ""  # drawtext falls back to default font


def ensure_ffmpeg():
    """Pre-start self-check: whether ffmpeg / ffprobe are available, with clear Chinese error messages."""
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"Not found {tool}, this project uses ffmpeg for actual editing.\n"
                f"  macOS: brew install ffmpeg\n"
                f"  Ubuntu: sudo apt install ffmpeg"
            )


def run(cmd, desc="ffmpeg command"):
    """Execute command, throw exception with tail of stderr on failure."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise RuntimeError(f"{desc} Execution failed (exit={proc.returncode}）：\n{tail}")
    return proc


def probe_duration(path: str) -> float:
    """Return video duration (seconds)."""
    proc = run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        desc="ffprobe read duration",
    )
    return float(proc.stdout.strip())


def probe_streams(path: str) -> dict:
    """Return ffprobe JSON (format + streams) for printing clip info."""
    proc = run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams",
         "-of", "json", path],
        desc="ffprobe read stream info",
    )
    return json.loads(proc.stdout)


def format_probe(path: str) -> str:
    """Format clip info into human-readable lines (for validation output)."""
    info = probe_streams(path)
    fmt = info.get("format", {})
    lines = [
        f"  File: {os.path.basename(path)}",
        f"  Duration: {float(fmt.get('duration', 0)):.2f}s",
        f"  Container: {fmt.get('format_name', '?')}",
        f"  Size: {int(fmt.get('size', 0)) / 1024:.1f} KB",
    ]
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            lines.append(
                f"  Video stream: {s.get('codec_name')} {s.get('width')}x{s.get('height')} "
                f"@ {s.get('r_frame_rate')} fps"
            )
        elif s.get("codec_type") == "audio":
            lines.append(
                f"  Audio stream: {s.get('codec_name')} {s.get('sample_rate')}Hz "
                f"{s.get('channels')}ch"
            )
    return "\n".join(lines)


def extract_frame(video: str, t: float, out_png: str, width: int = 512):
    """Extract a frame at t seconds, scaled to width wide, saved as PNG."""
    run(
        ["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", video,
         "-frames:v", "1", "-vf", f"scale={width}:-1", out_png],
        desc=f"Extract frame t={t:.1f}s",
    )
    return out_png
