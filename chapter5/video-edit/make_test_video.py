"""
Procedurally generate a test video containing "multiple distinctly different scenes" (no asset files required).

Each scene = a solid-color background + a large motion title (scene name in English) + a timecode watermark.
The title allows a Vision LLM to accurately determine "which scene this is" based solely on the frame, thus verifying two-step localization.
When switching to a real video: point SOURCE_VIDEO in demo.py to your own mp4 (see README).
"""
import os

from ffmpeg_utils import find_font, run

# Each scene: (name, background color, start second, duration seconds). Intentionally make each segment > 10s,
# so that the coarse-grained sampling of "one frame every 10s" is guaranteed to hit every scene.
SCENES = [
    ("HIKING",  "0x1E6B3A", 0,  15),   # Forest Green
    ("SURFING", "0x1565C0", 15, 15),   # Ocean Blue
    ("SKIING",  "0xE0E0E0", 30, 12),   # Snow White
    ("CYCLING", "0xE65100", 42, 12),   # Sunset Orange
]
TOTAL = SCENES[-1][2] + SCENES[-1][3]  # 54s
W, H, FPS = 1280, 720, 30


def _drawtext(text, size, y_expr, color="white", box=False):
    font = find_font()
    parts = [f"text='{text}'", f"fontsize={size}", f"fontcolor={color}",
             "x=(w-text_w)/2", f"y={y_expr}"]
    if font:
        parts.insert(0, f"fontfile={font}")
    if box:
        parts += ["box=1", "boxcolor=black@0.4", "boxborderw=20"]
    return "drawtext=" + ":".join(parts)


def make(out_path: str) -> str:
    """Generate the test video and return the path. Idempotent: overwrite each time, ensuring a clean starting state."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    clip_paths = []
    tmp_dir = os.path.dirname(out_path)

    for i, (name, color, start, dur) in enumerate(SCENES):
        clip = os.path.join(tmp_dir, f"_scene_{i}.mp4")
        # Make the title slowly drift up and down to create a realistic "motion picture", avoiding purely static frames.
        title = _drawtext(name, 140, "(h-text_h)/2 + 60*sin(t)", box=True)
        # Top-left timecode: t is the relative time within the segment; add start to get the global time.
        # In the drawtext expression, colons must be escaped as \: otherwise they are treated as option separators.
        clock = _drawtext(rf"t=%{{eif\:t+{start}\:d}}s", 48,
                          "40", color="yellow")
        vf = f"{title},{clock}"
        run(
            ["ffmpeg", "-y",
             "-f", "lavfi", "-i", f"color=c={color}:s={W}x{H}:d={dur}:r={FPS}",
             "-f", "lavfi", "-i", f"sine=frequency={220 + i * 110}:duration={dur}",
             "-vf", vf, "-pix_fmt", "yuv420p",
             "-c:v", "libx264", "-c:a", "aac", "-shortest", clip],
            desc=f"Generate scene {name}",
        )
        clip_paths.append(clip)

    # Use the concat demuxer to seamlessly concatenate into a complete raw source.
    list_file = os.path.join(tmp_dir, "_concat_list.txt")
    with open(list_file, "w") as f:
        for c in clip_paths:
            f.write(f"file '{os.path.abspath(c)}'\n")
    run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c", "copy", out_path],
        desc="Concatenate test video",
    )

    # Clean up intermediate segments.
    for c in clip_paths:
        os.remove(c)
    os.remove(list_file)
    return out_path


# For demo/README reference: scene ground truth table, used to verify localization error.
GROUND_TRUTH = {name.lower(): (start, start + dur) for name, _, start, dur in SCENES}
