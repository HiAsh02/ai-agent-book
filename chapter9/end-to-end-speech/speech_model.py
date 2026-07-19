"""
Pluggable speech model interface: two paradigms — end-to-end and cascaded.

Corresponds to Experiment 9-4 in "Deep Understanding of AI Agents": "Using Step-Audio R1 for End-to-End Speech Reasoning".

- End-to-End (EndToEndSpeechModel): A single model directly "listens → thinks → speaks", audio in, audio out,
  with no pure text reasoning stage exposed externally. Step-Audio R1 is the representative model in the book (audio encoder
  + audio adapter + Qwen2.5 32B decoder, requires multi-GPU, no public endpoint). To allow readers to
  actually run the "end-to-end speech reasoning" paradigm without relying on a self-built GPU cluster,
  this demo defaults to using OpenAI's speech-to-speech model `gpt-audio`: it is also "audio → single model → audio", a single call
  returns both the speech answer and its text transcription, without going through separate ASR/LLM/TTS stages. If you have already deployed
  the real Step-Audio R1, write the service address into STEP_AUDIO_ENDPOINT to switch to it.

- Cascaded (CascadedSpeechModel): Chains three independent models ASR → LLM → TTS into a pipeline,
  one after another. You can use OpenAI's whisper-1 / gpt-5.6-luna / tts-1 to actually run a complete loop.
  Cost: The models are connected via discrete text interfaces, and paralinguistic information such as the speaker's emotion, tone, and intonation
  is almost completely lost during handover (see chapter9.md Paradigm 2 · End-to-End Full-Modal Model). This path serves as a **baseline** in the demo for comparison with the end-to-end approach.
"""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI


# ---------------------------------------------------------------------------
#  Data Structure
# ---------------------------------------------------------------------------
@dataclass
class StageResult:
    """Result and latency of a single stage in the pipeline."""

    name: str          #  Stage name (e.g., "ASR Speech Recognition")
    model: str         #  Model used
    latency_s: float   #  Duration of this stage (seconds)
    text: Optional[str] = None       #  Text artifact (ASR transcription / LLM answer / end-to-end transcription)
    audio_path: Optional[str] = None #  Audio artifact (TTS synthesis / end-to-end speech answer)


@dataclass
class PipelineResult:
    """Result of a complete "speech input → thinking → speech output" cycle."""

    paradigm: str                 #  "cascaded" or "end_to_end"
    input_audio: str              #  Input audio path
    output_audio: Optional[str]   #  Output audio path
    stages: list[StageResult] = field(default_factory=list)

    @property
    def total_latency_s(self) -> float:
        return sum(s.latency_s for s in self.stages)


# ---------------------------------------------------------------------------
#  End-to-end paradigm (runnable: default gpt-audio; switchable to self-deployed Step-Audio R1)
# ---------------------------------------------------------------------------
class EndToEndSpeechModel:
    """End-to-end speech reasoning model: audio in → single model "listen→think→speak" → audio out.

    Two backends, choose one:

    1. **gpt-audio (default, OpenAI)**: A true speech-to-speech model, invoked via Chat
       Completions (modalities=["text","audio"], audio={voice,format},
       user message contains an input_audio content block). A single call returns the speech answer + its transcription,
       with no separate ASR/LLM/TTS stages — this is the essence of the end-to-end paradigm. The model name can be
       overridden by the environment variable E2E_MODEL (default gpt-audio).

    2. **Step-Audio R1 (optional, self-deployed)**: The end-to-end speech reasoning model from the book, consisting of an audio encoder +
       audio adapter + Qwen2.5 32B decoder, requires multi-GPU, no public endpoint. It truly reasons based on acoustic features via
       MGRD (Modality-Grounded Reasoning Distillation) and implements "thinking while speaking" through the MPS dual-brain architecture.
       If STEP_AUDIO_ENDPOINT is configured, this class switches to uploading audio to that address and retrieving audio
       (the request body varies by deployment; see the skeleton in run(), adapt as needed when integrating).
    """

    def __init__(
        self,
        client: OpenAI,
        model: Optional[str] = None,
        voice: str = "alloy",
        system_prompt: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        self.client = client
        self.model = model or os.getenv("E2E_MODEL", "gpt-audio")
        self.voice = voice
        #  Prefer explicitly passed endpoint (CLI --step-audio-endpoint), otherwise fall back to environment variable
        self.endpoint = (endpoint if endpoint is not None
                         else os.getenv("STEP_AUDIO_ENDPOINT", "")).strip()
        self.system_prompt = system_prompt or (
            "You are a Chinese voice assistant. Please first complete the necessary reasoning internally, then output the conclusion in concise, colloquial,"
            "readable Chinese, within three sentences."
        )

    @property
    def backend(self) -> str:
        """Currently active end-to-end backend identifier."""
        return "step-audio-r1" if self.endpoint else "gpt-audio"

    # -- Backend 1: Self-deployed Step-Audio R1 (optional) --------------------------------
    def _run_step_audio(self, input_audio: str, output_audio: str) -> PipelineResult:
        #  Different deployment schemes (vLLM / custom HTTP service) have different request bodies; here we provide the most common
        #  "upload audio, retrieve audio" pattern for adaptation when connecting to a real Step-Audio R1.
        import requests  #  Lazy import: only needed when the endpoint is actually configured

        t0 = time.perf_counter()
        with open(input_audio, "rb") as f:
            resp = requests.post(self.endpoint, files={"audio": f}, timeout=120)
        resp.raise_for_status()
        with open(output_audio, "wb") as out:
            out.write(resp.content)
        latency = time.perf_counter() - t0

        stage = StageResult(
            name="End-to-End (Listen→Think→Speak, single model fusion)",
            model="Step-Audio R1",
            latency_s=latency,
            audio_path=output_audio,
        )
        return PipelineResult(
            paradigm="end_to_end",
            input_audio=input_audio,
            output_audio=output_audio,
            stages=[stage],
        )

    # -- Backend 2: gpt-audio speech-to-speech (default) --------------------------
    def _run_gpt_audio(self, input_audio: str, output_audio: str) -> PipelineResult:
        in_fmt = "mp3" if input_audio.lower().endswith(".mp3") else "wav"
        out_fmt = "wav" if output_audio.lower().endswith(".wav") else "mp3"
        with open(input_audio, "rb") as f:
            in_b64 = base64.b64encode(f.read()).decode()

        t0 = time.perf_counter()
        resp = self.client.chat.completions.create(
            model=self.model,
            modalities=["text", "audio"],
            audio={"voice": self.voice, "format": out_fmt},
            messages=[
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": in_b64, "format": in_fmt},
                        }
                    ],
                },
            ],
        )
        latency = time.perf_counter() - t0

        audio = resp.choices[0].message.audio
        if audio is None or not audio.data:
            raise RuntimeError(
                f"End-to-End Model {self.model}  did not return audio. Please ensure this Key has access to gpt-audio,"
                "or use E2E_MODEL to specify an available speech-to-speech model."
            )
        with open(output_audio, "wb") as out:
            out.write(base64.b64decode(audio.data))

        #  End-to-end has only "one segment": listen→think→speak fused in a single forward pass. The transcript is the speech text output
        #  produced by the model, not an independent intermediate text stage for TTS consumption.
        stage = StageResult(
            name="End-to-End (Listen→Think→Speak, single model, one call)",
            model=self.model,
            latency_s=latency,
            text=audio.transcript,
            audio_path=output_audio,
        )
        return PipelineResult(
            paradigm="end_to_end",
            input_audio=input_audio,
            output_audio=output_audio,
            stages=[stage],
        )

    def run(self, input_audio: str, output_audio: str) -> PipelineResult:
        if self.endpoint:
            return self._run_step_audio(input_audio, output_audio)
        return self._run_gpt_audio(input_audio, output_audio)


# ---------------------------------------------------------------------------
#  Cascade Paradigm (Baseline)
# ---------------------------------------------------------------------------
class CascadedSpeechModel:
    """Cascade voice pipeline: ASR → LLM → TTS, three independent models in series.

    Default uses OpenAI:
      - ASR: whisper-1        (speech → text)
      - LLM: gpt-5.6-luna     (text reasoning → text response)
      - TTS: tts-1            (text → speech)

    ASR/TTS only have corresponding endpoints with direct OpenAI connection (OpenRouter has no audio endpoints), so `client` is fixed
    (must be direct OpenAI); the intermediate pure-text LLM reasoning can use a separate `llm_client` via OpenRouter,
    thus bypassing the organizational real-name authentication required for direct gpt-5.6* connection. `llm_client` falls back to `client` when not set.
    """

    def __init__(
        self,
        client: OpenAI,
        asr_model: str = "whisper-1",
        llm_model: str = "gpt-5.6-luna",
        tts_model: str = "tts-1",
        tts_voice: str = "alloy",
        system_prompt: Optional[str] = None,
        llm_client: Optional[OpenAI] = None,
    ) -> None:
        self.client = client
        self.llm_client = llm_client or client
        self.asr_model = asr_model
        self.llm_model = llm_model
        self.tts_model = tts_model
        self.tts_voice = tts_voice
        self.system_prompt = system_prompt or (
            "You are a voice assistant. Please perform necessary reasoning first, then give a concise, colloquial, "
            "Chinese answer suitable for reading aloud. Keep the answer within three sentences."
        )

    # -- Stage 1: ASR Speech Recognition ------------------------------------------------
    def transcribe(self, audio_path: str) -> StageResult:
        t0 = time.perf_counter()
        with open(audio_path, "rb") as f:
            resp = self.client.audio.transcriptions.create(
                model=self.asr_model,
                file=f,
            )
        latency = time.perf_counter() - t0
        return StageResult(
            name="ASR Speech Recognition",
            model=self.asr_model,
            latency_s=latency,
            text=resp.text.strip(),
        )

    # -- Stage 2: LLM Reasoning ----------------------------------------------------
    def think(self, question_text: str) -> StageResult:
        t0 = time.perf_counter()
        resp = self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": question_text},
            ],
            temperature=0.3,
        )
        latency = time.perf_counter() - t0
        return StageResult(
            name="LLM Reasoning",
            model=self.llm_model,
            latency_s=latency,
            text=resp.choices[0].message.content.strip(),
        )

    # -- Stage 3: TTS Speech Synthesis ------------------------------------------------
    def synthesize(self, text: str, output_audio: str) -> StageResult:
        t0 = time.perf_counter()
        resp = self.client.audio.speech.create(
            model=self.tts_model,
            voice=self.tts_voice,
            input=text,
        )
        resp.stream_to_file(output_audio)
        latency = time.perf_counter() - t0
        return StageResult(
            name="TTS Speech Synthesis",
            model=self.tts_model,
            latency_s=latency,
            audio_path=output_audio,
        )

    # -- Full Pipeline ----------------------------------------------------------
    def run(self, input_audio: str, output_audio: str) -> PipelineResult:
        asr = self.transcribe(input_audio)
        llm = self.think(asr.text)
        tts = self.synthesize(llm.text, output_audio)
        return PipelineResult(
            paradigm="cascaded",
            input_audio=input_audio,
            output_audio=output_audio,
            stages=[asr, llm, tts],
        )


def synthesize_question_audio(
    client: OpenAI,
    question_text: str,
    output_audio: str,
    tts_model: str = "tts-1",
    voice: str = "shimmer",
) -> None:
    """Use TTS to first synthesize a speech segment of "user question" as the common input for both pipelines."""
    resp = client.audio.speech.create(model=tts_model, voice=voice, input=question_text)
    resp.stream_to_file(output_audio)
