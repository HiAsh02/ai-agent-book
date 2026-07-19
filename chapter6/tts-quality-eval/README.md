# Experiment 6-5: Fully Automated TTS Quality Evaluation Pipeline

Companion to Chapter 6 of "Deep Understanding of AI Agents" – Experiment 6-5 ★★: Building a Fully Automated TTS Quality Evaluation Pipeline.

Use multiple **TTS providers / configurations** (OpenAI, ElevenLabs, Fish Audio, Minimax, Doubao, or different models/voices/speeds from the same provider) to synthesize the same set of challenging reference texts. Then, use a **multimodal LLM-as-a-Judge** approach to score the synthesized speech across multiple dimensions according to a **Rubric**. Finally, aggregate the results into a **comparison table** reflecting the strengths and weaknesses of different providers/configurations in terms of accuracy and naturalness.

## Purpose

Address practical engineering questions: *For the same text, how big is the gap between `tts-1` and `tts-1-hd`? How much quality is sacrificed by changing the voice or increasing the speed to 1.5x?* This demo turns such comparisons into a **single-command, reproducible pipeline**.

## Evaluation Dimensions and Rubric

For each synthesized speech, objective features (duration, speed, character error rate) are first measured. Then, the evaluation model scores them on a 1–5 scale:

| Dimension | Meaning |
|-----------|---------|
| Clarity | Whether the transcription matches the original text (more missing/incorrect/extra characters result in a lower score, corresponding to the accuracy dimension) |
| Naturalness | Whether the speed is close to natural reading (approximately 4–6 characters/second for Chinese; too fast or too slow incurs penalties) |
| Pacing & Rhythm | Judge whether the rhythm is reasonable based on speed and text length (excessive speed often implies dropped characters) |
| Overall | Comprehensive impression score |

Objective metric **CER (Character Error Rate) / Character Accuracy**: Normalize the Whisper back-transcribed text and the original text (remove punctuation and whitespace, unify case), then compute character-level edit distance. `CER = Edit distance / Reference character count`, `Character accuracy = 1 - CER`. Calculated at the **character level** for Chinese (equivalent to the intelligibility dimension of WER in the book).

## Provider Adaptation Notes

- **TTS Synthesis (Multiple Providers)**: Corresponds to the book's "Integrating mainstream services: OpenAI, ElevenLabs, Fish Audio, Minimax, Doubao". Each provider is implemented according to their public REST API (OpenAI uses the official SDK; the rest use built-in `urllib` with no extra dependencies). By default (without `--providers`), only 4 OpenAI configurations are run, requiring only a single `OPENAI_API_KEY` for zero-configuration execution; `--providers openai,minimax,...` enables cross-provider horizontal comparison. Required environment variables and voice field semantics for each provider can be found via `python demo.py --list-providers`.

  | Provider | Environment Variable | Voice Semantics |
  |----------|---------------------|-----------------|
  | `openai` | `OPENAI_API_KEY` | alloy/nova…; model=tts-1 / tts-1-hd / gpt-4o-mini-tts |
  | `elevenlabs` | `ELEVENLABS_API_KEY` | voice_id; model defaults to eleven_multilingual_v2 |
  | `fishaudio` | `FISH_API_KEY` (alias `FISHAUDIO_API_KEY`) | reference_id (leave empty for default voice) |
  | `minimax` | `MINIMAX_API_KEY` + `MINIMAX_GROUP_ID` | voice_id; model defaults to speech-01-turbo |
  | `doubao` | `DOUBAO_APP_ID` + `DOUBAO_ACCESS_TOKEN` | voice_type (Volcengine) |

  > Note: Only the **OpenAI** path in this repository has been end-to-end verified; the other four are implemented according to their respective public REST documentation. Please override `config.PROVIDER_CONFIGS` with your account's available voice/model before use. If the corresponding key is missing, the row for that provider will be marked as a failure, **without interrupting the entire table**.
- **Quality Evaluation (Default)**: Use Whisper (`whisper-1`) to back-transcribe the synthesized speech into text, calculate CER, then use `gpt-5.6-luna` (current cost-effective flagship) to score based on the "transcribed text + duration + speed + CER" according to the Rubric. Use Simplified Chinese prompts during transcription to guide Whisper to output Simplified Chinese, avoiding inflated CER due to Traditional Chinese character differences.
  **Credentials/Fallback**: TTS synthesis and Whisper back-transcription must use **direct OpenAI connection** (`OPENAI_API_KEY`; OpenRouter does not provide audio/transcription); **only the LLM Rubric chat evaluation supports OpenRouter fallback** – since direct connection for `gpt-5.x` requires organizational real-name authentication, as long as `OPENROUTER_API_KEY` is set, the evaluation will prioritize OpenRouter (`gpt-*` maps to `openai/*`).
- **Quality Evaluation (Optional, Book's Approach)**: `--gemini` enables **Gemini multimodal direct "listening" to audio** for scoring (original text + audio + Rubric input together), requiring `GEMINI_API_KEY`. The default model is `gemini-3.5-flash` (verified to support audio input); the code first probes `/models`, and if this name is unavailable, it automatically falls back to the currently available model (e.g., `gemini-2.5-pro`).

> The book uses Gemini to directly listen to synthesized speech for scoring (this demo defaults to `gemini-3.5-flash`, verified to support audio); the default is changed to "Whisper back-transcription + LLM Rubric" to enable **zero additional configuration for execution**, while retaining the `--gemini` flag to reproduce the book's approach. The difference between the two: Gemini can directly perceive timbre, prosody, and emotion; the back-transcription approach can only make conservative inferences based on measurable features (see "Limitations").

## Files

| File | Description |
|------|-------------|
| `config.py` | Model names and unit prices, provider registry (`PROVIDERS` / `PROVIDER_CONFIGS`), TTS configuration sets, test corpus |
| `pipeline.py` | Multi-provider synthesis dispatch / ffprobe duration / Whisper back-transcription / CER calculation / LLM Rubric / optional Gemini |
| `demo.py` | Entry point: run full pipeline for multiple configurations × multiple corpus items, print detailed per-item results + comparison summary table |
| `requirements.txt` / `env.example` | Dependencies and environment variable examples |

## Running

```bash
pip install -r requirements.txt          # Only needs openai
brew install ffmpeg                        # Provides ffprobe (duration detection)
export OPENAI_API_KEY=sk-...

python demo.py            # Default: 4 OpenAI configurations × 4 corpus items, Whisper back-transcription + LLM Rubric
python demo.py --quick   # Use only the first 2 corpus items for a quick smoke test
python demo.py --extra   # Additionally include the gpt-4o-mini-tts configuration
python demo.py --gemini  # Switch evaluation to Gemini multimodal direct audio listening (requires GEMINI_API_KEY)
python demo.py --fresh   # Ignore existing audio files and re-synthesize everything

# Multi-provider / Custom input (new)
python demo.py --providers openai,minimax,elevenlabs   # Cross-provider horizontal comparison (requires respective keys)
python demo.py --text '2026年营收增长37.5%'             # Replace the corpus with a single custom textpython demo.py --judge-model gpt-5.6-luna                 # Override the LLM evaluation model
python demo.py --output ./runs/exp1                     # Custom output directory

# Offline (no API keys required)
python demo.py --list-providers   # View all providers and their configuration status
python demo.py --dump-rubric      # View the Rubric dimension definitions
```

See `python demo.py --help` (in Chinese) for all parameters. Synthesized audio is written to `output/` (ignored by `.gitignore`), and structured results are written to `output/results.json` (use `--output` to change the directory).
**Idempotent**: By default, existing audio files are reused; repeated runs will not re-synthesize.

## Test Corpus

4 items covering different challenge points: numbers/percentages/dates, polyphonic characters (行/长/重/还), long news-style sentences, proper nouns + emotional exclamation. Items can be added or removed in `config.py`'s `CORPUS`.
## Robustness

- Missing `OPENAI_API_KEY` immediately exits with a clear error message; missing `ffprobe` provides installation instructions.
- If any step (synthesis/transcription/evaluation) fails for a single (configuration, corpus) pair, only that item is marked as a failure, **without interrupting the entire table**; the summary table aggregates based on successful items.
- The OpenAI client includes automatic retries (`max_retries=5`) to mitigate occasional network fluctuations.
- The ffprobe call checks the return code and the parsability of the output.

## Limitations

- **The default evaluation cannot see the audio itself**: It only infers based on back-transcribed text and objective features, making it impossible to directly judge timbre consistency, true prosody, and emotional expression (the book's Gemini approach can, reproduced with `--gemini`). Therefore, the "naturalness/emotion" dimension is a conservative estimate. The timbre consistency dimension requires reference to the speech, which this demo does not cover.
- CER depends on Whisper transcription quality; Whisper's own errors introduce noise. Numbers/proper nouns may exhibit non-phonetic differences due to writing form (Arabic numerals vs. Chinese numerals).
- The Rubric is scored by an LLM, which introduces evaluation model bias; scores are intended for **relative comparison** rather than as an absolute benchmark.
