"""Core steps of the TTS quality evaluation pipeline.

An evaluation chain:
  Synthesis (OpenAI TTS) -> Duration detection (ffprobe) -> Back-translation (Whisper) -> Compute CER/word accuracy
      -> LLM Rubric scoring (gpt-5.6-luna) [Optional: Gemini audio review gemini-3.5-flash]

Note: TTS synthesis and Whisper back-translation must go through OpenAI direct connection (OpenRouter does not provide audio/transcription);
only LLM Rubric's chat review supports OpenRouter fallback—gpt-5.x direct connection requires organizational real-name authentication,
so as long as OPENROUTER_API_KEY is set, the review model is called via OpenRouter first (see get_judge_client_and_model).

All external functions are robust: a single failure throws an exception with context, which is caught by demo.py
and recorded as a failure in the summary table without interrupting the entire table.
"""

import base64
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

import config

# ---------------------------------------------------------------------------
#Client (with automatic retry to mitigate occasional network jitter).
# ---------------------------------------------------------------------------
_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    """OpenAI direct connection client: used for TTS synthesis and Whisper back-translation (these two cannot go through OpenRouter)."""
    global _client
    if _client is None:
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise RuntimeError(
                "Missing OPENAI_API_KEY (TTS synthesis / Whisper back-translation require OpenAI direct connection)."
                "Please `export OPENAI_API_KEY=sk-...` or write it into .env."
            )
        _client = OpenAI(api_key=key, max_retries=5, timeout=60.0)
    return _client


# ---------------------------------------------------------------------------
#LLM Rubric review client: supports OpenRouter fallback.
#gpt-5.x direct connection to OpenAI requires organizational real-name authentication; as long as OPENROUTER_API_KEY is set, OpenRouter is preferred.
#Note: Only chat review can fallback; TTS / Whisper still require OpenAI direct connection (see get_client).
# ---------------------------------------------------------------------------
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_judge_client: Optional[OpenAI] = None
_judge_client_kind: str = ""


def _to_openrouter_model(model: str) -> str:
    """Map model name to OpenRouter id: contains '/' as native id; gpt-* -> openai/*;
    claude-* -> anthropic/claude-opus-4.8; otherwise fallback to openai/gpt-5.6-luna."""
    if "/" in model:
        return model
    if model.startswith("gpt-"):
        return "openai/" + model
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"


def get_judge_client_and_model(model: str):
    """Construct the LLM review client and return (client, actual model name).

    Fallback: gpt-5.x and OPENROUTER_API_KEY set -> prefer OpenRouter; otherwise if OPENAI_API_KEY set ->
    direct connection; otherwise if OPENROUTER_API_KEY set -> OpenRouter (model name mapping); none -> clear error.
    """
    global _judge_client, _judge_client_kind
    primary = os.environ.get("OPENAI_API_KEY", "").strip()
    orkey = os.environ.get("OPENROUTER_API_KEY", "").strip()
    prefer_or = bool(orkey) and model.startswith("gpt-5")

    if not prefer_or and primary:
        if _judge_client_kind != "openai":
            _judge_client = OpenAI(api_key=primary, max_retries=5, timeout=60.0)
            _judge_client_kind = "openai"
        return _judge_client, model
    if orkey:
        if _judge_client_kind != "openrouter":
            _judge_client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=orkey,
                                   max_retries=5, timeout=60.0)
            _judge_client_kind = "openrouter"
        return _judge_client, _to_openrouter_model(model)
    if primary:
        if _judge_client_kind != "openai":
            _judge_client = OpenAI(api_key=primary, max_retries=5, timeout=60.0)
            _judge_client_kind = "openai"
        return _judge_client, model
    raise RuntimeError(
        "Missing OPENAI_API_KEY / OPENROUTER_API_KEY, cannot run LLM Rubric review."
    )


# ---------------------------------------------------------------------------
#1) TTS synthesis (multi-provider dispatch)
# ---------------------------------------------------------------------------
def synthesize(cfg: config.TTSConfig, text: str, out_path: str) -> None:
    """Dispatch to the corresponding service provider for speech synthesis according to cfg.provider, write to out_path (mp3). Throw exception on failure.

    OpenAI uses the official SDK; other providers use built-in urllib to call their public REST APIs,
    without introducing additional dependencies. Throw an exception with context when the corresponding key is missing, which is recorded as a row failure by the upper layer.
    """
    fn = _SYNTH_DISPATCH.get(cfg.provider)
    if fn is None:
        raise RuntimeError(
            f"Unknown provider: {cfg.provider!r}(Optional: {', '.join(_SYNTH_DISPATCH)}）"
        )
    audio = fn(cfg, text)
    if not audio:
        raise RuntimeError(f"{cfg.provider}TTS returned empty audio")
    with open(out_path, "wb") as f:
        f.write(audio)


def _require_env(name: str) -> str:
    #Use config.env_get to support environment variable aliases (e.g., Fish's FISH_API_KEY / FISHAUDIO_API_KEY).
    val = config.env_get(name)
    if not val:
        raise RuntimeError(f"Missing environment variable {name}, cannot synthesize with this provider.")
    return val


def _http_post(url: str, body: dict, headers: dict, timeout: float = 90.0) -> bytes:
    """POST JSON, return raw response bytes. Non-2xx throws an exception with a snippet of the response body."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {e.code}: {detail}") from None


def _synth_openai(cfg: config.TTSConfig, text: str) -> bytes:
    kwargs = dict(model=cfg.model, voice=cfg.voice, input=text)
    if cfg.supports_speed() and abs(cfg.speed - 1.0) > 1e-6:
        kwargs["speed"] = cfg.speed
    return get_client().audio.speech.create(**kwargs).content


def _synth_elevenlabs(cfg: config.TTSConfig, text: str) -> bytes:
    key = _require_env("ELEVENLABS_API_KEY")
    voice = cfg.voice or "21m00Tcm4TlvDq8ikWAM"
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
           f"?output_format=mp3_44100_128")
    body = {"text": text, "model_id": cfg.model or "eleven_multilingual_v2"}
    #ElevenLabs returns raw mp3 bytes.
    return _http_post(url, body, {"xi-api-key": key, "Accept": "audio/mpeg"})


def _synth_fishaudio(cfg: config.TTSConfig, text: str) -> bytes:
    key = _require_env("FISH_API_KEY")
    body = {"text": text, "format": "mp3"}
    if cfg.voice:
        body["reference_id"] = cfg.voice
    #Fish Audio /v1/tts accepts JSON, directly returns audio bytes.
    return _http_post("https://api.fish.audio/v1/tts", body,
                      {"Authorization": f"Bearer {key}"})


def _synth_minimax(cfg: config.TTSConfig, text: str) -> bytes:
    key = _require_env("MINIMAX_API_KEY")
    group = _require_env("MINIMAX_GROUP_ID")
    url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={group}"
    body = {
        "model": cfg.model or "speech-01-turbo",
        "text": text,
        "stream": False,
        "voice_setting": {"voice_id": cfg.voice, "speed": cfg.speed},
        "audio_setting": {"format": "mp3", "sample_rate": 32000},
    }
    raw = _http_post(url, body, {"Authorization": f"Bearer {key}"})
    data = json.loads(raw)
    #Returns JSON, audio is data.audio (hex encoded).
    hexstr = (data.get("data") or {}).get("audio")
    if not hexstr:
        err = data.get("base_resp", {})
        raise RuntimeError(f"Minimax no audio returned:{err or data}")
    return bytes.fromhex(hexstr)


def _synth_doubao(cfg: config.TTSConfig, text: str) -> bytes:
    import uuid
    appid = _require_env("DOUBAO_APP_ID")
    token = _require_env("DOUBAO_ACCESS_TOKEN")
    body = {
        "app": {"appid": appid, "token": token,
                "cluster": cfg.model or "volcano_tts"},
        "user": {"uid": "tts-quality-eval"},
        "audio": {"voice_type": cfg.voice, "encoding": "mp3",
                  "speed_ratio": cfg.speed},
        "request": {"reqid": str(uuid.uuid4()), "text": text, "operation": "query"},
    }
    #Volcengine authentication header is the special 'Bearer;{token}' form; audio is the base64-encoded data field.
    raw = _http_post("https://openspeech.bytedance.com/api/v1/tts", body,
                     {"Authorization": f"Bearer;{token}"})
    data = json.loads(raw)
    b64 = data.get("data")
    if not b64:
        raise RuntimeError(f"Doubao no audio returned: code={data.get('code')} "
                           f"message={data.get('message')}")
    return base64.b64decode(b64)


_SYNTH_DISPATCH = {
    "openai": _synth_openai,
    "elevenlabs": _synth_elevenlabs,
    "fishaudio": _synth_fishaudio,
    "minimax": _synth_minimax,
    "doubao": _synth_doubao,
}


# ---------------------------------------------------------------------------
#2) Duration detection (ffprobe)
# ---------------------------------------------------------------------------
def probe_duration(path: str) -> float:
    """Return audio duration (seconds). Throw exception if ffprobe is missing or fails."""
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe not found, please install ffmpeg (macOS: brew install ffmpeg).")
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr.strip()}")
    out = proc.stdout.strip()
    try:
        return float(out)
    except ValueError:
        raise RuntimeError(f"ffprobe output cannot be parsed as duration: {out!r}")


# ---------------------------------------------------------------------------
# 3) Back-translation (Whisper transcription)
# ---------------------------------------------------------------------------
# Use Simplified Chinese prompts to guide Whisper to output Simplified Chinese, avoiding occasional Traditional Chinese output that inflates CER due to glyph differences
# (that is a transcription script selection issue, not a TTS pronunciation error).
_ZH_PROMPT = "The following are sentences in Mandarin Simplified Chinese."


def transcribe(path: str) -> str:
    with open(path, "rb") as f:
        tr = get_client().audio.transcriptions.create(
            model=config.WHISPER_MODEL, file=f, language="zh", prompt=_ZH_PROMPT,
        )
    return tr.text or ""


# ---------------------------------------------------------------------------
# 4) Text normalization + Character Error Rate (character-level CER for Chinese, equivalent to the intelligibility dimension of WER as described in the book)
# ---------------------------------------------------------------------------
def normalize(text: str) -> str:
    """Remove punctuation/whitespace, keep only CJK / letters / digits, and lowercase for character-by-character comparison."""
    text = text.lower()
    return "".join(ch for ch in text if ch.isalnum())


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (character-level)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(
                prev[j] + 1,        # Delete
                cur[j - 1] + 1,     # Insert
                prev[j - 1] + (ca != cb),  # Substitute
            ))
        prev = cur
    return prev[-1]


@dataclass
class ErrorRate:
    cer: float          # Character Error Rate = edit distance / reference character count
    accuracy: float     # Character Accuracy = 1 - CER (lower bound 0)
    edits: int
    ref_len: int


def char_error_rate(reference: str, hypothesis: str) -> ErrorRate:
    ref = normalize(reference)
    hyp = normalize(hypothesis)
    if not ref:
        return ErrorRate(0.0, 1.0, 0, 0)
    dist = _edit_distance(ref, hyp)
    cer = dist / len(ref)
    return ErrorRate(cer=cer, accuracy=max(0.0, 1.0 - cer), edits=dist, ref_len=len(ref))


# ---------------------------------------------------------------------------
# 5) LLM Rubric evaluation (default, OpenAI closed-loop)
# ---------------------------------------------------------------------------
RUBRIC_DIMENSIONS = ["Clarity", "Naturalness", "Pause rhythm", "Overall"]

# Dimension description (for offline printing with --dump-rubric, also basis for evaluation prompt). Parentheses indicate correspondence with the book's
# four dimensions (Accuracy / Naturalness / Emotional Expression / Voice Consistency).
RUBRIC_DESCRIPTIONS = {
    "Clarity": "Whether the transcription is highly consistent with the original text; more missing/incorrect/extra characters result in lower scores (corresponds to \"Accuracy\" in the book).",
    "Naturalness": "Whether the speaking rate is close to natural reading (Chinese natural reading about 4-6 characters/second; too fast >7 or too slow <3 is unnatural).",
    "Pause rhythm": "Combine speaking rate and text length to judge whether pauses/rhythm are reasonable; too fast usually implies missing words and poor rhythm.",
    "Overall": "Overall impression score based on the above.",
}
# Note: The default (back-translation) evaluation cannot see the audio, so it cannot cover "Emotional Expression / Voice Consistency" in the book; these two dimensions require
# multimodal direct audio listening, reproduced with --gemini (voice consistency also requires reference to speech, not provided in this demo).

_JUDGE_SYSTEM = """You are a strict TTS (Text-to-Speech) quality evaluation expert.
You will receive: the original reference text, the expected emotion of that text, the transcription text obtained by Whisper back-translation of the synthesized speech,
and the objectively measured duration, speaking rate (characters/second), and Character Error Rate (CER) from the audio.
Please score the synthesized speech quality according to the Rubric on each dimension (integer 1-5, 5 is best):

- Clarity: Whether the transcription is highly consistent with the original text (more missing/incorrect/extra characters result in lower scores; higher CER results in lower scores).
- Naturalness: Whether the speaking rate is close to natural reading (Chinese natural reading about 4-6 characters/second; too fast >7 or too slow <3 is unnatural).
- Pause rhythm: Combine speaking rate and text length to judge whether pauses/rhythm are reasonable (too fast usually implies missing words and poor rhythm).
- Overall: Overall impression score based on the above.

Note: You cannot see the audio itself, so you can only make conservative and interpretable judgments based on the above measurable features.
Output only JSON, format:
{"Clarity": {"score": int, "reason": str},
 "Naturalness": {"score": int, "reason": str},
 "Pause rhythm": {"score": int, "reason": str},
 "Overall": {"score": int, "reason": str}}
reason should be a brief explanation in Chinese."""


@dataclass
class RubricResult:
    scores: dict            # dimension -> int
    reasons: dict           # dimension -> str
    raw: str = ""


def judge_rubric(reference: str, emotion: str, hypothesis: str,
                 duration: float, cer: float, model: Optional[str] = None) -> RubricResult:
    """Use the evaluation model (default gpt-5.6-luna) to score according to the Rubric. Return structured scores + comments.

    The evaluation chat call supports OpenRouter fallback (see get_judge_client_and_model)."""
    chars = len(normalize(reference))
    speed = chars / duration if duration > 0 else 0.0
    user = (
        f"Original reference text:{reference}\n"
        f"Expected emotion:{emotion}\n"
        f"Whisper back-translation text:{hypothesis}\n"
        f"Audio duration:{duration:.2f} seconds\n"
        f"Speech rate:{speed:.2f} characters/second (reference text {chars} valid characters)\n"
        f"Character error rate CER:{cer:.3f}\n"
    )
    judge_client, judge_model = get_judge_client_and_model(model or config.JUDGE_MODEL)
    resp = judge_client.chat.completions.create(
        model=judge_model,
        messages=[{"role": "system", "content": _JUDGE_SYSTEM},
                  {"role": "user", "content": user}],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    data = json.loads(raw)
    scores, reasons = {}, {}
    for dim in RUBRIC_DIMENSIONS:
        item = data.get(dim, {})
        if isinstance(item, dict):
            scores[dim] = int(item.get("score", 0))
            reasons[dim] = str(item.get("reason", "")).strip()
        else:  # Compatible model returns number directly
            scores[dim] = int(item)
            reasons[dim] = ""
    return RubricResult(scores=scores, reasons=reasons, raw=raw)


# ---------------------------------------------------------------------------
# 6) Optional: Gemini multimodal audio review (solution from the book). Use REST to avoid extra SDK dependencies.
# ---------------------------------------------------------------------------
def _resolve_gemini_model(api_key: str) -> str:
    """Probe currently available Gemini models to avoid default name expiration."""
    import urllib.request
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read())
        names = [m["name"].split("/")[-1] for m in data.get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
        # Prefer default gemini-3.5-flash (verified to support audio input), then fall back to pro / old flash series.
        for want in (config.GEMINI_MODEL_DEFAULT, "gemini-3.5-flash",
                     "gemini-2.5-pro", "gemini-2.5-flash", "gemini-flash-latest"):
            if want in names:
                return want
        # Fallback: any available model that is not tts/image
        for n in names:
            if "tts" not in n and "image" not in n and "embedding" not in n:
                return n
    except Exception:
        pass
    return config.GEMINI_MODEL_DEFAULT


def judge_gemini_audio(reference: str, emotion: str, audio_path: str) -> RubricResult:
    """Feed the synthesized audio + original text + Rubric to Gemini multimodal to directly 'listen' and score.

    Requires GEMINI_API_KEY. Disabled by default; enable with --gemini. On failure, raise exception and mark as failure by upper layer.
    """
    import urllib.request
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing GEMINI_API_KEY, cannot use Gemini audio review.")
    model = _resolve_gemini_model(key)
    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()
    prompt = (
        "You are a TTS quality review expert. Please directly listen to the following synthesized speech, compare it with the original text and expected emotion,"
        "Score on four dimensions from 1-5 with brief reasons, output only JSON:"
        '{"clarity":{"score":int,"reason":str},"naturalness":{"score":int,"reason":str},'
        '"pause rhythm":{"score":int,"reason":str},"overall":{"score":int,"reason":str}}\n'
        f"Original text:{reference}\nExpected emotion:{emotion}"
    )
    body = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "audio/mp3", "data": audio_b64}},
        ]}],
        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
    }
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(text)
    scores, reasons = {}, {}
    for dim in RUBRIC_DIMENSIONS:
        item = parsed.get(dim, {})
        scores[dim] = int(item.get("score", 0)) if isinstance(item, dict) else int(item)
        reasons[dim] = str(item.get("reason", "")).strip() if isinstance(item, dict) else ""
    return RubricResult(scores=scores, reasons=reasons, raw=text)
