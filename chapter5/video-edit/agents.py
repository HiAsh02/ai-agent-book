"""
Three agents in Experiment 5-6:

  VideoAnalyzerAgent —— Video analysis sub-agent, uses "two-step Vision localization" to find target scene boundaries.
  ProposerAgent      —— Parses natural language requirements into editing plans, calls sub-agents to locate and execute edits.
  ReviewerAgent      —— Extracts keyframes from the final video, uses Vision to check if edits are correct, and provides structured feedback.

The significance of encapsulating video analysis as an independent sub-agent: a large number of screenshots only enter the sub-agent's one-time context,
without polluting the main agent's (Proposer/Reviewer) conversation history — see the token statistics printed by demo.py.
"""
import base64
import json
import os
import re

from openai import OpenAI

from ffmpeg_utils import extract_frame, probe_duration

TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-5.6-luna")
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-5.6-luna")  #  Must support image input

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_client = None


def map_model_to_openrouter(model: str) -> str:
    """Map the direct model name to the id on OpenRouter (non-mappable ids fall back to the current cheap flagship)."""
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


def _temp_for(model):
    """Reasoning models (gpt-5 / o series, etc.) do not accept temperature=0."""
    return (1 if any(k in (model or "").lower()
                     for k in ("gpt-5", "o1", "o3", "o4", "thinking", "reasoner", "kimi-k3"))
            else 0)


def client() -> OpenAI:
    """Construct (and cache) an OpenAI client with a generic OpenRouter fallback.

    - With OPENAI_API_KEY: direct connection; but when the default model is gpt-5.x (direct connection requires organizational real-name authentication) and OPENROUTER_API_KEY is set, prefer OpenRouter.
    - Without OPENAI_API_KEY but with OPENROUTER_API_KEY: switch to OpenRouter (model name auto-mapped).
    """
    global _client, TEXT_MODEL, VISION_MODEL
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        orkey = os.getenv("OPENROUTER_API_KEY")
        prefer_or = bool(orkey) and (
            (TEXT_MODEL or "").lower().startswith("gpt-5") or (VISION_MODEL or "").lower().startswith("gpt-5")
        )
        if prefer_or or (not api_key and orkey):
            api_key, base_url = orkey, OPENROUTER_BASE_URL
            TEXT_MODEL = map_model_to_openrouter(TEXT_MODEL)
            VISION_MODEL = map_model_to_openrouter(VISION_MODEL)
        kw = {}
        if api_key:
            kw["api_key"] = api_key
        if base_url:
            kw["base_url"] = base_url
        _client = OpenAI(**kw)
    return _client


def _img_part(path: str) -> dict:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return {"type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "low"}}


def _extract_json(text: str) -> dict:
    """Robustly extract the first JSON object from the LLM response."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"Failed to parse JSON from reply: {text[:200]}")
    return json.loads(m.group(0))


class TokenMeter:
    """Accumulated tokens, used to compare the main context savings brought by 'sub-agent isolation screenshot'."""

    def __init__(self):
        self.prompt = 0
        self.completion = 0

    def add(self, resp):
        u = getattr(resp, "usage", None)
        if u:
            self.prompt += u.prompt_tokens
            self.completion += u.completion_tokens

    def total(self):
        return self.prompt + self.completion


# --------------------------------------------------------------------------- #
# Video Analysis Sub-Agent: Two-Step Vision Localization
# --------------------------------------------------------------------------- #
class VideoAnalyzerAgent:
    def __init__(self, meter: TokenMeter = None):
        self.meter = meter or TokenMeter()

    def _vision_locate(self, video, timestamps, question, frame_dir):
        """Extract frames at the given timestamps and pass them along with the question to the Vision LLM, returning {start,end}."""
        content = [{
            "type": "text",
            "text": (
                f"Below are screenshots of the same video at different time points (each image is preceded by the time of that frame in seconds).\n"
                f"Target question: {question}\n"
                f"Please determine the time interval during which the 'target scene' appears in the video. Judge solely based on the visual content.\n"
                f"Strictly output JSON: {{\"start\": <start second>, \"end\": <end second>, "
                f"\"reason\": \"<brief basis>\"}}. If the target scene is not visible in any screenshot,"
                f"Set start=end=-1."
            ),
        }]
        for t in timestamps:
            png = os.path.join(frame_dir, f"f_{t:.1f}.png")
            extract_frame(video, t, png)
            content.append({"type": "text", "text": f"[时间 t={t:.1f}s]"})
            content.append(_img_part(png))

        resp = client().chat.completions.create(
            model=VISION_MODEL,
            messages=[{"role": "user", "content": content}],
            temperature=_temp_for(VISION_MODEL),
            max_tokens=300,
        )
        self.meter.add(resp)
        data = _extract_json(resp.choices[0].message.content)
        return float(data["start"]), float(data["end"]), data.get("reason", "")

    def locate(self, video, question, coarse_interval=10.0, fine_interval=1.0,
               frame_dir="output/frames"):
        """
        Two-step localization:
          Step 1 (coarse): one frame every coarse_interval seconds, Vision gives approximate scene range.
          Step 2 (fine): expand one coarse interval above and below the coarse range, one frame every fine_interval seconds,
                         Vision precisely locates boundaries.
        Returns (start, end, trace).
        """
        os.makedirs(frame_dir, exist_ok=True)
        duration = probe_duration(video)
        trace = {}

        # ---- Step 1: Coarse-grained ----
        coarse_ts = [t for t in _frange(0, duration, coarse_interval)]
        cs, ce, creason = self._vision_locate(video, coarse_ts, question, frame_dir)
        trace["coarse"] = {"timestamps": coarse_ts, "start": cs, "end": ce,
                           "reason": creason}

        if cs < 0 or ce < 0:
            # Fallback: Coarse localization failed—degrade to full-video fine scan (step size enlarged to control cost).
            trace["coarse_fallback"] = True
            step = max(fine_interval, duration / 20.0)
            scan_ts = list(_frange(0, duration, step))
            cs, ce, creason = self._vision_locate(video, scan_ts, question, frame_dir)
            trace["coarse"]["fallback_scan"] = {"start": cs, "end": ce}
            if cs < 0:
                raise RuntimeError(
                    "Vision localization failed: no scene matching '{}' found in the entire video.\n"
                    "Please check whether the requirement description matches the video content, or replace the video.".format(question)
                )

        # ---- Step 2: Fine-grained (expand one coarse interval outside the coarse range) ----
        lo = max(0.0, cs - coarse_interval)
        hi = min(duration, ce + coarse_interval)
        fine_ts = list(_frange(lo, hi, fine_interval))
        fs, fe, freason = self._vision_locate(video, fine_ts, question, frame_dir)
        trace["fine"] = {"window": [lo, hi], "timestamps_count": len(fine_ts),
                         "start": fs, "end": fe, "reason": freason}

        if fs < 0 or fe < 0 or fe <= fs:
            #  Fallback: Fine localization failed — use coarse localization result to ensure the process can continue.
            trace["fine_fallback"] = True
            fs, fe = cs, ce

        #  Converge to within the video range.
        fs = max(0.0, fs)
        fe = min(duration, fe)
        return fs, fe, trace


def _frange(start, stop, step):
    """Floating-point range (inclusive of start and near-end sample points)."""
    out = []
    t = start
    while t < stop - 1e-6:
        out.append(round(t, 3))
        t += step
    # Add a sampling point near the end to ensure the final scene is covered.
    last = round(max(start, stop - 0.5), 3)
    if not out or abs(out[-1] - last) > step / 2:
        out.append(last)
    return out


# --------------------------------------------------------------------------- #
# Proposer Agent
# --------------------------------------------------------------------------- #
class ProposerAgent:
    def __init__(self, meter: TokenMeter = None):
        self.meter = meter or TokenMeter()

    def parse_request(self, nl_request: str) -> dict:
        """Parse natural language requirements into structured intents: target scene description + effect list."""
        resp = client().chat.completions.create(
            model=TEXT_MODEL,
            temperature=_temp_for(TEXT_MODEL),
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": (
                    "You are a video editing planner. Parse the user's Chinese editing requirements into JSON.\n"
                    "Fields:\n"
                    "  target_query: a one-sentence description for visual localization (English is better for matching on-screen text),"
                    "specifying which scene to cut;\n"
                    "  effects: array of effects, each element like "
                    "{\"type\":\"subtitle\",\"text\":\"...\"} or "
                    "{\"type\":\"slowmo\",\"factor\":2.0}, if no effects, use [].\n"
                    f"User requirement:{nl_request}\n"
                    "Output only JSON."
                ),
            }],
        )
        self.meter.add(resp)
        return _extract_json(resp.choices[0].message.content)

    def revise_bounds(self, start, end, feedback, duration):
        """Fine-tune the boundary based on Reviewer feedback (conservatively expand/contract)."""
        resp = client().chat.completions.create(
            model=TEXT_MODEL,
            temperature=_temp_for(TEXT_MODEL),
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"Current clip interval start={start:.1f}s end={end:.1f}s, total video duration {duration:.1f}s。\n"
                    f"Review feedback:{feedback}\n"
                    "Please provide the corrected interval, output JSON {\"start\":..,\"end\":..}."
                    "If feedback indicates irrelevant segments are included, contract; if missing content, expand, by 1~5 seconds."
                ),
            }],
        )
        self.meter.add(resp)
        d = _extract_json(resp.choices[0].message.content)
        return max(0.0, float(d["start"])), min(duration, float(d["end"]))


# --------------------------------------------------------------------------- #
# Reviewer Agent
# --------------------------------------------------------------------------- #
class ReviewerAgent:
    def __init__(self, meter: TokenMeter = None):
        self.meter = meter or TokenMeter()

    def review(self, clip_path, target_query, frame_dir="output/review_frames"):
        """
        Extract the first/middle/last keyframes of the final clip, and use Vision to check:
          - Whether the target scene is fully included (no omissions);
          - Whether any irrelevant scenes are included (no extras).
        Return a structured result {pass, score, feedback, frames_checked}.
        """
        os.makedirs(frame_dir, exist_ok=True)
        dur = probe_duration(clip_path)
        #  Take first/middle/last, and slightly contract at the start and end to avoid black frames.
        keyts = [min(0.5, dur * 0.1), dur / 2.0, max(0.0, dur - 0.5)]

        content = [{
            "type": "text",
            "text": (
                f"These are several keyframes (first/middle/last) of the final clip. The editing target is:{target_query}。\n"
                "Check: (1) whether the final clip fully presents the target scene; (2) whether it includes other scenes that should not appear.\n"
                "Strictly output JSON: {\"pass\": true/false, \"score\": 0-10, "
                "\"feedback\": \"<issues found or confirmed correct>\"}."
            ),
        }]
        for t in keyts:
            png = os.path.join(frame_dir, f"r_{t:.1f}.png")
            extract_frame(clip_path, t, png)
            content.append({"type": "text", "text": f"[In final clip t={t:.1f}s]"})
            content.append(_img_part(png))

        resp = client().chat.completions.create(
            model=VISION_MODEL,
            temperature=_temp_for(VISION_MODEL),
            max_tokens=300,
            messages=[{"role": "user", "content": content}],
        )
        self.meter.add(resp)
        data = _extract_json(resp.choices[0].message.content)
        data["frames_checked"] = keyts
        return data
