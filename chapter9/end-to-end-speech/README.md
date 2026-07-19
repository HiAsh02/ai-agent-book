# Experiment 9-4 Companion: End-to-End Speech Reasoning vs. Cascaded Pipeline

Corresponds to Chapter 9 of *Deep Understanding of AI Agents*, **Experiment 9-4 ★★★: Using Step-Audio R1 for End-to-End Speech Reasoning**.

## Purpose

The core of Experiment 9-4 in the book is the **end-to-end speech reasoning model Step-Audio R1**: a single model that directly "listens → thinks → speaks", combining ASR, LLM, and TTS into one. It transmits paralinguistic information (emotion, tone, speech rate, ambient sound) directly in the latent space, resulting in lower latency and more natural prosody.

Since Step-Audio R1 has no public endpoint and requires multi-GPU deployment, it is difficult for readers to run directly. Therefore, this demo uses OpenAI's speech-to-speech model `gpt-audio` as a **real, runnable end-to-end representative**: it also takes "audio in → single model → audio out", returning a spoken answer and its transcription in a single call, with **no** separate ASR/LLM/TTS stages in between. The demo lets you **compare the same problem** across real end-to-end and cascaded pipelines, allowing you to directly observe the differences in **latency** and **information loss (tone, paralinguistics)**—the latencies for both paths are measured in real-time during this run, and both output audio files are validated with `ffprobe`.

The demo provides two task types (`--task`), corresponding to the two comparison axes in the book:

- **`math` (default)**: Verbally presented math problems (Spoken-MQA style). The answer depends only on "what was said," so the accuracy of cascaded and end-to-end approaches is comparable (corresponding to the "Self-Cascading" section in 9.3). Therefore, this task primarily compares **latency**.
- **`paralinguistic`**: A phrase where "the answer depends on how it is said." In the cascaded pipeline, ASR compresses speech into plain text, so the LLM only receives the literal words. Any emotional judgment is **Textual Surrogate Reasoning** (Section 9.3, "The Problem of Textual Surrogate Reasoning")—guessing emotion from vocabulary. The end-to-end model, however, directly hears acoustic features (speech rate, pitch) and responds accordingly. This task compares the **information loss** dimension, which is the core problem that **MGRD (Modality-Grounded Reasoning Distillation)** in the book aims to solve.

## Principle: Three Speech Paradigms

The book categorizes speech architectures into three paradigms (chapter9.md "Three Paradigms of Speech Architecture"):

| Paradigm | Structure | Characteristics |
|----------|-----------|-----------------|
| **Cascaded** | ASR → LLM → TTS (three independent models in series) | Clear modules, independently tunable, good interpretability; but latency accumulates serially, models connect via plain text interfaces, and emotion/speech rate/tone/ambient sound are almost entirely lost at the interface |
| **End-to-End Omni** | Single model "listens→thinks→speaks" (Step-Audio R1, gpt-audio, etc.) | Lower latency, preserves paralinguistic information, natural prosody, can "think while speaking"; cost is large training data requirements and poor interpretability. **Still assumes "turn-taking," using VAD to segment turns** |
| **Full-Duplex** | Single model listens and speaks simultaneously, removing the "turn-taking" assumption (Moshi, GPT-Live) | Continuously processes input and output simultaneously, making decisions multiple times per second about whether to speak/listen/stop/interrupt; this demo does not cover this |

This demo focuses on the **comparison** between the first two paradigms: End-to-End (Paradigm 2) vs. Cascaded (Paradigm 1).

**Step-Audio R1 is a representative of Paradigm 2 that internalizes "reasoning" within a single model**: it truly reasons based on acoustic features through MGRD (Modality-Grounded Reasoning Distillation) and achieves "thinking while speaking" through the MPS dual-brain architecture. `gpt-audio` is a representative of the same paradigm (audio in, single model, audio out) that readers can directly call.

## Running

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure Key
cp env.example .env
# Edit .env, fill in a valid OPENAI_API_KEY (requires access to gpt-audio / whisper-1 / tts-1).
# Audio endpoints (end-to-end gpt-audio, cascaded ASR/TTS) are only available via direct OpenAI connection—OpenRouter has no audio endpoints.
# Therefore, this experiment requires a direct OpenAI API Key. Optional: additionally configure OPENROUTER_API_KEY, then the plain-text
# LLM reasoning in the cascaded pipeline will automatically switch to OpenRouter's gpt-5.6-luna (bypassing organizational identity verification for direct gpt-5.6* connections).

# 3. Run (default: math task, runs both end-to-end + cascaded on the same problem, prints real latency comparison)
python demo.py

# Paralinguistic task: highlights the advantage of end-to-end over cascaded (end-to-end hears tone, cascaded only sees text)
python demo.py --task paralinguistic

# Use a real emotional recording as input (better demonstrates tonal differences than TTS synthesis; mutually exclusive with --question)
python demo.py --task paralinguistic --audio-input my_voice.wav

# Run only end-to-end / custom question / change voice / change output directory
python demo.py --skip-cascade
python demo.py --question "The high-speed train from Beijing to Shanghai takes 4 hours. If I depart at 9:00, what time will I arrive?"
python demo.py --voice nova --output-dir out
python demo.py --help

# Switch to a self-deployed real Step-Audio R1 (overrides environment variables)
python demo.py --step-audio-endpoint http://localhost:8000/v1/audio/chat

# 4. (Optional) Listen to the generated speech answers
ffplay audio/answer_end_to_end.wav   # End-to-end
ffplay audio/answer_cascade.mp3      # Cascaded
```

See all CLI parameters with `python demo.py --help`: `--task`, `--question`, `--audio-input`, `--e2e-model`, `--step-audio-endpoint`, `--voice`, `--output-dir`, `--skip-cascade`. The default behavior (`python demo.py` runs the math task, end-to-end + cascaded comparison) remains consistent with the previous version.

Requires `ffprobe`/`ffplay` (for validation, listening to audio): `brew install ffmpeg` (macOS).

## Example Expected Output (Real Excerpt)

```
Paradigm 1: End-to-End Speech Reasoning (backend=gpt-audio, model=gpt-audio)
Form: Audio in → Single model "listens→thinks→speaks" → Audio out (single call, no separate ASR/LLM/TTS stages)
[Single Stage] End-to-End (listens→thinks→speaks, single model call)  |  Latency=7.21s
    Speech answer transcription (produced incidentally by the model, not an intermediate text stage): Let's calculate: Xiao Ming has 12 yuan, buys 3 pencils... finally has no money left.
    ffprobe validation: {'format': 'wav', 'duration(seconds)': 20.75, ...}
End-to-End Total Latency (single model forward pass): 7.21s

Paradigm 2 (Comparison Baseline): Cascaded Pipeline ASR → LLM → TTS
[Stage 1] ASR Speech Recognition  |  Model=whisper-1  |  Latency=1.35s
[Stage 2] LLM Reasoning          |  Model=gpt-5.6-luna  |  Latency=1.92s
[Stage 3] TTS Speech Synthesis   |  Model=tts-1  |  Latency=3.66s
Cascaded Total Latency (serial sum of stages): 6.94s

End-to-End vs Cascaded: Real Latency Comparison
【1】Measured Total Latency  End-to-End 7.21s; Cascaded ASR(1.35)+LLM(1.92)+TTS(3.66)=6.94s
【3】Table 9-1 from the book (cited from Step-Audio R1 paper, not produced by this demo)
    MPS Speak-First 92.8% / Full TBS 93.0% ……
```

### Real Excerpt from Paralinguistic Task (`--task paralinguistic`, one real run)

For the same sentence "Alright, that's it then. I have no objections." (TTS synthesized, relatively flat emotion), the responses from the two paths:

```
[Stage 1] ASR Speech Recognition  |  whisper-1  → 「Alright, that's it then. I have no objections.」   ← The cascaded LLM only receives this plain text

Responses from both paths to the same audio segment (allowing direct comparison of whether "how it was said" was heard):
    Cascaded (relying only on ASR text, Textual Surrogate Reasoning) → "It sounds like you're a bit resigned, maybe not entirely satisfied with this decision. ..."
    End-to-End (directly hearing acoustic features)        → "It sounds like you're a bit resigned, your speech rate isn't fast, and your pitch is quite steady. ..."
```

The difference is clear: **Cascaded** can only guess resignation from the literal words "no objections" and cannot cite any acoustic basis (the "Textual Surrogate Reasoning" from the book); **End-to-End** directly references acoustic features like "speech rate isn't fast, pitch is quite steady"—this is precisely what MGRD in the book aims to teach models: "thinking with your ears." Note that the default input is TTS synthesized, with relatively flat emotion, which weakens the difference; using `--audio-input` to feed a real emotional recording will make the contrast more apparent.

**Regarding Table 9-1**: The Spoken-MQA / URO-Bench scores printed in the demo are **cited from the Step-Audio R1 paper** (reproduced as Table 9-1 in the book), not generated by this demo—the only real outputs from this demo are the measured latencies and the two real audio files. Latency numbers fluctuate with network conditions and OpenAI load; `gpt-audio` produces the entire audio segment in a single forward pass. A truly streaming end-to-end model (like Step-Audio R1's MPS) can further reduce **time-to-first-token** by "thinking while speaking," a benefit not captured by this demo's total segment latency.

## How to Adapt for Real Step-Audio R1

The backend for the end-to-end path is switchable:

- **Default**: `STEP_AUDIO_ENDPOINT` not configured → uses `gpt-audio` (model name can be overridden with `E2E_MODEL`).
- **Real Step-Audio R1**: After deploying on multi-GPU, write the service address into `STEP_AUDIO_ENDPOINT`, and the demo's end-to-end path will switch to it. `speech_model.py`'s `EndToEndSpeechModel._run_step_audio` provides the call skeleton for "upload audio, retrieve audio"; request bodies vary by deployment scheme (vLLM / custom HTTP service), so adapt as needed.

## Limitations

- `gpt-audio` is a **representative** of the end-to-end paradigm, not Step-Audio R1 itself: it does not expose MPS's streaming time-to-first-token, nor does it have the paralinguistic benchmark scores reported in the Step-Audio R1 paper. Table 9-1 is therefore a **citation**, not a reproduction.
- The demo constructs input using "text TTS → input speech" solely for a demonstration loop; in real scenarios, input comes from the user's microphone, carrying richer paralinguistic information, and the loss in the cascaded pipeline is more pronounced.
- The relative latency of end-to-end vs. cascaded will fluctuate with network conditions, model load, and answer length; a single run does not represent a stable conclusion. The paradigm difference (whether paralinguistic information is preserved) is a more robust dimension for comparison.

## Files

- `demo.py`: Runnable main program (`python demo.py`), runs both end-to-end + cascaded on the same problem and prints a real comparison.
- `speech_model.py`: `EndToEndSpeechModel` (gpt-audio / switchable to Step-Audio R1) and `CascadedSpeechModel` (whisper-1 → gpt-5.6-luna → tts-1).
- `requirements.txt` / `env.example`: Dependencies and environment variable template.
- `audio/`: Input/output audio generated at runtime (ignored in `.gitignore`).
