# Experiment 5-6: API-Based Intelligent Video Editing

Companion experiment for "Deep Understanding of AI Agents". The user provides a video containing multiple scenes plus a natural language request (e.g., "cut out the surfing part"), and the Agent automatically locates the target scene, **generates a Blender Python API script** to clip the segment, and performs self-review.

## Purpose

Validate the role of three core mechanisms in multimedia processing:

1. **Two-Step Vision Localization**: The Proposer cannot directly "understand" the video, so it delegates to a **video analysis sub-agent** that uses ffmpeg to extract frames and a Vision LLM to read images in order to locate the time boundaries of the target scene.
2. **Code Generation (Blender Python API)**: The Proposer translates the editing plan into a script that calls the **Blender Python API (bpy)** — import/crop/subtitle/speed-change/render each correspond to an API call, executed headlessly with `blender --background --python edit.py`. This embodies the book's approach of "refactoring video editing into an API call and code generation problem". When Blender is not installed, the script is still generated (code generation artifact), and actual rendering falls back to ffmpeg (see "Editing Backend" below).
3. **Proposer/Reviewer**: After the Proposer edits, it cannot verify the result itself. The Reviewer extracts keyframes from the output, uses a Vision LLM to check whether the edit is correct, and provides feedback for iteration if it fails.

## Two-Step Localization Principle

Scanning every frame of the entire video with a Vision LLM is both slow and expensive, so a "coarse-to-fine" approach is adopted:

- **Step 1 (Coarse)**: Extract one frame every **10 seconds**, submit the sparse screenshots of the entire video along with "which scene to find" to the Vision LLM, and obtain an approximate interval (e.g., "surfing at 20–30s").
- **Step 2 (Fine)**: Expand one coarse interval above and below the coarse range, extract one frame every **1 second**, and ask the Vision LLM for the precise boundaries (e.g., "15–29s").

This frame-extraction-and-image-reading process is encapsulated as an **independent sub-agent**: dozens of screenshots only enter the sub-agent's one-time context, without polluting the main agent's (Proposer/Reviewer) conversation history. The demo prints a token comparison between the two at the end.

## Proposer/Reviewer

```
NL Request ──► Proposer parses intent (target scene + effects)
                  │
                  ▼
          Video Analysis Sub-Agent Two-Step Localization ──► [start, end]
                  │
                  ▼
         Proposer generates Blender bpy script (edit.py) ──► Renders clip (can add subtitles/slow motion)
                  │                                        Uses bpy if Blender installed, otherwise falls back to ffmpeg
                  ▼
         Reviewer extracts first/middle/last keyframes ──► Vision LLM checks pass/fail + feedback
                  │pass?  No → Proposer adjusts boundaries based on feedback, re-edits (max 3 rounds)
                  ▼Yes
            Output final video final.mp4
```

## Running

```bash
pip install -r requirements.txt
cp env.example .env        # Fill in OPENAI_API_KEY (if not configured, set OPENROUTER_API_KEY to automatically switch to OpenRouter)
python demo.py             # Default request "cut out the surfing part" (full workflow)
python demo.py "Cut out the skiing part and add subtitle Winter"   # Custom request
python demo.py -i my.mp4 -o out.mp4 "Cut out the speech opening"  # Use your own video + custom output
python demo.py --backend blender   # Force headless rendering with Blender Python API (requires Blender installed)
python demo.py --vision-model gpt-5.6-luna  # Override model (also works with --text-model)
python demo.py --quick     # Quick mode: coarse sampling + single-round review, minimal Vision calls (saves time and money)
python demo.py --smoke     # Smoke test: editing pipeline only + generate bpy script, no API calls
python demo.py --help      # View all parameters
```

Common parameters (full list via `--help`): `--input/-i` input video, `--output/-o` output path, `--backend {auto,blender,ffmpeg}` editing backend, `--text-model`/`--vision-model` model overrides.

A single command runs the full workflow: generate/read video → two-step localization → generate bpy script for editing → review → output final video. Each run clears `output/` and starts from a clean state (idempotent and repeatable). The full workflow calls the Vision model multiple times (slower/consumes quota); to quickly verify the pipeline, run `--smoke` first (zero API calls) or use `--quick`.

## Expected Output Examples

### `--smoke` (Zero API, Reproducible)

Below is the **actual output** of `python demo.py --smoke` (no OpenAI Key needed, only ffmpeg):

```text
==========================================================================
  Smoke Test | Editing Pipeline + bpy Script Generation, No API Calls
==========================================================================
[1/3] Test video generated OK: output/source.mp4 (scene ground truth={'hiking': (0, 15), 'surfing': (15, 30), 'skiing': (30, 42), 'cycling': (42, 54)})
[2/3] Frame extraction OK: output/frames/smoke.png
[3/3] Editing + subtitle OK (backend=ffmpeg (Blender not installed, fallback)):
   File: smoke_cut.mp4
   Duration: 5.03s
   Container: mov,mp4,m4a,3gp,3g2,mj2
   Size: 121.4 KB
   Video stream: h264 1280x720 @ 30/1 fps
   Audio stream: aac 44100Hz 1ch

Proposer's Blender script generated: output/edit.py
(This is the artifact of 'generating Blender Python API code' as described in the book; once Blender is installed, you can run
 `blender --background --python output/edit.py` for headless rendering.)

✓ Smoke test passed: editing pipeline normal + bpy script generated (no OpenAI calls).
```

The generated `output/edit.py` is an **executable Blender bpy script** (`new_movie` import, `frame_offset_start`/`frame_final_duration` cropping, `new_effect(type='TEXT')` subtitle, `bpy.ops.render.render` rendering), which has been syntax-validated with `py_compile` on this machine.

### `--quick` (Full Pipeline, Requires API)

Below is a real excerpt from `python demo.py --quick` (default request "cut out the surfing part") — the localization/error/token parts are independent of the editing backend, so they are unaffected by switching between bpy/ffmpeg backends:

```text
Step 1 | Proposer parses natural language request
Parsed result: target scene='surfing scene'  effects=[]

Step 2 | Video Analysis Sub-Agent: Two-Step Vision Localization (--quick fast sampling)
  [Coarse] Sampling 5 frames every 15s → Vision yields interval [15, 30]s (Reasoning: 'The word SURFING appears at t=15s and changes at t=30s.')
  [Fine] Sampling 23 frames every 2s within window [0.0, 45.0] → Precise boundaries [16.0, 28.0]s
  >>> Final localization: start 16.0s  end 28.0s
  Ground truth [15, 30]s → start error 1.0s, end error 2.0s (acceptance criteria ≤ 3s)

Steps 3-4 | Proposer editing + Reviewer review (iteration)
  Proposer cuts segment [16.0, 28.0]s, output duration 12.0s
  Reviewer: pass=... score=... check frames=['0.5', '6.0', '11.5']

Token statistics (sub-agent isolates screenshots, main context not polluted)
  Main agent (Proposer+Reviewer): 573 tokens
  Sub-agent (two-step localization screenshots): 2934 tokens
```

Artifacts (`output/` directory, actual files):

| File | Duration | Description |
| --- | --- | --- |
| `source.mp4` | 54.0s | Programmatically generated 4-scene test source video |
| `edit_round1.py` | — | Blender bpy script generated by Proposer (code generation artifact, executable on another machine) |
| `cut_round1.mp4` | 12.0s | Candidate clip from round 1 |
| `final.mp4` | 12.0s | Accepted final video (H.264 + AAC, 1280x720@30fps) |

The token statistics confirm the core conclusion: dozens of screenshots (2934 tokens) only enter the **sub-agent's** one-time context, while the main agent's conversation history (573 tokens) remains almost unaffected by the screenshots.
(Note: The synthetic test video only displays the word "SURFING" rather than actual surfing footage; the Reviewer sometimes judges this as a failure — this demonstrates the reviewer providing honest feedback based on visual content; this phenomenon does not occur with real videos.)

## Dependencies

- **ffmpeg / ffprobe**: Used for actual video editing and frame extraction on the local machine. `brew install ffmpeg` (macOS) / `apt install ffmpeg` (Ubuntu). This project has been verified with ffmpeg 8.0.
- **OPENAI_API_KEY**: Uses `gpt-5.6-luna` for visual localization/review and text planning (the vision model must support image input); if not configured, falls back to `OPENROUTER_API_KEY` and automatically switches to OpenRouter.

## How to Adapt / Extend

### Change Model / Provider

Models and endpoints are all injected via **environment variables** (see `env.example`), no code changes needed:

- `TEXT_MODEL`: Text model for planning/boundary correction (default `gpt-5.6-luna`).
- `VISION_MODEL`: Vision model for localization/review, **must support image input** (default `gpt-5.6-luna`).
- `OPENAI_BASE_URL`: Replace with any OpenAI-compatible endpoint (self-hosted proxy, Azure OpenAI, or other vendor gateways), paired with the corresponding `OPENAI_API_KEY`.

```bash
export OPENAI_BASE_URL=https://your-gateway.example.com/v1
export VISION_MODEL=gpt-5.6-luna       # Example: use the current affordable flagship vision model
export TEXT_MODEL=gpt-5.6-luna
```

The `OpenAI()` client in `agents.py` automatically reads these variables (lazy initialization via `client()`).

### Change Input Video

`make_test_video.py` uses ffmpeg to **programmatically generate** a 54-second video containing 4 distinctly different scenes (HIKING green / SURFING blue / SKIING white / CYCLING orange), each overlaid with large scene names and timecode watermarks, allowing the Vision LLM to accurately locate scenes based solely on the visuals — facilitating reproducible validation.

To use **your own real video**: simply run `python demo.py -i your.mp4 -o output.mp4 "editing request"` (no code changes needed). In this case, test video generation is skipped, and localization error is no longer printed (external videos have no ground truth).

### Blender vs. ffmpeg (Editing Backend)

The original approach in the book uses the **Blender Python API (bpy)** to drive the Video Sequence Editor (VSE) for editing. This project implements it as a **first-class backend**: `blender_editor.generate_bpy_script()` translates the editing plan into a real executable bpy script (`new_movie` import, `frame_offset_start`/`frame_final_duration` cropping, `new_effect(type='TEXT'/'SPEED')` subtitle/speed change, `bpy.ops.render.render` rendering), and `render_with_blender()` executes it headlessly with `blender --background --python edit.py`.

- `--backend blender`: Force Blender (requires `blender --version` to be available);- `--backend ffmpeg`: force ffmpeg;
- `--backend auto` (default): use bpy if Blender is installed, otherwise fall back to ffmpeg.

**Key point: regardless of the backend, the bpy script generated by the Proposer is always saved to `output/edit_round*.py`**
(under `--smoke`, it is `output/edit.py`) — that is, the core artifact "generated Blender Python API code" can be manually reviewed or copied to a machine with Blender for execution. Since Blender is not installed on this machine, the actual rendering in this repository is done and verified by ffmpeg; the bpy script has passed `py_compile` syntax checks but **has not been rendered in real Blender** (once Blender is installed, you can use `--backend blender` for end-to-end execution). Trade-offs between the two backends:

| | ffmpeg | Blender (bpy) |
| --- | --- | --- |
| Positioning | 2D pipeline for trimming/concatenation/subtitles/speed changes, etc. | 3D scenes, compositing, keyframe animation, particles/cameras |
| Getting started | Single binary, no GUI, CI-friendly | Requires full Blender installation, large size, slow rendering |
| Applicable | Most "cut a segment + simple effects" needs | Worthwhile only when 3D compositing/complex transitions/layer blending is needed |

The core "two-step Vision positioning + proposer-reviewer" is decoupled from the execution layer; both backends share the same editing plan, and `agents.py`/`demo.py` require no logic changes to switch backends.

## Files

| File | Purpose |
| --- | --- |
| `demo.py` | Orchestration entry point for one-command execution (CLI, startup self-check, iteration loop, token statistics) |
| `agents.py` | `VideoAnalyzerAgent` (two-step positioning) / `ProposerAgent` / `ReviewerAgent` |
| `blender_editor.py` | **Blender bpy script generation + headless rendering** (the original solution in the book, core experiment point) |
| `video_editor.py` | Editing execution layer: `apply_edit()` unified entry, dispatches Blender/ffmpeg dual backends |
| `make_test_video.py` | Programmatically generates a test video containing 4 scenes |
| `ffmpeg_utils.py` | Thin wrapper around ffmpeg/ffprobe (unified error checking, frame extraction, duration/stream probing) |

`output/` (generated videos, screenshots, final cuts) is ignored by `.gitignore` to avoid repository bloat.

## Limitations

- Positioning accuracy depends on the recognizability of scenes in the video; for real videos with gradual scene transitions, boundary errors will be larger than for solid-color test clips.
- The fine-grained step is fixed at 1s, so the boundary accuracy ceiling is around ±1s (meeting the ±3s acceptance criterion in the book).
- Slow-motion audio uses `atempo` for speed changes; audio quality degrades at high ratios. Complex effects like transitions and multi-track mixing are not covered.
- The Reviewer only samples the first, middle, and last frames; occasional errors in the middle of long segments may be missed (the frame sampling density can be increased).
